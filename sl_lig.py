import os
import re

from xml.etree.ElementTree import parse

def hex_display(t):
    s = ''
    for c in t:
        s += hex(ord(c))[2:].zfill(2)
    return s

def xorStr(a, b):
    if len(a) < len(b):
        a,b = b,a
    m = int( (len(a) + len(b)) / len(b) )
    b = b * m
    s = ''
    for i in range(len(a)):
        s += chr( ord(a[i]) ^ ord(b[i]) )
    return s

mac_finder = re.compile(r"[0-9A-F][0-9A-F]\-[0-9A-F][0-9A-F]\-[0-9A-F][0-9A-F]\-[0-9A-F][0-9A-F]\-[0-9A-F][0-9A-F]\-[0-9A-F][0-9A-F]", re.I)
mac_parser = re.compile(r"([0-9A-F][0-9A-F])\-([0-9A-F][0-9A-F])\-([0-9A-F][0-9A-F])\-([0-9A-F][0-9A-F])\-([0-9A-F][0-9A-F])\-([0-9A-F][0-9A-F])", re.I)

def binMacAddress(mac_string):
    mac = ''
    for c in mac_parser.match(mac_string).groups():
        mac += chr(int(c, 0x10))
    return mac


xml = parse(r"C:\Documents and Settings\Mario\Datos de Programa\SecondLife\user_settings\settings.xml")
if xml is not None:

    last_run_version    = xml.find("LastRunVersion")
    first_name          = xml.find("FirstName")
    last_name           = xml.find("LastName")

    if last_run_version is not None:
        print "SL version:    %s" % last_run_version.get("value")
    if first_name is not None:
        print "First name:    %s" % first_name.get("value")
    if last_name is not None:
        print "Last name:     %s" % last_name.get("value")

    try:
        encoded_hash = open(r"C:\Documents and Settings\Mario\Datos de Programa\SecondLife\user_settings\password.dat", "rb").read()
    except Exception, e:
        encoded_hash = None

    if encoded_hash is not None:
        print "\nProtected hash:\n          %s" % hex_display(encoded_hash)

        mac_list = mac_finder.findall(os.popen("ipconfig /all").read())
        for mac in mac_list:
            decoded_hash = xorStr(encoded_hash, binMacAddress(mac))
            print "\n\nMAC Address: %s" % mac
            print "MD5 hash: %s" % hex_display(decoded_hash)
