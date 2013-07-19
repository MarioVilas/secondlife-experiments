# Second Life login proxy
# by Mario Vilas (mvilas at gmail.com)

import sys
import os.path
import socket
import xmlrpclib
import urlparse

from sllib.Logger import Log
from sllib.Config import Config
from sllib.XMLRPCServer import XMLRPCServer

from CapProxy import CapProxyURIMangler


class LoginProxy:
    section = 'LoginProxy'
    uriSettings      = {
                        'URI': {
                                'loginProxyURI' : 'string',
                                'capProxyURI'   : 'string',
                                'simProxyURI'   : 'string',
                               },
                       }
    loginProxySettings  = {
                            'LoginProxy' : {
                                            'loginURI'      : 'string',
                                            'logPasswords'  : 'bool',
                                            'useSimProxy'   : 'bool',
                                            'redirToSimHost': 'ipaddr',
                                            'redirToSimPort': 'int',
                                            },
                          }


    def __init__(self, configFilename):
        self.cfg = Config()
        self.cfg.read(filename)

    def start(self):
        Log.loadSettings(self.cfg, self.section)

        self.simProxyURI    = None
        self.capProxyURI    = None
        self.loginProxyURI  = None
        self.cfg.load(self, self.uriSettings)

        self.loginURI       = 'https://login.agni.lindenlab.com/cgi-bin/login.cgi'
        self.logPasswords   = False
        self.useSimProxy    = False
        self.redirToSimHost = None
        self.redirToSimPort = None
        self.cfg.load(self, self.loginProxySettings)

        if self.capProxyURI:
            self.mangler    = CapProxyURIMangler(self.capProxyURI, remote = True)

        self.server = XMLRPCServer(self, self.section)
        self.server.register_function(self.login_to_simulator)
##        self.server.register_instance(self)
        self.server.start()
        Log(1, "LoginProxy loaded successfully")

    def kill(self):
        Log(1, "LoginProxy shut down")

##    def _dispatch(self, method, params):
##        print repr(method)
##        print repr(params)
##        if method == u'login_to_simulator':
##            try:
##                result = self.login_to_simulator(*params)
##                print repr(result)
##                return result
##            except Exception, e:
##                Log.logException()
##                raise

    def login_to_simulator(self, *arg_list):
        try:
            login_req = arg_list[0]     # should be a dictionary

            # Log login attempt
            first   = login_req['first']
            last    = login_req['last']
            if self.logPasswords:
                passwd      = login_req['passwd']
                if passwd.startswith('$1$'):
                    passwd  = passwd[3:]
                Log(1,
                    "User %s %s logging in\n"
                    "\thash: %s"
                    "" % (first, last, passwd)
                    )
            else:
                Log(1, "User %s %s logging in" % (first, last))

            # Send request to real login server
            server      = xmlrpclib.ServerProxy(self.loginURI)
            login_resp  = server.login_to_simulator(login_req)

            # Parse response
            login                       = login_resp['login']
            message                     = login_resp['message']
            if   login == 'false':
                reason                  = login_resp['reason']
            elif login == 'true':
                sim_ip                  = login_resp['sim_ip']
                sim_port                = login_resp['sim_port']
                seed_capability         = login_resp['seed_capability']

            # Log login success or failure
            if login == 'true':
    ##            first_name              = login_resp['first_name']
    ##            last_name               = login_resp['last_name']
                if self.logPasswords:
                    session_id          = login_resp['session_id']
                    secure_session_id   = login_resp['secure_session_id']
                    Log(1,
                        "User %s %s successfully logged in\n"
                        "\tsid:  %s\n"
                        "\tssid: %s" % \
                            (first, last, session_id, secure_session_id)
                        )
                else:
                    Log(1, "User %s %s logged in" % (first, last))
            else:
                message = message.replace('\n', ' ')
                message = message.replace('\r', '')
                Log(1, "User %s %s failed to log in: %s" % (first, last, message))

            # Modify the seed capabilities URI
            if login == 'true' and self.capProxyURI:
                Log(3, "Seed capability URI found: %s" % seed_capability)
                new_seed_capability = self.mangler.mangle(seed_capability)
                login_resp['seed_capability'] = new_seed_capability
                Log(2, "Forcing seed capability URI: %s" % new_seed_capability)

            # Redirect to our Sim
            if login == 'true':
                Log(3, "Sim %s:%d discovered" % (sim_ip, sim_port))
                orig_sim_ip, orig_sim_port  = sim_ip, sim_port
                if self.redirToSimHost:
                    sim_ip                  = self.redirToSimHost
                    sim_port                = self.redirToSimPort
                if self.useSimProxy and self.simProxyURI:
                    Log(3, "Requesting new Sim from SimProxy %s" % self.simProxyURI)
                    try:
                        simProxy            = xmlrpclib.ServerProxy(self.simProxyURI)
                        sim_ip, sim_port    = simProxy.newSim( (orig_sim_ip, orig_sim_port) )
                    except Exception, e:
                        Log.logException()
                if (orig_sim_ip, orig_sim_port) != (sim_ip, sim_port):
                    login_resp['sim_ip']    = sim_ip
                    login_resp['sim_port']  = sim_port
                    login_resp['message']   = 'All your base are belong to us'
                    Log(2,
                        "Forcing Sim redirection %s:%d -> %s:%d for %s %s" % \
                        (
                            orig_sim_ip,
                            orig_sim_port,
                            sim_ip,
                            sim_port,
                            first,
                            last
                        )
                        )
                else:
                    Log(2, "User %s %s connected to Sim %s:%d" % \
                           (first, last, sim_ip, sim_port)
                        )

            # Send response back to the client
            return login_resp

        except Exception, e:
            Log.logException()
            raise


if __name__ == "__main__":
    scriptname  = os.path.basename(sys.argv[0])
##    filename    = os.path.splitext(scriptname)[0] + '.cfg'
    filename = 'SimProxy.cfg'
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ('-h', '-help', '--help'):
            print "%s [alternate config file]" % scriptname
            exit()
        filename = sys.argv[1]

    print "LoginProxy started, hit Enter to stop..."
    lp = LoginProxy(filename)
    lp.start()
    raw_input()
    lp.kill()
