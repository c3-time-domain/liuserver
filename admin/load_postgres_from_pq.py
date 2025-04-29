import os
import pyarrow.parquet
import psycopg


def db( dbcon ):
    if dbcon is not None:
        yield dbcon
        return

    try:
        pghost = os.getenv( 'PGHOST', 'postgres' )
        pgport = os.getenv( 'PGPORT', 5432 )
        pguser = os.getenv( 'PGUSER', 'postgres' )
        pgpass = os.getenv( 'PGPASS', 'fragile' )
        pgname = os.getenv( 'PGNAME', 'ls_xgboost' )

        dbcon = psycopg.connect( dbname=pname, user=pguser, password=pgpass, host=pghost, port=pgport )
        yield dbcon
    finally:
        if dbcon is not None:
            dbcon.rollback()
            dbcon.close()


def load( pqfile, batchsize ):
    
