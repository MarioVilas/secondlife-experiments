# Second Life HTTP transport encoder and decoder
# by Mario Vilas (mvilas at gmail.com)

#------------------------------------------------------------------------------
# Imports

import types
import base64
from xml.etree import ElementTree

#------------------------------------------------------------------------------
# Exports

__all__ = ["LLSD"]

#------------------------------------------------------------------------------
# User interface

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
        children = xml.getchildren()
        if xml.tag != 'llsd' or len(children) != 1:
            raise Exception, "Bad llsd data"
        return self.__build(children[0])

    @classmethod
    def dump(self, llsd):
        xml  = self.tostring(llsd)
        open(file, 'w').write(xml)

    @classmethod
    def tostring(self, llsd):
        return '<llsd>%s</llsd>' % self.__marshall(llsd)

    @classmethod
    def totree(self, llsd):
        xml  = self.tostring(llsd)
        tree = ElementTree.fromstring(xml)
        return tree

    fromfile    = parse
    tofile      = dump

#------------------------------------------------------------------------------
# Internally used worker methods and classes

    class LLElement(str):

        def set_llsd(self, name, props = {}):
            self.__name     = name
            self.__props    = props

        def get_llsd(self):
            return self.__name, str(self), self.__props

    @classmethod
    def __marshall(self, data):
        classname       = self.__name__
        typename        = data.__class__.__name__
        marshaller_name = '_%s__marshall_%s' % (classname, typename)
        if not hasattr(self, marshaller_name):
            raise KeyError, marshaller_name
##            marshaller  = self.__marshall_string
        else:
            marshaller  = getattr(self, marshaller_name)
        return marshaller(data)

    @classmethod
    def __build(self, element):
        classname       = self.__name__
        typename        = element.tag
        builder_name    = '_%s__build_%s' % (classname, typename)
        if not hasattr(self, builder_name):
            raise KeyError, builder_name
##            builder     = self.__build_string
        else:
            builder     = getattr(self, builder_name)
        return builder(element)

    @staticmethod
    def __properties(element):
        props = {}
        for key, value in element.items():
            props[key] = value
        return props

    @staticmethod
    def __tag(name, value, props = {}):
        value = str(value)
        props = ''.join( [ (' %s="%s"' % p) for p in props.iteritems() ] )
        if value or props:
            return '<%(name)s%(props)s>%(value)s</%(name)s>' % vars()
        return '<%(name)s />' % vars()

#------------------------------------------------------------------------------
# Marshallers

    @classmethod
    def __marshall_dict(self, data):
        m    = ''
        tags = data.keys()
        tags.sort()
        for key in tags:
            value = data[key]
            m    += self.__tag('key', key) + self.__marshall(value)
        return self.__tag('map', m)

    @classmethod
    def __marshall_list(self, data):
        children = ''.join([ self.__marshall(element) for element in data ])
        return self.__tag('array', children)

    __marshall_tuple = __marshall_list

    @classmethod
    def __marshall_NoneType(self, data):
        return self.__tag('undef', '')

    @classmethod
    def __marshall_bool(self, data):
        return self.__tag('boolean', int(bool(data)))

    # XXX python only supports floats, we need doubles
##    @classmethod
##    def __marshall_float(self, data):
##        return self.__tag('real', repr(data))

    @classmethod
    def __marshall_int(self, data):
        return self.__tag('integer', data)

    __marshall_long = __marshall_int

    @classmethod
    def __marshall_str(self, data):
        return self.__tag('string', data)

    @classmethod
    def __marshall_LLElement(self, data):
        name, value, props = data.get_llsd()
        if name == 'binary':
            if props.get('encoding', '') == 'base64':
                value = base64.encodestring(str(value))
##                value = value.replace('\n', '')
##                value = value.replace('\r', '')
        return self.__tag(name, value, props)

#------------------------------------------------------------------------------
# Builders

    @classmethod
    def __build_map(self, element):
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
    def __build_array(self, element):
        return [ self.__build(child) for child in element.getchildren() ]

    @staticmethod
    def __build_undef(element):
        return None

    @staticmethod
    def __build_boolean(element):
        return bool(int(element.text))

    # XXX python only supports floats, we need doubles
    # so we'll represent reals using LLElement instead
##    @staticmethod
##    def __build_real(element):
##        return float(element.text)
    @classmethod
    def __build_real(self, element):
        result = self.LLElement(element.text)
        result.set_llsd('real')
        return result

    @staticmethod
    def __build_integer(element):
        try:
            return int(element.text)
        except ValueError:
            return long(element.text)

    @staticmethod
    def __build_string(element):
        return element.text

    @classmethod
    def __build_uuid(self, element):
        result = self.LLElement(element.text)
        result.set_llsd('uuid')
        return result

    @classmethod
    def __build_script(self, element):
        result = self.LLElement(element.text)
        result.set_llsd('script')
        return result

    @classmethod
    def __build_binary(self, element):
        props = self.__properties(element)
        if not props.has_key('encoding'):
            data = str(element.text)
        elif props['encoding'] == 'base64':
            data = base64.decodestring(str(element.text))
        else:
            raise ValueError, "Unknown encoding: %r" % props['encoding']
        result = self.LLElement(data)
        result.set_llsd('binary', props)
        return result

#------------------------------------------------------------------------------
# Test code
if __name__ == '__main__':
    import difflib
    data = open('httpcap.txt','r').read()
    c = 0
    btag = '<llsd>'
    etag = '</llsd>'
    b = data.find(btag)
    while b >= 0:
        e = data.find(etag, b) + len(etag)
        xml = data[b:e]
        llsd = LLSD.fromstring(xml)
        xml_2 = LLSD.tostring(llsd)
        xml = xml.replace('\r','')
        xml = xml.replace('\n','')
        xml_2 = xml_2.replace('\r','')
        xml_2 = xml_2.replace('\n','')
##        if len(xml) != len(xml_2):
        if xml != xml_2:
            print
            print xml
            print
            print llsd
            print
            print xml_2
            print
            xml = xml.replace('>','>\n')
            xml_2 = xml_2.replace('>','>\n')
            open('1.txt','w+').write(xml)
            open('2.txt','w+').write(xml_2)
##            for x in difflib.unified_diff([xml], [xml_2], lineterm='\n'):
##                print x
            print
            raise Exception, 'Failed on number %d' % c
        c += 1
        b = data.find(btag, e)
