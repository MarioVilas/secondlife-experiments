# Second Life UDP transport encoder and decoder
# by Mario Vilas (mvilas at gmail.com)

import struct
import tokenize
import re

import SLTypes
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

    def __init__(self, rawPacket, slTemplate):
##        self.slTemplate = slTemplate
        if len(rawPacket) < SLPacketConstant.LL_PACKET_ID_SIZE:
            raise SLException, "Packet too short"

# +-+-+-+-+----+--------+--------+--------+--------+--------+-----...-----+
# |Z|R|R|A|    |                                   |        |  Extra      |
# |E|E|E|C|    |    Sequence number (4 bytes)      | Extra  |  Header     |
# |R|L|S|K|    |                                   | (byte) | (N bytes)   |
# +-+-+-+-+----+--------+--------+--------+--------+--------+-----...-----+

        # all integers in packet header are in network byte order
        # however, the message data's integers are little endian

        self.id             = rawPacket[:SLPacketConstant.LL_PACKET_ID_SIZE]
        self.flags          = struct.unpack('!B', rawPacket[0])[0]
        self.sequenceNumber = struct.unpack('!L', rawPacket[1:5])[0]
        extraDataSize       = struct.unpack('!B', rawPacket[5])[0]
        self.extraData      = rawPacket[6:extraDataSize]
        blockData           = rawPacket[6+extraDataSize:]

        if( (self.flags & (SLPacketConstant.FLAGS_MASK ^ 0xFF)) != 0 ):
            raise SLException, \
                "Unknown flags: 0x%.2x" % \
                (self.flags & SLPacketConstant.FLAGS_MASK)

        if self.flags & SLPacketConstant.LL_ZERO_CODE_FLAG:
            self.messageEncoding = 'Zerocoded'
        else:
            self.messageEncoding = 'Unencoded'

        self.ACK = []
        if self.hasAppendedAcks():
            remainingAcks       = struct.unpack('!B', blockData[len(blockData)-1])[0]
            posOfAck            = len(blockData)-4
            while remainingAcks > 0:
                remainingAcks   = remainingAcks - 1
                posOfAck        = posOfAck - 4
                packedAck       = blockData[ posOfAck + 4 : posOfAck + 8 ]
                numericAck      = struct.unpack('!L', packedAck)[0]
                self.ACK.append(numericAck)
            blockData           = blockData[:posOfAck]

        if blockData:
##            b = ord(blockData[0])
            b = struct.unpack('>B', blockData[0])[0]
            if b != 0xFF:
                self.messageFrequency       = 'High'
                self.messageNumber          = b
                blockData                   = blockData[1:]
            else:
##                b = ord(blockData[1])
                b = struct.unpack('>B', blockData[1])[0]
                if b != 0xFF:
                    self.messageFrequency   = 'Medium'
                    self.messageNumber      = struct.unpack('>H', blockData[:2])[0]
                    blockData               = blockData[2:]
                else:
                    self.messageFrequency   = 'Low'
                    self.messageNumber      = struct.unpack('>L', blockData[:4])[0]
                    blockData               = blockData[4:]

        self.blockData = blockData

        self.messageTemplate = slTemplate.byNumber[self.messageNumber]
        self.messageName     = self.messageTemplate.name
        self.messageTrust    = self.messageTemplate.trust

        if self.messageFrequency != self.messageTemplate.freq:
            if self.messageFrequency == 'Low' and self.messageTemplate.freq == 'Fixed':
                self.messageFrequency = 'Fixed'
            else:
                raise Exception, \
                    "Wrong frequency (%s) for message %s" % \
                    (self.messageFrequency, self.messageName)

    def decode(self):
        if self.isZeroEncoded():
            raise SLException, "Zeroencoding not supported"   # XXX
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

    def __str__(self):
        if self.messageEncoding == 'Zeroencoded':
            self.flags = self.flags | SLPacketConstant.LL_ZERO_CODE_FLAG
        else:
            self.flags = self.flags & \
             (SLPacketConstant.LL_ZERO_CODE_FLAG ^ SLPacketConstant.FLAGS_MASK)
        answer  = ''
        answer += struct.pack('!B', self.flags)
        answer += struct.pack('!L', self.sequenceNumber)
        answer += struct.pack('!B', len(self.extraData))
        answer += self.extraData
        if self.isFreqHigh():
            answer += struct.pack('>B', self.messageNumber)
        elif self.isFreqMedium():
            answer += struct.pack('>H', self.messageNumber)
        else:
            answer += struct.pack('>L', self.messageNumber)
        if not hasattr(self, 'blockData'):
            self.encode()
        answer += self.blockData
        self.id = answer[:SLPacketConstant.LL_PACKET_ID_SIZE]
        return answer

    def __repr__(self):
        return self.dump(dumpData = True, decodeData = True)

    def dump(self, decodeData = True):
        headerSize      = SLPacketConstant.LL_PACKET_ID_SIZE
        blockDataSize   = len(self.blockData)
        extraDataSize   = len(self.extraData)
        ackSize         = len(self.ACK) * 4
        packetSize      = headerSize + blockDataSize + extraDataSize + ackSize

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
            answer += '  ACK: %r\n' % self.ACK

        if decodeData:
            if not hasattr(self, 'decodedData'):
                self.decode()
            dumpedData = self.messageTemplate.dumpData(self.decodedData)
        else:
            answer += '  Message: %s\n' % self.messageName
            dumpedData = HexDumper.dumpBlock(self.blockData, 32)
        answer += dumpedData

        return answer
