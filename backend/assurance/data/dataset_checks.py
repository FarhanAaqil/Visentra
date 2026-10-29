"""Dataset assurance engine (Pillar I).

* SHA-256 per sample and a binary Merkle root that seals the whole set.
* 64-bit DCT perceptual hash, near duplicates at Hamming distance <= 8.
* 512-D spatial/spectral embedding (or an ONNX feature extractor when one is
  configured) scored with the hybrid anomaly measure from the blueprint:

      A_ood = 0.55 * s_IF + 0.45 * min(1, d_M / ref)

  s_IF is the Isolation Forest anomaly score 2^(-E[h]/c(n)) in (0, 1), and d_M
  is a leave-one-out Mahalanobis distance in a PCA subspace with Ledoit-Wolf
  shrinkage, normalised by the chi-square 99th percentile for that dimension.
  Both parts are absolute rather than min-max scaled, so a clean dataset does
  not get its "least typical" image flagged by construction.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

HAMMING_THRESHOLD = 8
OOD_THRESHOLD = 0.70
EMBEDDING_DIM = 512
MIN_SAMPLES_FOR_OOD = 6
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def compute_sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_merkle_root(leaf_hashes: list[str]) -> str:
    """Binary SHA-256 Merkle root over sorted leaves (odd levels repeat the last node)."""
    if not leaf_hashes:
        return hashlib.sha256(b"").hexdigest()
    level = [bytes.fromhex(h) for h in sorted(leaf_hashes)]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


def compute_phash(image_path: Path) -> str | None:
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    resized = cv2.resize(img, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    low_freq = cv2.dct(resized)[:8, :8].flatten()
    bits = (low_freq > np.median(low_freq[1:])).astype(np.uint8)
    val = 0
    for b in bits:
        val = (val << 1) | int(b)
    return f"{val:016x}"


def hamming_distance_hex(hash_a: str, hash_b: str) -> int:
    return (int(hash_a, 16) ^ int(hash_b, 16)).bit_count()


def find_near_duplicates(
    samples: list[tuple[str, Path]],
    phashes: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Pairs of samples whose perceptual hashes are within HAMMING_THRESHOLD bits.

    ``samples`` are (sample_id, path) pairs; ``phashes`` may supply precomputed hashes.
    """
    hashes: list[tuple[str, Path, str]] = []
    for sid, path in sorted(samples, key=lambda s: str(s[1])):
        h = (phashes or {}).get(sid) or compute_phash(path)
        if h:
            hashes.append((sid, path, h))

    pairs = []
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            dist = hamming_distance_hex(hashes[i][2], hashes[j][2])
            if dist <= HAMMING_THRESHOLD:
                pairs.append(
                    {
                        "sample_a_id": hashes[i][0],
                        "sample_b_id": hashes[j][0],
                        "image_a": hashes[i][1].name,
                        "image_b": hashes[j][1].name,
                        "phash_a": hashes[i][2],
                        "phash_b": hashes[j][2],
                        "hamming_distance": int(dist),
                        "severity": "critical" if dist == 0 else "warning",
                    }
                )
    return sorted(pairs, key=lambda x: x["hamming_distance"])


def extract_512d_embedding(image_path: Path) -> np.ndarray | None:
    """Hand-built spatial/spectral descriptor: chroma grid, DCT, Laplacian, HOG, histograms."""
    img_bgr = cv2.imread(str(image_path))
    if img_bgr is None:
        return None
    img_64 = cv2.resize(img_bgr, (64, 64), interpolation=cv2.INTER_AREA)
    img_lab = cv2.cvtColor(img_64, cv2.COLOR_BGR2LAB).astype(np.float32) / 255.0
    img_hsv = cv2.cvtColor(img_64, cv2.COLOR_BGR2HSV).astype(np.float32) / 255.0
    gray = cv2.cvtColor(img_64, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

    spatial_chroma: list[float] = []
    for gy in range(4):
        for gx in range(4):
            p_lab = img_lab[gy * 16 : (gy + 1) * 16, gx * 16 : (gx + 1) * 16]
            p_hsv = img_hsv[gy * 16 : (gy + 1) * 16, gx * 16 : (gx + 1) * 16]
            spatial_chroma.extend(p_lab.mean(axis=(0, 1)).tolist())
            spatial_chroma.extend(p_lab.std(axis=(0, 1)).tolist())
            spatial_chroma.extend(p_hsv.mean(axis=(0, 1)).tolist())
            spatial_chroma.extend(p_hsv.std(axis=(0, 1)).tolist())

    dct_block = np.log1p(np.abs(cv2.dct(gray)[:8, :8])).flatten()
    dct_block /= np.linalg.norm(dct_block) + 1e-8

    lap = cv2.Laplacian(gray, cv2.CV_32F)
    lap_vec = np.array(
        [
            float(np.sqrt(np.mean(lap[gy * 8 : (gy + 1) * 8, gx * 8 : (gx + 1) * 8] ** 2)))
            for gy in range(8)
            for gx in range(8)
        ],
        dtype=np.float32,
    )
    lap_vec /= np.linalg.norm(lap_vec) + 1e-8

    gx_s = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy_s = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag, ang = cv2.cartToPolar(gx_s, gy_s, angleInDegrees=True)
    hog_feats: list[float] = []
    for cy in range(4):
        for cx in range(4):
            m_p = mag[cy * 16 : (cy + 1) * 16, cx * 16 : (cx + 1) * 16].flatten()
            a_p = ang[cy * 16 : (cy + 1) * 16, cx * 16 : (cx + 1) * 16].flatten() % 180.0
            hist, _ = np.histogram(a_p, bins=8, range=(0.0, 180.0), weights=m_p)
            hog_feats.extend(hist.astype(np.float32).tolist())
    hog_vec = np.array(hog_feats, dtype=np.float32)
    hog_vec /= np.linalg.norm(hog_vec) + 1e-8

    hist_l = cv2.calcHist([img_lab], [0], None, [32], [0.0, 1.0]).flatten()
    hist_s = cv2.calcHist([img_hsv], [1], None, [32], [0.0, 1.0]).flatten()
    global_ls = np.concatenate([hist_l, hist_s]).astype(np.float32)
    global_ls /= np.linalg.norm(global_ls) + 1e-8

    vec = np.concatenate(
        [
            np.array(spatial_chroma, dtype=np.float32),
            dct_block.astype(np.float32),
            lap_vec,
            hog_vec,
            global_ls,
        ]
    )
    return (vec / (np.linalg.norm(vec) + 1e-8)).astype(np.float32)


@lru_cache(maxsize=2)
def _onnx_session(path: str):
    import onnxruntime as ort

    return ort.InferenceSession(path, providers=["CPUExecutionProvider"])


def _onnx_embedding(image_path: Path, model_path: str) -> np.ndarray | None:
    """Pooled features from an ImageNet-style ONNX backbone, folded down to 512-D."""
    img = cv2.imread(str(image_path))
    if img is None:
        return None
    sess = _onnx_session(model_path)
    rgb = cv2.cvtColor(cv2.resize(img, (224, 224)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    norm = (rgb - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
    feats = np.asarray(sess.run(None, {sess.get_inputs()[0].name: norm.transpose(2, 0, 1)[None]})[0]).ravel()
    if feats.size >= EMBEDDING_DIM:
        feats = feats[: feats.size - feats.size % EMBEDDING_DIM].reshape(EMBEDDING_DIM, -1).mean(axis=1)
    else:
        feats = np.pad(feats, (0, EMBEDDING_DIM - feats.size))
    return (feats / (np.linalg.norm(feats) + 1e-8)).astype(np.float32)


def embed(image_path: Path) -> np.ndarray | None:
    from backend.config import settings

    if settings.embedder_onnx:
        try:
            return _onnx_embedding(image_path, settings.embedder_onnx)
        except Exception:
            pass  # fall back to the built-in descriptor rather than skip the sample
    return extract_512d_embedding(image_path)


def embedder_name() -> str:
    from backend.config import settings

    return "onnx:" + Path(settings.embedder_onnx).name if settings.embedder_onnx else "spatial-spectral-512"


def _isolation_scores(x: np.ndarray, seed: int) -> np.ndarray:
    from sklearn.ensemble import IsolationForest

    forest = IsolationForest(n_estimators=256, random_state=seed, contamination="auto")
    forest.fit(x)
    return -forest.score_samples(x)  # the paper's 2^(-E[h]/c(n)), in (0, 1)


def _mahalanobis_loo(z: np.ndarray) -> tuple[np.ndarray, float]:
    """Leave-one-out Mahalanobis distances plus the p99 reference radius.

    A held-out point measured against a covariance estimated from m = n - 1
    samples follows Hotelling's T^2, so the reference comes from
    F(k, m - k) rather than a chi-square that assumes the covariance is known.
    """
    from scipy.stats import f as f_dist
    from sklearn.covariance import LedoitWolf

    n, k = z.shape
    m = n - 1
    dists = np.zeros(n)
    for i in range(n):
        lw = LedoitWolf().fit(np.delete(z, i, axis=0))
        diff = z[i] - lw.location_
        dists[i] = float(np.sqrt(max(diff @ lw.precision_ @ diff, 0.0)))
    scale = (m - 1) * k * (m + 1) / (m * (m - k))
    return dists, float(np.sqrt(scale * f_dist.ppf(0.99, k, m - k)))


def score_embeddings(x: np.ndarray, seed: int = 42) -> list[dict[str, float]]:
    """Hybrid anomaly score for each row of ``x`` (n x 512)."""
    from sklearn.decomposition import PCA

    n = len(x)
    if n < MIN_SAMPLES_FOR_OOD:
        return [{"anomaly_score": 0.0, "isolation": 0.0, "mahalanobis": 0.0} for _ in range(n)]

    s_if = _isolation_scores(x, seed)
    k = int(min(6, max(2, n // 8)))  # keep roughly 8 samples per covariance dimension
    # Standardise first so the texture blocks are not drowned out by colour variance.
    xs = (x - x.mean(axis=0)) / (x.std(axis=0) + 1e-6)
    z = PCA(n_components=k, random_state=seed).fit_transform(xs)
    d_m, ref = _mahalanobis_loo(z)
    m_part = np.minimum(1.0, d_m / ref)
    scores = 0.55 * s_if + 0.45 * m_part
    return [
        {"anomaly_score": float(s), "isolation": float(i), "mahalanobis": float(m)}
        for s, i, m in zip(scores, s_if, m_part, strict=True)
    ]


def score_ood(
    samples: list[tuple[str, Path]],
    seed: int = 42,
    save_to: Path | None = None,
) -> list[dict[str, Any]]:
    """Score every readable sample; returns per-sample dicts sorted by anomaly score.

    When ``save_to`` is given the embedding matrix is written there as .npy.
    """
    embedded = [(sid, p, embed(p)) for sid, p in sorted(samples, key=lambda s: str(s[1]))]
    embedded = [(sid, p, e) for sid, p, e in embedded if e is not None]
    if not embedded:
        return []

    x = np.stack([e for _, _, e in embedded])
    if save_to is not None:
        np.save(save_to, x)
    scored = score_embeddings(x, seed)
    results = []
    for (sid, path, _), sc in zip(embedded, scored, strict=True):
        flagged = sc["anomaly_score"] > OOD_THRESHOLD
        results.append(
            {
                "sample_id": sid,
                "image": path.name,
                "anomaly_score": round(sc["anomaly_score"], 4),
                "isolation_score": round(sc["isolation"], 4),
                "mahalanobis_score": round(sc["mahalanobis"], 4),
                "embedding_dim": EMBEDDING_DIM,
                "embedder": embedder_name(),
                "flag": "ood" if flagged else None,
                "severity": "warning" if flagged else "info",
            }
        )
    return sorted(results, key=lambda r: r["anomaly_score"], reverse=True)
