# HTTP capture file dumper
# by Mario Vilas (mvilas at gmail.com)

import sys
import os.path
import struct
import zlib

##from sllib import SLTypes
from sllib.Config import Config
from sllib.Logger import Log

from CapProxy import CapProxyCapture


class DumpHTTP:

    def dump(self, binfilename, txtfilename):
        capture     = open(binfilename, 'rb').read()
        textfile    = open(txtfilename, 'w')
        offset      = 0
        path        = '<Unknown>'

        while( (len(capture) - offset) != 0 ):
            offset, text = CapProxyCapture.unpack(capture, offset)
            textfile.write(text)

    def main(self):
        Log.log_level = 0

        scriptname  = os.path.basename(sys.argv[0])
        if len(sys.argv) > 4 or (len(sys.argv) > 1 and sys.argv[1].lower() in ('-h', '-help', '--help')):
            print "%s [capture.bin] [capture.txt] [SimProxy.cfg]" % scriptname
            exit()

        if len(sys.argv) > 3:
            cfgfilename = sys.argv[3]
        else:
            cfgfilename = 'SimProxy.cfg'

        settings = { 'CapProxy': { 'captureFile':'string' }}
        cfg = Config()
        cfg.read(cfgfilename)
        cfg.load(self, settings)

        if len(sys.argv) > 1:
            binfilename = sys.argv[1]
        else:
            binfilename = self.captureFile

        if len(sys.argv) > 2:
            txtfilename = sys.argv[2]
        else:
            txtfilename = os.path.splitext(binfilename)[0] + '.txt'
            if txtfilename == binfilename:
                txtfilename = txtfilename + '.txt'

        print "Binary file: %s" % binfilename
        print "Text file:   %s" % txtfilename
        self.dump(binfilename, txtfilename)

if __name__ == "__main__":
    d = DumpHTTP()
    d.main()
