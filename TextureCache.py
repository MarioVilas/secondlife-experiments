from struct import unpack
from time import ctime
from SLChat import bytes2uuid
from sys import argv

CACHE_BASE = '/home/saiets/.secondlife/cache'
def createJP2(uuid, index):
    pass

def main():
    TEXTURE_CACHE_ENTRY_SIZE = 600
    BASE_PATH = CACHE_BASE
    ENTRIES   = BASE_PATH + 'texture.entries'
    CACHE     = BASE_PATH + 'texture.cache'

    entries = open(ENTRIES,'rb')

    version = unpack('f', entries.read(4))[0]
    count   = unpack('L', entries.read(4))[0]

    print 'Entries Cache Version: %f' % version
    print 'Number of entries: %d' % count

    # texture.entries
    # read entries. each entry is just (uuid, size, date).
    # The order in the file (index) is used to access the texture.cache file

    uuids = {}

    for uuid in argv[1:]:
        uuids[uuid] = None

    found = False
    for i in range(count):
        uuid, size, date = unpack('16slL', entries.read(16+4+4))
        uuid = bytes2uuid(uuid)
        if not uuids:
           print '[%d] %s %d %s' % (i, uuid, size, ctime(date))
        else:
           if uuids.has_key(uuid):
              uuids[uuid] = (i, uuid, size, date)
              print '[%d] %s %d %s' % (i, uuid, size, ctime(date))
              found = True

    entries.close()

    if not found:
       return

    # texture.cache
    cache = open(CACHE, 'rb')

    for uuid in uuids:
        if uuids[uuid]:
           i, _, size, date = uuids[uuid]
        cache.seek(i * TEXTURE_CACHE_ENTRY_SIZE)
        d = cache.read(TEXTURE_CACHE_ENTRY_SIZE)

        output = open('%s.j2c' % uuid,'wb')
        output.write(d)

        output.write(open('%s/textures/%s/%s' % (BASE_PATH, uuid[0], uuid)).read())
        output.close()

if __name__ == '__main__':
   main()
