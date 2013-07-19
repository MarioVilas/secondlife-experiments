# Second Life HTTP transport encoder and decoder
# by Mario Vilas (mvilas at gmail.com)

import base64
from xml.etree import ElementTree

__all__ = ["LLSD"]

class LLSD:

    @classmethod
    def parse(self, filename):
        return self.fromtree( ElementTree.parse(filename) )

    @classmethod
    def fromstring(self, stringdata):
        return self.fromtree( ElementTree.fromstring(stringdata) )

    @classmethod
    def fromtree(self, xml):
        if hasattr(xml, 'getroot'):
            xml = xml.getroot()
        if xml.tag != 'llsd':
            raise Exception, "Bad llsd data"
        return tuple(self._array(xml))

    @classmethod
    def __build(self, element):
        builder_name = '_%s' % element.tag
        if not hasattr(self, builder_name):
            builder = self._string
##            raise KeyError, "Unknown type: %r" % builder_name
        builder = getattr(self, builder_name)
        return builder(element)

    @staticmethod
    def __properties(element):
        props = {}
        for key, value in element.items():
            props[key] = value
        return props

    @classmethod
    def _map(self, element):
        data     = {}
        children = element.getchildren()
        if (len(children) & 1) != 0:
            raise IndexError, "Incomplete map"
        for index in range(0, len(children), 2):
            key     = children[index]
            value   = children[index + 1]
            if key.tag != 'key':
                raise ValueError, "Bad map data"
            data[key.text] = self.__build(value)
        return data

    @classmethod
    def _array(self, element):
        return [ self.__build(child) for child in element.getchildren() ]

    @staticmethod
    def _undef(element):
        return None

    @staticmethod
    def _boolean(element):
        return bool(element.text)

    @staticmethod
    def _real(element):
        return float(element.text)

    @staticmethod
    def _integer(element):
        try:
            return int(element.text)
        except ValueError:
            return long(element.text)

    @classmethod
    def _binary(self, element):
        props = self.__properties(element)
        if not props.has_key('encoding'):
            return element.text
        if props['encoding'] == 'base64':
            return base64.decodestring(element.text)
        raise ValueError, "Unknown encoding: %r" % props['encoding']

    @staticmethod
    def _string(element):
        return element.text

    _uuid   = _string
    _script = _string


if __name__ == '__main__':
    import os
    data = open('CapProxy.log','r').read()
    c = 0
    btag = '<llsd>'
    etag = '</llsd>'
    mbtag = '<key>message</key><string>'
    metag = '</string>'
    b = data.find(btag)
    mnames = {}
    while b >= 0:
        e = data.find(etag, b) + len(etag)
        xml = data[b:e]
        bm = xml.rfind(mbtag)
        em = xml.find(metag, bm)
        if bm >= 0 and em >= 0 and em >= bm:
            bm = bm + len(mbtag)
            m = xml[bm:em]
            mnames[m] = None
        else:
            m = 'DATA'
####        name = './httpcap/%.8d_%s.xml' % (c, m)
##        name = './httpcap/%s_%d.xml' % (m, c)
##        print
##        print name
##        decoded = LLSD.fromstring(xml)
####        print decoded
##        print
##        open(name, 'w').write(xml)
        c += 1
        b = data.find(btag, e)
    print mnames.keys()
