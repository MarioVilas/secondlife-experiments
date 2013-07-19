# Config file reader
# by Mario Vilas (mvilas at gmail.com)

import types
import socket
import ConfigParser

class Config(ConfigParser.SafeConfigParser):

    def getipaddr(self, section, option):
        value = self.get(section, option)
        try:
            value = socket.gethostbyname(value)
        except socket.error, e:
            pass
        return value

    def getlist(self, section, option, allow_empty=False):
        value = self.get(section, option)
        value = value.replace(' ','').split(',')
        if not allow_empty:
            while '' in value: value.remove('')
        return value

    def getintlist(self, section, option):
        value = self.getlist(section, option)
        value = [ int(x) for x in value ]
        return value

    def getbooleanlist(self, section, option):
        value = self.getlist(section, option)
        value = [ bool(x) for x in value ]
        return value

    def setint(self, section, option, value):
        self.set(section, option, str(value))

    def setboolean(self, section, option, value):
        self.set(section, option, str(bool(value)))

    def setlist(self, section, option, value):
        value = [ str(x) for x in value ]
        value = ','.join(value)
        self.set(section, option, value)

    getstring       = ConfigParser.SafeConfigParser.get
    setstring       = ConfigParser.SafeConfigParser.set
    getbool         = ConfigParser.SafeConfigParser.getboolean
    getinteger      = ConfigParser.SafeConfigParser.getint

    getstringlist   = getlist
    setstringlist   = setlist
    setipaddr       = setstring
    setintlist      = setlist
    getintegerlist  = getintlist
    setintegerlist  = setintlist
    setboollist     = setlist
    setbooleanlist  = setboollist
    setbool         = setboolean
    setinteger      = setint

    def load(self, instance, settings):
        for section, properties in settings.iteritems():
            for option, optiontype in properties.iteritems():
                if not optiontype:
                    optiontype = 'string'
                try:
                    reader = getattr(self, 'get%s' % optiontype)
                except Exception, e:
                    raise TypeError, "Invalid option type: %s" % optiontype
                try:
                    value = reader(section, option)
                    setattr(instance, option, value)
                except ConfigParser.Error, e:
                    if not hasattr(instance, option):
                        raise

    def store(self, instance, settings):
        raise Exception, "XXX TO DO"
