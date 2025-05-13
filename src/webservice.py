import os
import logging
import simplejson

from contextlib import contextmanager

import psycopg
import flask
import flask.views
import flask_session

# ======================================================================
# UUID encoder for simplejson

class UUIDJSONEncoder( simplejson.JSONEncoder ):
    def default( self, obj ):
        if isinstance( obj, uuid.UUID ):
            return str(obj)
        else:
            return super().default( obj )

# ======================================================================

class BaseView( flask.views.View ):
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )

    @classmethod
    @contextmanager
    def db( cls, dbcon=None ):
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
        
        
    def dispatch_request( self, *args, **kwargs ):
        try:
            retval = self.do_the_things( *args, **kwargs )
            # Can't just use the default JSON handling, because it
            #   writes out NaN which is not standard JSON and which
            #   the javascript JSON parser chokes on.  Sigh.
            if isinstance( retval, dict ) or isinstance( retval, list ):
                return ( simplejson.dumps( retval, ignore_nan=True, cls=UUIDJSONEncoder ),
                         200, { 'Content-Type': 'application/json' } )
            elif isinstance( retval, str ):
                return retval, 200, { 'Content-Type': 'text/plain; charset=utf-8' }
            elif isinstance( retval, tuple ):
                return retval
            else:
                return retval, 200, { 'Content-Type': 'application/octet-stream' }
        except Exception as ex:
            # sio = io.StringIO()
            # traceback.print_exc( file=sio )
            # app.logger.debug( sio.getvalue() )
            flask.current_app.logger.exception( str(ex) )
            return str(ex), 500
    

# ======================================================================

class MainPage( BaseView ):
    def dispatch_request( self ):
        return flask.render_template( "main.html" )


# ======================================================================

class GetSources( BaseView ):
    def do_the_things( self, ra=None, dec=None, radius=None, maglim=None ):
        if any( x is None for x in [ra, dec, radius] ):
            return "Must give an ra, dec, and radius."
        ra = float( ra )
        dec = float( dec )
        radius = float( radius )
        maglim = None if maglim is None else float( maglim )

        if radius >= 300.:
            return "Error, can only search within at most 300 arcseconds.", 500
        
        with self.db() as dbcon:
            cursor = dbcon.cursor()
            q = ( "SELECT lsid, ra, dec, white_mag, xgboost, q3c_dist(ra,dec,%(ra)s,%(dec)s) AS dist "
                  "FROM ls_xgboost "
                  "WHERE q3c_radial_query(ra, dec, %(ra)s, %(dec)s, %(rad)s)" )
            subdict = { 'ra': ra, 'dec': dec, 'rad': radius/3600. }
            if maglim is not None:
                q += " AND white_mag<=%(maglim)s"
                subdict['maglim'] = maglim
            q += " ORDER BY q3c_dist(ra, dec, %(ra)s, %(dec)s)"
            cursor.execute( q, subdict )
            columns = { cursor.description[i].name: i for i in range(len(cursor.description)) }
            rows = cursor.fetchall()

        return { 'lsid': [ r[columns['lsid']] for r in rows ],
                 'ra': [ r[columns['ra']] for r in rows ],
                 'dec': [ r[columns['dec']] for r in rows ],
                 'dist': [ r[columns['dist']]*3600. for r in rows ],
                 'white_mag': [ r[columns['white_mag']] for r in rows ],
                 'xgboost': [ r[columns['xgboost']] for r in rows ],
                 'is_star': [ r[columns['xgboost']] >= 0.5 for r in rows ] }


# ======================================================================

app = flask.Flask( __name__ )
# app.logger.setLevel( logging.INFO )
app.logger.setLevel( logging.DEBUG )

urls = {
    "/": MainPage,
    "/getsources/<ra>/<dec>/<radius>": GetSources,
    "/getsources/<ra>/<dec>/<radius>/<maglim>": GetSources,
}

usedurls = {}
for url, cls in urls.items():
    if url not in usedurls.keys():
        usedurls[ url ] = 0
        name = url
    else:
        usedurls[ url ] += 1
        name = f'{url}.{usedurls[url]}'

    app.add_url_rule (url, view_func=cls.as_view(name), methods=['GET', 'POST'], strict_slashes=False )
