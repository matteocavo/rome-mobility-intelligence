"""Read bounded, regular files without trusting paths or mutable bundle manifests."""

import os
import stat
from pathlib import Path


def reject_links(path: Path) -> None:
    for item in [*reversed(path.parents), path]:
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Symlink/reparse paths are not trusted")


def trusted_bytes(path: Path, *, root: Path, max_bytes: int) -> bytes:
    path, root = Path(path), Path(root)
    if not path.is_absolute() or not root.is_absolute() or ".." in path.parts or ".." in root.parts:
        raise ValueError("Trusted paths must be absolute and cannot traverse parents")
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("Artifact path is outside the trusted root") from None
    reject_links(root)
    reject_links(path)
    # Deployment roots must not be writable by unrelated users/groups.
    if os.name != "nt":
        for item in [root, *[p for p in path.parents if p != root and root in p.parents]]:
            if item.stat().st_mode & 0o022:
                raise ValueError("Trusted storage is group/world writable")
    before = path.lstat()
    if os.name != "nt" and before.st_mode & 0o022:
        raise ValueError("Trusted file is group/world writable")
    if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
        raise ValueError("Untrusted file type or size")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError("Trusted file is not regular")
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("Trusted file was replaced during open")
        data = stream.read(max_bytes + 1)
        after = os.fstat(stream.fileno())
        if (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Trusted file changed during read")
    reject_links(path)
    if len(data) > max_bytes:
        raise ValueError("Trusted file exceeds the byte budget")
    return data
