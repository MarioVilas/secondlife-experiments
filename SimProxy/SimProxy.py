# Second Life sim proxy
# by Mario Vilas (mvilas at gmail.com)

import sys
import os.path
import ConfigParser
import socket
import select
import time
import struct
import thread
import threading
import xmlrpclib

from Logger import Log, loadLogFileSettings
from XMLRPCServer import XMLRPCServer
from MessageFilter import MessageFilterDispatcher
from SLTemplate import SLTemplate, HexDumper
from SLPacket import SLPacket
import SLTypes


class SimProxy:
    section = 'SimProxy'

    def __init__(self, configFilename):
        self.cfg = ConfigParser.SafeConfigParser()
        self.cfg.read(configFilename)

    def start(self):
        loadLogFileSettings(self.cfg)

        self.loadCaptureSettings()
        self.loadMessageTemplate()
        self.loadMessageFilters()

        self.sims           = {}                # (ip, port) -> sim
        self.lock           = threading.RLock()
        self.active         = True

        self.bindAddress    = self.cfg.get(self.section,    'bindAddress')
        self.simHost        = self.cfg.get(self.section,    'simHost')

        try:
            self.bindAddress = socket.gethostbyname(self.bindAddress)
        except Exception, e:
            pass

        try:
            self.simHost    = socket.gethostbyname(self.simHost)
        except Exception, e:
            pass

        if self.cfg.has_option(self.section,                'proxyBindPort'):
            proxyBindPort   = self.cfg.getint(self.section, 'proxyBindPort')
            proxyList       = self.cfg.get(self.section,    'proxyList')
            proxyList       = proxyList.replace(' ','').split(',')
            for proxySim in proxyList:
                if proxySim == '': continue
                proxySim    = proxySim.split(':')
                proxySim    = proxySim[0], int(proxySim[1])
                try:
                    proxySim    = (socket.gethostbyname(proxySim[0]), proxySim[1])
                except Exception, e:
                    pass
                proxyBindPort   = self.newSim(proxySim, proxyBindPort)[1]
                proxyBindPort   = proxyBindPort + 1

        if self.cap_filename:
            Log(1, "Storing captured packets in %s" % self.cap_filename)
            self.cap_file   = open(self.cap_filename, 'a+b')
        else:
            self.cap_file       = None

        self.server = XMLRPCServer(self, 'XMLRPC')
        self.server.register_function(self.newSim)
        self.server.start()
        Log(1, "SimProxy loaded successfully")

    def kill(self):
        Log(1, "Shutting down SimProxy...")
        self.active = False
##        self.lock.acquire()
        while self.sims:
            sim = self.sims[ self.sims.keys()[0] ].kill()
##        self.lock.release()
        Log(1, "Shut down SimProxy")

    def loadMessageTemplate(self):
        templateFile        = self.cfg.get(self.section,    'messageTemplate')
        self.slTemplate     = SLTemplate(templateFile)

    def loadMessageFilters(self):
        self.msgFilter      = MessageFilterDispatcher(self)

    def loadCaptureSettings(self):
        section             = 'SimProxy'

        if self.cfg.has_option(self.section,                'captureFile'):
            self.cap_filename   = self.cfg.get(self.section,'captureFile')
        else:
            self.cap_filename   = ''

        cap_fmt = self.cfg.get(self.section,                'captureFormat')
        cap_fmt = cap_fmt.lower()
        if   cap_fmt == 'binary':
            self.binaryCapture  = True
        elif cap_fmt == 'text':
            self.binaryCapture  = False
        else:
            raise Exception, "Unknown capture file format: %s" % cap_fmt

        self.storeResent    = self.cfg.getboolean(self.section, 'storeResent')
        self.storeBad       = self.cfg.getboolean(self.section, 'storeBad')

        if self.cfg.has_option(self.section,                 'allowCapture'):
            self.allowCapture   = self.cfg.get(self.section, 'allowCapture')
        else:
            self.allowCapture   = ''
        if self.cfg.has_option(self.section,                 'blockCapture'):
            self.blockCapture   = self.cfg.get(self.section, 'blockCapture')
        else:
            self.blockCapture   = ''

        self.allowCapture   = self.allowCapture.replace(' ','').split(',')
        self.blockCapture   = self.blockCapture.replace(' ','').split(',')

        while '' in self.allowCapture:
            self.allowCapture.remove('')
        while '' in self.blockCapture:
            self.blockCapture.remove('')

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

        self.isBlacklist    = (self.allowCapture == ['*'])

    def newSim(self, simAddr, bindPort = 0):
        simAddr = simAddr[0], int(simAddr[1])
        if self.active:
            self.lock.acquire()
            sim = self.sims.get(simAddr, None )
            if sim is None:
                sim = Sim(self, simAddr, bindPort)
            self.lock.release()
            return self.simHost, sim.bindPort
        raise Exception, "SimProxy is no longer running"

    def sniff(self, rawPacket, fromAddr, toAddr):
        if self.cap_file:
            if self.allowCapture != ['*']:
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
                s = self.pack(time.time(), fromAddr, toAddr, rawPacket)
            else:
                s = self.dump(time.time(), fromAddr, toAddr, rawPacket)
            self.lock.acquire()
            self.cap_file.write(s)
            self.lock.release()

    @staticmethod
    def pack(timestamp, fromAddr, toAddr, rawPacket):
        timestamp   = SLTypes.F32.encode(timestamp)
        fromIP      = SLTypes.IPADDR.encode(fromAddr[0])
        fromPort    = SLTypes.IPPORT.encode(fromAddr[1])
        toIP        = SLTypes.IPADDR.encode(toAddr[0])
        toPort      = SLTypes.IPPORT.encode(toAddr[1])
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
            raise                                           # XXX
            s += 'Exception: %s\n' % str(e)
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
            s += 'Exception: %s\n' % str(e)
            try:
                s += packet.dump(decodeData = False)
            except Exception, e:
                s += 'Exception: %s\n' % str(e)
                s += 'PACKET (%d bytes)\n' % len(rawPacket)
                s += HexDumper.dumpBlock(rawPacket, 32)
        s += '\n'
        return s


class Sim:

    def __init__(self, proxy, simAddr, bindPort = 0):
        self.proxy      = proxy
        self.simAddr    = simAddr

        self.addrToSock = {}  # (client ip, client port) -> socket
        self.sockToAddr = {}  # socket -> (client ip, client port)

        self.loggedErrorForSock = {}

        self.serverSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.serverSock.bind( (self.proxy.bindAddress, bindPort) )

        self.bindAddress    = self.proxy.bindAddress
        self.bindPort       = self.serverSock.getsockname()[1]

        self.active     = True
        self.event      = threading.Event()
        self.event.clear()

        thread.start_new_thread(Sim.run, (self,))

    def kill(self):
        Log(1, "Shutting down Sim %s:%d..." % self.simAddr)
        self.active = False
        try:
            del self.proxy.sims[self.simAddr]
        except KeyError, e:
            pass
        self.event.wait(2.0)

    def suicide(self):
        Log(1, "Shutting down Sim %s:%d..." % self.simAddr)
        self.active = False
        try:
            del self.proxy.sims[self.simAddr]
        except KeyError, e:
            pass

    def run(self):
        Log(1, "New Sim %s:%d proxied on port %d" % (self.simAddr + (self.bindPort,)))

        # main loop
        try:
            while self.active:

                # select all sockets
                socketList = [ self.serverSock ] + self.sockToAddr.keys()
                socketList = select.select(socketList, [], [], 1.0)[0]

                # proxy data client -> server
                if self.serverSock in socketList:
                    socketList.remove(self.serverSock)
                    try:
                        self.proxyClientToServer()
                    except Exception, e:
##                        raise       # XXX
                        pass

                # proxy data server -> client
                for clientSocket in socketList:
                    try:
                        self.proxyServerToClient(clientSocket)
                    except Exception, e:
##                        raise       # XXX
                        pass

        # clean up
        finally:

            # close all sockets
            self.serverSock.close()
            for clientSock in self.sockToAddr.keys():
                clientSock.close()
            self.addrToSock = {}
            self.sockToAddr = {}

            # signal we're done cleaning up
            self.event.set()

            Log(1, "Shut down Sim %s:%d" % self.simAddr)

    def connectClient(self, clientAddr):
##        print "connectClient", clientAddr, self.simAddr         # XXX
        clientSock = self.addrToSock.get(clientAddr, None)
        if clientSock is None:
            clientSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            clientSock.bind( ('0.0.0.0', 0) )
##            clientSock.connect(self.simAddr)
            self.addrToSock[clientAddr] = clientSock
            self.sockToAddr[clientSock] = clientAddr
            Log(1,
                "Client %s:%d connected to Sim %s:%d" % \
                (clientAddr + self.simAddr)
                )
        return clientSock

    def disconnectClient(self, clientSock):
##        print "disconnectClient", clientSock.fileno()           # XXX
        toAddr = self.sockToAddr[clientSock]
        del self.addrToSock[toAddr]
        del self.sockToAddr[clientSock]

    def proxyClientToServer(self):
##        print "proxyClientToServer", self.serverSock.fileno()   # XXX
        try:
            rawPacket, fromAddr = self.serverSock.recvfrom(65535)
        except Exception, e:
            self.logErrorForSock(
                self.serverSock,
                "proxyClientToServer (reading from client): %s" % str(e)
                )
            self.suicide()
            raise
        toAddr = self.simAddr
        self.proxy.sniff(rawPacket, fromAddr, toAddr)
        self.filterClientToServer(rawPacket, fromAddr, toAddr)
        try:
            clientSock = self.connectClient(fromAddr)
        except Exception, e:
            self.logErrorForSock(
                self.serverSock,
                "proxyClientToServer (connecting to server): %s" % str(e)
                )
            raise
        try:
            sentBytes = clientSock.sendto(rawPacket, toAddr)
        except Exception, e:
            self.logErrorForSock(
                self.serverSock,
                "proxyClientToServer (writing to server): %s" % str(e)
                )
            self.disconnectClient(clientSock)
            raise

    def proxyServerToClient(self, clientSock):
##        print "proxyServerToClient", clientSock.fileno()        # XXX
        try:
            rawPacket, fromAddr = clientSock.recvfrom(65535)
        except Exception, e:
            self.logErrorForSock(
                self.serverSock,
                "proxyServerToClient (reading from server): %s" % str(e)
                )
            self.disconnectClient(clientSock)
            raise
        toAddr = self.sockToAddr[clientSock]
        self.proxy.sniff(rawPacket, fromAddr, toAddr)
        self.filterServerToClient(rawPacket, fromAddr, toAddr)
        try:
            sentBytes = self.serverSock.sendto(rawPacket, toAddr)
        except Exception, e:
            self.logErrorForSock(
                self.serverSock,
                "proxyServerToClient (writing to client): %s" % str(e)
                )
            self.suicide()
            raise

    def __filterPacket(self, isClient, rawPacket, fromAddr, toAddr):
        try:
            packet = SLPacket(rawPacket, self.proxy.slTemplate)
            params = (packet, fromAddr, toAddr)
            result = self.proxy.msgFilter.run(self.proxy, isClient, *params)
            (newPacket, fromAddr, toAddr) = result
            if newPacket != packet:
                rawPacket = str(newPacket)
            return (rawPacket, fromAddr, toAddr)
        except Exception, e:
            raise                       # XXX
            return params

    def filterClientToServer(self, *listArgs, **dictArgs):
        self.__filterPacket(True, *listArgs, **dictArgs)

    def filterServerToClient(self, *listArgs, **dictArgs):
        self.__filterPacket(False, *listArgs, **dictArgs)

    def logErrorForSock(self, sock, errtext):
        if not self.loggedErrorForSock.has_key(sock):
            self.loggedErrorForSock[sock] = None
            try:
                Log(1, "Socket %d: %s" % (sock.fileno(), errtext))
            except Exception, e:
                pass


if __name__ == "__main__":
    scriptname  = os.path.basename(sys.argv[0])
    filename    = os.path.splitext(scriptname)[0] + '.cfg'
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
