"""VisentraBench harness: statistics, a miniature run, and the results endpoint."""

import json

from backend.bench import visentrabench as vb
from backend.config import settings


def test_wilson_interval_matches_known_values():
    assert vb.wilson(0, 0) == (0.0, 0.0)
    lo, hi = vb.wilson(142, 144)
    assert 95.0 < lo < 96.0 and 99.5 < hi < 100.0
    lo, hi = vb.wilson(0, 36)
    assert lo == 0.0 and 9.0 < hi < 10.0


def test_miniature_run_scores_every_stratum():
    result = vb.run(per_variant=1, seeds=[42])
    assert result["total_pipelines"] == 10
    assert result["per_stratum"]["S1_clean"] == 2
    visentra = result["methods"]["VISENTRA_complete"]
    hash_only = result["methods"]["B1_hash_only"]

    # Hash checks catch exactly the binary and ledger attacks.
    for variant in ("bit_flip", "checkpoint_swap", "ledger_model_swap", "ledger_output_edit"):
        assert hash_only["by_variant"][variant] == 100.0
    for variant in ("duplicate_poison", "ood_injection", "patch_strong"):
        assert hash_only["by_variant"][variant] == 0.0

    # The full system covers what hashes cannot.
    assert visentra["by_variant"]["patch_strong"] == 100.0
    assert visentra["by_variant"]["duplicate_poison"] == 100.0
    assert visentra["overall_recall"] > hash_only["overall_recall"]
    assert "B5_full_neural_cleanse" in result["not_run"]


async def test_results_endpoint_serves_the_file(client, tmp_path, monkeypatch):
    missing = tmp_path / "none.json"
    monkeypatch.setattr(settings, "bench_results", str(missing))
    assert (await client.get("/bench/latest")).status_code == 404

    path = tmp_path / "bench.json"
    path.write_text(json.dumps({"benchmark": "VisentraBench-1", "methods": {}}))
    monkeypatch.setattr(settings, "bench_results", str(path))
    r = await client.get("/bench/latest")
    assert r.status_code == 200
    assert r.json()["benchmark"] == "VisentraBench-1"
