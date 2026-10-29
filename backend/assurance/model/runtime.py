"""Preprocessing and batched forward passes, always executed through the sandbox."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from backend.sandbox import runner

DEFAULT_SIDE = 224


@dataclass
class Forward:
    logits: np.ndarray
    probs: np.ndarray
    penultimate: np.ndarray | None


def input_size(graph: dict) -> tuple[int, int]:
    """(height, width) from an NCHW input shape, defaulting symbolic dims to 224."""
    shape = (graph.get("inputs") or [{}])[0].get("shape") or []
    dims = [d if isinstance(d, int) and d > 0 else DEFAULT_SIDE for d in shape[-2:]]
    return (dims[0], dims[1]) if len(dims) == 2 else (DEFAULT_SIDE, DEFAULT_SIDE)


def to_model_rgb(img_bgr: np.ndarray, graph: dict) -> np.ndarray:
    h, w = input_size(graph)
    if img_bgr.shape[:2] != (h, w):
        img_bgr = cv2.resize(img_bgr, (w, h), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def _pack(images_rgb: np.ndarray) -> str:
    buf = io.BytesIO()
    np.save(buf, np.ascontiguousarray(images_rgb, dtype=np.uint8), allow_pickle=False)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _unpack(text: str) -> np.ndarray:
    return np.load(io.BytesIO(base64.b64decode(text)), allow_pickle=False)


def _result(reply: dict) -> Forward:
    logits = _unpack(reply["logits"]).astype(np.float64)
    pen = _unpack(reply["penultimate"]).astype(np.float64) if "penultimate" in reply else None
    return Forward(logits=logits, probs=softmax(logits), penultimate=pen)


def _job(images_rgb: np.ndarray, graph: dict) -> dict:
    return {
        "images": _pack(images_rgb),
        "preprocess": graph.get("preprocess", "imagenet"),
        "penultimate": graph.get("penultimate", ""),
    }


async def forward(model_path: Path, images_rgb: np.ndarray, graph: dict) -> Forward:
    return _result(await runner.run("forward", model_path, **_job(images_rgb, graph)))


def forward_sync(model_path: Path, images_rgb: np.ndarray, graph: dict) -> Forward:
    return _result(runner.run_sync("forward", model_path, **_job(images_rgb, graph)))


async def inspect(model_path: Path) -> dict:
    return await runner.run("inspect", model_path)


def inspect_sync(model_path: Path) -> dict:
    return runner.run_sync("inspect", model_path)
