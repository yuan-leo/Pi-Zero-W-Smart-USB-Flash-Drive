#!/usr/bin/python3
import argparse
from usb_share_common import printer_action, query

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', type=printer_action)
    args = parser.parse_args()
    print(query(['go' + args.action])[0])
