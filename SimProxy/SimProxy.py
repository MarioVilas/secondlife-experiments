# Second Life sim proxy
# by Mario Vilas (mvilas at gmail.com)

import sys
import os.path
import socket
import select
import time
import struct
import traceback
import thread
import threading
import xmlrpclib
import zlib

from sllib.Logger import Log
from sllib.Config import Config
from sllib.XMLRPCServer import XMLRPCServer
from sllib.SLPacketFilter import SLPacketFilter
from sllib.SLTemplate import SLTemplateFactory, HexDumper
from sllib.SLPacket import SLPacket
from sllib import SLTypes


class SimProxy:
    section         = 'SimProxy'
    xmlrpc_section  = 'SimProxy-XMLRPC'
    settings    = {
                    'URI': {
                                'loginProxyURI' : 'string',
                                'capProxyURI'   : 'string',
                                'simProxyURI'   : 'string',
                           },
                    'SimProxy': {
                                'simHost'       : 'ipaddr',
                                'bindAddress'   : 'ipaddr',
                                'bindPort'      : 'int',
                                'simList'       : 'list',
                                'bindAddress'   : 'string',
                                'bindAddress'   : 'string',
                                },
                  }

    def __init__(self, configFilename):
        self.cfg = Config()
        self.cfg.read(configFilename)

    def start(self):
        Log.loadSettings(self.cfg, self.section)
        self.loadSettings()

        self.pktCapture = PacketCapture(self.cfg)
        self.pktCapture.start()

        self.msgFilter  = SLPacketFilter(self)

        self.lock   = threading.RLock()
        self.active = True

        self.seed   = {}

        self.worker = Selector(self)
        self.worker.start()

        self.server = XMLRPCServer(self, self.xmlrpc_section)
        self.server.register_function(self.newSim)
        self.server.register_function(self.newSeed)
        self.server.register_function(self.getSeed)
        self.server.start()

        Log(1, "SimProxy loaded successfully")

    def kill(self):
        Log(1, "Shutting down SimProxy...")
        self.active = False
        self.worker.kill()
        Log(1, "Shut down SimProxy")

    def loadSettings(self):
        self.simProxyURI    = None
        self.capProxyURI    = None
        self.loginProxyURI  = None
        self.bindAddress    = '0.0.0.0'
        self.bindPort       = 0
        self.simList        = []

        self.cfg.load(self, self.settings)

        if self.bindPort:
            bindPort = self.bindPort
            for sim in self.simList:
                if sim == '': continue
                simAddress, simPort = sim.split(':')
                simPort = int(simPort) & 0xFFFF
                try:
                    simAddress = socket.gethostbyname(simAddress)
                except Exception, e:
                    pass
                bindPort = self.newSim((simAddress, simPort), bindPort)[1]
                bindPort = bindPort + 1

    def newSim(self, simAddr):
        simAddr = simAddr[0], int(simAddr[1])
        if self.active:
            self.lock.acquire()
            sim = self.worker.newSim(simAddr)
            self.lock.release()
            return self.simHost, sim.bindPort
        raise Exception, "SimProxy is no longer running"

    def newSeed(self, uri):
        h = hash(uri)
        self.seed[h] = uri
        return h

    def getSeed(self, h):
        return self.seed[h]


class PacketCapture:
    captureSettings  = {
                        'SimProxy': {
                                    'templateFile'      : 'string',
                                    'captureFile'       : 'string',
                                    'captureFormat'     : 'string',
                                    'captureCompression': 'int',
                                    'storeResent'       : 'bool',
                                    'storeBad'          : 'bool',
                                    'allowCapture'      : 'list',
                                    'blockCapture'      : 'list',
                                    },
                       }
    def __init__(self, cfg):
        self.loadSettings(cfg)
        self.slTemplate = SLTemplateFactory.load(self.templateFile)

    def start(self):
        if self.captureFile:
            Log(1, "Storing captured packets in %s" % self.captureFile)
            self.cap_file = open(self.captureFile, 'a+b')
            self.lock     = threading.RLock()
        else:
            self.cap_file = None

    def loadSettings(self, cfg):
        self.templateFile       = 'templates/1.18.1.2.txt'
        self.captureFile        = ''
        self.captureFormat      = 'binary'
        self.captureCompression = 9
        self.storeResent        = True
        self.storeBad           = True
        self.allowCapture       = []
        self.blockCapture       = []

        cfg.load(self, self.captureSettings)

        self.captureFormat = self.captureFormat.lower()
        if   self.captureFormat == 'binary':
            self.binaryCapture  = True
        elif self.captureFormat == 'text':
            self.binaryCapture  = False
        else:
            raise Exception, "Unknown capture file format: %s" % self.captureFormat

        if '*' in self.allowCapture and self.allowCapture != ['*']:
            raise Exception, (
                "Bad capture filter: "
                "allocCapture contains an * among other items"
                )
        if '*' in self.blockCapture and self.blockCapture != ['*']:
            raise Exception, (
                "Bad capture filter: "
                "blockCapture contains an * among other items"
                )
        if self.allowCapture == ['*'] and self.blockCapture == ['*']:
            raise Exception, (
                "Bad capture filter: "
                "allowCapture and blockCapture can't be both *"
                )
        if self.allowCapture == [] and self.blockCapture == []:
            raise Exception, (
                "Bad capture filter: "
                "allowCapture and blockCapture can't be both empty"
                )

        self.captureAll  = (self.allowCapture == ['*'] and self.blockCapture == [])
        self.captureNone = (self.allowCapture == [] and self.blockCapture == ['*'])
        self.isBlacklist = (self.allowCapture == ['*'])

    def sniff(self, rawPacket, fromAddr, toAddr):
        if self.cap_file and not self.captureNone:
            if not self.captureAll:
                try:
                    packet  = SLPacket(rawPacket, self.slTemplate)
                    msgname = packet.messageName
                    isdup   = packet.isResent()
                    isbad   = False
                except Exception, e:
                    msgname = None
                    isdup   = None
                    isbad   = True
                if not self.storeBad and isbad:
                    return
                if not self.storeResent and isdup:
                    return
                if self.isBlacklist:
                    if msgname in self.blockCapture:
                        return
                else:
                    if msgname not in self.allowCapture:
                        return
            if self.binaryCapture:
                s = self.pack(time.time(), fromAddr, toAddr, rawPacket,
                                self.captureCompression)
            else:
                s = self.dump(time.time(), fromAddr, toAddr, rawPacket)
            self.lock.acquire()
            self.cap_file.write(s)
            self.lock.release()

    @staticmethod
    def pack(timestamp, fromAddr, toAddr, rawPacket, captureCompression = 9):
        timestamp   = SLTypes.F32.encode(timestamp)
        fromIP      = SLTypes.IPADDR.encode(fromAddr[0])
        fromPort    = SLTypes.IPPORT.encode(fromAddr[1])
        toIP        = SLTypes.IPADDR.encode(toAddr[0])
        toPort      = SLTypes.IPPORT.encode(toAddr[1])
        rawPacket   = zlib.compress(rawPacket, captureCompression)
        rawPacket   = SLTypes.Variable.encode(rawPacket, 2)
        chunk = timestamp + fromIP + fromPort + toIP + toPort + rawPacket
        if len(chunk) != ( 4+4+2+4+2+len(rawPacket) ):
            raise Exception, "Internal error!"
        return chunk

    @staticmethod
    def unpack(packetCapture, offset):
        offset, timestamp   = SLTypes.F32.decode(packetCapture, offset)
        offset, fromIP      = SLTypes.IPADDR.decode(packetCapture, offset)
        offset, fromPort    = SLTypes.IPPORT.decode(packetCapture, offset)
        offset, toIP        = SLTypes.IPADDR.decode(packetCapture, offset)
        offset, toPort      = SLTypes.IPPORT.decode(packetCapture, offset)
        offset, rawPacket   = SLTypes.Variable.decode(packetCapture, offset, 2)
        rawPacket           = zlib.decompress(rawPacket)
        return offset, \
                (timestamp, (fromIP, fromPort), (toIP, toPort), rawPacket)

    def dump(self, timestamp, fromAddr, toAddr, rawPacket):
        s = '[%f] %s:%d -> %s:%d\n'
        s = s % (timestamp, fromAddr[0], fromAddr[1], toAddr[0], toAddr[1])

        # try to decode the packet header
        # if decoding fails, dump hex data
        try:
            packet = SLPacket(rawPacket, self.slTemplate)
        except Exception, e:
##            raise                                           # XXX
##            s += 'Exception: %s\n' % str(e)
            s += traceback.format_exc()
            s += 'PACKET (%d bytes)\n' % len(rawPacket)
            s += HexDumper.dumpBlock(rawPacket, 32)
            s += '\n'
            return s

        # try to decode the message data
        # if decoding fails, dump hex data
        try:
            s += packet.dump(decodeData = True)
        except Exception, e:
##            raise                                           # XXX
##            s += 'Exception: %s\n' % str(e)
            s += traceback.format_exc()
            try:
                s += packet.dump(decodeData = False)
            except Exception, e:
##                s += 'Exception: %s\n' % str(e)
                s += traceback.format_exc()
                s += 'PACKET (%d bytes)\n' % len(rawPacket)
                s += HexDumper.dumpBlock(rawPacket, 32)
        s += '\n'

##        # XXX DEBUG
##        # re encode the packet and verify the contents are the same
##        packet.decode()
##        packet.delBlockData()
##        reencodedPacket = str(packet)
##        if reencodedPacket != rawPacket:
##            s += 'ENCODING ERROR!\n'
##            s += self.dump(timestamp, fromAddr, toAddr, reencodedPacket)
####            raise Exception, "Oops!"

        return s


class ProxySocket:

    def __init__(self,
                    peerAddress,
                    peerPort,
                    bindAddress = '0.0.0.0',
                    bindPort    = 0
    ):
        self.peerAddress, self.peerPort = peerAddress, peerPort
        self.bindAddress, self.bindPort = bindAddress, bindPort

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind( (self.bindAddress, self.bindPort) )

        self.bindAddress, self.bindPort = self.sock.getsockname()

        Log(1,
            self.new_message % \
                (self.peerAddress, self.peerPort, self.bindPort)
            )

    def close(self):
        self.sock.close()
        del self.sock
        Log(1,
            self.die_message % \
                (self.peerAddress, self.peerPort, self.bindPort)
            )

    def send(self, packet):
        rawPacket = str(packet)
        return self.sock.sendto(rawPacket, (self.peerAddress, self.peerPort))

    def sendto(self, packet, addr):
        rawPacket = str(packet)
        return self.sock.sendto(rawPacket, addr)

    def recv(self, size = 0xFFFF):
        return self.sock.recv(size)

    def recvfrom(self, size = 0xFFFF):
        return self.sock.recvfrom(size)


class Sim(ProxySocket):
    new_message = "New sim proxy to %s:%d on port %d"
    die_message = "Shut down sim proxy to %s:%d on port %d"

    def connect(self, *listArgs, **dictArgs):
        return Viewer(*listArgs, **dictArgs)


class Viewer(ProxySocket):
    new_message = "New viewer connected from %s:%d proxied from port %d"
    die_message = "Shut down viewer connected from %s:%d proxied from port %d"

    def connect(self, *listArgs, **dictArgs):
        return Sim(*listArgs, **dictArgs)


class Worker:

    def __init__(self, main):
        self.main       = main
        self.active     = False
        self.event      = threading.Event()
        self.event.set()

    def start(self):
        if not self.active:
            self.active = True
            self.event.clear()
            thread.start_new_thread(self.__run, ())

    def kill(self):
        if self.active:
            self.active = False
            self.event.wait()

    def die(self):
        self.active = False
        self.event.set()

    def __run(self):
        try:
            self.run()
        except Exception, e:
            Log.logException()
            self.die()


class Selector(Worker):

    def __init__(self, main):
        Worker.__init__(self, main)

        self.byAddr   = {}      # (host, port) -> Sim or Viewer
        self.bySock   = {}      # socket -> Sim or Viewer

    def run(self):
        while self.active:
            self.select()
        self.die()

    def newSim(self, simAddr):
        return self.listen(Sim, simAddr)

    def newViewer(self, viewerAddr):
        return self.listen(Viewer, viewerAddr)

    def listen(self, ProxySockClass, peerAddr):
        if not self.byAddr.has_key(peerAddr):
            new_proxy = ProxySockClass(*peerAddr)
            self.byAddr[peerAddr]       = new_proxy
            self.bySock[new_proxy.sock] = new_proxy
        return self.byAddr[peerAddr]

    def connect(self, proxy, peerAddr):
        if not self.byAddr.has_key(peerAddr):
            new_proxy = proxy.connect(*peerAddr)
            self.byAddr[peerAddr]       = new_proxy
            self.bySock[new_proxy.sock] = new_proxy
        return self.byAddr[peerAddr]

    def select(self):
        socketList = self.bySock.keys()
        if socketList:
            socketList = select.select(socketList, [], [], 1)[0]
            for s in socketList:
                try:
                    proxyTo     = self.bySock[s]
                    fromViewer  = (proxyTo.__class__ == Sim)
                    rawPacket, fromAddr = proxyTo.recvfrom()
                    proxyFrom   = self.connect(proxyTo, fromAddr)
                    toAddr      = (proxyTo.peerAddress, proxyTo.peerPort)
                    isReply, newPacket = self.filterPacket(rawPacket, fromViewer)
                    if newPacket:
                        if isReply:
                            proxyFrom.sendto(newPacket, fromAddr)
                            self.capturePacket(rawPacket, fromAddr, toAddr)
                            self.capturePacket(newPacket, toAddr, fromAddr)
                        else:
                            proxyFrom.sendto(newPacket, toAddr)
                            self.capturePacket(newPacket, fromAddr, toAddr)
                except Exception, e:
                    Log.logException()

    def capturePacket(self, rawPacket, fromAddr, toAddr):
        self.main.pktCapture.sniff(rawPacket, fromAddr, toAddr)

    def filterPacket(self, rawPacket, fromViewer):
        isReply = False
        try:
            packet      = SLPacket(rawPacket, self.main.pktCapture.slTemplate)
            result      = self.main.msgFilter.run(fromViewer, packet)
            if result is not None:
                isReply, packet = result
                rawPacket       = str(packet)
        except Exception, e:
            Log.logException()
        return isReply, rawPacket


if __name__ == "__main__":
    scriptname  = os.path.basename(sys.argv[0])
##    filename    = os.path.splitext(scriptname)[0] + '.cfg'
    filename = 'SimProxy.cfg'
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ('-h', '-help', '--help'):
            print "%s [alternate config file]" % scriptname
            exit()
        filename = sys.argv[1]

    print "SimProxy started, hit Enter to stop..."
    sp = SimProxy(filename)
    sp.start()
    raw_input()
    sp.kill()
