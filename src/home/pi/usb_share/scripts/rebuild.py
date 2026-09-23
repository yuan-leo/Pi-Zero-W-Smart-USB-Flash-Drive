"""Build a replacement before stopping services; retain the old image on failure."""
import os
from pathlib import Path
import shutil
import tempfile
from usb_share_common import BASE, FLAGS, atomic_write, printing_safe, run, storage_lock


def validate_size(value, free):
    if not str(value).isdigit() or not 1 <= int(value) <= 2048:
        raise ValueError('USB size must be 1–2048 GiB')
    size = int(value) * 1024 ** 3
    if size + 2 * 1024 ** 3 > free:
        raise ValueError('Not enough space for a replacement image and 2 GiB reserve')
    return size


def rebuild(value):
    image = BASE / 'usb_share_disk.img'
    backup = BASE / 'usb_share_disk.img.previous'
    mount = BASE / 'upload'
    with storage_lock(blocking=False):
        size = validate_size(value, shutil.disk_usage(BASE).free)
        if backup.exists():
            raise RuntimeError('Remove or archive the previous image before another rebuild')
        if not printing_safe():
            raise RuntimeError('Printer active or unavailable')
        fd, temp_name = tempfile.mkstemp(prefix='usb-image-', dir=BASE)
        replacement = Path(temp_name)
        stopped = unmounted = detached = swapped = False
        was_attached = Path('/sys/module/g_mass_storage').exists()
        try:
            atomic_write(FLAGS / 'rebuilding_usb', 'create_image')
            with os.fdopen(fd, 'wb') as stream:
                os.posix_fallocate(stream.fileno(), 0, size)
                os.fsync(stream.fileno())
            atomic_write(FLAGS / 'rebuilding_usb', 'create_fs')
            run('/sbin/mkfs.vfat', '-F', '32', '-I', replacement)
            run('/sbin/fsck.vfat', '-n', replacement)
            if not printing_safe():
                raise RuntimeError('Printer became active or unavailable')
            atomic_write(FLAGS / 'rebuilding_usb', 'stop_services')
            run('/bin/systemctl', 'stop', 'smbd')
            stopped = True
            if was_attached:
                run('/sbin/modprobe', '-r', 'g_mass_storage')
                detached = True
            os.sync()
            run('/bin/umount', mount)
            unmounted = True
            # Preserve the original inode and image until the replacement is mounted.
            os.link(image, backup)
            os.replace(replacement, image)
            swapped = True
            run('/bin/mount', mount)
            unmounted = False
            if was_attached:
                run('/sbin/modprobe', 'g_mass_storage', 'file=' + str(image),
                    'stall=0', 'ro=1', 'removable=1')
                detached = False
            run('/bin/systemctl', 'start', 'smbd')
            stopped = False
            atomic_write(FLAGS / 'rebuilding_usb', 'complete')
        except Exception:
            # Never replace an image still attached or mounted after a later failure.
            if swapped and unmounted:
                os.replace(backup, image)
            if unmounted:
                run('/bin/mount', mount)
            if detached:
                run('/sbin/modprobe', 'g_mass_storage', 'file=' + str(image),
                    'stall=0', 'ro=1', 'removable=1')
            if stopped:
                run('/bin/systemctl', 'start', 'smbd')
            raise
        finally:
            if replacement.exists():
                replacement.unlink()
