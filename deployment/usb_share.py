#!/usr/bin/python3
"""Compatibility entry point for old systemd units."""
import os
os.execv('/usr/bin/python3', ['/usr/bin/python3', '-E', '-s', '/usr/local/lib/usb-share/usb_share.py'])
