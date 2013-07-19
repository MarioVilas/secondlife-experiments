# Simple XML-RPC server that runs in background
# by Mario Vilas (mvilas at gmail.com)

import thread
from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler

from Logger import Log

__all__ = ["XMLRPCServer"]

class XMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    pass

class XMLRPCServer(SimpleXMLRPCServer):

    def __init__(self, main, section):
        path    = main.cfg.get(section,     'scriptPath')
        ip      = main.cfg.get(section,     'bindAddress')
        port    = main.cfg.getint(section,  'bindPort')

        serverURL = "http://%s:%d%s" % (ip, port, path)
        Log(1, "Listening XMLRPC at %s" % serverURL)

        handler = XMLRPCRequestHandler
        handler.rpc_paths = (path,)
        SimpleXMLRPCServer.__init__( self,
                            addr            = (ip, port),
                            requestHandler  = handler,
                            logRequests     = False,
                            allow_none      = False,
                            encoding        = None
                            )

    def start(self):
        self.thread = thread.start_new_thread(self.__class__.serve_forever, (self,))
