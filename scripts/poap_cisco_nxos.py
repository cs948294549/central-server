#!/bin/env python3
#md5sum="664d8c0c811a1aa9c3f50a4a58d722a0"
"""
If any changes are made to this script, please run the below command
in bash shell to update the above md5sum. This is used for integrity check.
f=poap_nexus_script.py ; cat $f | sed '/^#md5sum/d' > $f.md5 ; sed -i \
"s/^#md5sum=.*/#md5sum=\"$(md5sum $f.md5 | sed 's/ .*//')\"/" $f
"""

import glob
import os
import pkgutil
import re
import shutil
import signal
import sys
import syslog
import time
from time import gmtime, strftime
import tarfile
import errno

try:
    import subprocess as sp
except ImportError:
    sp = None

try:
    from cisco import cli
    from cisco import transfer
    legacy = True
except ImportError:
    from cli import *
    legacy = False

options = {
   "hostname": "10.143.225.1:8888",
   "transfer_protocol": "http",
   "mode": "serial_number",
   "required_space": 100000,
   "source_path": "/",
   "destination_path": "/bootflash/",
   "timeout_config":120,
   "source_config_file":"",
   "serial_number":"",
   }

def poap_log(info):
    """
    Log the trace into console and poap_script log file in bootflash
    Args:
        file_hdl: poap_script log bootflash file handle
        info: The information that needs to be logged.
    """
    global log_hdl, syslog_prefix
    # Don't syslog passwords
    parts = re.split("\s+", info.strip())
    for (index, part) in enumerate(parts):
        # blank out the password after the password keyword (terminal password *****, etc.)
        if part == "password" and len(parts) >= index + 2:
            parts[index + 1] = "<removed>"
    # Recombine for syslogging
    info = " ".join(parts)
    # We could potentially get a traceback (and trigger this) before
    # we have called init_globals. Make sure we can still log successfully
    try:
        info = "%s - %s" % (syslog_prefix, info)
    except NameError:
        info = " - %s" % info
    syslog.syslog(9, info)
    if "log_hdl" in globals() and log_hdl is not None:
        log_hdl.write("\n")
        log_hdl.write(info)
        log_hdl.flush()

def get_config_filename():
    poap_log("Setting source cfg filename based-on serial number")
    if 'POAP_SERIAL' in os.environ:
        poap_log("serial number %s" % os.environ['POAP_SERIAL'])
        options["source_config_file"] = "%s.cfg" % os.environ['POAP_SERIAL']
        options["serial_number"] = os.environ['POAP_SERIAL']
    poap_log("Selected conf file name : %s" % options["source_config_file"])
get_config_filename()

poap_log("get_config_filename finished")

poap_log(cli('show run all | in copp'))


def copy_config_file():
    srcfilename = options["source_config_file"]
    dstfilename = srcfilename
    protocol =  options["transfer_protocol"]
    host =  options["hostname"]
    source = "%s%s" %(options["source_path"],srcfilename)
    destination = "%s%s" %("bootflash:",dstfilename)
    vrf =  os.environ['POAP_VRF']
    copy_cmd = " copy %s://%s%s %s  vrf %s " % (protocol, host, source, destination, vrf)
    poap_log(copy_cmd)
    poap_log("Starting to copy file to %s" % destination)
    try:
        cli("delete %s" % destination)
    except Exception as e:
        poap_log("delete failed %s" % str(e))
    try:
        cli(copy_cmd)
        poap_log("Copy done using transfer module")
    except Exception as e:
        poap_log("copy failed %s" % str(e))
        raise

copy_config_file()

poap_log('copy_config_file finished')

def intstall_startup_config():
    srcfilename = options["source_config_file"]
    install_cmd = "copy  bootflash:%s start " % srcfilename
    try:
        cli(install_cmd)
        poap_log(cli("show start "))
        poap_log("copy bootflash:%s startup-config sucessful" % srcfilename )
        cli("terminal dont-ask ; delete bootflash:*.log")
        cli("terminal dont-ask ; reload")
    except Exception as e:
        poap_log("failed %s" % str(e))
        raise


intstall_startup_config()