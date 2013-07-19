# Second Life UDP message filters dispatcher
# by Mario Vilas (mvilas at gmail.com)

from Logger import Log
from Dispatcher import Dispatcher

import udpfilter
from udpfilter.PacketFilterBase import PacketFilterBase

__all__ = ["SLPacketFilter"]

class SLPacketFilter(Dispatcher):

    def __init__(self, main):
        self.main = main
        Dispatcher.__init__(self, udpfilter, PacketFilterBase)

    def run(self, fromViewer, packet):
        isReply     = False
        name        = packet.messageName
        filterlist  = self.getFilters(name)
        if fromViewer:
            Log(4, "Received viewer message %s" % name)
        else:
            Log(4, "Received sim message %s" % name)
        if len(filterlist) > 0:
            if fromViewer:
                Log(3, "Filtering viewer message %s" % name)
            else:
                Log(3, "Filtering sim message %s" % name)
            for fn in filterlist:
                result = fn(fromViewer, packet)
                if result is None:  continue        # ignore the packet
                isReply, packet = result
                if not packet:      break           # drop the packet
                if isReply:         break           # send a fake reply
                if packet.messageName != name:
                    return self.run(fromViewer, packet)
        return isReply, packet                      # change the packet
