from PacketFilterBase import *

class PrivacyFilter(PacketFilterBase):

    def TrackAgent(self, fromViewer, packet):
        if fromViewer:
            return None, ''                     # drop the packet

    def ViewerStats(self, fromViewer, packet):
        if fromViewer:
            return None, ''                     # drop the packet
