"""Shared validation, file operations and bounded printer protocol handling."""
import contextlib
import ipaddress
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time

BASE = Path('/home/pi/usb_share')
FLAGS = BASE / 'flags'
RUN = Path('/run/usb-share')
LIB = Path('/usr/local/lib/usb-share')


def run(*args):
    return subprocess.run(list(map(str, args)), check=True, capture_output=True,
                          text=True, timeout=120).stdout.strip()


def atomic_write(path, value, mode=0o644):
    path = Path(path)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_flag(name, default=''):
    try:
        return (FLAGS / name).read_text().strip()
    except FileNotFoundError:
        return default


def set_flag(name, enabled):
    if enabled:
        atomic_write(FLAGS / name, '')
    else:
        try:
            (FLAGS / name).unlink()
        except FileNotFoundError:
            pass


def hostname(value):
    if not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', value):
        raise ValueError('Invalid hostname')
    return value.lower()


def printer_address(value):
    return str(ipaddress.IPv4Address(value))


def printer_action(value):
    if value not in ('pause', 'resume', 'stop') and not re.fullmatch(r'print,[0-9]{1,8}', value):
        raise ValueError('Invalid printer command')
    return value


def receive_frame(sock, deadline, limit=1024 * 1024):
    """Anycubic replies end with ,end; TCP reads need not match frames."""
    result = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Printer response timed out')
        sock.settimeout(remaining)
        chunk = sock.recv(min(4096, limit - len(result) + 1))
        if not chunk:
            raise ConnectionError('Incomplete printer response')
        result.extend(chunk)
        if len(result) > limit:
            raise ValueError('Printer response too large')
        if re.search(rb',end(?:,|\s)*$', result):
            return result.decode('utf-8').strip()


def query(commands, host=None, timeout=4):
    host = printer_address(host or read_flag('printer_ip'))
    deadline = time.monotonic() + timeout
    with socket.create_connection((host, 6000), timeout=timeout) as sock:
        responses = []
        for command in commands:
            sock.settimeout(max(0.001, deadline - time.monotonic()))
            sock.sendall((command + ',').encode('utf-8'))
            responses.append(receive_frame(sock, deadline))
        return responses


def printing_safe():
    # Protection is enabled by default, including migration from older versions.
    if not (FLAGS / 'enable_anycubic').exists() or (FLAGS / 'disable_print_protection').exists():
        return True
    try:
        response = query(['getstatus'])[0].split(',')
        return len(response) >= 3 and response[0] == 'getstatus' and response[1].strip() == 'stop'
    except (OSError, ValueError, IndexError):
        return False


@contextlib.contextmanager
def storage_lock(blocking=True):
    import fcntl
    with (RUN / 'storage.lock').open('r+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield


def usb_control(action):
    if action not in ('reset', 'unplug'):
        raise ValueError('Invalid USB action')
    if not printing_safe():
        raise RuntimeError('USB changes blocked: printer active or unavailable')
    atomic_write(FLAGS / 'usb_reset_status', 'stopping_usb')
    try:
        if Path('/sys/module/g_mass_storage').exists():
            run('/sbin/modprobe', '-r', 'g_mass_storage')
        os.sync()
        if action == 'reset':
            atomic_write(FLAGS / 'usb_reset_status', 'starting_usb')
            run('/sbin/modprobe', 'g_mass_storage', 'file=' + str(BASE / 'usb_share_disk.img'),
                'stall=0', 'ro=1', 'removable=1')
    except Exception:
        atomic_write(FLAGS / 'usb_reset_status', 'error')
        raise
    else:
        (FLAGS / 'usb_reset_status').unlink()
