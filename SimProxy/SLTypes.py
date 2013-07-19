# Second Life protocol data marshalling
# by Mario Vilas (mvilas at gmail.com)

from struct import pack, unpack

__all__ =   [
                "U8",
                "U16",
                "U32",
                "U64",
                "S8",
                "S16",
                "S32",
                "S64",
                "F32",
                "F64",
                "LLVector3d",
                "LLVector4d",
                "LLVector3",
                "LLVector4",
                "LLQuaternion",
                "BOOL",
                "LLUUID",
                "IPADDR",
                "IPPORT",
                "Fixed",
                "Variable",
            ]

# base class only, not a real data type
class SLType:
    def __init__(self):
        raise Exception, "You should not instantiate these objects!"

    @classmethod
    def decode(cls, data, offset):
        value = unpack(cls.fmt, data[offset:offset+cls.size])
        if len(value) == 1:
            value = value[0]
        return offset + cls.size, value

    @classmethod
    def encode(cls, value):
        if len(cls.fmt) <= 2:
            return pack(cls.fmt, value)
        else:
            return pack(cls.fmt, *value)

class U8(SLType):
    fmt  = 'B'
    size = 1

class U16(SLType):
    fmt  = '<H'
    size = 2

class U32(SLType):
    fmt  = '<L'
    size = 4

class U64(SLType):
    fmt  = '<Q'
    size = 8

class S8(U8):
    fmt  = 'b'

class S16(U16):
    fmt  = '<h'

class S32(U32):
    fmt  = '<l'

class S64(U64):
    fmt  = '<q'

class F32(U32):
    fmt  = '<f'

class F64(U64):
    fmt  = '<d'

class LLVector3d(SLType):
    fmt  = '<fff'
    size = 12

class LLVector4d(SLType):
    fmt  = '<ffff'
    size = 16

class LLVector3(LLVector3d):
    pass

class LLVector4(LLVector4d):
    pass

class LLQuaternion(LLVector4d):
    pass

class BOOL(SLType):
    size = 1

    @classmethod
    def decode(cls, data, offset):
        return offset + cls.size, bool(ord(data[offset]))

    @classmethod
    def encode(cls, value):
        return chr(bool(value))

class LLUUID(SLType):
    # 00000000-0000-0000-0000-000000000000
    size = 16

    @classmethod
    def decode(cls, data, offset):
        luuid_bin = data[offset:offset+16]
        s = ''
        for c in luuid_bin:
            s += hex(ord(c))[2:].zfill(2)
        for i in ( 8, 13, 18, 23 ):
            s = s[:i] + '-' + s[i:]
        return offset + cls.size, s

    @classmethod
    def encode(cls, value):
        value = value.replace('-', '')
        s = ''
        for i in range(0, len(value), 2):
            s += chr(int(value[i:i+2], 0x10))
        return s

class IPADDR(U32):

    @classmethod
    def decode(cls, data, offset):
        offset, ip = U32.decode(data, offset)
        ip = '%d.%d.%d.%d' % (
            (ip >>  0) & 0xff,
            (ip >>  8) & 0xff,
            (ip >> 16) & 0xff,
            (ip >> 24) & 0xff)
        return offset, ip

    @classmethod
    def encode(cls, value):
        ip = [int(x) for x in value.split('.')]
        return pack('4B',*ip)

class IPPORT(U16):
    pass

class Fixed(SLType):

    @classmethod
    def decode(cls, data, offset, size):
        chunk = data[offset:offset+size]
        missing = size - len(chunk)
        if missing:
            raise Exception, "Missing %i bytes in Fixed parameter" % missing
        return offset + size, chunk

    @classmethod
    def encode(cls, value, size):
        if size != len(value):
            raise Exception, "Bad Fixed size: %r" % size
        v = value[0:size]
        p = '\0' * (size - len(v))
        return p + v

class Variable(SLType):

    @classmethod
    def decode(cls, data, offset, size):
        if   size == 1:
            offset, length = U8.decode(data, offset)
        elif size == 2:
            offset, length = U16.decode(data, offset)
        elif size == 4:
            offset, length = U32.decode(data, offset)
        else:
            raise Exception, "Bad Variable size: %r" % size
        return Fixed.decode(data, offset, length)

    @classmethod
    def encode(cls, value, size):
        value  = str(value)
        length = long(len(value))
        if size == 1:
            return U8.encode(length)  + value
        if size == 2:
            return U16.encode(length) + value
        if size == 4:
            return U32.encode(length) + value
        raise Exception, "Invalid Variable size: %r" % size
