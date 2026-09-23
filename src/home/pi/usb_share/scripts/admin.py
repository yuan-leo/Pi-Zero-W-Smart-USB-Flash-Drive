#!/usr/bin/python3 -I
"""The only sudo entry point. All actions and arguments are validated here."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

# -I excludes user-controlled imports; only this root-owned installation is added.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from usb_share_common import FLAGS, RUN, atomic_write, hostname, printer_action, query, run, storage_lock, usb_control


def job_status(job, state, error=''):
    atomic_write(RUN / (job + '.json'), json.dumps(dict(job_id=job, status=state, error=error)))


def start_job(action, values):
    import fcntl
    with (RUN / 'admin.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        job = uuid.uuid4().hex
        job_status(job, 'queued')
        if action in ('rebuild', 'update_rpi'):
            atomic_write(FLAGS / ('rebuilding_usb' if action == 'rebuild' else 'updating_rpi'), 'queued')
        args = ['/usr/bin/python3', '-I', str(Path(__file__).resolve()), '_worker',
                str(lock.fileno()), job, action] + values
        # The inherited lock covers queueing and the entire worker lifetime.
        try:
            subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, pass_fds=(lock.fileno(),), start_new_session=True)
        except Exception as exc:
            job_status(job, 'error', str(exc))
            if action in ('rebuild', 'update_rpi'):
                atomic_write(FLAGS / ('rebuilding_usb' if action == 'rebuild' else 'updating_rpi'), 'error')
            raise
        return dict(job_id=job, status='queued')


def validate(action, args):
    counts = {'rebuild': 1, 'upgrade': 0, 'update_rpi': 4, 'usb_reset': 0, 'usb_unplug': 0,
              'reboot': 0, 'shutdown': 0, 'network_scan': 0, 'enable_anycubic': 0,
              'disable_anycubic': 0, 'update_anycubic': 4, 'anycubic_action': 1}
    if action not in counts or len(args) != counts[action]:
        raise ValueError('Invalid administrative action or argument count')
    if action == 'rebuild':
        from rebuild import validate_size
        import shutil
        from usb_share_common import BASE
        validate_size(args[0], shutil.disk_usage(BASE).free)
    elif action == 'upgrade':
        from updater import manifest
        manifest()
    elif action == 'update_rpi':
        hostname(args[0]); hostname(args[1])
        if args[2] not in ('on', 'off') or args[3] not in ('0', '90', '180', '270'):
            raise ValueError('Invalid camera settings')
    elif action == 'update_anycubic':
        from usb_share_common import printer_address
        printer_address(args[0])
        if args[1] not in ('photon mono x', 'photon mono se') or any(x not in ('on', 'off') for x in args[2:]):
            raise ValueError('Invalid printer settings')
    elif action == 'anycubic_action':
        printer_action(args[0])


def perform(action, args):
    if action == 'rebuild':
        from rebuild import rebuild
        rebuild(args[0])
    elif action == 'upgrade':
        from updater import upgrade
        with storage_lock():
            upgrade()
    elif action == 'update_rpi':
        from rpi_update import update
        update(*args)
    elif action in ('usb_reset', 'usb_unplug'):
        with storage_lock():
            usb_control(action[4:])
    elif action in ('reboot', 'shutdown'):
        try:
            (FLAGS / 'updating_rpi').unlink()
        except FileNotFoundError:
            pass
        run('/bin/systemctl', '--no-block', 'reboot' if action == 'reboot' else 'poweroff')
    elif action == 'network_scan':
        return run('/usr/sbin/arp-scan', '-I', 'wlan0', '-l')
    elif action in ('enable_anycubic', 'disable_anycubic', 'update_anycubic'):
        from anycubic_update import update
        a = argparse.Namespace(a=action.split('_')[0])
        if action == 'update_anycubic':
            a.printer_ip, a.printer_model, a.enable_wifi, a.enable_protection = args
        update(a)
    elif action == 'anycubic_action':
        return query(['go' + args[0]])[0]
    return ''


def main(args):
    if os.geteuid() != 0:
        raise PermissionError('Run through the configured sudo helper')
    os.environ.clear()
    os.environ.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LANG='C.UTF-8')
    if args and args[0] == '_worker':
        # Only a child with a live inherited lock is allowed to run a worker.
        fd, job, action, *values = args[1:]
        if not (len(job) == 32 and all(c in '0123456789abcdef' for c in job)):
            raise ValueError('Invalid job ID')
        if os.readlink('/proc/self/fd/' + str(int(fd))) != str(RUN / 'admin.lock'):
            raise ValueError('Invalid worker lock')
        try:
            validate(action, values)
            job_status(job, 'running')
            perform(action, values)
            job_status(job, 'complete')
        except Exception as exc:
            job_status(job, 'error', str(exc))
            if action in ('rebuild', 'update_rpi'):
                atomic_write(FLAGS / ('rebuilding_usb' if action == 'rebuild' else 'updating_rpi'), 'error')
        return
    action, *values = args
    validate(action, values)
    if action in ('rebuild', 'upgrade', 'update_rpi'):
        print(json.dumps(start_job(action, values)))
    else:
        import fcntl
        with (RUN / 'admin.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print(json.dumps(dict(status=perform(action, values), error='')))


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception as exc:
        print(json.dumps(dict(error=str(exc))))
        sys.exit(1)
