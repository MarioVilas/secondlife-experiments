# Second Life UDP transport encoder and decoder
# by Mario Vilas (mvilas at gmail.com)

import struct
import time
import socket
import types

from SLTemplate import SLException, HexDumper


class SLPacketConstant:
    LL_PACKET_ID_SIZE   = 6

    LL_ACK_FLAG         = 0x10 # This packet contains appended acks.
    LL_RESENT_FLAG      = 0x20 # This packet is a resend from the source.
    LL_RELIABLE_FLAG    = 0x40 # This packet was sent reliably (implies please ack this packet)
    LL_ZERO_CODE_FLAG   = 0x80 # 0's in packet body are run length encoded, such that series of 1 to 255 zero bytes are encoded to take 2 bytes.

    FLAGS_MASK          = 0xF0

    # aliases for names given in libsecondlife
    MSG_APPENDED_ACKS   = LL_ACK_FLAG
    MSG_RESENT          = LL_RESENT_FLAG
    MSG_RELIABLE        = LL_RELIABLE_FLAG
    MSG_ZEROCODE        = LL_ZERO_CODE_FLAG


class SLPacket:

    def __init__(self, rawData = None, slTemplate = None):
##        self.id             = '\x00' * SLPacketConstant.LL_PACKET_ID_SIZE
        self.flags          = 0
        self.sequenceNumber = 0
        self.extraData      = ''
        if rawData is not None:
            self.fromString(rawData, slTemplate)

    def isReliable(self):
        return self.flags & SLPacketConstant.LL_RELIABLE_FLAG

    def isZeroEncoded(self):
        return self.flags & SLPacketConstant.LL_ZERO_CODE_FLAG

    def isResent(self):
        return self.flags & SLPacketConstant.LL_RESENT_FLAG

    def hasAppendedAcks(self):
        return self.flags & SLPacketConstant.LL_ACK_FLAG

    def isFreqHigh(self):
        return self.messageFrequency == 'High'

    def isFreqMedium(self):
        return self.messageFrequency == 'Medium'

    def isFreqLow(self):
        return self.messageFrequency == 'Low'

    def isFreqFixed(self):
        return self.messageFrequency == 'Fixed'

    def __setFlag(self, boolean, flagbit):
        if boolean:
            self.flags = self.flags | flagbit
        else:
            self.flags = self.flags & (flagbit ^ SLPacketConstant.FLAGS_MASK)

    def setReliable(self, boolean):
        self.__setFlag(boolean, SLPacketConstant.LL_RELIABLE_FLAG)

    def setZeroEncoded(self, boolean):
        self.__setFlag(boolean, SLPacketConstant.LL_RELIABLE_FLAG)

    def setResent(self, boolean):
        self.__setFlag(boolean, SLPacketConstant.LL_RELIABLE_FLAG)

    def getACKList(self):
        return self.ackList

    def setACKList(self, newlist):
        self.ackList = newlist
        self.__setFlag(len(newlist) != 0, SLPacketConstant.LL_ACK_FLAG)

    def __fromData(self, messageNameOrNumber, slTemplate):
        if type(messageNameOrNumber) in types.StringTypes:
            self.messageName    = messageNameOrNumber
            self.messageNumber  = slTemplate.getMessageNumber(self.messageName)
        elif type(messageNameOrNumber) in (types.IntType, types.LongType):
            self.messageNumber  = messageNameOrNumber
            self.messageName    = slTemplate.getMessageName(self.messageNumber)
        self.messageTemplate    = slTemplate.byNumber[self.messageNumber]
        self.messageTrust       = self.messageTemplate.trust
        self.messageFrequency   = self.messageTemplate.freq
        self.flags              = 0

    def fromDecodedData(self, messageNameOrNumber, decodedData, slTemplate):
        self.__fromData(messageNameOrNumber, slTemplate)
        if self.messageEncoding == 'Zeroencoded':
            self.setZeroEncoded(True)
        else:
            self.setZeroEncoded(False)
        self.decodedData = decodedData
        if hasattr(self, 'blockData'):
            del self.blockData
##        self.encode()

    def fromBlockData(self, messageNameOrNumber, blockData, slTemplate):
        self.__fromData(messageNameOrNumber, slTemplate)
        self.blockData = blockData
        if hasattr(self, 'decodedData'):
            del self.decodedData
##        self.decode()

    def fromString(self, rawPacket, slTemplate, decode = False):
        if len(rawPacket) < SLPacketConstant.LL_PACKET_ID_SIZE:
            raise SLException, "Packet too short"

# +-+-+-+-+----+--------+--------+--------+--------+--------+-----...-----+
# |Z|R|R|A|    |                                   |        |  Extra      |
# |E|E|E|C|    |    Sequence number (4 bytes)      | Extra  |  Header     |
# |R|L|S|K|    |                                   | (byte) | (N bytes)   |
# +-+-+-+-+----+--------+--------+--------+--------+--------+-----...-----+

        # packet header is big endian
        # the message number is big endian
        # the rest of the message is little endian

##        self.id             = rawPacket[:SLPacketConstant.LL_PACKET_ID_SIZE]
        self.flags          = struct.unpack('!B', rawPacket[0])[0]
        self.sequenceNumber = struct.unpack('!L', rawPacket[1:5])[0]
        extraDataSize       = struct.unpack('!B', rawPacket[5])[0]
        self.extraData      = rawPacket[6:extraDataSize]
        self.blockData      = rawPacket[6+extraDataSize:]

        unknownFlags = self.flags & (SLPacketConstant.FLAGS_MASK ^ 0xFF)
        if unknownFlags != 0:
            raise SLException, "Unknown flags: 0x%.2x" % unknownFlags

        self.ackList = []
        if self.hasAppendedAcks():
            ackCount        = struct.unpack('!B', self.blockData[-1])[0]
            ackData         = self.blockData[-(ackCount*4+1):-1]
            self.blockData  = self.blockData[:-(len(ackData)+1)]
            for i in range(0, len(ackData), 4):
                packedAck   = ackData[i:i+4]
                numericAck  = struct.unpack('!L', packedAck)[0]
                self.ackList.append(numericAck)

        if self.isZeroEncoded():
            self.blockData = self.zeroDecode(self.blockData)
            self.messageEncoding = 'Zerocoded'
        else:
            self.messageEncoding = 'Unencoded'

        if self.blockData:
            if self.blockData[:2] == '\xff\xff':
                self.messageFrequency   = 'Low'
                self.messageNumber      = struct.unpack('>L', self.blockData[:4])[0]
                self.blockData          = self.blockData[4:]
            elif self.blockData[0] == '\xff':
                self.messageFrequency   = 'Medium'
                self.messageNumber      = struct.unpack('>H', self.blockData[:2])[0]
                self.blockData          = self.blockData[2:]
            else:
                self.messageFrequency   = 'High'
                self.messageNumber      = struct.unpack('>B', self.blockData[0])[0]
                self.blockData          = self.blockData[1:]

        self.messageTemplate = slTemplate.byNumber[self.messageNumber]
        self.messageName     = self.messageTemplate.name
        self.messageTrust    = self.messageTemplate.trust

        if self.messageFrequency != self.messageTemplate.freq:
            if self.messageFrequency == 'Low' and self.messageTemplate.freq == 'Fixed':
                self.messageFrequency = 'Fixed'
            else:
                raise SLException, \
                    "Wrong frequency (%s) for message %s" % \
                    (self.messageFrequency, self.messageName)

        if decode:
            self.decode()

    def decode(self):
        offset, self.decodedData = \
            self.messageTemplate.decode(self.blockData, 0)
        remainder = len(self.blockData) - offset
        if remainder > 0:
            raise SLException, "Decoding error, %i bytes not decoded" % remainder
        elif remainder < 0:
            raise SLException, "Decoding error, %i bytes were missing" % -remainder
        return self.decodedData

    def encode(self):
        self.blockData = self.messageTemplate.encode(self.decodedData)
        return self.blockData

    def zeroDecode(self, data = None):
        if data is None:
            data = self.blockData
        if '\x00\x00' in data:
            d = HexDumper.dumpBlock(data, 32)
            raise SLException, "Two nulls found in zerocoded data:\n%s" % d
        if data[-1] == '\x00':
            d = HexDumper.dumpBlock(data, 32)
            raise SLException, "Trailing null found in zerocoded data:\n%s" % d
        result = ''
        i = 0
        while i < len(data):
            c = data[i]
            if c == '\x00':
                i += 1
                c = c * ord(data[i])
            result += c
            i += 1
        return result

    def zeroEncode(self, data = None):
        if data is None:
            data = self.blockData
        if '\x00\x00' in data:
            result = ''
            i = 0
            n = 0
            while i < len(data):
                c = data[i]
                if ord(c) == 0:
                    n += 1
                else:
                    result += (n * '\x00') + c
                    n = 0
            if len(result) < len(data):
                return result
        return data

    def __str__(self):
        answer  = ''
        answer += struct.pack('!B', self.flags)
        answer += struct.pack('!L', self.sequenceNumber)
        answer += struct.pack('!B', len(self.extraData))
        answer += self.extraData
        if not hasattr(self, 'blockData'):
            self.encode()
        if self.isFreqHigh():
            msgnum = struct.pack('>B', self.messageNumber)
        elif self.isFreqMedium():
            msgnum = struct.pack('>H', self.messageNumber)
        else:
            msgnum = struct.pack('>L', self.messageNumber)
        if self.isZeroEncoded():
            answer += self.zeroEncode(msgnum + self.blockData)
        else:
            answer += msgnum + self.blockData
        if self.hasAppendedAcks():
            for ack in self.ackList:
                answer += struct.pack('!L', ack)
            answer += struct.pack('!B', len(self.ackList))
##        self.id = answer[:SLPacketConstant.LL_PACKET_ID_SIZE]
        return answer

    def __repr__(self):
        return self.dump(decodeData = True)

    def dump(self, decodeData = True):
        headerSize      = SLPacketConstant.LL_PACKET_ID_SIZE
        blockDataSize   = len(self.blockData)
        extraDataSize   = len(self.extraData)
        ackSize         = len(self.ackList) * 4
        packetSize      = headerSize + blockDataSize + extraDataSize + ackSize

        if decodeData:
            if not hasattr(self, 'decodedData'):
                self.decode()
            dumpedData  = self.messageTemplate.dumpData(self.decodedData)
        else:
            dumpedData  = '  Message: %s\n' % self.messageName
            dumpedData += HexDumper.dumpBlock(self.blockData, 32)

        answer = 'PACKET %d bytes (%d header, %d data, %d acks)\n' % \
            ( packetSize, headerSize + extraDataSize, blockDataSize, ackSize )

        answer += '  Sequence: 0x%x\n' % self.sequenceNumber

        if self.flags != 0:
            answer += '  Flags:'
            if self.flags & SLPacketConstant.LL_ACK_FLAG:
                answer += ' ACK'
            if self.flags & SLPacketConstant.LL_RESENT_FLAG:
                answer += ' RESENT'
            if self.flags & SLPacketConstant.LL_RELIABLE_FLAG:
                answer += ' RELIABLE'
            if self.flags & SLPacketConstant.LL_ZERO_CODE_FLAG:
                answer += ' ZEROCODE'
            answer += '\n'

        if extraDataSize > 0:
            dumpedExtra = HexDumper.dump(self.extraData)
            if extraDataSize > 32:
                dumpedExtra = '\n' + dumpedExtra
            answer += '  Extra data (%d): %s' % \
                        ( extraDataSize, dumpedExtra )

        if ackSize > 0:
            answer += '  ACK: '
            for ack in self.ackList:
                answer += '0x.2x%, ' % ack
            answer = answer[:-2]
            answer += '\n'

        answer += dumpedData

        return answer


class ACKTracker:
    "ACK tracker"

    def __init__(self, timeout):
        self.__ack      = {}        # id -> timestamp
        self.__timeout  = timeout

    def getTimeout(self):
        return self.__timeout

    def setTimeout(self, timeout):
        self.__timeout = timeout

    def add(self, acklist):
        for ack in acklist:
            self.__ack[ack] = time.time()

    def clear(self, acklist):
        for ack in acklist:
            if self.__ack.has_key(ack):
                del self.__ack[ack]

    def needed(self):
        return self.__ack.keys()

    def expired(self):
        acklist = []
        now     = time.time()
        for ack, timestamp in self.__ack.iteritems():
            if (now - timestamp) >= self.__timeout:
                acklist.append(ack)
        return acklist


class Socket:
    "UDP socket handler"


    def __init__(self, slTemplate, timeout = 5.0):
        (
            "Class constructor\n"
            "  slTemplate: Message templates (SLTemplate)\n"
            "  timeout:    Timeout value in seconds (float)"
        )

        # message templates, needed to parse packets
        self.__slTemplate   = slTemplate

        # matches sequence numbers with outgoing packets and their destinations
        self.__sent         = {}            # seq. num -> (address, packet)

        # sequence number of the last packet for each host
        self.__last_recv    = {}            # address -> seq. num
        self.__last_sent    = {}            # address -> seq. num

        # tracks the ACKs needed for our outgoing reliable packets
        self.__ack          = ACKTracker(timeout)

        # UDP socket
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__sock.bind( ('0.0.0.0', 0) )


    def last(self, address):
        (
            "Gets the sequence number of the last packet we received"
            " from the given host, or -1 if we never received any"
            " packet at all from there"
        )
        return self.__last_recv.get(address, -1)


    def next(self, address):
        (
            "Gets the sequence number of the next packet"
            " we'll send to the given host"
        )
        return self.__last_sent.get(address, -1) + 1


    def sendto(self, packet, address):
        "Send the packet (SLPacket) to the given address (hostname, port)"

        # if the packet is meant to be sent reliably,
        #  add it to the ACK tracker
        if packet.isReliable():
            self.__ack.add(packet.sequenceNumber)
            self.__sent[packet.sequenceNumber] = (packet, address)

        # remember the last sent sequence number
        last = self.__last_sent.get(address, -1)
        if last < packet.sequenceNumber:
            self.__last_sent[address] = packet.sequenceNumber

        # send the packet
        return self.__sock.sendto(str(packet), address)


    def resend(self):
        "Resend all packets with expired ACKs"

        # get the list of expired ACKs
        acklist = self.__ack.expired()

        # for each expired ACK, resend the packet and reset the timestamp
        for ack in acklist:
            (packet, address) = self.__sent[packet.sequenceNumber]
            self.sendto(packet, address)


    def recvfrom(self):
        "Read from the socket and return a packet and it's source address"

        # read the packet from the network
        raw_packet, address = self.__sock.recvfrom(0xFFFF)
        packet = SLPacket(raw_packet, self.__slTemplate)

        # remember the last received sequence number
        last = self.__last_recv.get(address, -1)
        if last < packet.sequenceNumber:
            self.__last_recv[address] = packet.sequenceNumber

        # clear the ACKs from the server in our tracker
        if packet.hasAppendedAcks():
            self.__ack.clear(packet.ACK)
        if packet.messageName == 'PacketAck':
            packet.decode()
            acklist = []
            for ackd in packet.decodedData['Packets']:
                acklist.append(ackd['ID'])
            self.__ack.clear(acklist)

        # if the server is expecting an ACK for this packet, send it
        if packet.isReliable():
            ackdata = { 'Packets' : { 'ID' : packet.sequenceNumber } }
            ackpkt = SLPacket()
            ackpkt.fromDecodedData('PacketAck', ackdata, slTemplate)
            ackpkt.setReliable(False)
            ackpkt.sequenceNumber = self.next(address)
            ackpkt.encode()
            self.sendto(ackpkt, address)

        # return the packet and the peer address
        return packet, address
