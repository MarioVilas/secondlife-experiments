import sys
import socket
from struct import unpack, pack
import random
from time import time
from math import sqrt
from binascii import a2b_hex

from SLConstants import *
import SLProto

debug = False

NULL_KEY = '\x00'*16

def bytes2uuid(bytes):
    data = unpack('16B', bytes)
    w = '%02x%02x'
    return ('%s-%s-%s-%s-%s' % (w*2, w, w, w, w*3)) % data

def vector2rotation(vector):
    x, y, z = vector
    t = 1.0 - x*x - y*y - x*x
    if t > 0:
       return x, y, z, sqrt(t)
    else:
       return x, y, z, 0 
    
class TextureEntry:
    def __init__(self, data = None):
        if data: self.initFromData(data)

    def initFromData(self, data):
        pass

class SLObject:
    DATA_LOCATION_76   = None
    DATA_LOCATION_60   = None
    COMP_HEADER        = None
    COMP_VOLUME_HEADER = None
    COMP_VOLUME_PATH   = None

    def __init__(self, pkt = None, data = None, dumpFile = None):
        self.childs = {}
        self.od = {}

        if self.__class__.COMP_HEADER is None:
           self.initDecoders()

        if pkt is not None:
           self.initFromPkt(pkt, data)

        if dumpFile is not None:
           self.initFromDumpFile(dumpFile)

    def initFromDumpFile(self, dumpFile, index = 0):
        from xml.dom import minidom
        xmldoc = minidom.parse(dumpFile)

        geometries = xmldoc.getElementsByTagName('LindenGeometry')

        objects = geometries[index].getElementsByTagName('Object')

        self.initFromXMLObject(objects[0])

        for object in objects[1:]:
            child = SLObject()
            child.initFromXMLObject(object)
            self.childs[hash(child)] = child

    def initFromXMLObject(self, xmlNode):
        self.od = od = {}
        attribs  = xmlNode.attributes

        shape    = attribs['Shape'].value
        desc     = attribs['Description'].value
        od['PCode']    = int(attribs['PCode'].value)
        od['Material'] = int(attribs['Material'].value)
        od['Scale']    = [float(each) for each in attribs['Scale'].value.split()]
        od['Position'] = [float(each) for each in attribs['Offset'].value.split()]
        od['Rotation'] = [float(each) for each in attribs['Orientation'].value.split()]
        sprofile = attribs['ShapeProfile'].value.split()
        od['ProfileCurve'] = int(sprofile[0])
        od['ProfileBegin'] = int(round(float(sprofile[1]) / CUT_QUANTA))
        od['ProfileEnd'] = int(50000 - round(float(sprofile[2]) / CUT_QUANTA))
        od['ProfileHollow'] = int(round(float(sprofile[3]) / HOLLOW_QUANTA))

        spath    = attribs['ShapePath'].value.split()
        od['PathCurve'] = int(spath[0])
        od['PathBegin'] = int(round(float(spath[1]) / CUT_QUANTA))
        od['PathEnd'] = int(50000 - round(float(spath[2]) / CUT_QUANTA))
        od['PathTwist'] = int(round(float(spath[3]) / SCALE_QUANTA))
        od['PathTwistBegin'] = int(round(float(spath[4]) / SCALE_QUANTA))
        od['PathScaleX'] = int(200 - round(float(spath[5]) / SCALE_QUANTA))
        od['PathScaleY'] = int(200 - round(float(spath[6]) / SCALE_QUANTA))
        od['PathShearX'] = int(round(float(spath[7]) / SHEAR_QUANTA))
        od['PathShearY'] = int(round(float(spath[8]) / SHEAR_QUANTA))
        od['PathRadiusOffset'] = int(round(float(spath[9]) / SCALE_QUANTA))
        od['PathTaperX'] = int(round(float(spath[10]) / TAPER_QUANTA))
        od['PathTaperY'] = int(round(float(spath[11]) / TAPER_QUANTA))
        od['PathRevolutions'] = int(round((float(spath[12]) - 1.0) / REV_QUANTA))
        od['PathSkew'] = int(round(float(spath[13]) / SCALE_QUANTA))
        faces    = int(attribs['NumberOfFaces'].value)

        od['MediaURL'] = ''
        try:
           od['TextureEntry'] = a2b_hex(attribs['TextureEntry'].value)
        except:
           pass

        # packing ExtraParams. See llviewerobject.cpp::LLViewerObject::processUpdateMessage()
        extraParamsXML = xmlNode.getElementsByTagName('ExtraParameter')
        extraParams    = {}

        for ep in extraParamsXML:
            type = int(ep.getAttribute('Type'))
            extraParams[type] = {'ParamType': type}
            extraParams[type]['ParamInUse'] = int(ep.getAttribute('InUse'))
            extraParams[type]['ParamData']  = a2b_hex(ep.getAttribute('Data'))
            extraParams[type]['ParamSize']  = len(extraParams[type]['ParamData'])

        od['ExtraParams'] = extraParams
        
    def initDecoders(self):
        b = SLProto.SLBlock('Location_76','Single')
        b.appendVar('CollisionNormal','LLVector4')
        self.__class__.DATA_LOCATION_76 = b

        b = SLProto.SLBlock('Location_60','Single')
        b.appendVar('Position','LLVector3')
        b.appendVar('Velocity','LLVector3')
        b.appendVar('Acceleration','LLVector3')
        b.appendVar('Rotation','LLVector3')
        b.appendVar('Omega','LLVector3')
        # self.rotation     = vector2rotation(self.rotation)
        self.__class__.DATA_LOCATION_60 = b

        b = SLProto.SLBlock('Header','Single')
        b.appendVar('FullID','LLUUID')
        b.appendVar('ID','U32')
        b.appendVar('PCode','U8')
        self.__class__.COMP_HEADER = b

        b = SLProto.SLBlock('PCODE_VOLUME', 'Single')
        b.appendVar('State','U8')
        b.appendVar('CRC','U32')
        b.appendVar('Material','U8')
        b.appendVar('ClickAction','U8')
        b.appendVar('Scale','LLVector3')
        b.appendVar('Position','LLVector3')
        b.appendVar('Rotation','LLVector3')
        b.appendVar('SpecialCode','U32')
        b.appendVar('Owner','LLUUID')
        self.__class__.COMP_VOLUME_HEADER = b

        b = SLProto.SLBlock('PCODE_VOLUME_PATH','Single')
        b.appendVar('PathCurve','U8')
        b.appendVar('PathBegin','U16')
        b.appendVar('PathEnd','U16')
        b.appendVar('PathScaleX','U8')
        b.appendVar('PathScaleY','U8')
        b.appendVar('PathShearX','U8')
        b.appendVar('PathShearY','U8')
        b.appendVar('PathTwist','U8')
        b.appendVar('PathTwistBegin','U8')
        b.appendVar('PathRadiusOffset','U8')
        b.appendVar('PathTaperX','U8')
        b.appendVar('PathTaperY','U8')
        b.appendVar('PathRevolutions','U8')
        b.appendVar('PathSkew','U8')
        self.__class__.COMP_VOLUME_PATH = b

        b = SLProto.SLBlock('PCODE_VOLUME_PROFILE','Single')
        b.appendVar('ProfileCurve','U8')
        b.appendVar('ProfileBegin','U16')
        b.appendVar('ProfileEnd','U16')
        b.appendVar('ProfileHollow','U16')
        self.__class__.COMP_VOLUME_PROFILE = b

    def addChild(self, obj):
        self.childs[obj.uuid] = obj

    def initFromPkt(self, pkt, *args):
        # call initFromObjectUpdate, initFromObjectUpdateCompressed, etc
        method = 'initFrom%s' % pkt.name
        getattr(self, method)(pkt, *args)

    def initFromObjectUpdate(self, pkt, od):
        self.uuid     = od['FullID']
        self.localID  = od['ID']
        self.parentID = od['ParentID']
        self.od       = od

        self.updateFromObjectData(od['ObjectData'])

    def updateFromObjectData(self, data):
        # see llviewerobject.cpp:LLViewerObject::processUpdateMessage()
        ofs = 0
        if len(data) == 76:
           ofs, moreValues = self.DATA_LOCATION_76.decode(data, ofs)
           self.od.update(moreValues)
        if len(data) >= 60:
           ofs, moreValues = self.DATA_LOCATION_60.decode(data, ofs)
           moreValues['Rotation'] = vector2rotation(moreValues['Rotation'])
           self.od.update(moreValues)
        else:
           print 'Unsupported ObjectData length (%d)' % len(data)
           
    def initFromObjectUpdateCompressed(self, pkt, od):
        data = od['Data']
        ofs = 0
        values = {}
        self.od = values

        decoder = SLProto.SLVariable('fake','','')

        ofs, moreValues = self.COMP_HEADER.decode(data, ofs)
        values.update(moreValues)

        self.uuid    = values['FullID']
        self.localID = values['ID']
        values['Flags'] = od['UpdateFlags']

        # LLViewerObject::processUpdateMessage() 
        ofs, moreValues = self.COMP_VOLUME_HEADER.decode(data, ofs)
        moreValues['Rotation'] = vector2rotation(moreValues['Rotation'])
        values.update(moreValues)

        if values['SpecialCode'] & 0x80:
           ofs, values['Omega'] = decoder.LLVector3(data, ofs)

        if values['SpecialCode'] & 0x20:
           ofs, values['ParentID'] = decoder.U32(data, ofs)
        else:
           values['ParentID'] = 0

        self.parentID = values['ParentID']

        if values['SpecialCode'] & 0x02:
           ofs, values['TreeData'] = decoder.U8(data, ofs)
        elif values['SpecialCode'] & 0x01:
           decoder.count = 4
           ofs, values['PartData'] = decoder.Variable(data, ofs)

        if values['SpecialCode'] & 0x04:
           ofs, values['Text']      = decoder.String(data, ofs)
           ofs, values['TextColor'] = decoder.U32(data, ofs)
        else:
           values['Text'] = ''

        if values['SpecialCode'] & 0x200:
           ofs, values['MediaURL'] = decoder.String(data, ofs)
        else:
           values['MediaURL'] = ''

        if values['SpecialCode'] & 0x08:
           # LLViewerObject::unpackParticleSource()
           print "Don't know how to unpack a particle source yet"
           return

        # unpack extra parameters
        ofs, num_params = decoder.U8(data, ofs)
        params = []
        decoder.count = 4
        for p in range(num_params):
            ofs, type  = decoder.U16(data, ofs)
            ofs, param = decoder.Variable(data, ofs)
            params.append((type, param))

        if values['SpecialCode'] & 0x10:
           ofs, values['SoundUUID'] = decoder.LLUUID(data, ofs)
           ofs, values['SoundGain'] = decoder.F32(data, ofs)
           ofs, values['SoundFlags'] = decoder.U8(data, ofs)
           ofs, values['SoundRadius'] = decoder.F32(data, ofs)

        if values['SpecialCode'] & 0x100:
           # name value list
           ofs, values['NameValueList'] = decoder.String(data, ofs)

        # See LLViewerObject::createObject() in newview/llviewerobject.cpp
        # and then processUpdateMessage() for the specific class
        if values['PCode'] == LL_PCODE_VOLUME:
           # LLVOVolume::processUpdateMessage()

           #  LLVolumeMessage::unpackVolumeParams()
           #   LLVolumeMessage::unpackPathParams()
           ofs, moreValues = self.COMP_VOLUME_PATH.decode(data, ofs)
           values.update(moreValues)

           #   LLVolumeMessage::unpackProfileParams()
           ofs, moreValues = self.COMP_VOLUME_PROFILE.decode(data, ofs)
           values.update(moreValues)

           decoder.count = 4
           ofs, values['TextureEntry'] = decoder.Variable(data, ofs)

           if values['SpecialCode'] & 0x40:
              print 'No texture animation handling yet'
        else:
           print 'Unsupported PCode for compressed update: %d' % values['PCode']
           self.parentID = 0

    def initFromObjectUpdateCached(self, pkt, od):
        self.localID = od['ID']
        self.od = {}
        self.od['Flags'] = od['UpdateFlags']

    def initFromTerseObjectUpdate(self, pkt, od):
        data = od['Data']
        ofs = 0
        values = {}
        self.od = values

        values['TextureEntry'] = od['TextureEntry']

        decoder = SLProto.SLVariable('fake','','')

        ofs, self.localID = decoder.U32(data, ofs)

        
    def update(self, pkt, od):
        self.initFromPkt(pkt, od)

class SLMiMPkt:
    def __init__(self, name = None, sock = None, dataFile = None):
        self.sim = None
        if name:
            self.name = name
            self.msg = {}
        if sock:
            self.readFromSocket(sock)
        if dataFile:
            self.readFromFile(dataFile)

    def read(self, sock, count):
        answer = ''
        while len(answer) < count:
            answer += sock.recv(count-len(answer))
        return answer

    def readFromSocket(self, sock):
        self.direction = self.read(sock, 1)
        ip = unpack('BBBB', self.read(sock,4))
        port, count = unpack('<LL', self.read(sock, 8))
        ip = '%d.%d.%d.%d' % ip
        self.sim = (ip, port)
        self.data = self.read(sock, count)

    def readFromFile(self, dataFile):
        line = dataFile.readline()
        hostport, data = line.split(None, 1)
        self.direction = hostport[0]
        if self.direction == hostport:
           hostport, data = line[1:].split(None, 1)
        ip, port = hostport[1:].split(':')
        port = int(port)
        self.sim = (ip, port)

        try:
            self.data = eval(data)
        except Exception, e:
            print "Failed evaluating: %r (%s)" % (data, e)

    def writeToSocket(self, sock, direction = 'o'):
        toWrite  = direction
        ip = [int(x) for x in self.sim[0].split('.')]
        toWrite += pack('<BBBBLL',
            ip[0], ip[1], ip[2], ip[3],
            self.sim[1],   # port
            len(self.data))
        toWrite += self.data

        sock.send(toWrite)
        
    def dump(self, msg = ''):
        print '%s%s' % (msg, self.direction),
        try:
            raise Exception
            self.template.dump(self.msg)
        except Exception, e:
            print '%s:%d %r' % (self.sim[0], self.sim[1], self.data)

class SLMiM:
    def __init__(self, host = 'localhost', port = 0xdeb0, dataFile = None):
        self.isSniffing = False
        self.AgentData = None
        self.lastSeenSim = None
        self.objectsByID = {}
        self.objectsByLocalID = {}
        self.learning = False

        if dataFile is None:
           self.sock = socket.socket()
           self.sock.connect((host, port))
           hola = self.sock.recv(5)
           if hola != 'Hola\n':
               raise Exception, "Didn't get expected handshake"
           self.dataFile = None
        else:
           self.dataFile = open(dataFile, 'rb')
           self.sock = None
           self.startLearning()

        self.tr = SLProto.TemplateReader()

    def fileno(self):
        return self.sock.fileno()

    def startSniffing(self):
        if not self.sock: return
        if not self.isSniffing:
           self.sock.send('1')
           self.isSniffing = True
           return False
        else:
           return True

    def stopSniffing(self):
        if not self.sock: return
        if self.isSniffing:
            self.sock.send('0')
            self.isSniffing = False
            return True
        else:
            return False

    def startLearning(self):
        self.learning = True

    def stopLearning(self):
        self.learning = False

    def learnObject(self, obj):
        if (debug): print 'learned new object: %r' % obj.uuid
        self.objectsByID[obj.uuid] = obj
        self.objectsByLocalID[obj.localID] = obj
        if not self.objectsByLocalID.has_key(obj.parentID):
           # create a template parent
           parent = SLObject()
           parent.localID = obj.parentID
           self.objectsByLocalID[parent.localID] = parent

        self.objectsByLocalID[obj.parentID].addChild(obj)

    def getObject(self, uuid):
        return self.objectsByID[uuid]

    def learnFrom(self, pkt):
        if pkt.name == 'ObjectUpdate':
           pkt.msg = pkt.template.decode(pkt.data)
           for od in pkt.msg['ObjectData']:
               try:
                  obj = self.getObject(od['FullID'])
                  obj.update(pkt, od)
                  # if obj.parentID != od['ParentID']:
                  #   print "WARNING: Object changed parent, can't handle it yet"
                  print 'updated: %r' % od['FullID']
               except Exception:
                  obj = SLObject(pkt, od)
                  self.learnObject(obj)
        elif pkt.name == 'ObjectUpdateCompressed':
           pkt.msg = pkt.template.decode(pkt.data)
           for od in pkt.msg['ObjectData']:
               try:
                  id = od['Data'][:16]
                  obj = self.getObject(id)
                  obj.update(pkt, od)
                  od = obj.od
                  if obj.parentID != od['ParentID']:
                     print "WARNING: Object changed parent, can't handle it yet"
                  print 'updated: %r' % od['FullID']
               except Exception, e:
                  obj = SLObject(pkt, od)
                  self.learnObject(obj)
               
    def nextPacket(self):
        if self.sock: pkt =  SLMiMPkt(sock = self.sock)
        else: pkt =  SLMiMPkt(dataFile = self.dataFile)
        pkt.template = self.tr.templateFor(pkt.data)
        pkt.name = pkt.template.name
        return pkt

    def waitAny(self, messages = [], blocks = [], direction = None, timeout = 2**33):
        sniffing = self.startSniffing()
        gotIt = False
        endTime = time() + timeout

        while (not gotIt) and (time() < endTime):
            pkt = self.nextPacket()
            self.lastSeenSim = pkt.sim
            if direction and direction != pkt.direction:
                continue
            try:
                if debug: print pkt.dump()
                if self.learning:
                   self.learnFrom(pkt)
                gotIt = pkt.name in messages
                pktBlocks = [block.name for block in pkt.template.blocks]
                for block in blocks:
                    if block in pktBlocks:
                        gotIt = True
                        break
            except Exception, e:
                raise
                print e, 
                pkt.dump()

        if not sniffing: self.stopSniffing()

        if gotIt:
           pkt.msg = pkt.template.decode(pkt.data)
        else:
           return None

        return pkt

    def waitMessage(self, message, **kargs):
        return self.waitAny([message], **kargs)

    def waitBlock(self, block, **kargs):
        return self.waitAny(blocks = [block], **kargs)

    def sleep(self, delay, **kargs):
        # it'll miss all the packets received during this period...
        # it's not really nice
        # not accurate, it'll wait at least the speicifed time,
        # may be more depending on the traffic

        endTime = time() + delay
        while endTime > time():
              self.waitAny([], [], timeout = endTime - time(), **kargs)

    def waitUpdate(self, uuids = [], localIDs = [], **kargs):
        sniffing = self.startSniffing()
        found = None
        while not found:
           pkt = self.waitAny(messages = [
               'ObjectUpdate',
               'ObjectUpdateCompressed',
               'ObjectUpdateCached'], **kargs)

           if pkt.name == 'ObjectUpdate':
              for od in pkt.msg['ObjectData']:
                  # print 'ID: %s localID: %d flags: %x' % (bytes2uuid(od['FullID']), od['ID'], od['Flags'])
                  if ((not localIDs and not uuids) or 
                      (od['ID'] in localIDs) or
                      (od['FullID'] in uuids)):
                         found = SLObject(pkt = pkt, data = od)
                         break
           elif pkt.name == 'ObjectUpdateCached':
              for od in pkt.msg['ObjectData']:
                  if (not localIDs or
                     (od['ID'] in localIDs)):
                        found = SLObject(pkt = pkt, data = od)
                        break

           elif pkt.name == 'ObjectUpdateCompressed':
              for od in pkt.msg['ObjectData']:
                  fullID, localID = unpack('<16sL', od['Data'][:20])
                  # print 'ID: %s localID: %d flags: %x (compressed)' % (bytes2uuid(fullID), localID, od['UpdateFlags'])
                  if ((not localIDs and not uuids) or 
                      (localID in localIDs) or
                      (fullID in uuids)):
                         found = SLObject(pkt = pkt, data = od)
                         break

        if not sniffing: self.stopSniffing()
        return found

    def collectAgentData(self):
       while 1:
          pkt = self.waitBlock('AgentData')
          if pkt.direction == 'o': break
       self.AgentData = pkt.msg['AgentData']
       return self.AgentData

    def onChatFromSimulator(self, pkt):
        msg = pkt.msg['ChatData']
        print '%s (%d:%d): %s' % (
            msg['FromName'], 
            msg['ChatType'],
            msg['SourceType'],
            msg['Message'])

    # sending events
    def chat(self, text, type = 1, channel = 0):
        # building a ChatFromViewer
        pkt = SLMiMPkt('ChatFromViewer')
        pkt.msg['ChatData'] = {}
        pkt.msg['ChatData']['Channel'] = channel 
        pkt.msg['ChatData']['Message'] = text
        pkt.msg['ChatData']['Type'] = 1
        self.spoof(pkt)

    def IM(self, fromName, toID, regionID, ID, text, position = (0.0, 0.0, 0.0)):
        im = SLMiMPkt('ImprovedInstantMessage')
        im.msg['MessageBlock'] = {}
        im.msg['MessageBlock']['FromGroup'] = False
        im.msg['MessageBlock']['ToAgentID'] = toID
        im.msg['MessageBlock']['ParentEstateID'] = 0
        im.msg['MessageBlock']['RegionID'] = regionID
        im.msg['MessageBlock']['Position'] = position
        im.msg['MessageBlock']['Offline'] = 0
        im.msg['MessageBlock']['Dialog'] = 0
        im.msg['MessageBlock']['ID'] = ID
        im.msg['MessageBlock']['Timestamp'] = 0
        im.msg['MessageBlock']['FromAgentName'] = fromName
        im.msg['MessageBlock']['Message'] = text
        im.msg['MessageBlock']['BinaryBucket'] = '\x00'
        self.spoof(im)
        
    def randomOffset(self):
        return (
          random.random()*0.1 - 0.05,
          random.random()*0.1 - 0.05,
          random.random()*0.1 - 0.05)

    def grab(self, localID, offset = None):
        if offset is None:
           offset = self.randomOffset()
        grab = SLMiMPkt('ObjectGrab')
        grab.msg['ObjectData'] = {}
        grab.msg['ObjectData']['LocalID'] = localID
        grab.msg['ObjectData']['GrabOffset'] = offset
        self.spoof(grab)

    def deGrab(self, localID):
        deGrab = SLMiMPkt('ObjectDeGrab')
        deGrab.msg['ObjectData'] = {}
        deGrab.msg['ObjectData']['LocalID'] = localID
        self.spoof(deGrab)
        
    def touch(self, localID, offset = None):
        self.grab(localID, offset)
        self.deGrab(localID)
        
    def sit(self, fullID, offset = None):
        if offset is None:
           offset = self.randomOffset()
        sitRequest = SLMiMPkt('AgentRequestSit')
        sitRequest.msg['TargetObject'] = {}
        sitRequest.msg['TargetObject']['TargetID'] = fullID
        sitRequest.msg['TargetObject']['Offset'] = offset
        self.spoof(sitRequest)
        
    def spoof(self, pkt, direction = 'o', reliable = False):
        if pkt.sim is None:
           pkt.sim = self.lastSeenSim
        if not pkt.msg.has_key('AgentData'):
           pkt.msg['AgentData'] = self.AgentData

        pkt.data = self.tr.encodeMessage(pkt.name, pkt.msg)

        if self.sock: pkt.writeToSocket(self.sock, direction)
        else: print '%r' % pkt.data
        

    def v_times_q(self, v, q):
        rw = -q[0] * v[0] - q[1] * v[1] - q[2] * v[2]
        rx =  q[3] * v[0] + q[1] * v[2] - q[2] * v[1]
        ry =  q[3] * v[1] + q[2] * v[0] - q[0] * v[2]
        rz =  q[3] * v[2] + q[0] * v[1] - q[1] * v[0]

        nx = -rw*q[0] + rx*q[3] - ry*q[2] + rz * q[1]
        ny = -rw*q[1] + ry*q[3] - rz*q[0] + rx * q[2]
        nz = -rw*q[2] + rz*q[3] - rx*q[1] + ry * q[0]
        return (nx, ny, nz)

    def v_times_v(self, a, b):
        return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
        
    def v_plus_v(self, a, b):
        return (a[0]+b[0], a[1]+b[1], a[2]+b[2])

    def neg_q(self, q):
        return (-q[0], -q[1], -q[2], q[3])

    def undo_find_local_contact_point(self, rot, scale):
        # used to un-shift objects, as they were shifted during export
        # fixed surface normal to (0,0,1)
        # delta is the answer
        # see llviewermenu::undo_find_local_contect_point()

        local_norm = self.v_times_q((0,0,1), self.neg_q(rot))

        v = [0]*6

        v[0] = (-1, 0, 0)
        v[1] = ( 1, 0, 0)
        v[2] = ( 0,-1, 0)
        v[3] = ( 0, 1, 0)
        v[4] = ( 0, 0,-1)
        v[5] = ( 0, 0, 1)

        contact = v[0]
        cur_val = 0

        for i in range(6):
            val = self.v_times_v(v[i], local_norm)
            if val < cur_val:
               contact = v[i]
               cur_val = val

        contact = (
           contact[0] * 0.5 * scale[0],
           contact[1] * 0.5 * scale[1],
           contact[2] * 0.5 * scale[2])

        return self.v_times_q(contact, rot)

    def createObjectSetAt(self, root, pos, **kargs):
        objects = {}
        x, y, z = pos

        for obj in root.childs.values():
            objX, objY, objZ = obj.od['Position']
            newObjs = self.createObjectSetAt(obj, (x+objX, y+objY, z+objZ), alreadyKnown = objects, **kargs)
            objects.update(newObjs)

        try:
           kargs['alreadyKnown'].update(objects)
        except:
           kargs['alreadyKnown'] = objects
        newObj = self.createObjectAt(root, (x, y, z), **kargs)
        objects[newObj.localID] = newObj
        return objects


    def createObjectAt(self, obj, pos, rotation = None, waitAnswer = True, withTexture = True, withExtraParams = True, alreadyKnown = {}):
        waitAnswer |= withTexture | withExtraParams

        # print '\nknown: %r' % alreadyKnown
        if obj.od['PCode'] != 9:
           print 'Warning!!! you tried to create an object with PCode = %d' % obj.od['PCode']
           return None, None

        if rotation is None:
           try:
              rotation = obj.od['Rotation']
           except:
              rotation = (0,0,0,0)

        pkt = SLMiMPkt('ObjectAdd')

        pkt.msg['AgentData'] = {}
        pkt.msg['AgentData']['AgentID'] = self.AgentData['AgentID']
        pkt.msg['AgentData']['SessionID'] = self.AgentData['SessionID']
        pkt.msg['AgentData']['GroupID'] = NULL_KEY
        pkt.msg['ObjectData'] = obj.od.copy()

        od = pkt.msg['ObjectData']
        od['Rotation'] = rotation
        od['AddFlags'] = 2 # CreateSelected

        pos = self.v_plus_v(pos, self.undo_find_local_contact_point(rotation, od['Scale']))

        od['RayStart'] = pos
        od['RayEnd'] = pos
        od['RayEndIsIntersection'] = False
        od['RayTargetID'] = NULL_KEY
        od['BypassRaycast'] = True

        od['State'] = 0

        if waitAnswer:
           sniffing = self.startSniffing()

        self.spoof(pkt)
        print 'created object at %r' % (pos,)

        if waitAnswer:
           newObj = None
           while not newObj:
              updatedObj = self.waitUpdate()
              # print 'Updated object: %d flags: %x' % (updatedObj.localID, updatedObj.od['Flags'])
              if ((updatedObj.od['Flags'] & 2) and 
                  (not alreadyKnown.has_key(updatedObj.localID))):
                    newObj = updatedObj

        if newObj:
           print '   just created: %d' % newObj.localID
           if withTexture and obj.od.has_key('TextureEntry'):
              self.setObjectImage(newObj, obj.od['TextureEntry'], obj.od['MediaURL'])
           if withExtraParams and obj.od.has_key('ExtraParams'):
              self.setObjectExtraParams(newObj, obj.od['ExtraParams'])

        if waitAnswer:
           if not sniffing:
              self.stopSniffing()

        return newObj

    def setObjectImage(self, obj, textureEntry, mediaURL):
        # print 'Setting image for %d: %r' % (obj.localID, textureEntry)
        pkt = SLMiMPkt('ObjectImage')
        pkt.msg['ObjectData'] = {}
        pkt.msg['ObjectData']['ObjectLocalID'] = obj.localID
        pkt.msg['ObjectData']['TextureEntry'] = textureEntry
        pkt.msg['ObjectData']['MediaURL'] = mediaURL
        self.spoof(pkt)
        # self.waitUpdate(localIDs =  [obj.localID])

    def setObjectExtraParams(self, obj, extraParams):
        if not extraParams: return
        # print 'Setting extra parameters for %d: %r' % (obj.localID, extraParams)
        pkt = SLMiMPkt('ObjectExtraParams')
        pkt.msg['ObjectData'] = []
        for ep in extraParams.values():
            params = ep.copy()
            params['ObjectLocalID'] = obj.localID
            pkt.msg['ObjectData'].append(params)
        self.spoof(pkt)
        # self.waitUpdate(localIDs =  [obj.localID])
       
    # raw sniffing
    def sniff(self, fileName = None):
        f = sys.stdout
        if fileName:
           f = open(fileName, "wb")
        self.startSniffing()
        while 1:
            pkt = self.nextPacket()
            try:
                pkt.msg, pkt.template = self.tr.decodePacket(pkt.data)
                pkt.name = pkt.template.name
                pkt.dump()
            except Exception, e:
                print "Failed decoding! %s" % e
                pkt.dump()
                print
    
if __name__ == '__main__':
    port = 0xdeb0
    fileName = None
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    if len(sys.argv) > 2:
        fileName = sys.argv[2]

    SLMiM('localhost',port).sniff(fileName = fileName)
    
