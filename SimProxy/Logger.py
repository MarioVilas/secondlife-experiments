# Simple text logger
# by Mario Vilas (mvilas at gmail.com)

import time
import threading
import xmlrpclib

__all__ = ["Log", "loadLogFileSettings"]


def loadLogFileSettings(cfg):
    section = 'Log'

    if cfg.has_option(section,                  'verbosity'):
        Log.log_level   = cfg.getint(section,   'verbosity')
    else:
        Log.log_level   = 1

##    Log.log_filter  = []
##    if cfg.has_option(section,                  'logXmlRpcFilter'):
##        log_filter      = cfg.get(section,      'logXmlRpcFilter')
##        log_filter      = log_filter.split(',')
##        for x in log_filter:
##            Log.log_filter.append( x.strip() )

    try:
        Log.log_file = open(cfg.get(section,    'logFile'), 'w+')
    except Exception, e:
        Log.log_file = None


class Logger:

    http_request_template = '''
---------------------------------------------
HTTP request from %(ip)s:%(port)d
 - %(method)s %(path)s %(version)s
 - Request headers:

%(headers)s
---------------------------------------------'''

    http_response_template = '''
---------------------------------------------
HTTP response to %(ip)s:%(port)d
 - %(version)s %(code)s %(text)s
 - Response headers:

%(headers)s
---------------------------------------------'''

    xmlrpc_request_template = '''
---------------------------------------------
XML-RPC request from %(ip)s:%(port)d
%(req_method)s

%(text_data)s
---------------------------------------------'''

    xmlrpc_response_template = '''
---------------------------------------------
XML-RPC response to %(ip)s:%(port)d

%(text_data)s
---------------------------------------------'''

    xmlrpc_response_template_fault = '''
---------------------------------------------
XML-RPC response fault %(faultCode)d:

%(faultString)s
---------------------------------------------'''

    xmlrpc_request_template_error = '''
---------------------------------------------
XML-RPC request could not be parsed:

%(xmlreq_raw)s
---------------------------------------------'''

    xmlrpc_response_template_error = '''
---------------------------------------------
XML-RPC response could not be parsed:

%(xmlresp_raw)s
---------------------------------------------'''

    log_level       = 0
    log_file        = None
    log_filter      = []

    log_lock = threading.RLock()

    def log(self, level, text):
        if self.log_level >= level:
            self.log_lock.acquire()
            text = '[%s] %s' % (time.asctime(), text)
            if self.log_file is not None:
                print text >> self.log_file
            else:
                print text
            self.log_lock.release()

    __call__ = log

    def logHTTPRequest(self, req, peerAddr):
        headers = req.getMessage().getHeadersData()
        method  = req.getMethod()
        path    = req.getPath()
        version = req.getVersion()
        ip,port = peerAddr
        self.log(3, self.http_request_template % vars())

    def logHTTPResponse(self, resp, peerAddr):
        headers = resp.getMessage().getHeadersData()
        version = resp.getVersion()
        code    = resp.getCode()
        text    = resp.getCodeText()
        ip,port = peerAddr
        self.log(3, self.http_response_template % vars())

    def xmlMakePretty(self, xml_data):
        text_data = ''
        for key in xml_data:
##            if key not in self.log_filter:
                text_data += '%s: %s\n' % (key, xml_data[key])
##            else:
##                text_data += '%s: *** NOT LOGGED ***\n' % key
        text_data = text_data[:len(text_data)-1]
        return text_data

    def logXMLRPCRequest(self, xmlreq_raw, peerAddr):
        ip,port = peerAddr
        try:
            xmlreq      = xmlrpclib.loads(xmlreq_raw)
            req_method  = xmlreq[1]
            req_data    = xmlreq[0][0]
        except Exception:
            self.log(2, self.xmlrpc_request_template_error % vars())
            return
        if type(req_data) == type({}):
            text_data = self.xmlMakePretty(req_data)
        else:
            text_data = repr(req_data)
        self.log(2, self.xmlrpc_request_template % vars())

    def logXMLRPCResponse(self, xmlresp_raw, peerAddr):
        ip,port = peerAddr
        try:
            xmlresp     = xmlrpclib.loads(xmlresp_raw)
            resp_data   = xmlresp[0][0]
        except xmlrpclib.Fault, f:
            faultCode   = f.faultCode
            faultString = f.faultString
            self.log(2, self.xmlrpc_response_template_fault % vars())
            return
        except Exception:
            self.log(2, self.xmlrpc_response_template_error % vars())
            return
        if type(resp_data) == type({}):
            text_data = self.xmlMakePretty(resp_data)
        else:
            text_data = repr(resp_data)
        self.log(2, self.xmlrpc_response_template % vars())

# singleton logger
Log = Logger()
