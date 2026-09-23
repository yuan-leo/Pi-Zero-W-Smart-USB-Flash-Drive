#!/usr/bin/python3
import argparse
from pathlib import Path
from usb_share_common import FLAGS, LIB, atomic_write, hostname, set_flag


def update(current, new, camera, rotation):
    current, new = hostname(current), hostname(new)
    if camera not in ('on', 'off') or rotation not in ('0', '90', '180', '270'):
        raise ValueError('Invalid camera configuration')
    try:
        atomic_write(FLAGS / 'updating_rpi', 'updating_camera')
        template = 'start_camera_stream_' + (rotation if camera == 'on' else 'disabled') + '.sh'
        atomic_write('/usr/local/share/start_camera_stream.sh',
                     (LIB / 'camera_templates' / template).read_text(), 0o755)
        set_flag('enable_camera', camera == 'on')
        for angle in ('0', '90', '180', '270'):
            set_flag('rotate_' + angle, camera == 'on' and angle == rotation)
        atomic_write(FLAGS / 'updating_rpi', 'updating_hostname')
        if current != new:
            lines = Path('/etc/hosts').read_text().splitlines()
            output = []
            for line in lines:
                body, sep, comment = line.partition('#')
                fields = body.split()
                fields = [new if field.lower() == current else field for field in fields]
                output.append('\t'.join(fields) + ((' #' + comment) if sep else ''))
            atomic_write('/etc/hosts', '\n'.join(output) + '\n')
            atomic_write('/etc/hostname', new + '\n')
        atomic_write(FLAGS / 'updating_rpi', 'reboot')
    except Exception:
        atomic_write(FLAGS / 'updating_rpi', 'error')
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--current_hostname', required=True, type=hostname)
    p.add_argument('--new_hostname', required=True, type=hostname)
    p.add_argument('--enable_camera', required=True, choices=('on', 'off'))
    p.add_argument('--rotation', required=True, choices=('0', '90', '180', '270'))
    a = p.parse_args()
    update(a.current_hostname, a.new_hostname, a.enable_camera, a.rotation)
