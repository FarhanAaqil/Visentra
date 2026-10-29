"""VISENTRA demo seeder.

Builds a deterministic pipeline that exercises all four pillars with real
artifacts, no synthetic fallbacks:

  1. Contributor "VISENTRA Demo"
  2. A procedural 18 image dataset with a planted near-duplicate and an OOD
     texture, unpacked, Merkle sealed and screened
  3. Model v1.0, an ONNX classifier with a planted checkerboard Trojan,
     trained on that dataset and interrogated (comes back suspicious)
  4. Model v1.1, the clean twin with identical topology (comes back clean)
  5. Signed inferences on both, including one checkerboard-stamped query
     that the Trojan hijacks to class 7

Run it against a live server:

    python scripts/seed_demo.py            # uses VISENTRA_API or http://localhost:8000

or let the backend call ``seed_demo_data(app=app)`` on first start.
"""

import asyncio
import contextlib
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.assurance import synthetic  # noqa: E402
from backend.assurance.model.zoo import build_classifier  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = os.getenv("VISENTRA_API", "http://localhost:8000")
DEMO_NAME = "VISENTRA Demo"
IDS_FILE = Path(__file__).resolve().parent / "demo_ids.json"
HEADERS = {"X-Visentra-Actor": "seed-script"}


def _ok(r: httpx.Response) -> dict:
    if r.status_code >= 400:
        raise RuntimeError(f"{r.request.method} {r.request.url.path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


async def _upload_model(client: httpx.AsyncClient, cid: str, did: str, version: str, trojan: bool) -> dict:
    name = f"traffic_classifier_v{version}.onnx"
    return _ok(
        await client.post(
            "/models",
            data={"contributor_id": cid, "version": version, "dataset_id": did},
            files={"file": (name, build_classifier(trojan=trojan), "application/octet-stream")},
        )
    )


async def _infer(client: httpx.AsyncClient, mid: str, name: str, img, config: dict) -> dict:
    return _ok(
        await client.post(
            "/inference",
            data={"model_id": mid, "config": json.dumps(config, sort_keys=True)},
            files={"image": (name, synthetic.encode_png(img), "image/png")},
        )
    )


async def _run_seed_steps(client: httpx.AsyncClient) -> dict:
    existing = next((c for c in _ok(await client.get("/contributors")) if c["name"] == DEMO_NAME), None)
    if existing:
        print(f"Demo data already present (contributor {existing['id']}), nothing to do.")
        if IDS_FILE.exists():
            return json.loads(IDS_FILE.read_text())
        return {"contributor_id": existing["id"]}

    print("[1] Registering contributor")
    cid = _ok(await client.post("/contributors", json={"name": DEMO_NAME, "role": "Assurance Lead"}))["id"]

    print("[2] Uploading and screening the dataset")
    archive = synthetic.zip_images(synthetic.demo_dataset(seed=42))
    ds = _ok(
        await client.post(
            "/datasets",
            data={"contributor_id": cid, "version": "1.0"},
            files={"file": ("traffic_scenes_v1.zip", archive, "application/zip")},
        )
    )
    did = ds["id"]
    analysis = _ok(await client.post(f"/datasets/{did}/analyze"))
    print(
        f"    {ds['sample_count']} samples, Merkle root {ds['merkle_root'][:16]}…, "
        f"{analysis['duplicate_pairs']} duplicate pair(s), {analysis['ood_flagged']} OOD sample(s)"
    )

    print("[3] Registering model v1.0 (carries a planted Trojan) and interrogating it")
    trojan = await _upload_model(client, cid, did, "1.0", trojan=True)
    scan = _ok(await client.post(f"/models/{trojan['id']}/backdoor-scan"))
    top = scan["triggers"][0]
    print(f"    verdict {scan['verdict']}, top trigger {top['trigger_type']} (C_bd={top['confidence']:.2f})")

    print("[4] Registering model v1.1 (clean twin) and interrogating it")
    clean = await _upload_model(client, cid, did, "1.1", trojan=False)
    clean_scan = _ok(await client.post(f"/models/{clean['id']}/backdoor-scan"))
    print(f"    verdict {clean_scan['verdict']}, top C_bd={clean_scan['top_confidence']:.2f}")

    print("[5] Running signed inferences")
    config = {"batch_size": 1, "precision": "fp32", "threshold": 0.5}
    inferences = [
        await _infer(client, trojan["id"], "query_amber_01.png", synthetic.scene(1, 8001), config),
        await _infer(client, trojan["id"], "query_azure_02.png", synthetic.scene(3, 8002), config),
        await _infer(
            client,
            trojan["id"],
            "query_leaf_stamped_03.png",
            synthetic.stamp_checkerboard(synthetic.scene(2, 8003), 44, 44, 16),
            config,
        ),
        await _infer(client, clean["id"], "query_crimson_04.png", synthetic.scene(0, 8004), config),
        await _infer(
            client,
            clean["id"],
            "query_leaf_stamped_05.png",
            synthetic.stamp_checkerboard(synthetic.scene(2, 8003), 44, 44, 16),
            config,
        ),
    ]
    for inf in inferences:
        print(f"    {inf['id'][:8]} -> class {inf['output']['top_class']} ({inf['confidence']:.2f}), signed")

    ids = {
        "contributor_id": cid,
        "dataset_id": did,
        "model_id": trojan["id"],
        "clean_model_id": clean["id"],
        "inference_ids": [i["id"] for i in inferences],
    }
    with contextlib.suppress(OSError):  # read-only checkouts can still seed
        IDS_FILE.write_text(json.dumps(ids, indent=2))
    print("Demo pipeline ready.")
    return ids


async def seed_demo_data(app=None, base_url: str | None = None) -> dict:
    """Seed in-process through ASGI when ``app`` is given, otherwise over HTTP."""
    if app is not None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://seed", timeout=120, headers=HEADERS
        ) as c:
            return await _run_seed_steps(c)

    url = (base_url or BASE_URL).rstrip("/")
    async with httpx.AsyncClient(base_url=url, timeout=120, headers=HEADERS) as client:
        try:
            _ok(await client.get("/health", timeout=5))
        except Exception as e:
            print(f"Cannot reach the backend at {url}: {e}")
            print("Start it first: uvicorn backend.main:app --port 8000")
            return {}
        return await _run_seed_steps(client)


def main() -> None:
    asyncio.run(seed_demo_data(base_url=BASE_URL))


if __name__ == "__main__":
    main()
