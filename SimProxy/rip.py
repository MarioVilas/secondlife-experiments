# Capture file ripper
# by Mario Vilas (mvilas at gmail.com)

import types
import string
import sys
import os.path
import ConfigParser

from SimProxy import SimProxy
from SLPacket import SLPacket
from Logger import Log

###############################################################################

class Ripper:
    outfolder = './'

    @classmethod
    def write(self, uuid, data):
        filename = os.path.join(self.outfolder, uuid + self.ext)
        open(filename, 'wb').write(data)

    @classmethod
    def writeFailed(self, uuid, data):
        self.write(uuid + '_failed', data)

    @classmethod
    def rip(self, message):
        pass

    @classmethod
    def finalize(self):
        pass

class RipperCollection:

    class ImageData(Ripper):
##        ext = '.j2c'
        ext = '.jp2'

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
        pass

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

###############################################################################

def rip(sp, binfilename = 'capture.bin', outfolder = './rip'):
    capture     = open(binfilename, 'rb').read()
    offset      = 0
    objects     = 0
    meshes      = 0
    textures    = 0
    pktcount    = -1
    pktsuccess  = 0
    pktfailed   = 0

    if not os.path.exists(outfolder):
        os.makedirs(outfolder)
    Ripper.outfolder = outfolder

    while( (len(capture) - offset) != 0 ):
        pktcount        = pktcount + 1
        offset, entry   = sp.unpack(capture, offset)
        try:
            rawPacket   = entry[len(entry)-1]
            packet      = SLPacket(rawPacket, sp.slTemplate)
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

    return (pktcount, pktsuccess, pktfailed, objects, meshes, textures)

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

    sp = SimProxy(cfgfilename)
    sp.loadCaptureSettings()

    if len(sys.argv) > 1:
        binfilename = sys.argv[1]
    else:
        binfilename = sp.cap_filename
        if not sp.binaryCapture:
            print "Error, capture file is in text format: %s" % binfilename
            exit()

    if len(sys.argv) > 2:
        outfolder = sys.argv[2]
    else:
        outfolder = './rip'
    if not os.path.isdir(outfolder):
        print "Not a folder: %s" % outfolder

    sp.loadMessageTemplate()

    print "Capture file:  %s" % binfilename
    print "Output folder: %s" % outfolder
    (pktcount, pktsuccess, pktfailed, objects, meshes, textures) = rip(sp, binfilename, outfolder)
    print "Rip complete! %d packets read (%d successful, %d failed)" % (pktcount, pktsuccess, pktfailed)
    print "  Objects:  %d" % objects
    print "  Meshes:   %d" % meshes
    print "  Textures: %d" % textures
