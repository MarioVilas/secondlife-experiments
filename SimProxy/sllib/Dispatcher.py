# Generic plugin dispatcher
# by Mario Vilas (mvilas at gmail.com)

import types
import os.path

from Logger import Log

__all__ = ["Dispatcher"]

class Dispatcher:

    def __init__(self, filterPackage, filterClass):
        self.__filterPackage = filterPackage
        self.__filterClass   = filterClass
        self.load()

    def load(self):
        self.filters = {}
        package = self.__filterPackage
        modlist = dir(package)
        modlist.sort()
        for modname in modlist:
            self.loadModule(package, modname)

    def loadModule(self, package, modname):
        mod = getattr(package, modname)
        if not modname.startswith('_'):
            Log(3, "Found module %s" % modname)
            if type(mod) == types.ModuleType:
                clslist = dir(mod)
                clslist.sort()
                for clsname in clslist:
                    self.loadClass(mod, clsname)

    def loadClass(self, mod, clsname):
        if not clsname.startswith('_'):
            Log(3, "Found class %s" % clsname)
            cls = getattr(mod, clsname)
            if hasattr(cls, '__bases__') and self.__filterClass in cls.__bases__:
                pyfile = os.path.basename(mod.__file__)
                Log(1, 'Loaded filter %s from %s' % (clsname, pyfile))
                inst   = cls(self.main)
                fnlist = dir(inst)
                fnlist.sort()
                for fnname in fnlist:
                    self.loadMethod(inst, fnname)

    def loadMethod(self, inst, fnname):
        if not fnname.startswith('_'):
            fn = getattr(inst, fnname)
            if hasattr(fn, '__call__'):
                Log(3, "Found method %s" % fnname)
                if self.main.pktCapture.slTemplate.byName.has_key(fnname):
                    self.filters[fnname] = self.filters.get(fnname, [])
                    self.filters[fnname].append(fn)
                    Log(2, 'Added message %s' % fnname)

    def getFilters(self, name):
        return self.filters.get(name, [])
