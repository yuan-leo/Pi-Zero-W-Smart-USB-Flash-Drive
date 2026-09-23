"""Install only an HTTPS archive whose digest was provisioned by an administrator."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile

MANIFEST = Path('/etc/usb-share/release.json')


def manifest():
    info = MANIFEST.stat()
    if info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('Release manifest must be root-owned and not group/world writable')
    data = json.loads(MANIFEST.read_text())
    url = urllib.parse.urlsplit(data['url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password:
        raise ValueError('An HTTPS release URL is required')
    if not re.fullmatch('[0-9a-f]{64}', data['sha256']):
        raise ValueError('A pinned SHA-256 digest is required')
    return data


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise ValueError('Refusing a non-HTTPS redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def extract_verified(archive, target):
    with zipfile.ZipFile(archive) as source:
        if sum(item.file_size for item in source.infolist()) > 256 * 1024 * 1024:
            raise ValueError('Release archive is too large')
        for item in source.infolist():
            name = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (name.is_absolute() or '..' in name.parts or '\\' in item.filename
                    or ':' in item.filename or stat.S_ISLNK(mode)):
                raise ValueError('Unsafe archive member')
        source.extractall(target)


def upgrade():
    release = manifest()
    with tempfile.TemporaryDirectory(prefix='usb-share-upgrade-') as work:
        work = Path(work)
        archive = work / 'release.zip'
        digest = hashlib.sha256()
        total = 0
        opener = urllib.request.build_opener(HTTPSRedirect())
        with opener.open(release['url'], timeout=30) as response, archive.open('wb') as out:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > 128 * 1024 * 1024:
                    raise ValueError('Release download is too large')
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != release['sha256']:
            raise ValueError('Release checksum mismatch')
        target = work / 'release'
        extract_verified(archive, target)
        subprocess.run(['/bin/bash', str(target / 'install.sh')], cwd=target, check=True,
                       timeout=300)
