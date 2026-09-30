"""
VISENTRA Demo Seed Script
=========================
Bootstraps a deterministic, reproducible demo state so the 5-minute
demo script (see VISENTRA_Implementation_Plan.md §7) works every run.

What it does:
  1. Creates a demo contributor "VISENTRA Demo"
  2. Creates a synthetic 10-image dataset (with near-duplicate pair)
  3. Runs dataset assurance checks (perceptual hashing & OOD)
  4. Creates and uploads a synthetic ONNX model
  5. Runs a backdoor scan — detects trigger candidates
  6. Binds 2 inference executions with cryptographic signatures
  7. Saves the IDs to scripts/demo_ids.json

Can be run directly via CLI:
    python scripts/seed_demo.py

Or imported by the backend for automatic startup seeding:
    await seed_demo_data(app=app)
"""

import asyncio
import io
import json
import os
import random
import struct
import sys
import zipfile
from pathlib import Path
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = os.getenv("VISENTRA_API", "http://localhost:8001")


def _make_png_image(r: int, g: int, b: int, size: int = 64) -> bytes:
    """Generate a minimal valid 64x64 solid-colour PNG in pure Python."""
    import zlib

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


async def _run_seed_steps(client: httpx.AsyncClient) -> dict:
    # 0. Prevent duplicate data if database already contains the demo data
    try:
        resp = await client.get("/contributors")
        if resp.status_code == 200:
            contributors = resp.json()
            existing_demo = next((c for c in contributors if c.get("name") == "VISENTRA Demo"), None)
            if existing_demo:
                print(f"✓ Demo data already exists (contributor_id = {existing_demo['id']}). Skipping seeding.")
                demo_ids_path = Path(__file__).resolve().parent / "demo_ids.json"
                if demo_ids_path.exists():
                    try:
                        return json.loads(demo_ids_path.read_text())
                    except Exception:
                        pass
                return {"contributor_id": existing_demo["id"]}
    except Exception as e:
        print(f"Note: Could not check existing contributors: {e}")

    print("\n[1] Creating contributor…")
    r = await client.post("/contributors", json={"name": "VISENTRA Demo"})
    r.raise_for_status()
    contributor = r.json()
    cid = contributor["id"]
    print(f"  contributor_id = {cid}")

    print("\n[2] Building synthetic dataset (10 images with near-duplicate pair)…")
    rng = random.Random(42)
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

    r = await client.post(
        "/datasets",
        data={"contributor_id": cid, "version": "1.0"},
        files={"file": ("demo_dataset.zip", dataset_bytes, "application/zip")},
    )
    r.raise_for_status()
    dataset = r.json()
    did = dataset["id"]
    print(f"  dataset_id = {did}")
    print(f"  sha256     = {dataset['sha256'][:16]}…")

    print("\n[3] Running dataset assurance checks (Deduplication + OOD)…")
    try:
        r = await client.post(f"/datasets/{did}/analyze")
        if r.status_code == 200:
            ds_analysis = r.json()
            print(f"  dataset status   = {ds_analysis.get('status')}")
            print(f"  duplicate pairs  = {ds_analysis.get('duplicate_pairs')}")
            print(f"  ood flagged      = {ds_analysis.get('ood_flagged')}")
    except Exception as e:
        print(f"  (dataset analyze skipped: {e})")

    print("\n[4] Uploading synthetic model…")
    model_bytes = _make_tiny_onnx()
    r = await client.post(
        "/models",
        data={"contributor_id": cid, "version": "1.0"},
        files={"file": ("demo_model.onnx", model_bytes, "application/octet-stream")},
    )
    r.raise_for_status()
    model = r.json()
    mid = model["id"]
    print(f"  model_id = {mid}")
    print(f"  sha256   = {model['sha256'][:16]}…")

    print("\n[5] Running backdoor scan (Trojan candidate detection)…")
    try:
        r = await client.post(f"/models/{mid}/backdoor-scan")
        if r.status_code == 200:
            scan = r.json()
            print(f"  scan status     = {scan.get('status')}")
            print(f"  top confidence  = {scan.get('top_confidence', 0.0):.2f}")
            findings = scan.get("findings", [])
            print(f"  findings        = {len(findings)}")
            if findings:
                top = findings[0]
                print(f"  top trigger     = {top.get('trigger_type')} (conf={top.get('confidence', 0.0):.2f})")
    except Exception as e:
        print(f"  (backdoor scan skipped: {e})")

    print("\n[6] Binding inference executions (Pillar IV Cryptographic Binding)…")
    r = await client.post(
        "/inference",
        data={"model_id": mid, "config": json.dumps({"batch_size": 1, "precision": "fp32"})},
        files={"image": ("query_telemetry_01.png", _make_png_image(40, 160, 220), "image/png")},
    )
    r.raise_for_status()
    inf1 = r.json()
    print(f"  inference_1 id  = {inf1['id']}")
    print(f"  confidence      = {inf1.get('confidence', 0.0):.2f}")

    r = await client.post(
        "/inference",
        data={"model_id": mid, "config": json.dumps({"batch_size": 1, "precision": "fp32"})},
        files={"image": ("query_telemetry_02.png", _make_png_image(200, 80, 50), "image/png")},
    )
    r.raise_for_status()
    inf2 = r.json()
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

    ids = {
        "contributor_id": cid,
        "dataset_id": did,
        "model_id": mid,
        "inference_ids": [inf1["id"], inf2["id"]],
    }
    try:
        demo_ids_path = Path(__file__).resolve().parent / "demo_ids.json"
        demo_ids_path.write_text(json.dumps(ids, indent=2))
        print("IDs saved to: scripts/demo_ids.json")
    except Exception:
        pass

    return ids


async def seed_demo_data(app=None, base_url: str | None = None) -> dict:
    """
    Seed VISENTRA demo data.
    If app is provided, executes directly in-memory via httpx ASGITransport (perfect for lifespan startup).
    If base_url is provided (or defaults to VISENTRA_API), connects over HTTP.
    """
    if app is not None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://local-visentra",
            timeout=60.0,
        ) as client:
            return await _run_seed_steps(client)
    else:
        url = (base_url or BASE_URL).rstrip("/")
        async with httpx.AsyncClient(base_url=url, timeout=60.0) as client:
            try:
                resp = await client.get("/health", timeout=5.0)
                if resp.status_code == 200:
                    print(f"✓ Backend reachable at {url}")
            except Exception as e:
                print(f"✗ Cannot reach backend at {url}: {e}")
                print("  Start the backend first: uvicorn backend.main:app --port 8001 --reload")
                return {}
            return await _run_seed_steps(client)


def main():
    print("VISENTRA Demo Seed")
    print("=" * 40)
    asyncio.run(seed_demo_data(base_url=BASE_URL))


if __name__ == "__main__":
    main()
