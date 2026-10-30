"""Pillars III and IV: Trojan interrogation, signed inference, cascades and scoring."""

import hashlib
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend import storage
from backend.api.report import compute_orthogonal_four_pillar_score
from backend.assurance import synthetic
from backend.assurance.inference import signer
from backend.assurance.model.zoo import TARGET_CLASS, build_classifier

PAYLOAD = {
    "inference_id": "c81e728d9d4c2f636f067f89cc14862c",
    "dataset_merkle_root": "a62e33b47f12980c4e19d2b57811f68a90c1e442d8b76a123f90c8812be47ef1",
    "model_id": "0a1de9e07c3f4912a819c7721b54f09d",
    "model_sha256": "00f91613de26c6734fbae69e22f97eb5d411cf768026d433808815068964963a",
    "arch_fingerprint": "bf5c7a2ca7a14a26eb02bdf02be01262",
    "input_sha256": "4a8b9c12d3e4f50192837465a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
    "config_sha256": "7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2e3d4c5b6a7f8e",
    "output": {"top_class": 0, "confidence": 0.9142},
    "timestamp": "2026-10-27T11:42:08.000Z",
}


async def _pipeline(client, cid, trojan=True, seed=42):
    ds = await client.post(
        "/datasets",
        data={"contributor_id": cid, "version": "1.0"},
        files={"file": ("d.zip", synthetic.zip_images(synthetic.demo_dataset(seed=seed)), "application/zip")},
    )
    did = ds.json()["id"]
    await client.post(f"/datasets/{did}/analyze")
    m = await client.post(
        "/models",
        data={"contributor_id": cid, "version": "1.0", "dataset_id": did},
        files={"file": ("m.onnx", build_classifier(trojan=trojan, seed=seed), "application/octet-stream")},
    )
    return did, m.json()


async def _infer(client, mid, img):
    r = await client.post(
        "/inference",
        data={"model_id": mid, "config": '{"precision": "fp32"}'},
        files={"image": ("q.png", synthetic.encode_png(img), "image/png")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_ed25519_signature_rejects_any_field_change():
    sig, pub = signer.sign_evidence_tuple(PAYLOAD)
    assert len(sig) == 128
    assert signer.verify_evidence_signature(PAYLOAD, sig, pub)
    assert signer.verify_evidence_signature(dict(reversed(list(PAYLOAD.items()))), sig, pub)
    for field, value in [("output", {"top_class": 7, "confidence": 0.99}), ("model_sha256", "0" * 64)]:
        assert not signer.verify_evidence_signature({**PAYLOAD, field: value}, sig, pub)
    assert not signer.verify_evidence_signature(PAYLOAD, None, pub)


def test_scoring_keeps_model_integrity_separate_from_trojan_risk():
    suspicious_but_intact = compute_orthogonal_four_pillar_score(
        ds_intact_ratio=1.0,
        dup_count=6,
        ood_count=1,
        model_hash_intact_ratio=1.0,
        max_backdoor_confidence=0.998,
        valid_signed_inference_ratio=1.0,
    )
    assert suspicious_but_intact["model_integrity"] == 100.0
    assert suspicious_but_intact["backdoor_screening"] == 0.0
    assert suspicious_but_intact["dataset_integrity"] == 42.0  # 100 - 10*5 - 8*1
    assert suspicious_but_intact["overall"] == 63.4

    tampered = compute_orthogonal_four_pillar_score(1.0, 0, 0, 0.5, 0.0, 1.0, model_tampered_ratio=0.5)
    assert tampered["model_integrity"] == 0.0
    assert tampered["backdoor_screening"] == 100.0


async def test_trojaned_model_is_flagged_with_evidence(client, contributor):
    _, model = await _pipeline(client, contributor["id"], trojan=True)
    r = await client.post(f"/models/{model['id']}/backdoor-scan")
    assert r.status_code == 200, r.text
    scan = r.json()

    assert scan["verdict"] == "suspicious"
    assert scan["probe_source"].startswith("dataset:")
    top = scan["triggers"][0]
    assert top["trigger_type"] == "checkerboard_16px"
    assert top["target_class"] == TARGET_CLASS
    assert top["consistency_rate"] > 0.9
    assert top["escalated"] and top["cluster_score"] > 0.3
    assert top["strip_entropy_drop"] > 0.5
    flip = top["evidence"]["flips"][0]
    assert flip["before"].startswith("data:image/png;base64,") and flip["after"].startswith("data:image/png")
    groups = {p["group"] for p in top["evidence"]["activation_scatter"]}
    assert groups == {"clean", "triggered"}
    assert all(t["confidence"] < 0.3 for t in scan["triggers"][1:])

    model_now = (await client.get(f"/models/{model['id']}")).json()
    assert model_now["status"] == "suspicious"
    latest = (await client.get(f"/models/{model['id']}/backdoor-scans/latest")).json()
    assert latest["scan_id"] == scan["scan_id"]
    findings = (await client.get(f"/models/{model['id']}/backdoor-findings")).json()
    assert len(findings) == len(scan["triggers"])


async def test_clean_twin_passes_without_escalation(client, contributor):
    _, model = await _pipeline(client, contributor["id"], trojan=False)
    scan = (await client.post(f"/models/{model['id']}/backdoor-scan")).json()
    assert scan["verdict"] == "clean"
    assert scan["escalated"] == []
    assert (await client.get(f"/models/{model['id']}")).json()["status"] == "verified"


async def test_tampered_model_cannot_be_scanned(client, contributor):
    _, model = await _pipeline(client, contributor["id"], trojan=False, seed=3)
    await client.post(f"/demo/models/{model['id']}/tamper")
    assert (await client.post(f"/models/{model['id']}/backdoor-scan")).status_code == 409


async def test_inference_is_signed_and_reverifies(client, contributor):
    did, model = await _pipeline(client, contributor["id"], trojan=True, seed=11)
    inf = await _infer(client, model["id"], synthetic.stamp_checkerboard(synthetic.scene(2, 5), 44, 44, 16))
    assert inf["output"]["top_class"] == TARGET_CLASS
    assert len(inf["signature"]) == 128
    assert inf["public_key"] == (await client.get("/keys/public")).json()["public_key"]
    dataset = (await client.get(f"/datasets/{did}")).json()
    assert inf["dataset_merkle_root"] == dataset["merkle_root"]

    ok = (await client.post(f"/inference/{inf['id']}/reverify")).json()
    assert ok["status"] == "ok"
    assert all(v is not False for v in ok["checks"].values())

    evidence = (await client.get(f"/inference/{inf['id']}/evidence")).json()
    assert evidence["signature"]["value"] == inf["signature"]


async def test_reverify_catches_edited_evidence_and_swapped_input(client, contributor):
    _, model = await _pipeline(client, contributor["id"], trojan=False, seed=12)
    inf = await _infer(client, model["id"], synthetic.scene(1, 3))

    path = storage.inference() / f"{inf['id']}.json"
    doc = json.loads(path.read_text())
    doc["output"]["top_class"] = 9
    path.write_text(json.dumps(doc))
    edited = (await client.post(f"/inference/{inf['id']}/reverify")).json()
    assert edited["status"] == "mismatch"
    assert edited["checks"]["record_matches_evidence"] is False
    assert edited["checks"]["signature_valid"] is True

    inf2 = await _infer(client, model["id"], synthetic.scene(3, 4))
    (storage.area("inference/inputs") / inf2["input_sha256"]).write_bytes(b"swapped input")
    swapped = (await client.post(f"/inference/{inf2['id']}/reverify")).json()
    assert swapped["checks"]["input_hash_match"] is False


async def test_model_tamper_cascades_to_its_inferences_only(client, contributor):
    _, victim = await _pipeline(client, contributor["id"], trojan=False, seed=21)
    _, bystander = await _pipeline(client, contributor["id"], trojan=False, seed=22)
    victim_infs = [await _infer(client, victim["id"], synthetic.scene(c, 9)) for c in (0, 1)]
    safe = await _infer(client, bystander["id"], synthetic.scene(2, 9))

    r = (await client.post(f"/demo/models/{victim['id']}/tamper")).json()
    assert sorted(r["invalidated_inferences"]) == sorted(i["id"] for i in victim_infs)
    for inf in victim_infs:
        assert (await client.get(f"/inference/{inf['id']}")).json()["status"] == "mismatch"
    assert (await client.get(f"/inference/{safe['id']}")).json()["status"] == "ok"

    audit = (await client.get("/audit", params={"artifact_id": victim_infs[0]["id"]})).json()
    assert audit[0]["action"] == "inference.invalidate"

    await client.post(f"/demo/models/{victim['id']}/restore")
    await client.post(f"/models/{victim['id']}/verify")
    healed = (await client.post(f"/inference/{victim_infs[0]['id']}/reverify")).json()
    assert healed["status"] == "ok"


async def test_dataset_tamper_cascades_through_models(client, contributor):
    did, model = await _pipeline(client, contributor["id"], trojan=False, seed=31)
    inf = await _infer(client, model["id"], synthetic.scene(0, 2))
    await client.post(f"/demo/datasets/{did}/tamper")
    verdict = (await client.post(f"/datasets/{did}/verify")).json()
    assert verdict["invalidated_inferences"] == [inf["id"]]
    check = (await client.post(f"/inference/{inf['id']}/reverify")).json()
    assert check["checks"]["dataset_root_match"] is False


async def test_certificates_verify_and_detect_forgery(client, contributor):
    await _pipeline(client, contributor["id"], trojan=True, seed=41)
    cert = (await client.get(f"/report/{contributor['id']}/certificate")).json()
    good = (await client.post("/report/certificate/verify", json=cert)).json()
    assert good == {"signature_valid": True, "trusted_key": True, "key_id": cert["signature"]["key_id"]}

    forged = json.loads(json.dumps(cert))
    forged["document"]["report"]["score"]["overall"] = 99.9
    assert (await client.post("/report/certificate/verify", json=forged)).json()["signature_valid"] is False

    rogue = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(signer.canonical_bytes(forged["document"])).digest()
    forged["signature"]["value"] = rogue.sign(digest).hex()
    forged["signature"]["public_key"] = rogue.public_key().public_bytes_raw().hex()
    resigned = (await client.post("/report/certificate/verify", json=forged)).json()
    assert resigned["signature_valid"] is True
    assert resigned["trusted_key"] is False


async def test_seeded_demo_exercises_every_pillar(client):
    from backend.main import app
    from scripts.seed_demo import seed_demo_data

    ids = await seed_demo_data(app=app)
    report = (await client.get(f"/report/{ids['contributor_id']}")).json()
    pillars = {p["key"]: p for p in report["pillars"]}
    assert all(p["assessed"] for p in pillars.values())
    assert pillars["model_integrity"]["score"] == 100.0
    assert pillars["backdoor_screening"]["score"] < 20
    assert pillars["inference_binding"]["score"] == 100.0
    assert report["findings_count"]["models_suspicious"] == 1
