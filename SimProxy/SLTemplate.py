# Second Life message encoder and decoder
# by Mario Vilas (mvilas at gmail.com)

from struct import pack, unpack

import SLTypes
from Logger import Log


class HexDumper:

    @staticmethod
    def dump(rawPacket, boundary = 16):
        if boundary is None:
            boundary = len(rawPacket)
        s = ''
        for i in range(0, len(rawPacket), boundary):
            for c in rawPacket[i:i+boundary]:
                s += '%.2x ' % ord(c)
            s += '\n'
        s += '\n'
        return s

    @staticmethod
    def dumpBlock(rawPacket, boundary = 16):
        if boundary is None:
            boundary = len(rawPacket)
        s = '{\n\t'
        for i in range(0, len(rawPacket), boundary):
            for c in rawPacket[i:i+boundary]:
                s += '%.2x ' % ord(c)
            s += '\n\t'
        s = s[:len(s)-1]
        s += '}\n'
        return s

    @staticmethod
    def stringC(data):
        data = data.replace('\\', '\\\\')
        data = data.replace('\'', '\\\'')
        data = data.replace('\"', '\\\"')
        data = data.replace('\r', '\\r')
        data = data.replace('\n', '\\n')
        data = data.replace('\t', '\\t')
        data = data.replace('\x00', '\\0')
        return "'%s'" % data

    @classmethod
    def stringRepr(cls, data):
        if repr(data) == ("'%s'" % data):
            return data
        cstr = cls.stringC(data)
        if repr(cstr) == ("%s" % cstr.replace('\\', '\\\\')):
            return cstr
        data = HexDumper.dump(data, None)
        data = data.replace('\n', '')
        data = '< %s >' % data
        return data


class SLException(Exception):
    pass


class SLTemplate:
#    {
#    	TestMessage Low 1 NotTrusted Zerocoded
#    	{
#    		TestBlock1		Single
#    		{	Test1		U32	}
#    	}
#    	{
#    		NeighborBlock		Multiple		4
#    		{	Test0		U32	}
#    		{	Test1		U32	}
#    		{	Test2		U32	}
#    	}
#    }

    # format strings to print messages in a "nice" way
    fmtHeaderStart = (
                '{\n'
                '\t%(messageName)s'
                '\t%(messageFrequency)s'
                '\t%(messageRelativeNumber)s'
                '\t%(messageTrust)s'
                '\t%(messageEncoding)s'
                '\n'
                )
    fmtSingleBlockStart  = (
                '\t{\n'
                '\t\t%(blockName)s\t%(blockType)s\n'
                )
    fmtMultiBlockStart   = (
                '\t{\n'
                '\t\t%(blockName)s\t%(blockType)s\t%(blockCount)s\n'
                )
    fmtSingleParameter = (
                '\t\t{\t'
                '%(parameterName)s\t%(parameterType)s'
                '\t}\n'
                )
    fmtMultiParameter = (
                '\t\t{\t'
                '%(parameterName)s\t%(parameterType)s\t%(parameterCount)s'
                '\t}\n'
                )
    fmtParameterValue = (
                '\t\t{\t'
                '%(parameterName)s\t%(parameterValue)s'
                '\t}\n'
                )
    fmtBlockEnd  = (
                '\t}\n'
                )
    fmtHeaderEnd = (
                '}\n'
                )

    # valid frequency labels
    freqLabels        = [
                        "Low",
                        "Medium",
                        "High",
                        "Fixed",
                        ]

    # valid trust labels
    trustLabels       = [
                        "NotTrusted",
                        "Trusted",
                        ]

    # valid encoding labels
    encodingLabels    = [
                        "Unencoded",
                        "Zerocoded",
                        ]

    # valid block types
    blockTypes        = [
                        "Single",
                        "Multiple",
                        "Variable",
                        ]

    def __init__(self, filename):
        self.byNumber   = {}
        self.byName     = {}

        # read the text file
        sig_found = False
        text = ''
        Log.log(1, "Reading message template %s" % filename)
        fd = open(filename, 'r')
        linecount = 0
        for line in fd:
            line = line.split('//')[0]      # remove comments
            line = line.strip()             # remove leading and trailing whitespace
            line = line.replace('\t', ' ')  # replace tabs for spaces
            while 1:                        # coalesce spaces
                new  = line.replace('  ', ' ')
                if new == line: break
                line = new
            line = line.replace(' {', '{')  # strip spaces before opening brackets
            line = line.replace('{ ', '{')  # strip spaces after opening brackets
            line = line.replace(' }', '}')  # strip spaces before closing brackets
            line = line.replace('} ', '}')  # strip spaces after closing brackets
            if not sig_found and line.startswith('version'):
                sig_found = True
                if line != 'version 2.0':
                    raise SLException, "Uncompatible message template format: %s" % line
                continue                    # skip the version line
            text += line
            linecount += 1

        ###########################
##        firstSlice  = 'RpcChannelRequest'
##        lastSlice   = 'RpcScriptReplyInbound'
##        slicingNow  = False
        ###########################

        # message definition
        msgcount_low    = 0
        msgcount_medium = 0
        msgcount_high   = 0
        msgcount_fixed  = 0
        while text:
            if text[0] == '}':
                break
            if text[0] != '{':
                raise SLException, "Parsing error"
            text = text[1:]
            p = text.find('{')
            q = text.find('}')
            if p == -1:
                raise SLException, "Parsing error"

            # message has no blocks
            if p > q:       
                header = text[:q]
                text = text[q+1:]
                name, freq, number, trust, encoding = header.split(' ')
                ###########################
##                if not slicingNow:
##                    if name == firstSlice:
##                        slicingNow = True
##                else:
##                    print "%s," % name,
##                    if name == lastSlice:
##                        slicingNow = False
####                if name.lower().find('god') != -1:
####                    print "%s," % name,
                ###########################
                if freq not in self.freqLabels:
                    raise SLException, "Bad frequency label: %s" % freq
                if trust not in self.trustLabels:
                    raise SLException, "Bad trust label: %s" % freq
                if encoding not in self.encodingLabels:
                    raise SLException, "Bad encoding label: %s" % freq
                if   freq == 'Low':
                    msgcount_low += 1
                elif freq == 'Medium':
                    msgcount_medium += 1
                elif freq == 'High':
                    msgcount_high += 1
                elif freq == 'Fixed':
                    msgcount_fixed += 1
                snumber = number
                if snumber[:2] == '0x':
                    number = long(snumber[2:], 0x10)
                else:
                    number = long(snumber)
                if number == 0:
                    raise SLException, "Bad message number: %s" % snumber
                if freq in ('High', 'Fixed'):
                    msgnum = number
                elif freq == 'Medium':
                    msgnum = number + 0xFF00L
                elif freq == 'Low':
                    msgnum = number + 0xFFFF0000L
                msg = SLMessage(name, freq, msgnum, trust, encoding)
                self.byNumber[msgnum]   = msg
                self.byName[name]       = msg
                continue

            # message has blocks
            header = text[:p]
            text = text[p:]
            name, freq, number, trust, encoding = header.split(' ')
            ###########################
##            if not slicingNow:
##                if name == firstSlice:
##                    slicingNow = True
##            else:
##                print "%s," % name,
##                if name == lastSlice:
##                    slicingNow = False
####            if name.lower().find('god') != -1:
####                print "%s," % name,
            ###########################
            if freq not in self.freqLabels:
                raise SLException, "Bad frequency label: %s" % freq
            if trust not in self.trustLabels:
                raise SLException, "Bad trust label: %s" % freq
            if encoding not in self.encodingLabels:
                raise SLException, "Bad encoding label: %s" % freq
            if   freq == 'Low':
                msgcount_low += 1
            elif freq == 'Medium':
                msgcount_medium += 1
            elif freq == 'High':
                msgcount_high += 1
            elif freq == 'Fixed':
                msgcount_fixed += 1
            snumber = number
            if snumber[:2] == '0x':
                number = long(snumber[2:], 0x10)
            else:
                number = long(snumber)
            if number == 0:
                raise SLException, "Bad message number: %s" % snumber
            if freq in ('High', 'Fixed'):
                msgnum = number
            elif freq == 'Medium':
                msgnum = number + 0xFF00L
            elif freq == 'Low':
                msgnum = number + 0xFFFF0000L
            msg = SLMessage(name, freq, msgnum, trust, encoding)
            self.byNumber[msgnum]   = msg
            self.byName[name]       = msg

            # block definitions
            while 1:
                if text[0] == '}':
                    break
                if text[0] != '{':
                    raise SLException, "Parsing error"
                text = text[1:]
                p = text.find('{')
                q = text.find('}')
                if p == -1 or p > q:
                    raise SLException, "Parsing error"
                header = text[:p]
                text = text[p:]
                header = header.split(' ')
                name = header[0]
                bltype = header[1]
                if bltype not in self.blockTypes:
                    raise SLException, "Bad block type: %s" % bltype
                if bltype == 'Multiple':
                    if len(header) != 3:
                        raise SLException, "Parsing error"
                    count = long(header[2])
                    if count == 0:
                        raise SLException, "Bad block count: %s" % header[2]
                else:
                    if len(header) != 2:
                        raise SLException, "Parsing error"
                    count = 1
                blk = SLBlock(name, bltype, count)
                msg.blocks.append(blk)

                # parameter definitions
                while 1:
                    if text[0] == '}':
                        break
                    if text[0] != '{':
                        raise SLException, "Parsing error"
                    text = text[1:]
                    p = text.find('{')
                    q = text.find('}')
                    if p < q and p != -1:
                        print text[:100]
                        raise SLException, "Parsing error"
                    header = text[:q]
                    text = text[q+1:]
                    header = header.split(' ')
                    name = header[0]
                    ptype = header[1]
                    if ptype in ('Fixed', 'Variable'):
                        if len(header) != 3:
                            raise SLException, "Parsing error"
                        size = long(header[2])
                        if size == 0:
                            raise SLException, "Bad parameter count: %s" % header[2]
                    else:
                        if len(header) != 2:
                            raise SLException, "Parsing error"
                        size = None
                    try:
                        pclass = getattr(SLTypes, ptype)
                    except SLException, e:
                        raise SLException, "Bad parameter type: %s" % ptype
                    prm = SLParameter(name, ptype, pclass, size)
                    blk.parameters.append(prm)

                # closing bracket of each block definition
                if text[0] != '}':
                    raise SLException, "Parsing error"
                text = text[1:]

            # closing bracket of each message definition
            if text[0] != '}':
                raise SLException, "Parsing error"
            text = text[1:]

        Log.log(1,
            "%d lines read, "
            "%d messages found "
            "(Low: %d, Medium: %d, High: %d, Fixed: %d)" % (
                linecount,
                msgcount_low + msgcount_medium + msgcount_high + msgcount_fixed,
                msgcount_low,
                msgcount_medium,
                msgcount_high,
                msgcount_fixed
                )
            )

    def dump(self, filename):
        text = ''

        # for each message...
        messageList = self.byNumber.keys()
        messageList.sort()
        for messageNumber in messageList:
            messageTemplate             = self.byNumber[messageNumber]
            messageName                 = messageTemplate.name
            messageFrequency            = messageTemplate.freq
            messageTrust                = messageTemplate.trust
            messageEncoding             = messageTemplate.encoding
            if   messageFrequency == 'High':
                messageRelativeNumber   = str(messageNumber)
            elif messageFrequency == 'Medium':
                messageRelativeNumber   = str(messageNumber - 0xFF00L)
            elif messageFrequency == 'Low':
                messageRelativeNumber   = str(messageNumber - 0xFFFF0000L)
            elif messageFrequency == 'Fixed':
                messageRelativeNumber   = hex(messageNumber)
            else:
                raise SLException, "Who's been messing with the templates?"
            text                       += self.fmtHeaderStart % vars()

            # for each block...
            for blockTemplate in messageTemplate.blocks:
                blockName               = blockTemplate.name
                blockType               = blockTemplate.bltype
                if blockType == 'Multiple':
                    blockCount          = blockTemplate.count
                    text               += self.fmtMultiBlockStart % vars()
                else:
                    text               += self.fmtSingleBlockStart % vars()

                # for each parameter...
                for parameterTemplate in blockTemplate.parameters:
                    parameterName       = parameterTemplate.name
                    parameterType       = parameterTemplate.ptype
                    if parameterType in ('Variable', 'Fixed'):
                        parameterCount  = parameterTemplate.size
                        text           += self.fmtMultiParameter % vars()
                    else:
                        text           += self.fmtSingleParameter % vars()

                # end of block
                text                   += self.fmtBlockEnd % vars()

            # end of message
            text                       += self.fmtHeaderEnd % vars()

        # write the text template to disk
        open(filename, 'w').write(text)
        return text

    def getMessageName(self, messageNumber):
        if not self.byNumber.has_key(messageNumber):
            raise SLException, "Invalid message number: %s" % messageNumber
        return self.byNumber[messageNumber].name

    def getMessageNumber(self, messageName):
        if not self.byName.has_key(messageName):
            raise SLException, "Invalid message name: %s" % messageName
        return self.byName[messageName].number


class SLMessage:

    def __init__(self, name, freq, number, trust, encoding):
        self.name, self.freq, self.number, self.trust, self.encoding = \
            name, freq, number, trust, encoding
        self.blocks = []

    def decode(self, data, offset = 0):
        answer = {}
        for blockTemplate in self.blocks:
            offset, block = blockTemplate.decode(data, offset)
            answer[blockTemplate.name] = block
        return offset, answer

    def encode(self, value):
        answer = ''

        if   self.freq == 'High':
            answer += struct.pack('<B', self.number)
        elif self.freq == 'Medium':
            answer += struct.pack('<H', self.number)
        else:
            answer += struct.pack('<L', self.number)

        for blockTemplate in self.blocks:
            answer += blockTemplate.encode(value[blockTemplate.name])

##        if self.encoding == 'Zeroencode':
##            raise SLException, "Zeroencode not supported"     # XXX

        return answer

    def dumpData(self, decodedData):
        messageTemplate = self
        text = ''

        # decode one message
        messageNumber                   = messageTemplate.number
        messageName                     = messageTemplate.name
        messageFrequency                = messageTemplate.freq
        messageTrust                    = messageTemplate.trust
        messageEncoding                 = messageTemplate.encoding
        if   messageFrequency == 'High':
            messageRelativeNumber       = str(messageNumber)
        elif messageFrequency == 'Medium':
            messageRelativeNumber       = str(messageNumber - 0xFF00L)
        elif messageFrequency == 'Low':
            messageRelativeNumber       = str(messageNumber - 0xFFFF0000L)
        elif messageFrequency == 'Fixed':
            messageRelativeNumber       = hex(messageNumber)
        else:
            raise SLException, "Who's been messing with the templates?"
        text                           += SLTemplate.fmtHeaderStart % vars()

        # for each block...
        for blockTemplate in messageTemplate.blocks:
            blockName                   = blockTemplate.name
            blockType                   = blockTemplate.bltype
            if blockType == 'Multiple':
                blockCount              = blockTemplate.count
            else:
                blockCount              = 1

            # for each block's chunk...
            for i in range(blockCount):
                if blockType == 'Multiple':
                    text               += SLTemplate.fmtMultiBlockStart % vars()
                else:
                    text               += SLTemplate.fmtSingleBlockStart % vars()
                if blockType == 'Single':
                    blockData           = decodedData[blockName]
                else:
                    blockData           = decodedData[blockName][i]

                # for each parameter...
                for parameterTemplate in blockTemplate.parameters:
                    parameterName       = parameterTemplate.name
                    parameterType       = parameterTemplate.ptype
                    parameterValue      = blockData[parameterName]

                    # represent according to data type
                    parameterValue      = parameterTemplate.dump(parameterValue)

                    # end of parameter
                    text               += SLTemplate.fmtParameterValue % vars()

                # end of block
                text                   += SLTemplate.fmtBlockEnd % vars()

        # end of message
        text                           += SLTemplate.fmtHeaderEnd % vars()

        # return the text
        return text


class SLBlock:

    def __init__(self, name, bltype, count):
        self.name, self.bltype, self.count = name, bltype, count
        self.parameters = []

    def decode(self, data, offset):
        if self.bltype == 'Single':
            answer = {}
            for parameterTemplate in self.parameters:
                offset, value = parameterTemplate.decode(data, offset)
                answer[parameterTemplate.name] = value
        else:
            answer = []
            if self.bltype == 'Multiple':
                count = self.count
            elif self.bltype == 'Variable':
                offset, count = SLTypes.U8.decode(data, offset)
            else:
                raise SLException, "Who's been messing with the templates?"
            for i in range(count):
                block = {}
                for parameterTemplate in self.parameters:
                    offset, value = parameterTemplate.decode(data, offset)
                    block[parameterTemplate.name] = value
                answer.append(block)
        return offset, answer

    def encode(self, value):
        answer = ''
        if self.bltype == 'Single':
            for parameterTemplate in self.parameters:
                data = value[parameterTemplate.name]
                answer += parameterTemplate.encode(data)
        else:
            count = len(value)
            if self.bltype == 'Multiple':
                if count != self.count:
                    raise SLException, "Bad block length: %i" % count
            elif self.bltype == 'Variable':
                answer += SLTypes.U8.encode(count)
            else:
                raise SLException, "Who's been messing with the templates?"
            for block in value:
                for parameterTemplate in self.parameters:
                    answer += parameterTemplate.encode(block)
        return answer


class SLParameter:

    def __init__(self, name, ptype, pclass, size = None):
        self.name, self.ptype, self.pclass, self.size = \
            name, ptype, pclass, size

    def decode(self, data, offset):
        if self.ptype in ('Variable', 'Fixed'):
            return self.pclass.decode(data, offset, self.size)
        return self.pclass.decode(data, offset)

    def encode(self, value):
        if self.ptype in ('Variable', 'Fixed'):
            return self.pclass.encode(value, self.size)
        return self.pclass.encode(value)

    def dump(self, value):
        if type(value) == type(0L):
            return hex(value)
        if type(value) == type(0):
            if  self.name.endswith('Handle') or \
                self.name.endswith('Flags') or \
                self.name.endswith('ID') or \
                self.name == 'CRC':
                    return hex(value)
        if self.ptype == 'LLUUID':
            return str(value)
        return repr(value)


# some testing code
if __name__ == '__main__':
    slt = SLTemplate('templates/1.18.1.2.txt')
    slt.dump('testTemplate.txt')
