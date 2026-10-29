"""Lineage, audit trail and core registration flows."""

import io
import zipfile


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


async def test_health_reports_version(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"]


async def test_contributor_round_trip(client, contributor):
    r = await client.get(f"/contributors/{contributor['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Test Lab"
    assert r.json()["created_at"].endswith("Z")


async def test_unknown_contributor_is_404(client):
    r = await client.get("/contributors/does-not-exist")
    assert r.status_code == 404


async def test_chain_links_dataset_to_model(client, contributor):
    cid = contributor["id"]
    ds = await client.post(
        "/datasets",
        data={"contributor_id": cid, "version": "1.0"},
        files={"file": ("d.zip", _zip_bytes({"a.txt": b"x"}), "application/zip")},
    )
    assert ds.status_code == 201
    did = ds.json()["id"]

    m = await client.post(
        "/models",
        data={"contributor_id": cid, "version": "1.0", "dataset_id": did},
        files={"file": ("m.onnx", b"not really onnx", "application/octet-stream")},
    )
    assert m.status_code == 201
    mid = m.json()["id"]
    assert m.json()["dataset_id"] == did

    chain = (await client.get(f"/chain/{cid}")).json()
    edges = {(e["source"], e["target"]) for e in chain["edges"]}
    assert (cid, did) in edges
    assert (did, mid) in edges
    assert (cid, mid) not in edges
    tiers = {n["id"]: n["tier"] for n in chain["nodes"]}
    assert tiers[cid] == 0 and tiers[did] == 1 and tiers[mid] == 2


async def test_model_with_unknown_dataset_is_rejected(client, contributor):
    r = await client.post(
        "/models",
        data={"contributor_id": contributor["id"], "version": "1.0", "dataset_id": "nope"},
        files={"file": ("m.onnx", b"bytes", "application/octet-stream")},
    )
    assert r.status_code == 404


async def test_mutations_write_audit_entries(client, contributor):
    cid = contributor["id"]
    m = await client.post(
        "/models",
        data={"contributor_id": cid, "version": "2.0"},
        files={"file": ("m.onnx", b"audit me", "application/octet-stream")},
        headers={"X-Visentra-Actor": "auditor@lab"},
    )
    mid = m.json()["id"]
    await client.post(f"/models/{mid}/verify")

    entries = (await client.get("/audit", params={"artifact_id": mid})).json()
    actions = [e["action"] for e in entries]
    assert "model.upload" in actions
    assert "model.verify" in actions
    upload = next(e for e in entries if e["action"] == "model.upload")
    assert upload["actor"] == "auditor@lab"

    created = (await client.get("/audit", params={"artifact_id": cid})).json()
    assert created[0]["action"] == "contributor.create"
