import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/home/pi/usb_share/scripts'))
sys.path.insert(0, str(ROOT / 'tools'))
import usb_share_common as common
import usb_share
import anycubic_status
import admin
import rebuild
import updater
import build_release


class ValidationTests(unittest.TestCase):
    def test_hostnames_reject_shell_syntax_and_invalid_labels(self):
        for value in ('x;id', '$(id)', '-x', 'a.b', '', 'a' * 64, 'x\n'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                common.hostname(value)
        self.assertEqual(common.hostname('Printer-01'), 'printer-01')

    def test_printer_actions_only_accept_protocol_commands(self):
        for value in ('print,1,stop', 'pause;id', '--help', 'print,-1', 'print,$(id)'):
            with self.assertRaises(ValueError):
                common.printer_action(value)
        self.assertEqual(common.printer_action('print,123'), 'print,123')

    def test_rebuild_capacity_and_zero_size(self):
        for value in ('0', '-1', '1;id', '2049', '1.5'):
            with self.assertRaises(ValueError):
                rebuild.validate_size(value, 100 * 1024**3)
        with self.assertRaises(ValueError):
            rebuild.validate_size('4', 5 * 1024**3)
        self.assertEqual(rebuild.validate_size('4', 6 * 1024**3), 4 * 1024**3)

    def test_admin_rejects_extra_arguments(self):
        with self.assertRaises(ValueError):
            admin.validate('reboot', [';id'])
        with self.assertRaises(ValueError):
            admin.validate('arbitrary', [])

    def test_printer_model_options_match_the_api(self):
        page = (ROOT / 'src/home/pi/usb_share/html_root/settings.php').read_text()
        select = re.search(r'<select name="printer_model".*?</select>', page, re.S).group()
        for model in re.findall(r'<option value="([^"]+)"', select):
            admin.validate('update_anycubic', ['192.168.1.20', model, 'off', 'on'])


class PrinterTests(unittest.TestCase):
    def test_split_and_large_tcp_frames(self):
        chunks = [b'getfile,', b'x' * 4096, b'/1,e', b'nd']
        sock = Mock()
        sock.recv.side_effect = chunks
        result = common.receive_frame(sock, time.monotonic() + 1)
        self.assertEqual(result, 'getfile,' + 'x' * 4096 + '/1,end')

    def test_incomplete_and_oversized_frames_fail(self):
        sock = Mock()
        sock.recv.side_effect = [b'getstatus,pr', b'']
        with self.assertRaises(ConnectionError):
            common.receive_frame(sock, time.monotonic() + 1)
        sock.recv.side_effect = [b'x' * 20]
        with self.assertRaises(ValueError):
            common.receive_frame(sock, time.monotonic() + 1, limit=10)

    def test_json_preserves_apostrophes_and_quotes(self):
        files = 'getfile,O\'Brien "test".pwmx/1,end'
        with patch.object(anycubic_status, 'query', return_value=[files, 'getstatus,stop,end']), patch.object(anycubic_status, 'read_flag', return_value=''):
            data = anycubic_status.get_status()
        self.assertEqual(json.loads(json.dumps(data))['files'], files)
        self.assertEqual(data['connection'], 'Connected')

    def test_print_protection_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(common, 'FLAGS', Path(folder)):
            (Path(folder) / 'enable_anycubic').touch()
            with patch.object(common, 'query', side_effect=TimeoutError):
                self.assertFalse(common.printing_safe())
            for state in ('print', 'pause', 'unknown'):
                with patch.object(common, 'query', return_value=['getstatus,' + state + ',end']):
                    self.assertFalse(common.printing_safe())
            with patch.object(common, 'query', return_value=['getstatus,stop,end']):
                self.assertTrue(common.printing_safe())


class WatcherTests(unittest.TestCase):
    def test_new_event_during_reset_is_not_lost(self):
        state = usb_share.DirtyState()
        state.mark()
        generation = state.ready(delay=0)
        state.mark()
        state.finish(generation)
        self.assertIsNotNone(state.ready(delay=0))
        state.finish(state.ready(delay=0))
        self.assertIsNone(state.ready(delay=0))


class RebuildTests(unittest.TestCase):
    def exercise(self, failing_command=None):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / 'flags').mkdir()
            image = base / 'usb_share_disk.img'
            image.write_bytes(b'original image')
            calls = []

            def run(*args):
                calls.append(tuple(map(str, args)))
                if failing_command and args[0] == failing_command:
                    # Fail only once so recovery can remount.
                    if sum(c[0] == failing_command for c in calls) == 1:
                        raise subprocess.CalledProcessError(1, args)
                return ''

            with patch.object(rebuild, 'BASE', base), patch.object(rebuild, 'FLAGS', base / 'flags'), \
                 patch.object(rebuild, 'storage_lock', return_value=contextlib.nullcontext()), \
                 patch.object(rebuild, 'printing_safe', return_value=True), \
                 patch.object(rebuild, 'validate_size', return_value=1024), \
                 patch.object(rebuild.os, 'posix_fallocate', create=True), \
                 patch.object(rebuild.os, 'sync', create=True), patch.object(rebuild, 'run', side_effect=run):
                if failing_command:
                    with self.assertRaises(subprocess.CalledProcessError):
                        rebuild.rebuild('1')
                    self.assertEqual(image.read_bytes(), b'original image')
                else:
                    rebuild.rebuild('1')
                    self.assertEqual((base / 'usb_share_disk.img.previous').read_bytes(), b'original image')
                    self.assertEqual((base / 'flags/rebuilding_usb').read_text(), 'complete')
                self.assertFalse(list(base.glob('usb-image-*')))
            return calls

    def test_format_failure_preserves_image_and_running_services(self):
        calls = self.exercise('/sbin/mkfs.vfat')
        self.assertFalse(any(c[0] == '/bin/systemctl' for c in calls))

    def test_unmount_failure_preserves_image(self):
        self.exercise('/bin/umount')

    def test_mount_failure_rolls_back(self):
        self.exercise('/bin/mount')

    def test_success_retains_backup(self):
        self.exercise()


class UpgradeTests(unittest.TestCase):
    def test_archive_rejects_traversal_and_symlinks(self):
        for name in ('../outside', '/absolute', 'C:/outside', 'a\\..\\outside', 'link'):
            with tempfile.TemporaryDirectory() as folder:
                archive = Path(folder) / 'test.zip'
                with zipfile.ZipFile(archive, 'w') as out:
                    member = zipfile.ZipInfo(name)
                    if name == 'link':
                        member.external_attr = (stat.S_IFLNK | 0o777) << 16
                    out.writestr(member, b'payload')
                with self.assertRaises(ValueError):
                    updater.extract_verified(archive, Path(folder) / 'out')

    def test_checksum_failure_never_extracts_or_executes(self):
        response = io.BytesIO(b'tampered archive')
        opener = Mock()
        opener.open.return_value = response
        with patch.object(updater, 'manifest', return_value={'url': 'https://example.com/release.zip', 'sha256': '0' * 64}), \
             patch.object(updater.urllib.request, 'build_opener', return_value=opener), \
             patch.object(updater, 'extract_verified') as extract, patch.object(updater.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'checksum'):
                updater.upgrade()
            extract.assert_not_called()
            run.assert_not_called()

    def test_deterministic_release_uses_only_canonical_source(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a.zip', Path(folder) / 'b.zip'
            self.assertEqual(build_release.build(a), build_release.build(b))
            with zipfile.ZipFile(a) as archive:
                names = archive.namelist()
                self.assertIn('html_root/includes/security.php', names)
                self.assertIn('scripts/admin.py', names)
                self.assertIn('install.sh', names)
                self.assertFalse(any('_build' in name or name.endswith('.so') or '__pycache__' in name for name in names))


@unittest.skipUnless(shutil.which('node'), 'Node is required for browser syntax checks')
class FrontendTests(unittest.TestCase):
    def test_inline_javascript_syntax(self):
        for path in (ROOT / 'src/home/pi/usb_share/html_root').rglob('*.php'):
            content = re.sub(r'<\?php.*?\?>', '', path.read_text(), flags=re.S)
            for script in re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', content, re.S):
                if script.strip():
                    with self.subTest(path=path.name):
                        result = subprocess.run(['node', '--check'], input=script, text=True, capture_output=True)
                        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipIf(os.name == 'nt', 'POSIX flock behavior is verified in Linux CI')
class ConcurrencyTests(unittest.TestCase):
    def test_second_job_cannot_start_while_lock_is_held(self):
        import fcntl
        with tempfile.TemporaryDirectory() as folder, patch.object(admin, 'RUN', Path(folder)):
            with (Path(folder) / 'admin.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError), patch.object(admin.subprocess, 'Popen') as popen:
                    admin.start_job('upgrade', [])
                popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
