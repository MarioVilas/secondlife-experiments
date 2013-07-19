# Second Life login proxy
# by Mario Vilas (mvilas at gmail.com)

import sys
import os.path
import ConfigParser
import socket
import xmlrpclib

from XMLRPCServer import XMLRPCServer
from Logger import Log, loadLogFileSettings


class LoginProxy:

    def __init__(self, configFilename):
        self.cfg = ConfigParser.SafeConfigParser()
        self.cfg.read(filename)
        loadLogFileSettings(self.cfg)

        section             = 'LoginProxy'
        self.loginURI       = self.cfg.get(section,        'loginURI')
        self.logPasswords   = self.cfg.getboolean(section, 'logPasswords')

        try:
            self.redirToSimHost = self.cfg.get(section,    'redirToSimHost')
            self.redirToSimPort = self.cfg.get(section,    'redirToSimPort')
        except Exception, e:
            self.redirToSimHost = None
            self.redirToSimPort = None

        try:
            self.simProxyURI    = self.cfg.get(section,    'simProxyURI')
        except Exception, e:
            self.simProxyURI    = None

        try:
            self.redirToSimHost = socket.gethostbyname(self.redirToSimHost)
        except Exception, e:
            pass

    def start(self):
        self.server = XMLRPCServer(self, 'LoginProxy')
        self.server.register_function(self.login_to_simulator)
        self.server.start()
        Log(1, "LoginProxy loaded successfully")

    def kill(self):
        Log(1, "LoginProxy shut down")

    def login_to_simulator(self, *arg_list):
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
            Log(1, "User %s %s logging in" % first, last)

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
                Log(1, "User %s %s logged in" % first, last)
        else:
            Log(1, "User %s %s failed to log in: %s" % first, last, message)

        # Redirect to our Sim
        if login == 'true':
            orig_sim_ip, orig_sim_port  = sim_ip, sim_port
            login_resp['message']       = 'All your base are belong to us'
            if self.redirToSimHost:
                sim_ip                  = self.redirToSimHost
                sim_port                = self.redirToSimPort
            if self.simProxyURI:
                Log(1, "Requesting new Sim from SimProxy %s" % self.simProxyURI)
                try:
                    simProxy            = xmlrpclib.ServerProxy(self.simProxyURI)
                    sim_ip, sim_port    = simProxy.newSim( (orig_sim_ip, orig_sim_port) )
                except Exception, e:
                    Log(1, "Error from SimProxy: %s" % str(e))
            if (orig_sim_ip, orig_sim_port) != (sim_ip, sim_port):
                login_resp['sim_ip']    = sim_ip
                login_resp['sim_port']  = sim_port
                Log(1,
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
                Log(1, "User %s %s connected to Sim %s:%d" % \
                       (first, last, sim_ip, sim_port)
                    )

        # Send response back to the client
        return login_resp


if __name__ == "__main__":
    scriptname  = os.path.basename(sys.argv[0])
    filename    = os.path.splitext(scriptname)[0] + '.cfg'
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
