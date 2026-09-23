# Security update and migration

The maintained application source is `src/home/pi/usb_share/html_root` and
`src/home/pi/usb_share/scripts`. `tools/build_release.py` builds both into one
deterministic archive. Historical portal copies have been removed; do not deploy
the old `resource_files/2_4_4_resources.zip` or copy the repository over a live Pi.
Generated camera build output was removed and is ignored. The bundled native
camera libraries are retained for existing hardware but are
not included in the application release.

## Behavior changes

- All portal pages and APIs require a configured password. There is no default
  portal password. HTTPS is required by default. The camera is bound to loopback
  and is served through the authenticated portal, including on HTTPS.
- Administrative actions use POST and a session CSRF token. External API clients
  must authenticate, keep the session cookie, read the page's `csrf-token` meta
  value, and send it as `X-CSRF-Token` with form-encoded POST parameters.
- The web account can invoke only the root-owned `admin.py` helper through sudo.
  The helper validates every action and argument; user input never becomes shell
  syntax. Uploads do not overwrite existing names; deletion preserves case and
  cannot leave the upload directory.
- Print protection uses the current flags directory. It defaults to enabled for
  Anycubic support and blocks USB resets/rebuilds if the printer is active,
  paused, unreachable, or returns an invalid status. Settings can explicitly
  disable protection. Manual controls follow the same protection checks.
- The USB gadget is read-only to the attached host (`ro=1`); files are managed
  through the Pi. Devices requiring write access need a separate ownership
  handoff design. Do not restore simultaneous writable access to the image from
  both the Pi and USB host.
- Rebuild still creates an **empty filesystem**; it does not resize/copy files.
  It allocates and verifies a replacement before stopping Samba and detaching
  USB, retains `usb_share_disk.img.previous`, and completes without a reboot.
  It needs space for the new image plus a 2 GiB reserve, in addition to the old
  image. Archive/remove the previous image manually after verifying the new
  filesystem and before another rebuild. A failed unmount never deletes the old
  image. Errors after activation retain the backup for administrator recovery.
- Printer status has a four-second overall network deadline, complete-frame
  reads, real JSON, a shared three-second cache, and non-overlapping browser
  polling. Frames larger than 1 MiB are rejected.
- Upgrades run once as locked background jobs; the progress page only polls the
  returned job ID. Each upgrade requires an administrator-provisioned HTTPS URL
  and SHA-256 digest. No script from a mutable branch is executed automatically.

## Build and verify

```sh
python3 -m unittest discover -s tests -v
php tests/security_test.php
node tests/frontend_test.js
python3 tools/build_release.py
```

Output: `dist/usb-share.zip` and `dist/usb-share.zip.sha256`. CI also lints PHP
and shell files, checks POSIX lock exclusion, and uploads these artifacts. It
does not automatically tag, publish, or deploy a release.

## Migrate an existing Pi

This installer targets an existing Debian/Raspberry Pi OS installation with
Apache/PHP, sudo, Python 3 (3.7+), `python3-watchdog`, `dosfstools`, Samba,
`arp-scan`, the existing USB image/mount, and optional mjpg-streamer. Application
PHP is compatible with 7.3 syntax, but use an OS/PHP version receiving security
updates. The PHP regression runner requires PHP 7.4+.

1. Back up the SD card/configuration and USB image. Stop printing. Stop the old
   USB watcher service; the installer refuses migration while a known legacy
   watcher process is running. Disable its old service/cron startup entry so only
   `usb-share-watcher.service` starts afterward. Service names vary by image.
2. Build the release, transfer it to the Pi, compare its digest against the
   trusted build output, and extract it to a private administrator directory.
   Run `sudo bash install.sh` from that directory. The installer preserves the
   disk image and existing settings. It installs the portal at
   `/var/www/usb-share` and helpers at `/usr/local/lib/usb-share`, owned by root.
3. Run `sudo usb-share-password` interactively. The password is hashed into
   `/etc/usb-share/auth.json`, readable only by root and the web-server group.
4. Configure an Apache TLS virtual host with `DocumentRoot /var/www/usb-share`,
   a certificate trusted by your clients, and the same Directory rules as
   `deployment/usb-share.conf`. Redirect HTTP to HTTPS. Do not trust forwarded
   HTTPS headers from arbitrary clients. If using a trusted TLS-terminating proxy,
   configure Apache's HTTPS environment only for that proxy.
5. Remove any legacy blanket `www-data` sudo permission and permissions for
   arbitrary shells, `rm`, interpreters, or scripts under `/home/pi`. Review
   `sudo -l -U www-data`; the only required entry is
   `/usr/local/lib/usb-share/admin.py`. The installer adds its narrow rule but
   cannot safely guess which unrelated sudo rules may be removed.
6. Verify that Apache serves PHP rather than PHP source, and remove custom old
   aliases/vhosts pointing at other historical portal copies. The installer
   denies the two known legacy application directories and the upload directory.
   Keep the upload directory outside every web document root.
7. Ensure the mounted FAT filesystem permits writes by `www-data`. Restrict Samba
   access to authorized users and an intended interface; its authentication is
   separate from the portal. Change any factory `pi`/`raspberry` SSH credentials.
   Do not make helper files or their parent directories writable by `www-data`.
8. Verify the watcher with `systemctl status usb-share-watcher` and
   `journalctl -u usb-share-watcher`. Check camera port 8080 binds only to
   `127.0.0.1`. Reboot once after migration to verify persistent service setup.

For explicitly trusted, isolated HTTP-only development, an administrator may set
`"allow_http": true` in `auth.json`; this sends Basic-auth credentials without
transport encryption. It is disabled by default and is not needed for HTTPS.

## Configure a subsequent upgrade

Publish the built archive at an HTTPS URL. Independently obtain its trusted
SHA-256 digest from the build output. As root, provision
`/etc/usb-share/release.json` (root-owned, mode 0644) with:

```json
{
  "url": "https://your-release-host.example/usb-share.zip",
  "sha256": "replace-with-the-64-character-lowercase-digest"
}
```

The digest is a trust decision: do not obtain it solely from an untrusted archive
download. A missing/malformed manifest, failed download, mismatched digest,
archive traversal/symlink, or failed installer prevents successful completion.
Open `/includes/upgrade_portal.php` and select **Install configured release**.
Reloading that page resumes polling the stored job without starting another.
Job results are in `/run/usb-share/<job-id>.json` and disappear on reboot.

## Hardware acceptance checks

The local regression suite mocks privileged disk and service operations. Before
using this on a printer, verify a small upload/delete, reconnect after idle,
protection during printing and network loss, a rebuild on a disposable image,
and recovery after a simulated unmount failure. Confirm the printer's firmware
uses the expected `,end` response terminator. POSIX locks run in Linux CI; actual
USB gadget behavior, Apache configuration, and firmware responses require a Pi.
