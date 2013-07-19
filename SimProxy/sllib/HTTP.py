# Simple web server
# by Mario Vilas (mvilas at gmail.com)

# TO DO LIST:
#
#   [ ] Fix SSL support
#   [ ] Implement validate() methods
#   [ ] Implement chunked encoding (or at least raise an exception)
#   [ ] Implement MIME multipart messages (or at least raise an exception)
#   [ ] Implement SSL in the server (using which wrapper? must decide!)
#   [ ] Add client and server methods to parse form data
#   [ ] Write some test code
#   [ ] Test HTTP/0.9 (or drop it if broken and it's too much hassle to fix it)
#

import types
import mimetools
import StringIO
import re

import base64
import quopri
import uu

import zlib
import gzip

import socket
import select
import urllib2
import urlparse


from Logger import Log


__all__ = [
            "HTTPException",
            "HTTPMessage",
            "HTTPRequest",
            "HTTPResponse",
            "ContentEncoding",
            "TransferEncoding",
            "HTTPClient",
            "HTTPServer",
            "HTTPConstant",
            ]


class HTTPException(Exception):
    pass


class HTTPMessage:
    re_rline    = '([^\t ]+)[\t ]+([^\t ]+)[\t ]+([^\r\n]+)'
    fs_rline    = '%s %s %s%s'
    re_rline_09 = '([^\t ]+)[\t ]+([^\r\n]+)'
    fs_rline_09 = '%s %s%s'

    def __init__(self, data = None):
        if data is not None:
            self.readdata(data)

    def hasversion(self):
        return hasattr(self, '_HTTPMessage__version')

    def hasdata(self):
        return hasattr(self, '_HTTPMessage__data')

    def getversion(self):
        return self.__version

    def getdata(self):
        return self.__data

    def setversion(self, version):
        self.__version      = str(version)

    def setdata(self, data):
        self.__data         = data

    def __codec(self, encoding_header, fn):
        encoding        = self.getheader(encoding_header)
        if encoding:
            data        = self.getdata()
            data        = fn(encoding, data)
        self.setdata(data)

    def encodecontent(self):
        self.__codec('Content-Encoding',          ContentEncoding.encodestring)

    def encodetransfer(self):
        self.__codec('Content-Transfer-Encoding', TransferEncoding.encodestring)

    def decodetransfer(self):
        self.__codec('Content-Transfer-Encoding', TransferEncoding.decodestring)

    def decodecontent(self):
        self.__codec('Content-Encoding',          ContentEncoding.decodestring)

    def encode(self):
        self.encodecontent()
        self.encodetransfer()

    def decode(self):
        self.decodetransfer()
        self.decodecontent()

    def readdata(self, headers_and_data):
        if headers_and_data == HTTPConstant.newline:
            self.setallheaders('')
        else:
            pos     = headers_and_data.find(HTTPConstant.newline*2)
            if pos < 0:
                raise HTTPException, 'Incomplete header'
            data    = headers_and_data[pos+(len(HTTPConstant.newline)*2):]
            headers = headers_and_data[:pos]
            self.setallheaders(headers)
            self.setdata(data)

    @classmethod
    def fromdata(self, data):
        msg = self()
        msg.readdata(data)
        return msg

    def getcontentlength(self):
        length = self.getheader('Content-Length', None)
        if length is not None:
            length = long(length)
        return length

    def validate(self):
        pass                # XXX TO DO

    def __str__(self):
        headers = self.getallheaders()
        data    = self.getdata()
        return headers + data

    def getallheaders(self):
        hdr          = HTTPConstant.newline.join(self.__headers + [''])
        hdr         += HTTPConstant.newline
        return hdr

    def setheaderslist(self, hdrlist):
        hdr          = HTTPConstant.newline.join(hdrlist + [''])
        hdr         += HTTPConstant.newline
        return self.setallheaders(hdr)

    def setallheaders(self, headers):
        self.__headers  = []
        self.__hdrdict  = {}
        self.addheaders(headers)

    def addheaders(self, headers):
        headers = headers.split(HTTPConstant.newline)
        i = 0
        while i < len(headers):
            if headers[i] == '':
                del headers[i]
            else:
                i += 1
        self.__headers += headers
        for hdr in headers:
            p = hdr.find(':')
            if p <= 0:
                raise HTTPException, "Invalid header"
            name  = hdr[:p].strip().lower()
            value = hdr[p+1:].strip()
            if value.endswith(HTTPConstant.newline):
                value = value[:-len(HTTPConstant.newline)]
            if not self.__hdrdict.has_key(name):
                self.__hdrdict[name]  = value
            else:
                self.__hdrdict[name] += '; ' + value

    def getheader(self, name, default = None):
        return self.__hdrdict.get(name.lower(), default)

    def setheader(self, name, value):
        self.removeheader(name)
        self.__hdrdict[name.lower()] = value
        self.__headers.append('%s: %s' % (name, value))

    def removeheader(self, name):
        name = name.lower()
        if self.__hdrdict.has_key(name):
            del self.__hdrdict[name]
        i = 0
        while i < len(self.__headers):
            if self.__headers[i].lower().startswith(name + ':'):
                del self.__headers[i]
            else:
                i += 1

    delheader = removeheader

    def __len__(self):              return len(self.__headers)
    def __repr__(self):             return repr(str(self))
    def __getitem__(self, k):       return self.__hdrdict[k.lower()]
    def __setitem__(self, k, d):    self.setheader(k, d)
    def __delitem__(self, k):       self.removeheader(k)
    def has_key(self, k):           return self.__hdrdict.has_key(k.lower())
    def __contains__(self, k):      return k.lower() in self.__hdrdict
    def __iter__(self):             return self.__headers.__iter__()
    def iterkeys(self):             return self.__hdrdict.iterkeys()
    def itervalues(self):           return self.__hdrdict.itervalues()
    def iteritems(self):            return self.__hdrdict.iteritems()
    def keys(self):                 return self.__hdrdict.keys()
    def values(self):               return self.__hdrdict.values()
    def items(self):                return self.__hdrdict.items()
    def get(self, *argl, **argd):   return self.__hdrdict.get(*argl, **argd)


class HTTPRequest(HTTPMessage):

    def hasmethod(self):
        return hasattr(self, '_HTTPRequest__method')

    def haspath(self):
        return hasattr(self, '_HTTPRequest__path')

    def getmethod(self):
        return self.__method

    def getpath(self):
        return self.__path

    def setmethod(self, method):
        self.__method       = str(method)

    def setpath(self, path):
        self.__path         = str(path)

    def __str__(self):
        method      = self.getmethod()
        path        = self.getpath()
        version     = self.getversion()
        if version == 'HTTP/0.9':
            request_line = self.fs_rline_09 % \
                (method, path, HTTPConstant.newline)
        else:
            request_line = self.fs_rline % \
                (method, path, version, HTTPConstant.newline)
        return request_line + HTTPMessage.__str__(self)

    def readdata(self, data):
        data = HTTPConstant.normalizenewlines(data)
        pos  = data.find(HTTPConstant.newline)
        if pos < 0:
            raise HTTPException, 'Invalid request'
        line    = data[:pos]
        headers = data[pos+len(HTTPConstant.newline):]
        mobj    = re.search(self.re_rline, line)
        if not mobj:
            mobj = re.search(self.re_rline_09, line)
            if not mobj:
                raise HTTPException, 'Invalid request line'
            self.setversion('HTTP/0.9')
            g = mobj.groups()
        else:
            g = mobj.groups()
            self.setversion(g[2])
        self.setmethod(g[0])
        self.setpath(g[1])
        HTTPMessage.readdata(self, headers)

    @classmethod
    def fromurl(self, url, data = None, version = 'HTTP/1.0'):
        parsed_url  = urlparse.urlparse(url)
        host        = parsed_url[1].strip()
        path        = parsed_url.geturl()
        path        = path[ len(parsed_url[0]+'://'+parsed_url[1]) : ]
        if path == '':
            path    = '/'
        hdr         = ''
        if version == 'HTTP/1.1':
            hdr    += 'Host: %s' % host
            hdr    += HTTPConstant.newline
        if data is None:
            method  = 'GET'
        else:
            method  = 'POST'
            hdr    += 'Content-Length: %d' % len(data)
            hdr    += HTTPConstant.newline
            hdr    += 'Content-Type: application/x-www-form-urlencoded'
            hdr    += HTTPConstant.newline
        return self.fromparams(path, method, hdr, data, version)

    @classmethod
    def fromparams( self,
                    path    = '/',
                    method  = None,
                    hdr     = None,
                    data    = None,
                    version = None
                    ):
        if method is None:
            if data is None:
                method = 'GET'
            else:
                method = 'POST'
        if data is None:
            data = ''
        if hdr is None:
            if method == 'POST':
                hdr = 'Content-Length: %d%s' % (len(data), HTTPConstant.newline)
            else:
                hdr = ''
        if not hdr.endswith(HTTPConstant.newline):
            hdr += HTTPConstant.newline
        req = HTTPRequest()
        req.setmethod(method)
        req.setpath(path)
        req.setallheaders(hdr)
        req.setdata(data)
        if version is None:
            if not req.has_key('Host'):
                version = 'HTTP/1.0'
            else:
                version = 'HTTP/1.1'
        req.setversion(version)
        return req

    def validate(self):
        pass                # XXX TO DO


class HTTPResponse(HTTPMessage):

    def hascode(self):
        return hasattr(self, '_HTTPResponse__code')

    def hasdescription(self):
        return hasattr(self, '_HTTPResponse__description')

    def getcode(self):
        return self.__code

    def getdescription(self):
        return self.__description

    def setcode(self, code):
        self.__code         = str(code)

    def setdescription(self, description):
        self.__description  = str(description)

    def __str__(self):
        version             = self.getversion()
        if version == 'HTTP/0.9':
            response_line   = ''
        else:
            code            = self.getcode()
            description     = self.getdescription()
            response_line   = self.fs_rline % \
                (version, code, description, HTTPConstant.newline)
        return response_line + HTTPMessage.__str__(self)

    def readdata09(self, data):
        self.setversion('HTTP/0.9')
        HTTPMessage.read(data)

    def readdata(self, data):
        data = HTTPConstant.normalizenewlines(data)
        pos  = data.find(HTTPConstant.newline)
        if pos < 0:
            raise HTTPException, 'Invalid header'
        response_line   = data[:pos]
        headers         = data[pos+len(HTTPConstant.newline):]
        mobj            = re.search(self.re_rline, response_line)
        if not mobj:
            raise HTTPException, 'Invalid response line'
        g = mobj.groups()
        self.setversion(g[0])
        self.setcode(g[1])
        self.setdescription(g[2])
        HTTPMessage.readdata(self, headers)

    @classmethod
    def fromparams( self,
                    code    = 200,
                    data    = None,
                    hdr     = None,
                    desc    = None,
                    version = None
                    ):
        code = str(code)
        if desc is None:
            desc = HTTPConstant.responses[int(code)]
        if data is None:
            data = ''
        if hdr is None:
            hdr  = 'Content-Length: %d%s' % (len(data), HTTPConstant.newline)
        if not hdr.endswith(HTTPConstant.newline * 2):
            hdr += (HTTPConstant.newline * 2)
        resp = self()
        resp.setcode(code)
        resp.setdescription(desc)
        resp.setallheaders(hdr)
        resp.setdata(data)
        if version is None:
            if not resp.has_key('Connection'):
                version = 'HTTP/1.0'
            else:
                version = 'HTTP/1.1'
        resp.setversion(version)
        return resp

    # this method actually connects to the given url and downloads the response
    @classmethod
    def fromurl(self, url, data = None):
        urlobj   = urllib2.urlopen(url, data)
        response = self()
        response.setversion('HTTP/1.1')     # XXX this is a hack!
        response.setcode(urlobj.code)
        response.setdescription(urlobj.msg)
        response.setheaderslist(urlobj.info().headers)
        response.setdata(urlobj.read())
        return response

    def validate(self):
        pass                # XXX TO DO


class ContentEncoding:

    @staticmethod
    def encodestring(encoding, data):
        if encoding == 'gzip':
            sf = StringIO.StringIO()
            zf = gzip.GzipFile(fileobj = sf)
            zf.write(data)
            return sf.getvalue()
        if encoding == 'deflate':
            return zlib.compress(data, 9)
        if encoding == 'none':
            return data
        else:
            raise ValueError, encoding

    @staticmethod
    def decodestring(encoding, data):
        if encoding == 'gzip':
            sf = StringIO.StringIO(data)
            zf = gzip.GzipFile(fileobj = sf)
            return zf.read()
        if encoding == 'deflate':
            return zlib.decompress(data)
        if encoding == 'none':
            return data
        else:
            raise ValueError, encoding


class TransferEncoding:

    @staticmethod
    def encodestring(encoding, data):
        if encoding == 'base64':
            return base64.encodestring(data)
        if encoding == 'quoted-printable':
            return quopri.encodestring(data)
        if encoding in ('uuencode', 'x-uuencode', 'uue', 'x-uue'):
            return uu.encodestring(data)
        if encoding == '7bit':
            return str(data).encode('utf_7')
        if encoding == '8bit':
            return str(data).encode('utf_8')
        if encoding == 'none':
            return data
        else:
            raise ValueError, encoding

    @staticmethod
    def decodestring(encoding, data):
        if encoding == 'base64':
            return base64.decodestring(data)
        if encoding == 'quoted-printable':
            return quopri.decodestring(data)
        if encoding in ('uuencode', 'x-uuencode', 'uue', 'x-uue'):
            return uu.decodestring(data)
        if encoding == '7bit':
            return str(data)
        if encoding == '8bit':
            return str(data)
        if encoding == 'none':
            return data
        else:
            raise ValueError, encoding


class HTTPParser:

    @classmethod
    def fromsocket(self, sock):
##        return self( sock )
        return self( sock.makefile('rwb') )

    @classmethod
    def fromfile(self, filename):
        return self( open(filename, 'rb') )

    def __init__(self, fd):
        self.fd = fd

##    def fileno(self):
##        return self.fd
##
##    def setfileno(self, fd):
##        self.fd, fd = fd, self.fd
##        return fd

    def isactive(self):
        return hasattr(self, 'fd')

    def read(self, max = None):
        if hasattr(self.fd, 'flush'):
            self.fd.flush()
        if max is None:
            data = self.fd.read()
        else:
            data = self.fd.read(max)
        Log(4, "READ: %r" % data)
        return data

    def readline(self):
        if hasattr(self.fd, 'flush'):
            self.fd.flush()
        if hasattr(self.fd, 'readline'):
            data = self.fd.readline()
        else:
            data = ''
            while True:
                char = self.fd.read(1)
                data += char
                if char == '\n': break
        Log(4, "READLINE: %r" % data)
        return data

    def readall(self, length = None):
        if hasattr(self.fd, 'flush'):
            self.fd.flush()
        if length is None:
            data = self.fd.read()
        else:
            data = ''
            while length - len(data):
                new_data = self.fd.read(length - len(data))
                if not new_data: break
                data += new_data
        Log(4, "READALL: %r" % data)
        return data

    def write(self, data):
        data = str(data)
        Log(4, "WRITE: %r" % data)
        length = self.fd.write(data)
        if hasattr(self.fd, 'flush'):
            self.fd.flush()
        return length

    def writeline(self, data):
        data = str(data)
        Log(4, "WRITELINE: %r" % data)
        if hasattr(self.fd, 'writeline'):
            length = self.fd.writeline(data)
        else:
            length = self.fd.write(data + HTTPConstant.newline)
        if hasattr(self.fd, 'flush'):
            self.fd.flush()
        return length

##    def writeall(self, data):
##        data = str(data)
##        Log(4, "WRITEALL: %r" % data)
##        while len(data):
##            length = self.fd.write(data)
##            if not length: break
##            data = data[length:]
##        if hasattr(self.fd, 'flush'):
##            self.fd.flush()
##        return len(data)

    def close(self):
        if self.isactive():
            if hasattr(self.fd, 'flush'):
                self.fd.flush()
            if hasattr(self.fd, 'close'):
                self.fd.close()
            del self.fd

    def readheaders(self, maxhdr = 0x10000):
        data = ''
        line = '123'
        while len(line) > len(HTTPConstant.newline) and len(data) < maxhdr:
            line  = self.readline()
            data += line
        return data

    def readdata(self, length = None, maxdata = 0x100000):
        if length is None:      return self.readall()
        if length < 0:          raise HTTPException, "Bad Content-Length"
        if length > maxdata:    raise HTTPException, "Content-Length too large"
        return self.readall(length)


class HTTPClient(HTTPParser):

    @classmethod
    def fromurl(self, url):
        parsed  = urlparse.urlparse(url)
        proto   = parsed[0].lower()
        host    = parsed[1].strip()
        if proto[-1] == 's':
            port = 443
        else:
            port = 80
        if ':' in host:
            host, port  = host.split(':')
            host        = host.strip()
            port        = int(port)
        Log(4, "CONNECT: %s:%d" % (host,port))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect( (host, port) )
        if proto[-1] == 's':
            fd = socket.ssl(s)
            return self(fd)
        else:
            return self.fromsocket(s)

    def readresponse(self, maxhdr = 0x10000, maxdata = 0x100000):
        headers     = self.readheaders(maxhdr)
        if not headers:
            self.close()
            return None
        response    = HTTPResponse.fromdata(headers)
        length      = response.getcontentlength()
        data        = self.readdata(length, maxdata)
        response.setdata(data)
        return response

    def writerequest(   self,
                        path    = '/',
                        method  = None,
                        hdr     = None,
                        data    = None,
                        version = None
                        ):
        req = HTTPRequest.fromparams(path, method, hdr, data, version)
        return self.write(req)


class HTTPServer(HTTPParser):

    @staticmethod
    def bindandlisten(self, addr):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(addr)
        s.listen(5)
        return s

    @classmethod
    def fromlisteningsocket(self, sock):
        s, addr = sock.accept()
        return self(s), addr

    def readrequest(self, maxhdr = 0x10000, maxdata = 0x100000):
        headers     = self.readheaders(maxhdr)
        if not headers:
            self.close()
            return None
        request     = HTTPRequest.fromdata(headers)
        length      = request.getcontentlength()
        if length is not None:
            data    = self.readdata(length, maxdata)
            request.setdata(data)
        return request

    def writeresponse(  self,
                        code    = 200,
                        data    = None,
                        hdr     = None,
                        desc    = None,
                        version = None
                        ):
        resp = HTTPResponse.fromparams(code, desc, hdr, data, version)
        return self.write(resp)


class HTTPConstant:
    newline   = '\r\n'
    responses = {
        100: 'Continue',
        101: 'Switching Protocols',

        200: 'OK',
        201: 'Created',
        202: 'Accepted',
        203: 'Non-Authoritative Information',
        204: 'No Content',
        205: 'Reset Content',
        206: 'Partial Content',

        300: 'Multiple Choices',
        301: 'Moved Permanently',
        302: 'Found',
        303: 'See Other',
        304: 'Not Modified',
        305: 'Use Proxy',
        306: '(Unused)',
        307: 'Temporary Redirect',

        400: 'Bad Request',
        401: 'Unauthorized',
        402: 'Payment Required',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed',
        406: 'Not Acceptable',
        407: 'Proxy Authentication Required',
        408: 'Request Timeout',
        409: 'Conflict',
        410: 'Gone',
        411: 'Length Required',
        412: 'Precondition Failed',
        413: 'Request Entity Too Large',
        414: 'Request-URI Too Long',
        415: 'Unsupported Media Type',
        416: 'Requested Range Not Satisfiable',
        417: 'Expectation Failed',

        500: 'Internal Server Error',
        501: 'Not Implemented',
        502: 'Bad Gateway',
        503: 'Service Unavailable',
        504: 'Gateway Timeout',
        505: 'HTTP Version Not Supported',
    }

    @staticmethod
    def normalizenewlines(data):
        data = data.replace('\r','')
        data = data.replace('\n','\r\n')
        return data
