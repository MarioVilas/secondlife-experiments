import os.path
import time

# name.cache

## version	2
## 973cfc2a-5b14-753a-9789-763c3016d5cd	1184207382	khanu	Ariantho
## 73d9d2f1-c6f1-7e52-b132-321efda6e478	1184207378	Saiets	Rasmuson

class LUUID:
    # 00000000-0000-0000-0000-000000000000
    # 8        4    4    4    12

    UUID_STR_LENGTH = 37

    def __init__(self, id_string):
        if len(id_string) != (LUUID.UUID_STR_LENGTH - 1):
            raise Exception, "Bad UUID string %r" % id_string
        id_string = id_string.replace('-', '')
        id_binary = ''
        for i in range(0, len(id_string), 2):
            c = int(id_string[i:i+2], 0x10)
            c ^= 0x33
            id_binary += chr(c)
        self.id_binary = id_binary

    def __repr__(self):
        # true UUID value
        i = 0
        s = ''
        for c in self.id_binary:
            s += hex(ord(c))[2:].zfill(2)
            if i in [ 4, 6, 8, 10 ]:
                s += '-'
            i += 1
        return s

    def __str__(self):
        # xored against 0x33 to store in name.cache file
        i = 0
        s = ''
        for c in self.id_binary:
            s += hex(ord(c) ^ 0x33)[2:].zfill(2)
            if i in [ 4, 6, 8, 10 ]:
                s += '-'
            i += 1
        return s

class NameCacheEntry:

    def __init__(self, text):
        (self.id_string, self.create_time, self.firstname, self.lastname) = \
            text.strip(' \t\r\n').split('\t')
        self.uuid = \
            LUUID(self.id_string)
        self.create_time = \
            float(self.create_time)
        self.create_time_ascii = \
            time.asctime(time.gmtime(self.create_time))

    def __str__(self):
        return "%s\t%i\t%s\t%s\n" % \
            (self.id_string, self.create_time, self.firstname, self.lastname)

    def __repr__(self):
        s = (
            "First name: %s\n"
            "Last name:  %s\n"
            "Cached on:  %s\n"
            "UUID:       %s\n"
        ) % (self.firstname, self.lastname, self.create_time_ascii, self.uuid)
        return s

class NameCache:

    CN_FILE_VERSION = 2

    sl_path = r'C:\Documents and Settings\Mario\Datos de Programa\SecondLife'

    def __init__(self):
        self.names = []
        f = open(os.path.join(self.sl_path, r'cache\name.cache'), 'r')
        s = f.readline()
        (version_string, version) = s.strip(' \t\r\n').split('\t')
        if version_string != 'version':
            raise Exception, "Bad SL name cache file"
        if version != str(NameCache.CN_FILE_VERSION):
            raise Exception, "Unsupported SL name cache file version"
        for s in f:
            e = NameCacheEntry(s)
            self.names.append(e)

    def __str__(self):
        s = 'version\t%i\n' % NameCache.CN_FILE_VERSION
        for e in self.names:
            s += str(e)
        return s

    def __repr__(self):
        s = "Second Life name cache:\n\n"
        for e in self.names:
            s += repr(e)
            s += "\n"
        return s

    def __iter__(self):
        return self.names.__iter__()

    def __len__(self):
        return len(self.names)

    def __getitem__(self, index):
        return self.names[index]

    def __setitem__(self, index, entry):
        self.names[index] = entry

if __name__ == '__main__':
    n = NameCache()
    print repr(n)   # pretty text showing real UUIDs
    #print str(n)    # actual names.cache file contents
