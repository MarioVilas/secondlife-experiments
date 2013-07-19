# Second Life seed capabilities proxy
# by Mario Vilas (mvilas at gmail.com)

import sys
import os.path
import socket
import xmlrpclib
import urlparse
import urllib2
import re
import base64
import struct
import zlib

from sllib import SLTypes
from sllib.Logger import Log
from sllib.Config import Config
from sllib.LLSD import LLSD
from sllib.WebServer import WebServer, RequestHandler


class CapProxy:
    section         = 'CapProxy'
    uriSettings     = {
                        'URI': {
                                'loginProxyURI' : 'string',
                                'capProxyURI'   : 'string',
                                'simProxyURI'   : 'string',
                               },
                       }
    settings        = {
                        'CapProxy': {
                                    'interceptURLs'     : 'bool',
                                    'useSimProxy'       : 'bool',
                                    'captureFile'       : 'string',
                                    'captureCompression': 'int',
                                    }
                       }

    def __init__(self, configFilename):
        self.cfg = Config()
        self.cfg.read(filename)

    def start(self):
        Log.loadSettings(self.cfg, self.section)

        self.loginProxyURI      = None
        self.cfg.load(self, self.uriSettings)

        self.interceptURLs      = False
        self.useSimProxy        = False
        self.captureFile        = ''
        self.captureCompression = 9
        self.cfg.load(self, self.settings)

        if self.captureFile:
            Log(1, "Storing HTTP transactions in file %r" % self.captureFile)
            self.captureFile    = open(self.captureFile, 'a+b')
        else:
            self.captureFile    = None

        self.server         = WebServer(self, self.section, CapProxyHandler)
        self.server.mangler = CapProxyURIMangler(self.capProxyURI,
                                                 self.simProxyURI,
                                                 remote = False
                                                )
        self.server.sim     = CapProxySimIntercept(self.simProxyURI)
        self.server.main    = self
        self.server.start()
        Log(1, "CapProxy loaded successfully")

    def kill(self):
        Log(1, "CapProxy shut down")


class CapProxyCapture:

    @classmethod
    def packRequest(self, path, request, level = 9):
        data = '\x01' + path + '\x00' + request
        return self._pack(data, level)

    @classmethod
    def packResponse(self, response, level = 9):
        data = '\x00' + response
        return self._pack(data, level)

    @classmethod
    def _pack(self, data, level = 9):
        data = zlib.compress(data, level)
        data = SLTypes.Variable.encode(data, 4)
        return data

    @classmethod
    def unpack(self, capture, offset):
        offset, data        = SLTypes.Variable.decode(capture, offset, 4)
        data                = zlib.decompress(data)
        is_request          = bool(ord(data[0]))
        if is_request:
            path, request   = data[1:].split('\x00')
            text            = 'From %s\r\nRequest:\r\n%s' % (path, request)
        else:
            response        = data[1:]
            text            = 'Response:\r\n%s' % response
        return offset, text


class CapProxyURIMangler:
    __url_find = re.compile('https?://[^<]+', re.I)

    def __init__(self, uri, sp_uri, remote = False):
        if not urlparse.urlsplit(uri)[0]:
            raise Exception, "Should be an absolute URI: %r" % uri
        self.__absolute = uri
        self.__relative = self.relative(uri)
        self.__sp_uri   = sp_uri
        self.__remote   = remote
        self.__seed     = {}

    def is_mangled(self, uri):
        uri = self.absolute(uri)
        return uri.startswith(self.__absolute)

    def mangle(self, uri):
        return self.__absolute + self.newSeed(uri)

    def unmangle(self, uri):
        uri = self.relative(uri)
        uri = uri[ len(self.__relative) : ]
        return self.getSeed(uri)

    def __do_xml(self, xml, do_mangle = True):
        s = self.__url_find.search(xml)
        while s:
            b, e = s.span()
            original_uri = xml[b:e]
            mangled_uri  = original_uri
            is_m = self.is_mangled(original_uri)
            if do_mangle and not is_m:
                mangled_uri = self.mangle(original_uri)
            elif not do_mangle and is_m:
                mangled_uri = self.unmangle(original_uri)
            xml = xml[:b] + mangled_uri + xml[e:]
            p = e - len(original_uri) + len(mangled_uri)
            s = self.__url_find.search(xml, p)
        return xml

    def mangle_xml(self, xml):
        return self.__do_xml(xml, True)

    def unmangle_xml(self, xml):
        return self.__do_xml(xml, False)

    def absolute(self, uri):
        if not urlparse.urlsplit(uri)[0]:
            uri = urlparse.urljoin(self.__absolute, uri)
        return uri

    @staticmethod
    def relative(uri):
        uri = urlparse.urlsplit(uri)[2]
        return uri

    @staticmethod
    def quote(uri):
##        return ''.join( [ ('%%%.2x' % ord(c)) for c in uri ] )
        return urllib2.quote(uri).replace(':','%3a')

    @staticmethod
    def unquote(uri):
        return urllib2.unquote(uri)

    def newSeed(self, uri):
        Log(1, "Discovered seed capabilities URI %s" % uri)
        if self.__remote:
            simProxy    = xmlrpclib.ServerProxy(self.__sp_uri)
            hashed_uri  = simProxy.newSeed(uri)
        else:
            hashed_uri  = hash(uri)
            self.__seed[hashed_uri] = uri
        hashed_uri      = str(hashed_uri)
        Log(2, "Remembered seed capabilities URI as hash %s" % hashed_uri)
        return hashed_uri

    def getSeed(self, hashed_uri):
        Log(2, "Received hash %s" % hashed_uri)
        hashed_uri      = long(hashed_uri)
        if self.__seed.has_key(hashed_uri):
            uri         = self.__seed[hashed_uri]
        else:
            simProxy    = xmlrpclib.ServerProxy(self.__sp_uri)
            uri         = simProxy.getSeed(hashed_uri)
        Log(2, "Received capabilities URI: %s" % uri)
        if hash(uri) != hashed_uri:
            Log(1, "Bad hashed URI: (%d != %d) %s" % (hash(uri), hashed_uri, uri))
        return uri



class CapProxySimIntercept:
    __ip_template = '<script>%s:%d</script>'
    __ip_find = re.compile(
        '<string>'
        '([0-9][0-9]?[0-9]?\\.'
        '[0-9][0-9]?[0-9]?\\.'
        '[0-9][0-9]?[0-9]?\\.'
        '[0-9][0-9]?[0-9]?)'
        '\\:'
        '([0-9][0-9]?[0-9]?[0-9]?[0-9]?)'
        '</string>'
        , re.I)
    __teleport_1 = '<key>SimIP</key><binary encoding="base64">'
    __teleport_2 = '</binary><key>SimPort</key><integer>'
    __teleport_3 = '</integer>'

    def __init__(self, uri):
        if not urlparse.urlsplit(uri)[0]:
            raise Exception, "Should be an absolute URI: %r" % uri
        self.__uri = uri

    def newSim(self, simAddr):
        Log(1, "Requesting Sim proxy for %s:%d" % simAddr)
        simProxy = xmlrpclib.ServerProxy(self.__uri)
        simAddr  = simProxy.newSim(simAddr)
        simAddr  = tuple(simAddr)
        Log(1, "Granted Sim proxy as %s:%d" % simAddr)
        return simAddr

    def change_xml(self, xml):
        
        # <key>sim-ip-and-port</key>
        # <string>63.210.157.71:13006</string>
        s = self.__ip_find.search(xml)
        while s:
##            print s                                 # XXX
            b, e = s.span()
            original_sim = xml[b:e]
            simAddr      = s.groups()
            simAddr      = simAddr[0], int(simAddr[1])
            simAddr      = self.newSim(simAddr)
            new_sim      = self.__ip_template % simAddr
            xml = xml[:b] + new_sim + xml[e:]
            p = b - len(original_sim) + len(new_sim)
            s = self.__ip_find.search(xml, p)

        # <key>SimIP</key>
        # <binary encoding="base64">P9Kfug==</binary>
        # <key>SimPort</key>
        # <integer>12035</integer>
        b1      = xml.find(self.__teleport_1)
        while b1 > -1:
##            print b1                                # XXX
            e1  = b1 + len(self.__teleport_1)
            b2  = xml.find(self.__teleport_2, e1)
            e2  = b2 + len(self.__teleport_2)
            b3  = xml.find(self.__teleport_3, e2)
            e3  = b3 + len(self.__teleport_3)
            sim_ip          = xml[e1:b2]
            sim_port        = xml[e2:b3]
            d_sim_ip        = socket.inet_ntoa(base64.decodestring(sim_ip))
            d_sim_port      = int(sim_port)
            simAddr         = (d_sim_ip, d_sim_port)
            simAddr         = self.newSim(simAddr)
            new_sim_ip      = base64.encodestring(socket.inet_aton(simAddr[0]))
            new_sim_port    = str(simAddr[1])
            xml = xml[:e1] + new_sim_ip + xml[b2:e2] + new_sim_port + xml[b3:]
            b2  = e1 + len(new_sim_ip)
            e2  = b2 + len(self.__teleport_2)
            b3  = e2 + len(new_sim_port)
            e3  = b3 + len(self.__teleport_3)
            b1  = xml.find(self.__teleport_1, e3)

        return xml


class CapProxyHandler(RequestHandler):

    def do_POST(self):
        try:
            # Get arguments by reading body of request.
            # We read this in chunks to avoid straining
            # socket.read(); around the 10 or 15Mb mark, some platforms
            # begin to have problems (bug #792570).
            max_chunk_size = 10*1024*1024
            size_remaining = int(self.headers["Content-length"])
            L = []
            while size_remaining:
                chunk_size = min(size_remaining, max_chunk_size)
                L.append(self.rfile.read(chunk_size))
                size_remaining -= len(L[-1])
            request = ''.join(L)

            # If the request is not mangled, return a 404 error
            path = self.path
            if not self.server.mangler.is_mangled(path):
                raise HTTPError(
                    self.server.mangler.absolute(path),
                    404, 'Not found',
                    'Content-length: 0\r\n\r\n',
                    None)

            # Store the request
            fd = self.server.main.captureFile
            if fd:
                cap_level = self.server.main.captureCompression
                cap_data = CapProxyCapture.packRequest(path, request, cap_level)
                fd.write(cap_data)

            # Unmangle the request
##            while self.server.mangler.is_mangled(path):
            Log(3, 'Mangled URI: %s' % path)
            path = self.server.mangler.unmangle(path)
            Log(2, "Requested URI: %s" % path)
            Log(3, "Request data: %r" % request)
            unmangled_req = self.server.mangler.unmangle_xml(request)
            if unmangled_req != request:
                request = unmangled_req
                Log(3, "Unmangled request data: %r" % request)

            # Store the request
            fd = self.server.main.captureFile
            if fd:
                cap_level = self.server.main.captureCompression
                cap_data = CapProxyCapture.packRequest(path, request, cap_level)
                fd.write(cap_data)

            # Proxy the request
            response = urllib2.urlopen(path, request).read()
            Log(3, "Response data: %r" % response)

            # Store the response
            fd = self.server.main.captureFile
            if fd:
                cap_level = self.server.main.captureCompression
                cap_data = CapProxyCapture.packResponse(response, cap_level)
                fd.write(cap_data)

            # Parse the response
            if self.server.main.interceptURLs:
                try:
                    response = self.server.mangler.mangle_xml(response)
                except Exception, e:
                    Log.logException()
            if self.server.main.useSimProxy:
                try:
                    response = self.server.sim.change_xml(response)
                except Exception, e:
                    Log.logException()

            # Log the modified response data
            if self.server.main.interceptURLs or self.server.main.useSimProxy:
                Log(3, "Modified response data: %r" % response)

            # Store the response
            fd = self.server.main.captureFile
            if fd:
                cap_level = self.server.main.captureCompression
                cap_data = CapProxyCapture.packResponse(response, cap_level)
                fd.write(cap_data)

        except urllib2.HTTPError, e:
            Log.logException(2)
##            Log.logException(2, print_tb = False)
            if self.request_version != 'HTTP/0.9':
                self.wfile.write("%s %d %s\r\n" %
                                 (self.protocol_version, e.code, e.msg))
            self.wfile.write(e.hdrs)

        except Exception, e:
            # This should only happen if the module is buggy
            # internal error, report as HTTP server error
            Log.logException(2)
            self.send_response(500)
            self.end_headers()

        else:
            if response is not None:
                # got a valid response
                self.send_response(200)
                self.send_header("Content-type", "text/xml")
                self.send_header("Content-length", str(len(response)))
                self.send_header("Connection", "persistent")
                self.end_headers()
                self.wfile.write(response)
                self.wfile.flush()


if __name__ == "__main__":
    scriptname  = os.path.basename(sys.argv[0])
##    filename    = os.path.splitext(scriptname)[0] + '.cfg'
    filename = 'SimProxy.cfg'
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ('-h', '-help', '--help'):
            print "%s [alternate config file]" % scriptname
            exit()
        filename = sys.argv[1]

    print "CapProxy started, hit Enter to stop..."
    lp = CapProxy(filename)
    lp.start()
    raw_input()
    lp.kill()
