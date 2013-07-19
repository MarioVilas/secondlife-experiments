# Simple web server that runs in background
# by Mario Vilas (mvilas at gmail.com)

import thread
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

from Logger import Log

__all__ = ["WebServer", "RequestHandler", "WebServerStub"]


class RequestHandler(BaseHTTPRequestHandler):
    server_version      = ''
    sys_version         = ''
    protocol_version    = 'HTTP/1.1'

    def log_message(self, format, *params):
        Log(3, "WebServer: %s" % (format % params))

    def version_string(self):
        return ''


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
        self.thread = thread.start_new_thread(self.__class__.serve_forever, (self,))


class WebServer(WebServerStub, HTTPServer):

    def __init__(self, main, section, handler):
        WebServerStub.__init__(self, main, section)
        HTTPServer.__init__(self, (self.bindAddress, self.bindPort), handler)
