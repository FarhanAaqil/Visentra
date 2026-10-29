"""Deterministic procedural imagery for demos, tests and VisentraBench.

Every generator takes an explicit seed so the same call always produces the
same pixels. Images are small BGR uint8 arrays (OpenCV convention).
"""

from __future__ import annotations

import io
import zipfile

import cv2
import numpy as np

SIZE = 64

# Ten class "prototype" colours (BGR). The demo classifier keys off these.
PALETTE: list[tuple[int, int, int]] = [
    (60, 60, 200),  # 0 crimson
    (40, 150, 230),  # 1 amber
    (60, 190, 90),  # 2 leaf
    (200, 140, 40),  # 3 azure
    (170, 60, 140),  # 4 plum
    (150, 160, 60),  # 5 teal
    (90, 90, 120),  # 6 slate
    (210, 210, 220),  # 7 frost
    (40, 90, 140),  # 8 umber
    (180, 100, 220),  # 9 orchid
]


def _clip(img: np.ndarray) -> np.ndarray:
    return np.clip(img, 0, 255).astype(np.uint8)


def scene(cls: int, seed: int, size: int = SIZE) -> np.ndarray:
    """A smooth 'natural-ish' image dominated by the colour of ``cls``."""
    rng = np.random.default_rng(seed * 1009 + cls)
    base = np.array(PALETTE[cls % len(PALETTE)], dtype=np.float32)
    top = base * rng.uniform(0.75, 1.0) + rng.uniform(-18, 18, 3)
    bottom = base * rng.uniform(0.85, 1.1) + rng.uniform(-18, 18, 3)
    angle = rng.uniform(0, 2 * np.pi)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / (size - 1) - 0.5
    t = np.clip(0.5 + xx * np.cos(angle) + yy * np.sin(angle), 0.0, 1.0)[..., None]
    img = top * (1 - t) + bottom * t

    for _ in range(int(rng.integers(2, 5))):
        shade = base * rng.uniform(0.55, 1.25) + rng.uniform(-25, 25, 3)
        cx, cy = (int(v) for v in rng.integers(8, size - 8, 2))
        if rng.random() < 0.5:
            cv2.circle(img, (cx, cy), int(rng.integers(5, 14)), shade.tolist(), -1, cv2.LINE_AA)
        else:
            w, h = (int(v) for v in rng.integers(6, 18, 2))
            cv2.rectangle(img, (cx - w // 2, cy - h // 2), (cx + w // 2, cy + h // 2), shade.tolist(), -1)

    img = cv2.GaussianBlur(img, (5, 5), 1.2)
    return _clip(img)


def near_duplicate(img: np.ndarray, seed: int, strength: float = 2.0) -> np.ndarray:
    """Re-encoded copy: light sensor noise, a brightness nudge and JPEG recompression."""
    rng = np.random.default_rng(seed)
    out = _clip(img.astype(np.float32) + rng.normal(0, strength, img.shape) + 3.0)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR) if ok else out


def out_of_distribution(seed: int, size: int = SIZE) -> np.ndarray:
    """Structured texture that shares nothing with the scene distribution."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx, cy = rng.uniform(16, 48, 2)
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    rings = 0.5 + 0.5 * np.sin(r / rng.uniform(1.6, 2.2))
    a = np.array([rng.uniform(120, 255), rng.uniform(0, 60), rng.uniform(120, 255)])
    b = np.array([rng.uniform(0, 60), rng.uniform(150, 255), rng.uniform(0, 60)])
    img = rings[..., None] * a + (1 - rings[..., None]) * b
    img = cv2.GaussianBlur(img.astype(np.float32), (3, 3), 0.8)
    return _clip(img)


def encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:  # pragma: no cover - OpenCV always encodes uint8 BGR
        raise RuntimeError("PNG encoding failed")
    return buf.tobytes()


def decode(data: bytes) -> np.ndarray | None:
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)


def demo_dataset(
    seed: int = 42,
    clean: int = 16,
    duplicates: int = 1,
    ood: int = 1,
    classes: tuple[int, ...] = (0, 1, 2, 3),
) -> list[tuple[str, np.ndarray]]:
    """Named images: ``clean`` scenes cycling over ``classes``, plus near-duplicates and OOD textures."""
    images = []
    for i in range(clean):
        cls = classes[i % len(classes)]
        images.append((f"scene_{i:02d}_c{cls}.png", scene(cls, seed + i)))
    for d in range(duplicates):
        src_name, src = images[d * 3 % clean]
        images.append((src_name.replace(".png", f"_dup{d}.png"), near_duplicate(src, seed + 500 + d)))
    for o in range(ood):
        images.append((f"texture_{o:02d}_ood.png", out_of_distribution(seed + 900 + o)))
    return images


def zip_images(images: list[tuple[str, np.ndarray]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, img in images:
            zf.writestr(name, encode_png(img))
    return buf.getvalue()


def stamp_checkerboard(img: np.ndarray, x: int, y: int, size: int = 8) -> np.ndarray:
    """1px checkerboard patch, the classic BadNets trigger."""
    out = img.copy()
    yy, xx = np.mgrid[0:size, 0:size]
    pattern = np.where((yy + xx) % 2 == 0, 255, 0).astype(np.uint8)
    h, w = out.shape[:2]
    y2, x2 = min(y + size, h), min(x + size, w)
    out[y:y2, x:x2] = pattern[: y2 - y, : x2 - x, None]
    return out
