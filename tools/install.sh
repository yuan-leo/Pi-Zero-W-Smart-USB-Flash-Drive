#!/bin/bash
# Run from the root of a verified release archive. This migrates an existing Pi.
set -euo pipefail
test "$(id -u)" = 0 || { echo 'Run as root.' >&2; exit 1; }
cd -- "$(dirname -- "$0")"
test -d html_root && test -d scripts
test -f /home/pi/usb_share/usb_share_disk.img
command -v php >/dev/null
command -v visudo >/dev/null
/usr/bin/python3 -c 'import watchdog'
# A running old watcher has none of the new locks. Stop its service before migration.
/usr/bin/python3 - <<'PY'
from pathlib import Path
legacy = {b'/usr/local/share/usb_share.py', b'/home/pi/usb_share/html_root/usb_share.py'}
for proc in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        if legacy.intersection(proc.read_bytes().split(b'\0')):
            raise SystemExit('Stop the legacy USB watcher before installing (PID ' + proc.parent.name + ').')
    except (FileNotFoundError, ProcessLookupError):
        pass
PY
visudo -cf deployment/usb-share.sudoers
for file in html_root/*.php html_root/includes/*.php; do php -l "$file" >/dev/null; done

install -d -o root -g root -m 755 /usr/local/lib/usb-share /var/www/usb-share
install -d -o root -g www-data -m 750 /etc/usb-share
install -d -o root -g root -m 755 /home/pi/usb_share/flags
# Root-owned parents prevent the web account replacing privileged code/configuration.
chown root:root /home/pi/usb_share/flags
chmod 755 /home/pi/usb_share/flags
find /home/pi/usb_share/flags -maxdepth 1 -type f -exec chown root:root {} +
find /home/pi/usb_share/flags -maxdepth 1 -type f -exec chmod 644 {} +
cp -R html_root/. /var/www/usb-share/
cp -R scripts/. /usr/local/lib/usb-share/
chown -R root:root /var/www/usb-share /usr/local/lib/usb-share
find /var/www/usb-share /usr/local/lib/usb-share -type d -exec chmod 755 {} +
find /var/www/usb-share /usr/local/lib/usb-share -type f -exec chmod 644 {} +
chmod 755 /usr/local/lib/usb-share/admin.py
rotation=0
for angle in 90 180 270; do
    if test -f "/home/pi/usb_share/flags/rotate_$angle"; then rotation=$angle; fi
done
if ! test -f /home/pi/usb_share/flags/enable_camera; then rotation=disabled; fi
install -m 755 "scripts/camera_templates/start_camera_stream_$rotation.sh" /usr/local/share/start_camera_stream.sh
# Stop the old externally-bound camera before restarting it on loopback.
if pgrep -x mjpg_streamer >/dev/null; then pkill -x mjpg_streamer; fi
/usr/local/share/start_camera_stream.sh
install -m 755 deployment/upgrade_usb_share /usr/local/bin/upgrade_usb_share
install -m 755 deployment/configure_auth.php /usr/local/sbin/usb-share-password
install -m 644 deployment/usb-share.tmpfiles /etc/tmpfiles.d/usb-share.conf
systemd-tmpfiles --create /etc/tmpfiles.d/usb-share.conf
install -m 440 deployment/usb-share.sudoers /etc/sudoers.d/usb-share
install -m 644 deployment/usb-share-watcher.service /etc/systemd/system/usb-share-watcher.service
# Preserve existing service units that invoke this old public path, without old code.
install -m 755 deployment/usb_share.py /usr/local/share/usb_share.py
if ! test -f /etc/apache2/sites-available/usb-share.conf; then
    install -m 644 deployment/usb-share.conf /etc/apache2/sites-available/usb-share.conf
fi
install -m 644 deployment/deny-legacy.conf /etc/apache2/conf-available/usb-share-deny-legacy.conf
a2enconf usb-share-deny-legacy
a2ensite usb-share
a2dissite 000-default || true
apache2ctl configtest
systemctl daemon-reload
systemctl enable usb-share-watcher.service
# Defer starting/restarting the watcher until after installer-held storage locks release.
systemctl --no-block restart usb-share-watcher.service
systemctl reload apache2
echo 'Installed. Configure a password with sudo usb-share-password, then enable HTTPS.'
echo 'Remove any pre-existing broad www-data sudo rules; only usb-share.sudoers is needed.'
