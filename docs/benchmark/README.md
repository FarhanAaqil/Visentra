# VisentraBench-180

Reproducible benchmark for the four assurance methods. Every number on this page comes from
[visentrabench_results.json](visentrabench_results.json), written by `python scripts/run_visentrabench.py`
(180 pipelines, seeds 42, 101, 202, 303, 404, 173.6 s on the machine that produced it).

## Protocol

Each pipeline is built from scratch: a procedural 16-image dataset, a hand-weighted ONNX classifier and a
sandboxed inference signed with Ed25519. The stratum's attack is applied *after* registration, then each
method decides whether the pipeline is compromised. 36 pipelines per stratum:

| Stratum | Variants (18 each) |
|---|---|
| S1 clean | untouched (36), measures false positives |
| S2 dataset | 3 near-duplicate re-encodes · 2 injected OOD textures |
| S3 binary | 12 single-bit weight flips · whole checkpoint swap |
| S4 Trojan | strong checkerboard implant · weak implant (gain 0.9–1.6) |
| S5 provenance | ledger claims a different model hash · ledger output edited |

## Results

| Method | Attack recall | 95% Wilson CI | SD across seeds | Clean FPR | Mean latency |
|---|---|---|---|---|---|
| B1 hash only | 50.0% | 41.9–58.1 | 0.0 | 0.0% | 0.9 ms |
| B3 STRIP only | 15.3% | 10.3–22.0 | 3.1 | 0.0% | 252.3 ms |
| B4 activation clustering | 0.7% | 0.1–3.8 | 1.2 | 5.6% | 255.2 ms |
| VISENTRA | 98.6% | 95.1–99.6 | 1.5 | 13.9% | 480.6 ms |

### By attack variant (detection rate, %)

| Variant | B1 hash only | B3 STRIP only | B4 activation clustering | VISENTRA |
|---|---|---|---|---|
| Clean (false positives) | 0.0 | 0.0 | 5.6 | 13.9 |
| Duplicate poisoning | 0.0 | 0.0 | 0.0 | 100.0 |
| OOD injection | 0.0 | 0.0 | 0.0 | 100.0 |
| Weight bit-flip | 100.0 | 0.0 | 0.0 | 100.0 |
| Checkpoint swap | 100.0 | 0.0 | 0.0 | 100.0 |
| Trojan, strong patch | 0.0 | 100.0 | 5.6 | 100.0 |
| Trojan, weak patch | 0.0 | 22.2 | 0.0 | 88.9 |
| Ledger model swap | 100.0 | 0.0 | 0.0 | 100.0 |
| Ledger output edit | 100.0 | 0.0 | 0.0 | 100.0 |

## Reading the results

- Hash checks are cheap and perfect on what they cover (binary and ledger tampering) and blind to everything semantic.
- STRIP alone only sees Trojans that survive superimposition; it misses most weak implants and every non-Trojan attack.
- Activation clustering without a consistency gate is dominated by benign feature shifts: colour patches separate
  activations about as well as the real trigger, so at a threshold that keeps clean models quiet it finds almost nothing.
- VISENTRA's only misses are weak Trojans (88.9% caught). All of its clean false positives come from
  Pillar I screening ({'data': 5}) on 16-image datasets at the blueprint thresholds;
  larger datasets and per-deployment threshold calibration are the obvious levers.

## Caveats

- S1 clean pipelines measure false positives; recall is computed over S2 to S5.
- Every VISENTRA false positive comes from Pillar I screening at the blueprint thresholds (OOD > 0.70, Hamming <= 8) on 16-image datasets; see visentra_false_positive_sources.
- By-stratum and by-variant numbers for S1 are flag rates, i.e. false positives.
- Pipelines are procedurally generated 64x64 scenes and hand-weighted ONNX classifiers, not CIFAR-10, GTSRB or Tiny-ImageNet; treat the numbers as a controlled study.
- B4 flags a model when the best trigger silhouette reaches 0.67, the highest value seen on clean models over held-out seeds 900-909; without a flip-consistency gate, benign colour patches separate activations about as well as a real trigger does.
- Latency is mean wall-clock per pipeline on the machine that ran the harness, including sandbox process start-up.
- B5_full_neural_cleanse: gradient trigger reverse-engineering is not implemented in this build.
