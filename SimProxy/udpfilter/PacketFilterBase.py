class PacketFilterBase:
    def __init__(self, proxy):
        self.proxy = proxy

    # def TestMessage(self, fromViewer, packet):
    #     return None                          # ignore the packet
    #     return None, ''                      # drop the packet
    #     return False, packet                 # change the packet
    #     return True, packet                  # reply to the packet

    # don't forget to call packet.setDecodedData() or changes will be ignored
