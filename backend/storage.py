"""Content-addressed storage layout.

Paths are resolved on every call so tests (and operators) can point
STORAGE_ROOT somewhere else without re-importing modules.
"""

import hashlib
from pathlib import Path

import aiofiles

from backend.config import settings

CHUNK = 1 << 16


def root() -> Path:
    return Path(settings.storage_root)


def area(name: str) -> Path:
    """Return storage/<name>, creating it on first use."""
    path = root() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def datasets() -> Path:
    return area("datasets")


def models() -> Path:
    return area("models")


def evidence() -> Path:
    return area("evidence")


def inference() -> Path:
    return area("inference")


def vault() -> Path:
    """Pristine copies taken before a demo tamper, used by restore."""
    return area("vault")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file_sync(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


async def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    async with aiofiles.open(path, "rb") as f:
        while chunk := await f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def sample_dir(dataset_sha: str) -> Path:
    return area(f"datasets/{dataset_sha}.samples")


def relative(path: Path) -> str:
    """Storage-relative POSIX path, so the database survives moving STORAGE_ROOT."""
    return path.resolve().relative_to(root().resolve()).as_posix()


def resolve(rel: str) -> Path:
    path = (root() / rel).resolve()
    if not is_within(path, root()):
        raise ValueError(f"path escapes storage root: {rel}")
    return path
