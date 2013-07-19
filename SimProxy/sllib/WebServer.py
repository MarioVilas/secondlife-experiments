# Simple web server that runs in background
# by Mario Vilas (mvilas at gmail.com)

import thread
import threading
import socket
import select

##from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

from HTTP import HTTPServer
from Logger import Log

__all__ = ["WebServer", "RequestHandler", "WebServerStub"]


##class RequestHandler(BaseHTTPRequestHandler):
##    server_version      = ''
##    sys_version         = ''
##    protocol_version    = 'HTTP/1.1'
##
##    def log_message(self, format, *params):
##        Log(3, "WebServer: %s" % (format % params))
##
##    def version_string(self):
##        return ''


class RequestHandler:

    def __call__(self, server, request, addr):
        params = server, request, addr
        method = 'do_' + request.getmethod()
        if hasattr(self, method):
            return getattr(self, method)(*params)
        method = 'do_' + request.getmethod().upper()
        if hasattr(self, method):
            return getattr(self, method)(*params)
        raise KeyError, method


class WebServerStub:
    message = "Listening HTTP at %s:%d"
    serverSettings = {
                        'bindAddress'   :   'ipaddr',
                        'bindPort'      :   'int',
                     }

    def __init__(self, main, section):
        self.bindAddress    = '0.0.0.0'
        self.bindPort       = 80
        main.cfg.load(self, {section:self.serverSettings})
        Log(1, self.message % (self.bindAddress, self.bindPort))

    def start(self):
        self.thread = thread.start_new_thread(self.serve_forever, ())

    def kill(self):
        pass


class WebServer(WebServerStub):

    def __init__(self, main, section, handler):
        self.handler = handler
        WebServerStub.__init__(self, main, section)

    def start(self):
        self.bindAndListen()
        self.active     = True
        self.event      = threading.Event()
        self.event.clear()
        WebServerStub.start(self)

    def kill(self, timeout = 5):
        self.active = False
        self.event.wait(timeout)

    def bindAndListen(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.bindAddress, self.bindPort))
        self.sock.listen(5)

    def serve_forever(self):
        try:
            while self.active:
                sr, sw, se = select.select([self.sock], [], [self.sock])
                if self.sock in se:
                    try:
                        self.sock.shutdown(2)
                        self.sock.close()
                    except socket.error, e:
                        Log.logException()
                    del self.sock
                    self.active = False
                    break
                if self.sock in sr:
                    accdata = self.sock.accept()
                    thread.start_new_thread(self.handle_request, accdata)
        except Exception, e:
            Log.logException()
        self.active = False
        self.event.set()

    def handle_request(self, sock, addr):
        Log(2, "Request received from %s:%d" % addr)
        try:
            server = HTTPServer.fromsocket(sock)
            while server.isactive():
                request = server.readrequest()
                if request is None:
                    server.close()
                    break
                try:
                    self.handler(server, request, addr)
                except Exception, e:
                    Log.logException()
                    if server.isactive():
                        server.writeresponse(500, hdr='Connection: close')
                        server.close()
                    break
            sock.shutdown(2)
            sock.close()
            print "CLOSE SERVER"
        except Exception, e:
            Log.logException()

##class WebServer(WebServerStub, HTTPServer):
##
##    def __init__(self, main, section, handler):
##        WebServerStub.__init__(self, main, section)
##        HTTPServer.__init__(self, (self.bindAddress, self.bindPort), handler)
