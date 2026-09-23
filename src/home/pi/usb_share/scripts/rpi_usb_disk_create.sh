#!/bin/sh
# Compatibility entry point; all validation and locking live in the admin helper.
set -eu
[ "$#" -eq 1 ] || { echo 'Usage: rpi_usb_disk_create.sh SIZE_GIB' >&2; exit 2; }
exec /usr/local/lib/usb-share/admin.py rebuild "$1"
