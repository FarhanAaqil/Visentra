"""Safe unpacking of uploaded dataset archives into content-addressed samples.

Archive member names are never used as filesystem paths: every sample is
written as ``<sha256><ext>`` inside the dataset's sample directory, so
zip-slip style names (``../../etc/passwd``) cannot escape it. Size and count
limits stop decompression bombs.
"""

from __future__ import annotations

import hashlib
import tarfile
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import cv2
import numpy as np

from backend.assurance.data.dataset_checks import SUPPORTED_IMAGE_EXTS

MAX_MEMBER_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_MEMBERS = 10_000


class ArchiveError(ValueError):
    pass


@dataclass
class ExtractedSample:
    name: str
    sha256: str
    path: Path


def _members(archive: Path) -> Iterator[tuple[str, bytes]]:
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            if len(infos) > MAX_MEMBERS:
                raise ArchiveError(f"archive has more than {MAX_MEMBERS} entries")
            for info in infos:
                if info.file_size > MAX_MEMBER_BYTES:
                    continue
                yield info.filename, zf.read(info)
        return

    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            count = 0
            for member in tf:
                if not member.isfile() or member.size > MAX_MEMBER_BYTES:
                    continue
                count += 1
                if count > MAX_MEMBERS:
                    raise ArchiveError(f"archive has more than {MAX_MEMBERS} entries")
                f = tf.extractfile(member)
                if f is not None:
                    yield member.name, f.read()
        return

    # A bare image upload is a one-sample dataset.
    yield archive.name, archive.read_bytes()


def _is_image(data: bytes) -> bool:
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR) is not None


def extract_images(archive: Path, dest: Path, original_name: str = "") -> list[ExtractedSample]:
    """Unpack every decodable image in ``archive`` into ``dest``; returns samples sorted by name."""
    dest.mkdir(parents=True, exist_ok=True)
    samples: list[ExtractedSample] = []
    total = 0
    for raw_name, data in _members(archive):
        name = PurePosixPath(raw_name.replace("\\", "/")).name
        if raw_name == archive.name and original_name:
            name = PurePosixPath(original_name).name
        ext = PurePosixPath(name).suffix.lower()
        if ext not in SUPPORTED_IMAGE_EXTS or name.startswith("."):
            continue
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ArchiveError("archive expands beyond the 1 GiB limit")
        if not _is_image(data):
            continue
        sha = hashlib.sha256(data).hexdigest()
        path = dest / f"{sha}{ext}"
        if not path.exists():
            path.write_bytes(data)
        samples.append(ExtractedSample(name=name, sha256=sha, path=path))
    return sorted(samples, key=lambda s: s.name)
