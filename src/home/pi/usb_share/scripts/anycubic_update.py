#!/usr/bin/python3
import argparse
from usb_share_common import BASE, FLAGS, atomic_write, printer_address, run, set_flag


def update(args):
    if args.a == 'update':
        address = printer_address(args.printer_ip)
        if args.printer_model not in ('photon mono x', 'photon mono se'):
            raise ValueError('Unsupported printer model')
        if args.enable_wifi not in ('on', 'off') or args.enable_protection not in ('on', 'off'):
            raise ValueError('Invalid printer setting')
        atomic_write(FLAGS / 'printer_ip', address)
        atomic_write(FLAGS / 'printer_model', args.printer_model)
        set_flag('disable_print_protection', args.enable_protection == 'off')
        if args.enable_wifi == 'on':
            run('/bin/systemctl', 'enable', '--now', 'anycubic_wifi.service')
            set_flag('enable_wifi_file', True)
        else:
            run('/bin/systemctl', 'disable', '--now', 'anycubic_wifi.service')
            set_flag('enable_wifi_file', False)
            wifi = BASE / 'upload/WIFI.txt'
            if wifi.exists():
                wifi.unlink()
    elif args.a == 'enable':
        set_flag('enable_anycubic', True)
    elif args.a == 'disable':
        run('/bin/systemctl', 'disable', '--now', 'anycubic_wifi.service')
        for name in ('printer_ip', 'printer_model', 'enable_wifi_file', 'enable_anycubic'):
            set_flag(name, False)
    else:
        raise ValueError('Invalid update action')


def parser():
    p = argparse.ArgumentParser()
    p.add_argument('-a', choices=('enable', 'disable', 'update'), required=True)
    p.add_argument('--printer_ip')
    p.add_argument('--printer_model')
    p.add_argument('--enable_wifi', choices=('on', 'off'))
    p.add_argument('--enable_protection', choices=('on', 'off'))
    return p


if __name__ == '__main__':
    update(parser().parse_args())
