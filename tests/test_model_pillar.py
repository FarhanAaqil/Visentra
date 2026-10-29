"""Pillar II: sandboxed inspection, topology fingerprints, bit-flip tamper and restore."""

import subprocess
import sys
import textwrap

import onnx
import pytest

from backend.assurance import synthetic
from backend.assurance.model.zoo import TARGET_CLASS, build_classifier
from backend.config import settings
from backend.sandbox import runner


async def _upload_model(client, cid, payload: bytes, name="model.onnx", dataset_id=None):
    data = {"contributor_id": cid, "version": "1.0"}
    if dataset_id:
        data["dataset_id"] = dataset_id
    r = await client.post("/models", data=data, files={"file": (name, payload, "application/octet-stream")})
    assert r.status_code == 201, r.text
    return r.json()


async def _infer(client, model_id, img):
    return await client.post(
        "/inference",
        data={"model_id": model_id, "config": "{}"},
        files={"image": ("q.png", synthetic.encode_png(img), "image/png")},
    )


def test_fingerprint_ignores_node_names_but_not_structure(tmp_path):
    original = tmp_path / "a.onnx"
    original.write_bytes(build_classifier(trojan=True))
    model = onnx.load(str(original))
    for i, node in enumerate(model.graph.node):
        node.name = f"exporter_{i}"
    renamed = tmp_path / "b.onnx"
    renamed.write_bytes(model.SerializeToString())

    model.graph.node[1].op_type = "Sigmoid"
    altered = tmp_path / "c.onnx"
    altered.write_bytes(model.SerializeToString())

    fp = runner.run_sync("inspect", original)["arch_fingerprint"]
    assert runner.run_sync("inspect", renamed)["arch_fingerprint"] == fp
    assert runner.run_sync("inspect", altered)["arch_fingerprint"] != fp


def test_sandbox_blocks_network_after_hardening():
    code = textwrap.dedent(
        """
        import socket, sys
        sys.path.insert(0, sys.argv[1])
        import worker
        worker._harden(2048, 5)
        for attempt in (lambda: socket.create_connection(("example.com", 80)),
                        lambda: socket.socket().connect(("127.0.0.1", 9))):
            try:
                attempt()
            except PermissionError:
                print("blocked")
        """
    )
    cmd = [sys.executable, "-I", "-c", code, str(runner.WORKER.parent)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert out.stdout.split() == ["blocked", "blocked"], out.stderr


def test_sandbox_enforces_wall_clock_budget(tmp_path, monkeypatch):
    path = tmp_path / "m.onnx"
    path.write_bytes(build_classifier(trojan=False))
    monkeypatch.setattr(settings, "sandbox_timeout_s", 0.01)
    with pytest.raises(runner.SandboxError, match="budget"):
        runner.run_sync("inspect", path)


async def test_upload_inspects_graph_in_the_sandbox(client, contributor):
    m = await _upload_model(client, contributor["id"], build_classifier(trojan=True))
    assert len(m["arch_fingerprint"]) == 32
    graph = m["graph_summary"]
    assert graph["inputs"][0]["shape"][1:] == [3, 64, 64]
    assert graph["preprocess"] == "unit"
    assert graph["penultimate"] == "penultimate"
    assert "no_network" in graph["sandbox_guards"]


async def test_unparseable_and_pickle_models_are_never_executed(client, contributor):
    junk = await _upload_model(client, contributor["id"], b"\x00not protobuf", name="junk.onnx")
    assert junk["arch_fingerprint"] == "unparseable"
    pt = await _upload_model(client, contributor["id"], b"\x80\x04pickle payload", name="weights.pt")
    assert pt["arch_fingerprint"] == "not-executable"
    assert "never loaded" in pt["graph_summary"]["error"]

    r = await _infer(client, pt["id"], synthetic.scene(2, 1))
    assert r.status_code == 422


async def test_sandboxed_inference_classifies_scenes(client, contributor):
    m = await _upload_model(client, contributor["id"], build_classifier(trojan=False))
    r = await _infer(client, m["id"], synthetic.scene(3, 11))
    assert r.status_code == 201, r.text
    assert r.json()["output"]["top_class"] == 3
    assert r.json()["model_sha256"] == m["sha256"]


async def test_trojan_fires_on_checkerboard(client, contributor):
    m = await _upload_model(client, contributor["id"], build_classifier(trojan=True))
    stamped = synthetic.stamp_checkerboard(synthetic.scene(2, 4), 40, 40, 16)
    r = await _infer(client, m["id"], stamped)
    assert r.json()["output"]["top_class"] == TARGET_CLASS


async def test_bit_flip_is_caught_with_real_disk_hash_and_restored(client, contributor):
    m = await _upload_model(client, contributor["id"], build_classifier(trojan=False, seed=9))
    intact = (await client.post(f"/models/{m['id']}/verify")).json()
    assert intact["integrity"]["hash_match"] is True

    flipped = (await client.post(f"/demo/models/{m['id']}/tamper", params={"flips": 6})).json()
    assert len(flipped["flipped_offsets"]) == 6

    verdict = (await client.post(f"/models/{m['id']}/verify")).json()
    assert verdict["status"] == "tampered"
    assert verdict["actual_sha256"] != verdict["sha256"]
    assert verdict["integrity"]["arch_match"] is True  # weights changed, topology did not
    assert verdict["integrity"]["byte_diff"]["bytes_changed"] == 6
    assert verdict["integrity"]["byte_diff"]["first_offsets"] == flipped["flipped_offsets"]
    assert verdict["integrity"]["byte_diff"]["tensors_touched"]

    assert (await _infer(client, m["id"], synthetic.scene(1, 1))).status_code == 422

    await client.post(f"/demo/models/{m['id']}/restore")
    healed = (await client.post(f"/models/{m['id']}/verify")).json()
    assert healed["status"] == "verified"
    assert healed["actual_sha256"] == healed["sha256"]
