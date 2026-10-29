# VISENTRA Completion Roadmap

This roadmap turns the forensic audit in `docs/Visentra_Master_Research_Blueprint.docx`
into six shippable phases. Each phase lands as one pull request from `master` into
`main`, and CI (backend lint + tests, frontend lint + typecheck + build) must be green
before it merges.

## Where the codebase stood

The audit found a solid full-stack skeleton that leaned on synthetic fallbacks in
every pillar. These are the 14 defects from the ledger, plus the issues that turned
up during the code review for this roadmap:

| ID | Problem | Phase |
|----|---------|-------|
| D-01 | Dataset ZIPs stored as one opaque blob, `dataset_sample` never populated | 2 |
| D-02 | Seeded "ONNX" model is `os.urandom(4096)` | 3 |
| D-03 | Backdoor scan falls back to hard-coded synthetic findings, no flip evidence | 4 |
| D-04 | OOD "embedding" is a 96-bin colour histogram | 2 |
| D-05 | Inference signature column always NULL, UI fakes a valid badge | 4 |
| D-06 | No execution sandbox, `torch.load` pickle runs in the API process | 3 |
| D-07 | Model tamper does not cascade to dependent inferences | 4 |
| D-08 | `verify_model` hides the real disk hash, UI invents `f000deadbeef…` | 3, 5 |
| D-09 | No UI to ingest contributors, datasets, models or inferences | 5 |
| D-10 | Lineage is Contributor→Dataset and Contributor→Model, not a 4-tier chain | 1 |
| D-11 | `audit_log` table is never written | 1 |
| D-12 | Evidence panel shows the model UUID where its SHA-256 belongs | 5 |
| D-13 | A suspicious scan zeroes both Model Integrity and Backdoor pillars | 4 |
| D-14 | `alembic.ini` points at a migrations folder that does not exist | 1 |
| R-01 | Thumbnail endpoint reads any path on disk (path traversal) | 2 |
| R-02 | Backdoor scan samples images from *every* dataset on disk | 4 |
| R-03 | Re-running dataset analysis duplicates findings | 2 |
| R-04 | Solid-colour demo images all collide on pHash | 2 |
| R-05 | Tamper demo destroys the artifact, restore just deletes it | 3 |
| R-06 | No CI, no tests wired to the API, torch pulled in for nothing | 1 |

## Phase 1: Foundation, lineage schema and CI
- Repository hygiene: blueprint and design prototype under `docs/`, pinned and slimmer requirements, `pyproject.toml` for ruff and pytest.
- Settings and storage helpers so paths are resolved at call time (testable).
- Schema: `model.dataset_id`, dataset Merkle root, per-sample SHA-256, inference binding columns, timezone-aware timestamps.
- True 4-tier lineage graph (D-10) and audit trail writes on every mutation (D-11).
- Alembic async environment with an initial migration (D-14).
- Pytest API harness and a GitHub Actions pipeline for backend and frontend.

## Phase 2: Dataset assurance pillar
- Archive unpacking into content-addressed sample storage, sample rows, Merkle root (D-01).
- 512-D spatial/spectral embedding with hybrid Isolation Forest + Mahalanobis OOD (D-04), pluggable ONNX embedder.
- Merkle-aware dataset verification, sample-scoped thumbnails (R-01), idempotent analysis (R-03).

## Phase 3: Model pillar and sandbox
- Subprocess sandbox worker with resource caps and no network (D-06).
- Deterministic ONNX classifier generator with a planted checkerboard Trojan, plus a clean twin (D-02).
- Canonical topology fingerprint (op types and shapes, not node names).
- `verify_model` returns the real disk hash (D-08); bit-flip tamper and a vault-backed restore (R-05).

## Phase 4: Trojan interrogation, signed inference and scoring
- Two-stage gate: spatial trigger probe + STRIP entropy, escalating to penultimate-layer PCA clustering (D-03), scoped to the model's own dataset (R-02).
- Ed25519 signing over the full provenance tuple, persisted key, public key endpoint (D-05).
- Staggered 150 ms cascade invalidation over WebSockets (D-07).
- Decoupled four-pillar score from Equation 6 (D-13) and an exportable assurance certificate.
- Seeder that exercises every pillar with real data.

## Phase 5: Cherry Cinema forensic UI
- New design system (cherry palette, glass panels, motion tokens) and an animated WebGL backdrop.
- Restyled lineage graph with animated edges, cascade pulses and status glows.
- Ingest drawer for contributors, datasets, models and test inferences (D-09).
- Interrogation room with real flip images, activation scatter and a true hash diff (D-08).
- Evidence panel with live signature verification and the real model hash (D-12).
- Animated assurance report with pillar gauges.

## Phase 6: VisentraBench, hardening and docs
- Reproducible benchmark harness that generates and scores pipelines across all five strata, with Wilson intervals.
- Benchmark view in the UI fed by the harness output.
- End-to-end smoke test in CI, coverage gate, Docker and compose fixes.
- README and user guide rewritten for the finished system.
