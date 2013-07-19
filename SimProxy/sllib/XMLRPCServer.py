# Simple XML-RPC server that runs in background
# by Mario Vilas (mvilas at gmail.com)

from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler

from WebServer import WebServerStub
from Logger import Log

__all__ = ["XMLRPCServer", "XMLRPCRequestHandler"]

class XMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ()

class XMLRPCServer(WebServerStub, SimpleXMLRPCServer):
    message = "Listening XML-RPC at %s:%d"

    def __init__(self, main, section, handlerClass = XMLRPCRequestHandler):
        WebServerStub.__init__(self, main, section)
        SimpleXMLRPCServer.__init__( self,
                            addr           = (self.bindAddress, self.bindPort),
                            requestHandler = handlerClass,
                            logRequests    = (Log.verbose >= 3),
                            allow_none     = False,
                            encoding       = None
                            )
