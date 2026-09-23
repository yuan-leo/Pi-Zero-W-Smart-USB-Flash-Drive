#!/usr/bin/env python3
"""Build the portal and helpers from one source tree; never ship vendor build output."""
import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/home/pi/usb_share'


def build(output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    files = {}
    for directory in ('html_root', 'scripts'):
        for path in (SOURCE / directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.name != 'prep_image':
                files[path.relative_to(SOURCE).as_posix()] = path
    files['install.sh'] = ROOT / 'tools/install.sh'
    for path in (ROOT / 'deployment').rglob('*'):
        if path.is_file():
            files['deployment/' + path.relative_to(ROOT / 'deployment').as_posix()] = path
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            content = path.read_bytes()
            if path.suffix in ('.py', '.php', '.sh', '.js', '.css', '.conf', '.service', '.sudoers', '.tmpfiles') or path.parent.name == 'deployment':
                content = content.replace(b'\r\n', b'\n')
            archive.writestr(info, content)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest + '  ' + output.name + '\n')
    return digest


if __name__ == '__main__':
    print(build(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'dist/usb-share.zip'))
