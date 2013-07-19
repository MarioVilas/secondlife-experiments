import types

import msgfilter
from msgfilter.MessageFilterBase import MessageFilterBase

class MessageFilterDispatcher:

    def __init__(self, proxy):
        self.proxy              = proxy
        self.slTemplate         = proxy.slTemplate
        self.allMessageNames    = proxy.slTemplate.byName.keys()
        self.load()

    def load(self):
        self.filters = {}
        modlist = msgfilter.__dict__.keys()
        modlist.sort()
        for modname in modlist:
            mod = getattr(msgfilter, modname)
            if type(mod) == types.ModuleType:
                clslist = mod.__dict__.keys()
                clslist.sort()
                for clsname in clslist:
                    cls = getattr(mod, clsname)
                    if hasattr(cls, '__bases__') and MessageFilterBase in cls.__bases__:
                        Log(1, 'Loaded filter %s from module %s' % (clsname, modname))
                        inst   = cls(self)
                        fnlist = inst.__dict__.keys()
                        fnlist.sort()
                        for fnname in fnlist:
                            fn = getattr(inst, fnname)
                            if hasattr(fn, '__call__') and fnname in self.allMessageNames:
                                Log(1, 'Added message %s in filter %s' % (fnname, clsname))
                                self.filters[fnname] = self.filters.get(fnname, [])
                                self.filters[fnname].append(fn)

    def run(self, proxy, isClient, *params):
        try:
            name = params[0].messageName
            for fn in self.filters.get(name, []):
                result = fn(proxy, isClient, *params)
                if result is not None:
                    params = result
                    if params[0].messageName != name:
                        self.run(proxy, isClient, *params)
                        break
            return result
        except Exception, e:
            raise                   # XXX
            return params
