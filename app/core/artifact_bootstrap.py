"""Bounded private HTTPS delivery; never deserialize downloaded executable artifacts."""

import gzip
import hashlib
import ipaddress
import json
import os
import re
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from app.core.trusted_files import reject_links, trusted_bytes

FILES = frozenset({"checksums.json", "pipeline.joblib", "metadata.json", "contract.json"})
MAX_BYTES = 32 * 1024 * 1024


class BootstrapError(RuntimeError):
    def __init__(self):
        super().__init__("Model artifact bootstrap failed")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class Source:
    # Presigned S3 URLs are bearer credentials. Never include them in repr/logs.
    url: str = field(repr=False)
    allowed_host: str
    authorization: str = field(default="", repr=False)
    max_bytes: int = MAX_BYTES
    timeout_seconds: float = 60

    def validate(self):
        url = urlsplit(self.url)
        if (
            url.scheme != "https"
            or url.hostname != self.allowed_host
            or not re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z]{2,}", self.allowed_host)
            or self.allowed_host.endswith((".local", ".internal", ".localhost", ".invalid"))
            or url.username
            or url.password
            or url.fragment
            or url.port not in {None, 443}
            or not url.path
            or url.path.endswith("/")
            or any(c.isspace() or ord(c) < 32 for c in self.url)
            or any(ord(c) < 32 or ord(c) == 127 for c in self.authorization)
            or not 1 <= self.max_bytes <= MAX_BYTES
            or not 0 < self.timeout_seconds <= 120
        ):
            raise BootstrapError()
        try:
            ipaddress.ip_address(self.allowed_host)
        except ValueError:
            return
        raise BootstrapError()


def verify_bundle(path: Path, *, root: Path, digest: str) -> dict[str, bytes]:
    """Independent trust anchor first, then every payload; no pickle/ML imports."""
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("External manifest digest required")
    manifest = trusted_bytes(path / "checksums.json", root=root, max_bytes=65536)
    if hashlib.sha256(manifest).hexdigest() != digest:
        raise ValueError("External manifest checksum mismatch")
    checksums = json.loads(manifest)
    if not isinstance(checksums, dict) or set(checksums) != FILES - {"checksums.json"}:
        raise ValueError("Incomplete artifact manifest")
    payloads = {}
    for name, checksum in checksums.items():
        if not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
            raise ValueError("Invalid artifact checksum")
        payloads[name] = trusted_bytes(path / name, root=root, max_bytes=64_000_000)
        if hashlib.sha256(payloads[name]).hexdigest() != checksum:
            raise ValueError("Artifact checksum mismatch")
    return payloads


def _download(source, target, opener, clock):
    request = urllib.request.Request(source.url, headers={"Accept": "application/gzip"})
    if source.authorization:
        request.add_header("Authorization", source.authorization)
    deadline = clock() + source.timeout_seconds
    with opener.open(request, timeout=source.timeout_seconds) as response, target.open("xb") as out:
        if response.status != 200 or response.geturl() != source.url:
            raise BootstrapError()
        length = response.headers.get("Content-Length")
        if length and (not length.isdigit() or int(length) > source.max_bytes):
            raise BootstrapError()
        count = 0
        while True:
            remaining = deadline - clock()
            if remaining <= 0:
                raise BootstrapError()
            # urllib socket timeout alone is idle, not a total deadline. Bound each
            # receive by the remaining budget; read1 avoids waiting to fill a chunk.
            response.fp.raw._sock.settimeout(remaining)
            block = response.read1(min(65536, source.max_bytes - count + 1))
            if not block:
                break
            count += len(block)
            if count > source.max_bytes or clock() > deadline:
                raise BootstrapError()
            out.write(block)
            if length and count == int(length):
                break
        if count == 0 or (length and count != int(length)):
            raise BootstrapError()


def _extract(archive: Path, staging: Path, max_bytes: int):
    # Bound the entire decompressed TAR, including hidden metadata/padding, before
    # tarfile parses it. Do not use extractall, archive paths, or archive modes.
    with tempfile.TemporaryFile() as plain, gzip.open(archive, "rb") as zipped:
        total = 0
        while block := zipped.read(min(65536, max_bytes + 10240 - total + 1)):
            total += len(block)
            if total > max_bytes + 10240:
                raise BootstrapError()
            plain.write(block)
        plain.seek(0)
        seen, extracted = set(), 0
        with tarfile.open(fileobj=plain, mode="r:") as bundle:
            for member in bundle:
                if (
                    member.name not in FILES
                    or member.name in seen
                    or member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE}
                    or member.pax_headers
                    or member.linkname
                    or member.size < 0
                    or len(seen) >= len(FILES)
                ):
                    raise BootstrapError()
                extracted += member.size
                if extracted > max_bytes:
                    raise BootstrapError()
                seen.add(member.name)
                with bundle.extractfile(member) as src, (staging / member.name).open("xb") as out:
                    shutil.copyfileobj(src, out, length=65536)
            if seen != FILES:
                raise BootstrapError()


def bootstrap(
    source: Source | None,
    destination: Path,
    *,
    root: Path,
    digest: str,
    opener=None,
    clock=time.monotonic,
) -> bool:
    """None disables delivery. Never replace an existing operational directory."""
    if source is None:
        return False
    staging = archive = None
    try:
        source.validate()
        if (
            not destination.is_absolute()
            or not root.is_absolute()
            or ".." in destination.parts
            or ".." in root.parts
            or destination.parent != root
            or destination.exists()
            or destination.is_symlink()
        ):
            raise BootstrapError()
        reject_links(root)
        if os.name != "nt" and root.stat().st_mode & 0o022:
            raise BootstrapError()
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise BootstrapError()
        staging = Path(tempfile.mkdtemp(prefix=".model-stage-", dir=root))
        archive = staging / "download.tar.gz"
        _download(
            source,
            archive,
            opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()),
            clock,
        )
        _extract(archive, staging, source.max_bytes)
        archive.unlink()
        verify_bundle(staging, root=root, digest=digest)
        for name in FILES:
            (staging / name).chmod(0o444)
        staging.chmod(0o555)
        # Same filesystem, private parent, one publisher; destination must be absent.
        if destination.exists() or destination.is_symlink():
            raise BootstrapError()
        staging.rename(destination)
        staging = None
        return True
    except Exception:
        raise BootstrapError() from None
    finally:
        if staging is not None:
            try:
                staging.chmod(0o700)
                for item in staging.iterdir():
                    item.chmod(0o600)
                    item.unlink()
                staging.rmdir()
            except Exception:
                raise BootstrapError() from None
