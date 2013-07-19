# Capture file dumper
# by Mario Vilas (mvilas at gmail.com)

import sys
import os.path

from sllib.Config import Config
from sllib.Logger import Log

from SimProxy import PacketCapture

def dump(pc, binfilename, txtfilename):
    capture     = open(binfilename, 'rb').read()
    textfile    = open(txtfilename, 'w')
    packetCount = 0
    offset      = 0

    while( (len(capture) - offset) != 0 ):
        offset, entry = pc.unpack(capture, offset)
##        text = pc.dump(*entry)
        text = pc.dump(namesOnly = True, *entry)
        if text:
            textfile.write(text)
            packetCount += 1

    return packetCount

if __name__ == "__main__":
    Log.log_level = 0

    scriptname  = os.path.basename(sys.argv[0])
    if len(sys.argv) > 4 or (len(sys.argv) > 1 and sys.argv[1].lower() in ('-h', '-help', '--help')):
        print "%s [capture.bin] [capture.txt] [SimProxy.cfg]" % scriptname
        exit()

    if len(sys.argv) > 3:
        cfgfilename = sys.argv[3]
    else:
        cfgfilename = 'SimProxy.cfg'

    cfg = Config()
    cfg.read(cfgfilename)
    pc = PacketCapture(cfg)

    if len(sys.argv) > 1:
        binfilename = sys.argv[1]
    else:
        binfilename = pc.captureFile
        if not pc.binaryCapture:
            print "Capture file is already in text format: %s" % binfilename
            exit()

    if len(sys.argv) > 2:
        txtfilename = sys.argv[2]
    else:
        txtfilename = os.path.splitext(binfilename)[0] + '.txt'
        if txtfilename == binfilename:
            txtfilename = txtfilename + '.txt'

    print "Binary file: %s" % binfilename
    print "Text file:   %s" % txtfilename
    packetCount = dump(pc, binfilename, txtfilename)
    print "Dumped %d packets" % packetCount
