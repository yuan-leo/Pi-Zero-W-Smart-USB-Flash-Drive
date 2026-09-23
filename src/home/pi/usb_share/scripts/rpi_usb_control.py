#!/usr/bin/python3
import argparse
from usb_share_common import storage_lock, usb_control

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--action', required=True, choices=('reset', 'unplug'))
    args = p.parse_args()
    with storage_lock():
        usb_control(args.action)
