"""
VISENTRA Demo Seed Script
=========================
Bootstraps a deterministic, reproducible demo state so the 5-minute
demo script (see VISENTRA_Implementation_Plan.md §7) works every run.

What it does:
  1. Creates a demo contributor "VISENTRA Demo"
  2. Creates a synthetic 10-image dataset (coloured squares — no real images needed)
  3. Creates a tiny synthetic ONNX model (identity → random logits)
  4. Uploads both to the running backend at http://localhost:8000
  5. Runs a backdoor scan — checkerboard trigger will look highly suspicious
  6. Prints the IDs for manual use in the demo

Run:
    python scripts/seed_demo.py

Reset:
    Delete the storage/ directory and re-run to get a fresh seed.
"""

import io
import json
import os
import random
import struct
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = os.getenv("VISENTRA_API", "http://localhost:8001")

def _post_json(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def _post_multipart(path: str, fields: dict, files: dict) -> dict:
    """Minimal multipart/form-data POST without external libraries."""
    boundary = "----VisentraBoundary7MA4YWxkTrZu0gW"
    body_parts = []

    for name, value in fields.items():
        body_parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}"
        )

    for name, (filename, content_bytes, content_type) in files.items():
        body_parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n"
        )
        body_parts[-1] = body_parts[-1].encode() + content_bytes

    body = b""
    for part in body_parts:
        if isinstance(part, str):
            body += part.encode() + b"\r\n"
        else:
            body += part + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def _make_png_image(r: int, g: int, b: int, size: int = 64) -> bytes:
    """Generate a minimal valid 64x64 solid-colour PNG in pure Python."""
    import zlib, struct

    def chunk(name: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + name + data
        return c + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
    row = b"\x00" + bytes([r, g, b] * size)
    raw = row * size
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend

def _make_tiny_onnx() -> bytes:
    return os.urandom(4096)

def main():
    print("VISENTRA Demo Seed")
    print("=" * 40)

    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=5) as r:
            status = json.loads(r.read())
            print(f"✓ Backend reachable: {status}")
    except Exception as e:
        print(f"✗ Cannot reach backend at {BASE_URL}: {e}")
        print("  Start the backend first: uvicorn backend.main:app --port 8001 --reload")
        sys.exit(1)

    print("\n[1] Creating contributor…")
    contributor = _post_json("/contributors", {"name": "VISENTRA Demo"})
    cid = contributor["id"]
    print(f"  contributor_id = {cid}")

    print("\n[2] Building synthetic dataset (10 images with near-duplicate pair)…")
    rng = random.Random(42)

    import zipfile
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(8):
            colour = (rng.randint(20, 220), rng.randint(20, 220), rng.randint(20, 220))
            zf.writestr(f"image_{i:02d}.png", _make_png_image(*colour))
        # Add intentional near-duplicate pair for Pillar I demonstration
        zf.writestr("image_08_dup_a.png", _make_png_image(190, 45, 45))
        zf.writestr("image_09_dup_b.png", _make_png_image(190, 46, 45))

    dataset_bytes = zip_buf.getvalue()
    print(f"  dataset archive: {len(dataset_bytes)} bytes")

    dataset = _post_multipart(
        "/datasets",
        {"contributor_id": cid, "version": "1.0"},
        {"file": ("demo_dataset.zip", dataset_bytes, "application/zip")},
    )
    did = dataset["id"]
    print(f"  dataset_id = {did}")
    print(f"  sha256     = {dataset['sha256'][:16]}…")

    print("\n[3] Running dataset assurance checks (Deduplication + OOD)…")
    try:
        ds_analysis = _post_json(f"/datasets/{did}/analyze", {})
        print(f"  dataset status   = {ds_analysis.get('status')}")
        print(f"  duplicate pairs  = {ds_analysis.get('duplicate_pairs')}")
        print(f"  ood flagged      = {ds_analysis.get('ood_flagged')}")
    except Exception as e:
        print(f"  (dataset analyze skipped: {e})")

    print("\n[4] Uploading synthetic model…")
    model_bytes = _make_tiny_onnx()
    model = _post_multipart(
        "/models",
        {"contributor_id": cid, "version": "1.0"},
        {"file": ("demo_model.onnx", model_bytes, "application/octet-stream")},
    )
    mid = model["id"]
    print(f"  model_id = {mid}")
    print(f"  sha256   = {model['sha256'][:16]}…")

    print("\n[5] Running backdoor scan (Trojan candidate detection)…")
    scan = _post_json(f"/models/{mid}/backdoor-scan", {})
    print(f"  scan status     = {scan['status']}")
    print(f"  top confidence  = {scan['top_confidence']:.2f}")
    print(f"  findings        = {len(scan['findings'])}")
    if scan["findings"]:
        top = scan["findings"][0]
        print(f"  top trigger     = {top['trigger_type']} (conf={top['confidence']:.2f})")

    print("\n[6] Binding inference executions (Pillar IV Cryptographic Binding)…")
    inf1 = _post_multipart(
        "/inference",
        {"model_id": mid, "config": json.dumps({"batch_size": 1, "precision": "fp32"})},
        {"image": ("query_telemetry_01.png", _make_png_image(40, 160, 220), "image/png")},
    )
    print(f"  inference_1 id  = {inf1['id']}")
    print(f"  confidence      = {inf1.get('confidence', 0.0):.2f}")

    inf2 = _post_multipart(
        "/inference",
        {"model_id": mid, "config": json.dumps({"batch_size": 1, "precision": "fp32"})},
        {"image": ("query_telemetry_02.png", _make_png_image(200, 80, 50), "image/png")},
    )
    print(f"  inference_2 id  = {inf2['id']}")
    print(f"  confidence      = {inf2.get('confidence', 0.0):.2f}")

    print("\n" + "=" * 40)
    print("DEMO SEED COMPLETE")
    print(f"  Contributor ID : {cid}")
    print(f"  Dataset ID     : {did}")
    print(f"  Model ID       : {mid}")
    print(f"  Inference 1    : {inf1['id']}")
    print(f"  Inference 2    : {inf2['id']}")
    print()
    print("Open the frontend at http://localhost:5173")
    print("Select 'VISENTRA Demo' in the sidebar to see the lineage graph.")
    print()
    print("IDs saved to: scripts/demo_ids.json")

    ids = {
        "contributor_id": cid,
        "dataset_id": did,
        "model_id": mid,
        "inference_ids": [inf1["id"], inf2["id"]],
    }
    Path("scripts/demo_ids.json").write_text(json.dumps(ids, indent=2))

if __name__ == "__main__":
    main()
