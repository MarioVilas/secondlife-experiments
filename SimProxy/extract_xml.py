import os
import types

from sllib.LLSD import LLSD


try:
    os.makedirs('./httpcap')
except:
    pass

data = open('httpcap.txt','r').read()
c = 0
btag = '<llsd>'
etag = '</llsd>'
##mbtag = '<key>message</key><string>'
##metag = '</string>'
b = data.find(btag)
mnames = {}
while b >= 0:
    e = data.find(etag, b) + len(etag)
    xml = data[b:e]

##    bm = xml.rfind(mbtag)
##    em = xml.find(metag, bm)
##    if bm >= 0 and em >= 0 and em >= bm:
##        bm = bm + len(mbtag)
##        m = xml[bm:em]
##        mnames[m] = None
##    else:
##        m = 'Unknown'

    ll = LLSD.fromstring(xml)
    m = 'DATA'
    if type(ll) == types.DictType and ll.has_key('events'):
##        print ll
        for msg in ll['events']:
            m = msg['message']
##            print m
            mnames[m] = None

    name = './httpcap/%s_%d.xml' % (m,c)
    try:
        open(name, 'w+').write(xml)
    except:
        print xml
        raise
    c += 1
    b = data.find(btag, e)
print mnames.keys()
