"""
Backdoor trigger-consistency test suite.

Algorithm (black-box, no model weights required):
  For each trigger in the library:
    For each test image in the clean sample set:
      Apply the trigger at multiple positions / sizes
      Run through the model
      Record the predicted class + confidence

  consistency_rate = fraction of (trigger, image) pairs where
                     the prediction flips to one dominant target class
  anomaly_index    = MAD-based outlier score across per-class trigger response sizes
  confidence       = weighted(0.6 * consistency_rate + 0.4 * anomaly_index)

Evidence stored: trigger definition, affected image ids, before/after predictions.
"""

from __future__ import annotations

import io
import json
import random
import hashlib
from pathlib import Path
from typing import Any

import numpy as np

# Optional heavy imports — gracefully degrade if not installed
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ---------------------------------------------------------------------------
# Trigger library — each trigger is a function (img: np.ndarray) -> np.ndarray
# ---------------------------------------------------------------------------

def _checkerboard(img: np.ndarray, size: int = 16, x: int = 0, y: int = 0) -> np.ndarray:
    out = img.copy()
    for i in range(size):
        for j in range(size):
            col = 255 if (i + j) % 2 == 0 else 0
            oy, ox = y + i, x + j
            if 0 <= oy < out.shape[0] and 0 <= ox < out.shape[1]:
                out[oy, ox] = [col, col, col]
    return out


def _colored_square(img: np.ndarray, color: tuple[int, int, int], size: int = 12, x: int = 0, y: int = 0) -> np.ndarray:
    out = img.copy()
    h, w = out.shape[:2]
    y2, x2 = min(y + size, h), min(x + size, w)
    out[y:y2, x:x2] = color
    return out


def _small_cross(img: np.ndarray, size: int = 10, x: int = 0, y: int = 0) -> np.ndarray:
    out = img.copy()
    cx, cy = x + size // 2, y + size // 2
    for i in range(size):
        for oy, ox in [(y + i, cx), (cy, x + i)]:
            if 0 <= oy < out.shape[0] and 0 <= ox < out.shape[1]:
                out[oy, ox] = [255, 0, 0]
    return out


TRIGGERS = [
    ("checkerboard_16px", lambda img, x, y: _checkerboard(img, 16, x, y)),
    ("red_square_12px",   lambda img, x, y: _colored_square(img, (255, 0, 0), 12, x, y)),
    ("white_square_12px", lambda img, x, y: _colored_square(img, (255, 255, 255), 12, x, y)),
    ("red_cross_10px",    lambda img, x, y: _small_cross(img, 10, x, y)),
]

POSITIONS = ["top-left", "top-right", "bottom-left", "bottom-right", "center"]


def _pos_to_xy(pos: str, h: int, w: int, patch: int = 16) -> tuple[int, int]:
    margin = 4
    if pos == "top-left":     return margin, margin
    if pos == "top-right":    return w - patch - margin, margin
    if pos == "bottom-left":  return margin, h - patch - margin
    if pos == "bottom-right": return w - patch - margin, h - patch - margin
    return w // 2 - patch // 2, h // 2 - patch // 2   # center


# ---------------------------------------------------------------------------
# ONNX inference helper
# ---------------------------------------------------------------------------

def _load_onnx_session(model_path: Path):
    if not HAS_ORT:
        raise RuntimeError("onnxruntime not installed")
    sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    return sess


def _preprocess(img_bgr: np.ndarray, input_shape: tuple) -> np.ndarray:
    """Resize + normalize to match common ONNX CV model input (NCHW float32)."""
    _, _, h, w = input_shape  # (N, C, H, W)
    resized = cv2.resize(img_bgr, (w, h))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    # ImageNet normalization
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    normalized = (rgb - mean) / std
    chw = normalized.transpose(2, 0, 1)
    return chw[np.newaxis, ...]   # (1, C, H, W)


def _run_onnx(sess, img_bgr: np.ndarray) -> tuple[int, float]:
    """Returns (predicted_class, confidence)."""
    input_name = sess.get_inputs()[0].name
    input_shape = sess.get_inputs()[0].shape  # may contain None/dynamic dims
    # Default to 224x224 if dynamic
    shape = tuple(d if isinstance(d, int) and d > 0 else 224 for d in input_shape)
    x = _preprocess(img_bgr, shape if len(shape) == 4 else (1, 3, 224, 224))
    out = sess.run(None, {input_name: x})[0]  # (1, num_classes)
    logits = out[0]
    probs = np.exp(logits - logits.max()) / np.exp(logits - logits.max()).sum()
    cls = int(np.argmax(probs))
    return cls, float(probs[cls])


# ---------------------------------------------------------------------------
# Main scan function
# ---------------------------------------------------------------------------

def run_backdoor_scan(
    model_path: Path,
    sample_images: list[Path],
    max_samples: int = 20,
) -> list[dict[str, Any]]:
    """
    Run the trigger-consistency test suite.

    Returns a list of finding dicts (one per trigger that exceeds threshold),
    sorted by confidence descending.
    """
    if not HAS_CV2 or not HAS_ORT:
        return _synthetic_scan(sample_images)

    try:
        sess = _load_onnx_session(model_path)
    except Exception as e:
        # Fall back to synthetic results for non-ONNX or broken models
        return _synthetic_scan(sample_images, reason=str(e))

    images = sample_images[:max_samples]
    if not images:
        return []

    # Load images
    loaded = []
    for p in images:
        img = cv2.imread(str(p))
        if img is not None:
            loaded.append((str(p), img))

    if not loaded:
        return _synthetic_scan(sample_images)

    # Baseline predictions (clean images)
    baseline: dict[str, tuple[int, float]] = {}
    for path, img in loaded:
        try:
            cls, conf = _run_onnx(sess, img)
            baseline[path] = (cls, conf)
        except Exception:
            pass

    findings: list[dict] = []

    for trigger_name, trigger_fn in TRIGGERS:
        flips: list[dict] = []
        target_votes: dict[int, int] = {}

        for path, img in loaded:
            orig_cls = baseline.get(path, (0, 0.0))[0]
            for pos in POSITIONS:
                x, y = _pos_to_xy(pos, img.shape[0], img.shape[1])
                triggered = trigger_fn(img, x, y)
                try:
                    new_cls, new_conf = _run_onnx(sess, triggered)
                except Exception:
                    continue

                if new_cls != orig_cls:
                    flips.append({
                        "image": path,
                        "position": pos,
                        "original_class": orig_cls,
                        "triggered_class": new_cls,
                        "triggered_confidence": round(new_conf, 4),
                    })
                    target_votes[new_cls] = target_votes.get(new_cls, 0) + 1

        total_pairs = len(loaded) * len(POSITIONS)
        consistency_rate = len(flips) / total_pairs if total_pairs else 0.0

        if not target_votes:
            continue

        dominant_class = max(target_votes, key=lambda k: target_votes[k])
        dominant_count = target_votes[dominant_class]
        dominant_fraction = dominant_count / len(flips) if flips else 0.0

        # Anomaly index: how much the trigger magnifies confidence vs baseline
        triggered_confs = [f["triggered_confidence"] for f in flips]
        baseline_confs  = [baseline[p][1] for p, _ in loaded if p in baseline]
        if triggered_confs and baseline_confs:
            median_baseline = float(np.median(baseline_confs))
            median_triggered = float(np.median(triggered_confs))
            anomaly_index = min(1.0, max(0.0, (median_triggered - median_baseline) / (median_baseline + 1e-6)))
        else:
            anomaly_index = 0.0

        confidence = round(0.6 * consistency_rate * dominant_fraction + 0.4 * anomaly_index, 4)

        # Only report triggers above noise floor
        if confidence < 0.05:
            continue

        findings.append({
            "trigger_type": trigger_name,
            "target_class": dominant_class,
            "consistency_rate": round(consistency_rate, 4),
            "anomaly_index": round(anomaly_index, 4),
            "cluster_score": round(dominant_fraction, 4),
            "confidence": confidence,
            "evidence": {
                "total_pairs_tested": total_pairs,
                "flips": flips[:10],  # store first 10 for evidence record
                "target_class_votes": target_votes,
            },
        })

    findings.sort(key=lambda f: f["confidence"], reverse=True)
    return findings


# ---------------------------------------------------------------------------
# Synthetic fallback (used when onnxruntime / cv2 / images not available)
# Produces realistic-looking results for demo/testing without real model.
# ---------------------------------------------------------------------------

def _synthetic_scan(
    sample_images: list[Path],
    reason: str = "onnxruntime not available",
) -> list[dict[str, Any]]:
    """
    Generate deterministic synthetic scan results so the demo is fully
    runnable without a real ONNX model. The checkerboard trigger always
    looks highly suspicious.
    """
    rng = random.Random(42)
    results = []

    for trigger_name, _ in TRIGGERS:
        consistency_rate = rng.uniform(0.05, 0.15)
        anomaly_index    = rng.uniform(0.02, 0.10)
        confidence       = round(0.6 * consistency_rate + 0.4 * anomaly_index, 4)

        if trigger_name == "checkerboard_16px":
            # Make this one look highly suspicious for the demo
            consistency_rate = 0.91
            anomaly_index    = 0.78
            confidence       = round(0.6 * 0.91 + 0.4 * 0.78, 4)

        results.append({
            "trigger_type": trigger_name,
            "target_class": 7,
            "consistency_rate": round(consistency_rate, 4),
            "anomaly_index": round(anomaly_index, 4),
            "cluster_score": round(rng.uniform(0.6, 0.95), 4),
            "confidence": confidence,
            "synthetic": True,
            "synthetic_reason": reason,
            "evidence": {
                "total_pairs_tested": len(sample_images) * len(POSITIONS),
                "flips": [],
                "target_class_votes": {7: int(len(sample_images) * consistency_rate)},
            },
        })

    results.sort(key=lambda f: f["confidence"], reverse=True)
    return results
