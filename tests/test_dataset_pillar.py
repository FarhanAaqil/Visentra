"""Pillar I: archive unpacking, Merkle sealing, duplicate and OOD screening."""

import hashlib
import io
import zipfile

import numpy as np

from backend import storage
from backend.assurance import synthetic
from backend.assurance.data.dataset_checks import (
    compute_merkle_root,
    hamming_distance_hex,
    score_embeddings,
)


async def _upload(client, cid, payload: bytes, name="demo.zip"):
    r = await client.post(
        "/datasets",
        data={"contributor_id": cid, "version": "1.0"},
        files={"file": (name, payload, "application/zip")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_merkle_root_is_order_independent_and_handles_odd_levels():
    leaves = [hashlib.sha256(bytes([i])).hexdigest() for i in range(5)]
    assert compute_merkle_root(leaves) == compute_merkle_root(list(reversed(leaves)))
    assert compute_merkle_root(leaves) != compute_merkle_root(leaves[:4])
    assert compute_merkle_root([]) == hashlib.sha256(b"").hexdigest()


def test_hamming_distance_counts_bits():
    assert hamming_distance_hex("0000000000000000", "000000000000000f") == 4
    assert hamming_distance_hex("ffff", "ffff") == 0


def test_tiny_sets_are_not_scored():
    scores = score_embeddings(np.random.default_rng(0).normal(size=(4, 512)))
    assert all(s["anomaly_score"] == 0.0 for s in scores)


async def test_upload_unpacks_samples_and_seals_merkle_root(client, contributor):
    images = synthetic.demo_dataset(seed=7)
    ds = await _upload(client, contributor["id"], synthetic.zip_images(images))
    assert ds["sample_count"] == len(images)

    samples = (await client.get(f"/datasets/{ds['id']}/samples")).json()
    assert len(samples) == len(images)
    assert all(s["phash"] and len(s["phash"]) == 16 for s in samples)
    assert ds["merkle_root"] == compute_merkle_root([s["sha256"] for s in samples])


async def test_hostile_member_names_cannot_escape_storage(client, contributor):
    buf = io.BytesIO()
    png = synthetic.encode_png(synthetic.scene(1, 3))
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../escape.png", png)
        zf.writestr("notes.txt", b"not an image")
        zf.writestr("broken.png", b"\x89PNG but truncated")
    ds = await _upload(client, contributor["id"], buf.getvalue())

    assert ds["sample_count"] == 1
    assert not (storage.root().parent / "escape.png").exists()
    samples = (await client.get(f"/datasets/{ds['id']}/samples")).json()
    assert samples[0]["name"] == "escape.png"


async def test_analysis_finds_planted_duplicate_and_texture(client, contributor):
    ds = await _upload(client, contributor["id"], synthetic.zip_images(synthetic.demo_dataset(seed=42)))
    r = await client.post(f"/datasets/{ds['id']}/analyze")
    assert r.status_code == 200
    result = r.json()

    assert result["status"] == "flagged"
    assert result["duplicate_pairs"] == 1
    assert result["ood_flagged"] == 1
    ood = next(f for f in result["findings"] if f["check"] == "ood_anomaly")
    assert ood["image"].startswith("texture_")
    dup = next(f for f in result["findings"] if f["check"] == "near_duplicate")
    assert "_dup" in dup["image_a"] + dup["image_b"]

    flagged = {s["name"]: s["flags"] for s in (await client.get(f"/datasets/{ds['id']}/samples")).json()}
    assert "ood" in flagged[ood["image"]]

    # Re-running replaces the verdict rather than duplicating it.
    await client.post(f"/datasets/{ds['id']}/analyze")
    findings = (await client.get(f"/datasets/{ds['id']}/findings")).json()
    assert sum(f["check_type"] == "near_duplicate" for f in findings) == 1
    assert sum(f["check_type"] == "analysis_summary" for f in findings) == 1


async def test_clean_dataset_passes_screening(client, contributor):
    clean = synthetic.demo_dataset(seed=101, duplicates=0, ood=0)
    ds = await _upload(client, contributor["id"], synthetic.zip_images(clean))
    result = (await client.post(f"/datasets/{ds['id']}/analyze")).json()
    assert result["status"] == "verified"
    assert result["ood_flagged"] == 0 and result["duplicate_pairs"] == 0


async def test_thumbnails_are_scoped_to_their_dataset(client, contributor):
    a = await _upload(client, contributor["id"], synthetic.zip_images(synthetic.demo_dataset(seed=1)[:3]))
    b = await _upload(client, contributor["id"], synthetic.zip_images(synthetic.demo_dataset(seed=2)[:3]))
    sample_a = (await client.get(f"/datasets/{a['id']}/samples")).json()[0]

    ok = await client.get(f"/datasets/{a['id']}/samples/{sample_a['id']}/thumbnail", params={"size": 64})
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "image/jpeg"

    cross = await client.get(f"/datasets/{b['id']}/samples/{sample_a['id']}/thumbnail")
    assert cross.status_code == 404
    assert (await client.get(f"/datasets/{a['id']}/samples/nope/thumbnail")).status_code == 404


async def test_poisoned_sample_breaks_merkle_root_until_restored(client, contributor):
    ds = await _upload(client, contributor["id"], synthetic.zip_images(synthetic.demo_dataset(seed=5)))
    assert (await client.post(f"/datasets/{ds['id']}/verify")).json()["status"] == "verified"

    tamper = (await client.post(f"/demo/datasets/{ds['id']}/tamper")).json()
    verdict = (await client.post(f"/datasets/{ds['id']}/verify")).json()
    assert verdict["status"] == "tampered"
    assert verdict["integrity"]["archive_match"] is True
    assert verdict["integrity"]["merkle_match"] is False
    assert verdict["integrity"]["changed_samples"] == [tamper["sample_id"]]

    blocked = await client.post(f"/datasets/{ds['id']}/analyze")
    assert blocked.status_code == 409

    await client.post(f"/demo/datasets/{ds['id']}/restore")
    healed = (await client.post(f"/datasets/{ds['id']}/verify")).json()
    assert healed["status"] == "verified"
    assert healed["integrity"]["recomputed_merkle_root"] == ds["merkle_root"]
