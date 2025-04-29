import logging
import ismplejson

import flask
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
    def do_the_things( self, *args, **kwargs ):
        pass


# ======================================================================

app = flask.Flask( __name__ )
# app.logger.setLevel( logging.INFO )
app.logger.setLevel( logging.DEBUG )

urls = {
    "/": MainPage,
    "getsources/<ra>/<dec>/<radius>": GetSources,
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
