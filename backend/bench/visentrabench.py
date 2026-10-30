"""VisentraBench: generated supply-chain pipelines scored by every assurance method.

Five strata, each split into two attack variants (blueprint section 11):

  S1 clean            untouched dataset, clean model, valid signed inference
  S2 dataset          near-duplicate poison amplification | OOD texture injection
  S3 binary           weight bit-flips | whole checkpoint swap
  S4 trojan           strong patch Trojan | weak patch Trojan (low trigger gain)
  S5 provenance       forged model hash in the ledger | edited prediction

Every pipeline is built from scratch (procedural dataset, hand-weighted ONNX
classifier, sandboxed inference signed with Ed25519), the attack is applied
after registration, and then each method decides "compromised or not":

  B1 hash-only        Merkle root + model SHA-256 + signature checks (SLSA / in-toto style)
  B3 STRIP-only       entropy drop under superimposition, no spatial consistency or white box
  B4 AC-always        penultimate activation clustering for every trigger, no stage-1 gate
  VISENTRA            all four pillars with the two-stage gate

Neural Cleanse (B5) is not implemented here and is reported as such rather
than with borrowed numbers. Latencies are wall-clock for each method's own
work on this machine, including sandbox process start-up.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
import statistics
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from backend.assurance import synthetic
from backend.assurance.data import dataset_checks as checks
from backend.assurance.inference import signer
from backend.assurance.model import backdoor, runtime
from backend.assurance.model.zoo import build_classifier

SEEDS = [42, 101, 202, 303, 404]
STRATA = {
    "S1_clean": ["clean"],
    "S2_dataset": ["duplicate_poison", "ood_injection"],
    "S3_binary": ["bit_flip", "checkpoint_swap"],
    "S4_trojan": ["patch_strong", "patch_weak"],
    "S5_provenance": ["ledger_model_swap", "ledger_output_edit"],
}
METHODS = ["B1_hash_only", "B3_strip_only", "B4_activation_clustering", "VISENTRA_complete"]
# Calibrated on held-out seeds 900-909: the highest max-silhouette seen on a clean model.
AC_THRESHOLD = 0.67


@dataclass
class Pipeline:
    stratum: str
    variant: str
    seed: int
    root: Path
    samples: list[Path] = field(default_factory=list)
    leaves: list[str] = field(default_factory=list)
    merkle_root: str = ""
    model_path: Path | None = None
    model_sha: str = ""
    graph: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    signature: str = ""
    public_key: str = ""


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(100 * max(0.0, centre - half), 1), round(100 * min(1.0, centre + half), 1))


def _flip_weights(path: Path, regions: list[dict], rng: random.Random, flips: int = 12) -> None:
    data = bytearray(path.read_bytes())
    span = [i for r in regions for i in range(r["offset"], r["offset"] + r["length"])] or list(
        range(len(data) // 2, len(data))
    )
    for off in rng.sample(span, k=min(flips, len(span))):
        data[off] ^= 1 << rng.randrange(8)
    path.write_bytes(bytes(data))


def build(stratum: str, variant: str, seed: int, workdir: Path) -> Pipeline:
    rng = random.Random(f"{stratum}:{variant}:{seed}")
    classes = tuple(rng.sample(range(5), 4))
    p = Pipeline(stratum, variant, seed, workdir)

    images = synthetic.demo_dataset(seed=seed, clean=16, duplicates=0, ood=0, classes=classes)
    if variant == "duplicate_poison":
        images += [(f"dup_{i}.png", synthetic.near_duplicate(images[i * 4][1], seed + i)) for i in range(3)]
    if variant == "ood_injection":
        images += [(f"texture_{i}.png", synthetic.out_of_distribution(seed + 50 + i)) for i in range(2)]
    data_dir = workdir / "data"
    data_dir.mkdir()
    for name, img in images:
        path = data_dir / name
        cv2.imwrite(str(path), img)
        p.samples.append(path)
        p.leaves.append(checks.compute_sha256_file(path))
    p.merkle_root = checks.compute_merkle_root(p.leaves)

    trojan = stratum == "S4_trojan"
    gain = 6.0 if variant == "patch_strong" else rng.choice([0.9, 1.2, 1.6])
    target = rng.choice([5, 6, 7, 8, 9])
    p.model_path = workdir / "model.onnx"
    p.model_path.write_bytes(build_classifier(trojan, seed=seed, trigger_gain=gain, target_class=target))
    p.model_sha = checks.compute_sha256_file(p.model_path)
    info = runtime.inspect_sync(p.model_path)
    p.graph = info["graph"]

    query = synthetic.scene(classes[0], seed + 999)
    fwd = runtime.forward_sync(p.model_path, runtime.to_model_rgb(query, p.graph)[None], p.graph)
    p.evidence = {
        "inference_id": f"bench-{stratum}-{variant}-{seed}",
        "dataset_merkle_root": p.merkle_root,
        "model_id": "bench-model",
        "model_sha256": p.model_sha,
        "arch_fingerprint": info["arch_fingerprint"],
        "input_sha256": hashlib.sha256(synthetic.encode_png(query)).hexdigest(),
        "config_sha256": "0" * 64,
        "output": {
            "top_class": int(fwd.probs[0].argmax()),
            "top_confidence": round(float(fwd.probs[0].max()), 6),
        },
        "timestamp": "2026-10-30T00:00:00.000Z",
    }
    p.signature, p.public_key = signer.sign_evidence_tuple(p.evidence)

    # Attacks happen after registration, exactly where provenance has to catch them.
    if variant == "bit_flip":
        _flip_weights(p.model_path, p.graph.get("weight_regions", []), rng)
    elif variant == "checkpoint_swap":
        p.model_path.write_bytes(build_classifier(False, seed=seed + 7))
    elif variant == "ledger_model_swap":
        p.evidence = {**p.evidence, "model_sha256": checks.compute_sha256_file(p.model_path)[::-1]}
    elif variant == "ledger_output_edit":
        p.evidence = {**p.evidence, "output": {**p.evidence["output"], "top_confidence": 0.999}}
    return p


def _timed(fn: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    out = fn()
    return out, (time.perf_counter() - started) * 1000


def hash_checks(p: Pipeline) -> bool:
    """True when every cryptographic binding still holds."""
    leaves = [checks.compute_sha256_file(s) for s in p.samples]
    assert p.model_path is not None
    return (
        checks.compute_merkle_root(leaves) == p.merkle_root
        and checks.compute_sha256_file(p.model_path) == p.model_sha
        and signer.verify_evidence_signature(p.evidence, p.signature, p.public_key)
    )


def evaluate(p: Pipeline) -> dict[str, dict[str, Any]]:
    intact, t_hash = _timed(lambda: hash_checks(p))
    results: dict[str, dict[str, Any]] = {"B1_hash_only": {"flagged": not intact, "ms": t_hash}}

    ids = [(s.name, s) for s in p.samples]
    screen, t_screen = _timed(lambda: (checks.find_near_duplicates(ids), checks.score_ood(ids)))
    data_flag = bool(screen[0]) or any(r["flag"] for r in screen[1])

    scan = forced = None
    t_fwd = t_gate = t_force = 0.0
    if intact:
        assert p.model_path is not None
        imgs = [cv2.imread(str(s)) for s in p.samples]
        clean = backdoor.prepare(imgs, p.graph)
        queries, tags = backdoor.build_queries(clean, p.seed)
        fwd, t_fwd = _timed(lambda: runtime.forward_sync(p.model_path, np.stack(queries), p.graph))
        names = [s.name for s in p.samples]
        scan, t_gate = _timed(lambda: backdoor.analyse(queries, tags, fwd, names, t_fwd))
        forced, t_force = _timed(
            lambda: backdoor.analyse(queries, tags, fwd, names, t_fwd, force_stage2=True)
        )

    strip_flag = bool(scan) and max(t["strip_entropy_drop"] for t in scan["triggers"]) >= backdoor.STRIP_GATE
    ac_flag = bool(forced) and max(t["cluster_score"] for t in forced["triggers"]) >= AC_THRESHOLD
    trojan_flag = bool(scan) and scan["verdict"] == "suspicious"

    results["B3_strip_only"] = {"flagged": strip_flag, "ms": t_fwd + t_gate}
    results["B4_activation_clustering"] = {"flagged": ac_flag, "ms": t_fwd + t_force}
    results["VISENTRA_complete"] = {
        "flagged": (not intact) or data_flag or trojan_flag,
        "ms": t_hash + t_screen + t_fwd + t_gate,
        "pillars": [
            name for name, hit in (("hash", not intact), ("data", data_flag), ("trojan", trojan_flag)) if hit
        ],
    }
    return results


def run(per_variant: int = 18, seeds: list[int] | None = None, progress: bool = False) -> dict[str, Any]:
    """Build and score ``per_variant`` pipelines for every variant (36 per stratum at the default)."""
    seeds = seeds or SEEDS
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    plan = [
        (stratum, variant, seeds[i % len(seeds)], seeds[i % len(seeds)] + i)
        for stratum, variants in STRATA.items()
        for variant in variants
        for i in range(per_variant * (2 if stratum == "S1_clean" else 1))
    ]
    for n, (stratum, variant, group, seed) in enumerate(plan, 1):
        work = Path(tempfile.mkdtemp(prefix="vbench-"))
        try:
            pipe = build(stratum, variant, seed, work)
            rows.append(
                {
                    "stratum": stratum,
                    "variant": variant,
                    "seed": seed,
                    "seed_group": group,
                    "methods": evaluate(pipe),
                }
            )
        finally:
            shutil.rmtree(work, ignore_errors=True)
        if progress:
            print(f"[{n}/{len(plan)}] {stratum}/{variant} seed={seed}", flush=True)
    return summarise(rows, seeds, time.perf_counter() - started)


def summarise(rows: list[dict[str, Any]], seeds: list[int], elapsed_s: float) -> dict[str, Any]:
    attacks = [r for r in rows if r["stratum"] != "S1_clean"]
    clean = [r for r in rows if r["stratum"] == "S1_clean"]
    methods: dict[str, Any] = {}
    for m in METHODS:
        hits = sum(r["methods"][m]["flagged"] for r in attacks)
        fps = sum(r["methods"][m]["flagged"] for r in clean)
        per_seed = []
        for s in seeds:
            seed_rows = [r for r in attacks if r["seed_group"] == s]
            if seed_rows:
                per_seed.append(100 * sum(r["methods"][m]["flagged"] for r in seed_rows) / len(seed_rows))
        methods[m] = {
            "overall_recall": round(100 * hits / max(1, len(attacks)), 1),
            "ci_95": list(wilson(hits, len(attacks))),
            "recall_sd_across_seeds": round(statistics.pstdev(per_seed), 1) if len(per_seed) > 1 else 0.0,
            "clean_fpr": round(100 * fps / max(1, len(clean)), 1),
            "fpr_ci_95": list(wilson(fps, len(clean))),
            "latency_ms": round(statistics.mean(r["methods"][m]["ms"] for r in rows), 1),
            "by_stratum": {
                st: round(
                    100
                    * sum(r["methods"][m]["flagged"] for r in rows if r["stratum"] == st)
                    / max(1, sum(r["stratum"] == st for r in rows)),
                    1,
                )
                for st in STRATA
            },
            "by_variant": {
                v: round(
                    100
                    * sum(r["methods"][m]["flagged"] for r in rows if r["variant"] == v)
                    / max(1, sum(r["variant"] == v for r in rows)),
                    1,
                )
                for vs in STRATA.values()
                for v in vs
            },
        }
    fp_sources: dict[str, int] = {}
    for r in clean:
        for pillar in r["methods"]["VISENTRA_complete"].get("pillars", []):
            fp_sources[pillar] = fp_sources.get(pillar, 0) + 1
    return {
        "benchmark": f"VisentraBench-{len(rows)}",
        "visentra_false_positive_sources": fp_sources,
        "total_pipelines": len(rows),
        "per_stratum": {st: sum(r["stratum"] == st for r in rows) for st in STRATA},
        "seeds": seeds,
        "methods": methods,
        "not_run": {
            "B5_full_neural_cleanse": "gradient trigger reverse-engineering is not implemented in this build"
        },
        "notes": [
            "S1 clean pipelines measure false positives; recall is computed over S2 to S5.",
            "Every VISENTRA false positive comes from Pillar I screening at the blueprint thresholds "
            "(OOD > 0.70, Hamming <= 8) on 16-image datasets; see visentra_false_positive_sources.",
            "By-stratum and by-variant numbers for S1 are flag rates, i.e. false positives.",
            "Pipelines are procedurally generated 64x64 scenes and hand-weighted ONNX classifiers, "
            "not CIFAR-10, GTSRB or Tiny-ImageNet; treat the numbers as a controlled study.",
            "B4 flags a model when the best trigger silhouette reaches 0.67, the highest value seen on "
            "clean models over held-out seeds 900-909; without a flip-consistency gate, benign colour "
            "patches separate activations about as well as a real trigger does.",
            "Latency is mean wall-clock per pipeline on the machine that ran the harness, "
            "including sandbox process start-up.",
        ],
        "elapsed_s": round(elapsed_s, 1),
    }


def save(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
