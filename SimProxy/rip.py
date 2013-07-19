# Capture file ripper
# by Mario Vilas (mvilas at gmail.com)

import types
import string
import sys
import os.path
import urlparse

from sllib.SLPacket import SLPacket
from sllib.Config import Config
from sllib.Logger import Log

from SimProxy import PacketCapture

###############################################################################

class Ripper:
    outfolder        = './'
    outfolder_failed = './failed/'

    objtype     = 'other'
    ext         = ''

    objects     = 0
    meshes      = 0
    textures    = 0
    other       = 0

    @classmethod
    def __write(self, filename, data):
        open(filename, 'wb').write(data)
        if self.objtype:
            counter = getattr(Ripper, self.objtype)
            counter = counter + 1
            setattr(Ripper, self.objtype, counter)

    @classmethod
    def write(self, uuid, data):
        filename = os.path.join(self.outfolder, uuid + self.ext)
        self.__write(filename, data)

    @classmethod
    def writeFailed(self, uuid, data):
        filename = os.path.join(self.outfolder_failed, uuid + self.ext)
        self.__write(filename, data)

    @classmethod
    def rip(self, message):
        pass

    @classmethod
    def finalize(self):
        pass

class RipperCollection:

    class ImageData(Ripper):
##        ext         = '.j2c'
        ext         = '.jp2'
        objtype     = 'textures'

        @classmethod
        def rip(self, message):
            uuid    = message['ImageID']['ID']
            codec   = message['ImageID']['Codec']
            size    = message['ImageID']['Size']
            count   = message['ImageID']['Packets']
            data    = message['ImageData']['Data']
            self.newImage(uuid, codec, size, count)
            self.addImagePacket(uuid, 0, data)

        known = {}

        class Image:
            def __init__(self, codec = None, size = 0, count = 0):
                self.codec   = codec
                self.size    = size
                self.count   = count
                self.packet  = {}

        @classmethod
        def newImage(self, uuid, codec, size, count):
            if not self.known.has_key(uuid):
                self.known[uuid] = self.Image(codec, size, count)
            else:
                self.known[uuid].codec      = codec
                self.known[uuid].size       = size
                self.known[uuid].count      = count

        @classmethod
        def addImagePacket(self, uuid, number, data):
            if not self.known.has_key(uuid):
                self.known[uuid] = self.Image()
            image = self.known[uuid]
            image.packet[number] = data
            if image.count == len(image.packet.keys()):
                self.saveImage(uuid)

        @classmethod
        def saveImage(self, uuid):
            image = self.known[uuid]
            pktlist = []
            indexes = image.packet.keys()
            indexes.sort()
            for index in indexes:
                pktlist.append( image.packet[index] )
            data = string.join(pktlist, '')
            if len(data) != image.size:
                self.writeFailed(uuid, data)
                raise Exception, "Image size doesn't match received data"
            self.write(uuid, data)
            del self.known[uuid]

        @classmethod
        def finalize(self):
            for uuid in self.known.keys():
                try:
                    self.saveImage(uuid)
                except Exception, e:
                    pass
##                    print "Warning: image %s: %s" % (uuid, str(e))

    class ImagePacket(ImageData):

        @classmethod
        def rip(self, message):
            uuid    = message['ImageID']['ID']
            number  = message['ImageID']['Packet']
            data    = message['ImageData']['Data']
            self.__bases__[0].addImagePacket(uuid, number, data)

##    class LayerData(Ripper):
##        pass

    class ObjectUpdate(Ripper):
        ext     = ''
        objtype = ''
        
        @classmethod
        def rip(self, message):
            for objectdata in message['ObjectData']:
                uuid    = objectdata['FullID']
                url     = objectdata['MediaURL']
                if '\x00' in url:
                    url = url[:url.find('\x00')]
                if url:
                    favicon = 'http://' + urlparse.urlsplit(url)[1] + '/favicon.ico'
                    urlfile = '[InternetShortcut]\r\nURL=%s\r\nIconFile=%s\r\nIconIndex=1\r\n'
                    urlfile = urlfile % (url, favicon)
                    self.write(uuid + '.url', urlfile)
                    Ripper.other += 1
                # XXX to do...

    class ObjectUpdateCompressed(Ripper):
        pass

    class ImprovedTerseObjectUpdate(Ripper):
        pass

##    class ObjectProperties(Ripper):
##        pass

##    class ObjectPropertiesFamily(Ripper):
##        pass

    """
ObjectAdd
ObjectScale
ObjectFlagUpdate
ObjectImage
ObjectMaterial
ObjectShape
ObjectExtraParams
ObjectGroup
ObjectName
ObjectDescription
ObjectCategory
    """

##    class AvatarTextureUpdate(Ripper):
##        pass

##    class AvatarAnimation(Ripper):
##        pass

##    class AvatarAppearance(Ripper):
##        pass

##    class AvatarPropertiesReply(Ripper):
##        pass

##    class AvatarPropertiesUpdate(Ripper):
##        pass

    class ParcelProperties(Ripper):
        ext     = '.url'
        objtype = 'other'

        @classmethod
        def rip(self, message):
            name    = message['ParcelData']['Name']
            media   = message['ParcelData']['MediaURL']
            if '\x00' in name:
                name  = name[:name.find('\x00')]
            if '\x00' in media:
                media = media[:media.find('\x00')]
            if media:
                favicon = 'http://' + urlparse.urlsplit(media)[1] + '/favicon.ico'
                urlfile = '[InternetShortcut]\r\nURL=%s\r\nIconFile=%s\r\nIconIndex=1\r\n'
                urlfile = urlfile % (media, favicon)
                self.write(name, urlfile)

##    class ParcelOverlay(Ripper):
##        pass

###############################################################################

def rip(pc, binfilename = 'capture.bin', outfolder = './rip'):
    capture     = open(binfilename, 'rb').read()
    offset      = 0
    pktcount    = -1
    pktsuccess  = 0
    pktfailed   = 0

    Ripper.objects      = 0
    Ripper.meshes       = 0
    Ripper.textures     = 0
    Ripper.other        = 0

    outfolder_failed = os.path.join(outfolder, 'failed')
    if not os.path.exists(outfolder_failed):
        os.makedirs(outfolder_failed)
    Ripper.outfolder = outfolder
    Ripper.outfolder_failed = outfolder_failed

    while( (len(capture) - offset) != 0 ):
        pktcount        = pktcount + 1
        offset, entry   = pc.unpack(capture, offset)
        try:
            rawPacket   = entry[len(entry)-1]
            packet      = SLPacket(rawPacket, pc.slTemplate)
            packet.decode()
        except Exception, e:
##            print "Exception while decoding packet %d: %s" % (pktcount, str(e))
##            print sp.dump(*entry)
            pktfailed   = pktfailed + 1
            continue

        if hasattr(RipperCollection, packet.messageName):
            ripper = getattr(RipperCollection, packet.messageName)
            try:
                ripper.rip(packet.decodedData)
            except Exception, e:
                raise
##                print "Exception while ripping packet %d: %s" % (pktcount, str(e))
##                print sp.dump(*entry)
                pktfailed   = pktfailed + 1
                continue
            pktsuccess      = pktsuccess + 1

    for ripper in RipperCollection.__dict__.values():
        if type(ripper) == types.ClassType:
            ripper.finalize()

    objects     = Ripper.objects
    meshes      = Ripper.meshes
    textures    = Ripper.textures
    other       = Ripper.other

    return (pktcount, pktsuccess, pktfailed, objects, meshes, textures, other)

if __name__ == "__main__":
    Log.log_level = 0

    scriptname  = os.path.basename(sys.argv[0])
    if len(sys.argv) > 4 or (len(sys.argv) > 1 and sys.argv[1].lower() in ('-h', '-help', '--help')):
        print "%s [capture.bin] [output folder] [SimProxy.cfg]" % scriptname
        exit()

    if len(sys.argv) > 3:
        cfgfilename = sys.argv[3]
    else:
        cfgfilename = 'SimProxy.cfg'

    cfg = Config()
    cfg.read(cfgfilename)
    pc = PacketCapture(cfg)

    if len(sys.argv) > 1:
        binfilename = sys.argv[1]
    else:
        binfilename = pc.captureFile
        if not pc.binaryCapture:
            print "Capture file is in text format: %s" % binfilename
            exit()

    if len(sys.argv) > 2:
        outfolder = sys.argv[2]
    else:
        outfolder = './rip'

    print "Capture file:  %s" % binfilename
    print "Output folder: %s" % outfolder
    (pktcount, pktsuccess, pktfailed, objects, meshes, textures, other) = \
        rip(pc, binfilename, outfolder)
    print "Rip complete! %d packets read (%d successful, %d failed)" % (pktcount, pktsuccess, pktfailed)
    print "  Objects:  %d" % objects
    print "  Meshes:   %d" % meshes
    print "  Textures: %d" % textures
    print "  Other:    %d" % other
