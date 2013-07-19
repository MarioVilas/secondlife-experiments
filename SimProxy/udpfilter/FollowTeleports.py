from PacketFilterBase import *

class FollowTeleportsFilter(PacketFilterBase):
    
    def __newSim(self, packet, info_key, ip_key, port_key):
        decodedData             = packet.getDecodedData()
        circuit_info            = decodedData[info_key]
        sim_ip                  = circuit_info[ip_key]
        sim_port                = circuit_info[port_key]
        new_ip, new_port        = self.proxy.newSim( (sim_ip, sim_port) )
        circuit_info[ip_key]    = new_ip
        circuit_info[port_key]  = new_port
        packet.setDecodedData(decodedData)
        return packet

    def OpenCircuit(self, fromViewer, packet):
        if not fromViewer:
            packet = self.__newSim(packet, 'CircuitInfo', 'IP', 'Port')
            return False, packet

    def CrossedRegion(self, fromViewer, packet):
        if not fromViewer:
            packet = self.__newSim(packet, 'RegionData', 'SimIP', 'SimPort')
            return False, packet

    def EnableSimulator(self, fromViewer, packet):
        if not fromViewer:
            packet = self.__newSim(packet, 'SimulatorInfo', 'IP', 'Port')
            return False, packet

    def TeleportFinish(self, fromViewer, packet):
        if not fromViewer:
            packet = self.__newSim(packet, 'Info', 'SimIP', 'SimPort')
            return False, packet

##    def TeleportProgress(self, fromViewer, packet):
##        if not fromViewer:
##            message = 'All your base are belong to us\x00'
##            decodedData = packet.getDecodedData()
##            decodedData['Info']['Message'] = message
##            packet.setDecodedData(decodedData)
##            return False, packet
