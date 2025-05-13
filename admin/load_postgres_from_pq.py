import sys
import os
import re
import logging
import argparse

from contextlib import contextmanager

import pyarrow.parquet
import psycopg

_logger = logging.getLogger(__name__)
_logger.propagate = False
if not _logger.hasHandlers():
    _logout = logging.StreamHandler( sys.stderr )
    _logger.addHandler( _logout )
    _formatter = logging.Formatter( '[%(asctime)s - %(levelname)s] - %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S' )
    _logout.setFormatter( _formatter )
    _logger.setLevel( logging.INFO )


@contextmanager
def db( dbcon=None ):
    if dbcon is not None:
        yield dbcon
        return

    try:
        pghost = os.getenv( 'PGHOST', 'postgres' )
        pgport = os.getenv( 'PGPORT', 5432 )
        pguser = os.getenv( 'PGUSER', 'postgres' )
        pgpass = os.getenv( 'PGPASS', 'fragile' )
        pgname = os.getenv( 'PGNAME', 'ls_xgboost' )

        dbcon = psycopg.connect( dbname=pgname, user=pguser, password=pgpass, host=pghost, port=pgport )
        yield dbcon

    finally:
        if dbcon is not None:
            dbcon.rollback()
            dbcon.close()


# Stole this next one from code written for fastdb
def disable_indexes_and_fks():
    """This is scary.  It disables all indexes and foreign keys on the tables to be loaded.

    This can greatly improve the bulk loading time.  But, of course,
    it changes the database structure, which is scary.  It writes a
    file "reconstruct_indexes_constraints.sql" which
    can be feed through psql to undo the damage.

    """

    tables = [ 'ls_xgboost' ]
    tableindexes = {}
    indexreconstructs = []
    tableconstraints = {}
    constraintreconstructs = []
    tablepkconstraints = {}
    primarykeys = {}
    pkreconstructs = []

    pkmatcher = re.compile( r'^ *PRIMARY KEY \((.*)\) *$' )
    pkindexmatcher = re.compile( r' USING .* \((.*)\) *$' )

    with db() as conn:
        cursor = conn.cursor( row_factory=psycopg.rows.dict_row )

        # Find all constraints (including primary keys)
        for table in tables:
            tableconstraints[table] = []
            cursor.execute( f"SELECT table_name, conname, condef, contype "
                            f"FROM "
                            f"  ( SELECT conrelid::regclass::text AS table_name, conname, "
                            f"           pg_get_constraintdef(oid) AS condef, contype "
                            f"    FROM pg_constraint WHERE conparentid=0 "
                            f"  ) subq "
                            f"WHERE table_name='{table}'" )
            rows = cursor.fetchall()
            for row in rows:
                # ...empirically, I'm getting back binary blobs, not
                # strings.  ???  Understand psycopg3.
                for k in row.keys():
                    row[k] = None if row[k] is None else row[k].decode('utf-8')

                if row['contype'] == 'p':
                    if table in primarykeys:
                        raise RuntimeError( f"{table} has multiple primary keys!" )
                    match = pkmatcher.search( row['condef'] )
                    if match is None:
                        raise RuntimeError( f"Failed to parse {row['condef']} for primary key" )
                    primarykeys[table] = match.group(1)
                    tablepkconstraints[table] = row['conname']
                    pkreconstructs.insert( 0, ( f"ALTER TABLE {table} ADD CONSTRAINT "
                                                f"{row['conname']} {row['condef']};" ) )
                else:
                    tableconstraints[table].append( row['conname'] )
                    constraintreconstructs.insert( 0, ( f"ALTER TABLE {table} ADD CONSTRAINT {row['conname']} "
                                                        f"{row['condef']};" ) )

        # Make sure we found the primary key for all tables
        missing = []
        for table in tables:
            if table not in primarykeys:
                missing.append( table )
        if len(missing) > 0:
            raise RuntimeError( f'Failed to find primary key for: {[",".join(missing)]}' )

        # Now do table indexes
        for table in tables:
            tableindexes[table] = []
            cursor.execute( f"SELECT * FROM pg_indexes WHERE tablename='{table}'" )
            rows = cursor.fetchall()
            for row in rows:
                for k in row.keys():
                    row[k] = None if row[k] is None else row[k].decode('utf-8')
                match = pkindexmatcher.search( row['indexdef'] )
                if match is None:
                    raise RuntimeError( f"Error parsing index def {row['indexdef']}" )
                if match.group(1) == primarykeys[table]:
                    # The primary key index will be deleted when
                    #  the primary key constraint is deleted
                    continue
                if row['indexname'] in tableconstraints[table]:
                    # It's possible the index is already present in table constraints,
                    #   as a UNIQUE constraint will also create an index.
                    continue
                tableindexes[table].append( row['indexname'] )
                indexreconstructs.insert( 0, f"{row['indexdef']};" )

        # Save the reconstruction
        with open( "reconstruct_indexes_constraints.sql", "w" ) as ofp:
            for row in pkreconstructs:
                ofp.write( f"{row}\n" )
            for row in indexreconstructs:
                ofp.write( f"{row}\n" )
            for row in constraintreconstructs:
                ofp.write( f"{row}\n" )

        # Remove non-primary key constrinats
        for table in tableconstraints.keys():
            _logger.warning( f"Dropping non-pk constraints from {table}" )
            for constraint in tableconstraints[table]:
                cursor.execute( f"ALTER TABLE {table} DROP CONSTRAINT {constraint}" )

        # Remove indexes
        for table in tableindexes.keys():
            _logger.warning( f"Dropping indexes from {table}" )
            for dex in tableindexes[table]:
                cursor.execute( f"DROP INDEX {dex}" )

        # Remove primary keys
        for table, constraint in tablepkconstraints.items():
            _logger.warning( f"Dropping primary key from {table}" )
            cursor.execute( f"ALTER TABLE {table} DROP CONSTRAINT {constraint}" )

        # OMG
        conn.commit()


def recreate_indexes_and_fks( commandfile='reconstruct_indexes_constraints.sql' ):
    """Restore indexes and constraints destroyed by disable_indexes_and_fks()"""

    with open( commandfile ) as ifp:
        commands = ifp.readlines()

    with db() as conn:
        cursor = conn.cursor( row_factory=psycopg.rows.dict_row )
        for command in commands:
            _logger.info( f"Running {command}" )
            cursor.execute( command )

        conn.commit()



def load( pqfile, batchsize, is_bailout=False, stop_after=None ):
    pf = pyarrow.parquet.ParquetFile( pqfile )

    with db() as con:
        cursor = con.cursor()
        totcopied = 0
        with cursor.copy( "COPY ls_xgboost(lsid,ra,dec,white_mag,xgboost,is_bailout) FROM STDIN" ) as dbcopy:
            for rowset in pf.iter_batches( batch_size=batchsize ):
                _logger.info( f"Starting a batch of size {len(rowset)}..." )
                for i in range( len(rowset) ):
                    record = ( int( rowset['ls_id'][i].as_py() ),
                               float( rowset['ra'][i].as_py() ),
                               float( rowset['dec'][i].as_py() ),
                               float( rowset['white_mag'][i].as_py() ),
                               float( rowset['score'][i].as_py() ),
                               is_bailout )
                    dbcopy.write_row( record )

                totcopied += len( rowset )
                _logger.info( f"...have copied {totcopied} rows so far" )
                if ( stop_after is not None ) and ( totcopied >= stop_after ):
                    _logger.info( f"stopping prematurely as requested" )
                    break

        con.commit()

# ======================================================================

def main():
    parser =argparse.ArgumentParser( 'load_postgres_from_pq', description='load Chang Liu pq files to postgres' )
    parser.add_argument( 'pqfile', help="Name of parquet file" )
    parser.add_argument( '-s', '--batch-size', type=int, default=1000000,
                         help="Batch size to load" )
    parser.add_argument( '-b', '--bailout', action='store_true', default=False,
                         help="Set this if this is in the bailout file" )
    parser.add_argument( '-a', '--stop-after', type=int, default=None,
                         help="Only read this may rows (for testing purposes)." )
    args = parser.parse_args()

    try:
        disable_indexes_and_fks()
        load( args.pqfile, args.batch_size, is_bailout=args.bailout, stop_after=args.stop_after )
    finally:
        recreate_indexes_and_fks()

# ======================================================================

if __name__ == "__main__":
    main()


