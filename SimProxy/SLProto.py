# Second Life simple protocol handler
# by Mario Vilas (mvilas at gmail.com)

import random
import xmlrpclib

try:
    from hashlib import md5
except ImportError, e:
    from md5 import md5

from SLTemplate import SLException
##from Logger import Log, loadLogFileSettings


class SLUri:
    HOME    = 'home'
    LAST    = 'last'
    def __init__(self, island, x, y, z):
        (self.island, self.x, self.y, self.z) = (island, x, y, z)
    def __str__(self):
        return '%s&%d&%d&%d' % (self.island, self.x, self.y, self.z)


class SLClient:

    def __init__(self, transport,
            login_uri = "https://login.agni.lindenlab.com/cgi-bin/login.cgi"):
        self.loginURI   = login_uri
        self.transport  = transport

    @staticmethod
    def randomMAC():
##        return '00:11:22:33:44:55'
        mac = ''
        for i in range(6):
            mac += chr(random.randint(0, 256))
        return md5(mac).hexdigest()

    def login(self,
        first_name,
        last_name,
        password,
        startLocation   = SLUri.HOME,
        passIsHash      = False,
    ):

        if passIsHash:
            passwd_hash     = '$1$%s' % password
        else:
            passwd_hash     = '$1$%s' % md5(password).hexdigest()

        if 'nt' in sys.builtin_module_names:
            platform = 'Win'
        elif 'posix' in sys.builtin_module_names:
            platform = 'Lnx'
        elif 'mac' in sys.builtin_module_names:
            platform = 'Mac'
        else:
            platform = 'Lnx'    # *shrug*

        options = (
            'inventory-root',
            'inventory-skeleton',
            'inventory-lib-root',
            'inventory-lib-owner',
            'inventory-skel-lib',
            'initial-outfit',
            'gestures',
            'event_categories',
            'event_notifications',
            'classified_categories',
            'buddy-list',
            'ui-config',
            'login-flags',
            'global-textures',
            )

        login_req = {
            'first'             : first_name,
            'last'              : last_name,
            'passwd'            : passwd_hash,
            'start'             : startLocation,
            'platform'          : platform,
            'mac'               : self.randomMAC(),
            'options'           : options,
            'version'           : '1.18.1.2',
            'viewer-digest'     : '488b2304-0456-c259-1433-ce30dbb49c28',
            'channel'           : 'Second Life Release',
            'id0'               : '',
            'agree_to_tos'      : 'true',
        }

        server      = xmlrpclib.ServerProxy(self.loginURI)
        login_resp  = server.login_to_simulator(login_req)

        if login_resp['login'] == 'false':
            raise SLException, \
                "Login failed, reason: %s" % login_resp['message']

        self.loginSettings      = login_resp
        self.sessionID          = login_resp['session_id']
        self.secureSessionID    = login_resp['secure_session_id']
        self.agentID            = login_resp['agent_id']

        circuit_code    = login_resp['circuit_code']
        sim_ip          = login_resp['sim_ip']
        sim_port        = login_resp['sim_port']
        self.transport.useCircuitCode(circuit_code, (sim_ip, sim_port))
