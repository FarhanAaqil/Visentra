# VISENTRA user guide

This guide walks through the workstation with the seeded demo pipeline. Start the API
and the UI as described in the [README](../README.md); the first start seeds a
contributor called **VISENTRA Demo**.

## The five-minute demo

1. **Read the chain.** The lineage view shows Contributor → Dataset → Models →
   Inferences. Dataset v1.0 is amber (flagged), Model v1.0 is amber (suspicious),
   Model v1.1 and all certificates are green. The strip at the top shows the overall
   score (72.6, grade B) and the four pillars.
2. **Open the dataset.** Click *Dataset v1.0*. The *Samples* tab shows two images
   tagged as near duplicates; the *Duplicates* tab puts them side by side with their
   Hamming distance. *Screen samples* re-runs the analysis and the *OOD* tab then lists
   every sample's score, with the ringed texture above the 0.70 line.
3. **Poison it.** Press *Poison a sample*, then *Verify Merkle root*. The *Integrity*
   tab shows the archive hash still matches but the Merkle root does not, and shows the
   exact sample that changed (look for the checkerboard in its corner). *Restore* heals it.
4. **Interrogate the model.** Open *Model v1.0*. The scan shows `checkerboard_16px`
   far past the 0.30 verdict line with 100% flips to class 7. Its anchor map lights up
   everywhere, the activation scatter separates clean (green) from triggered (red)
   activations, and the flip gallery shows each before/after pair. Open *Model v1.1*
   for contrast: same architecture, no trigger crosses the gate, and stage 2 never ran.
5. **Check a certificate.** Open the inference that predicted class 7. It lists the
   bound tuple and its Ed25519 signature; *Re-verify certificate* recomputes every link.
6. **Attack the weights.** Back on Model v1.0, press *Bit-flip attack*. The node turns
   red, a red wave runs down its three edges as each certificate is invalidated, and
   the score drops to grade D. *Verify hash* shows the registered and on-disk hashes
   side by side, which tensors were hit and that the topology itself is unchanged.
   *Restore* puts the pristine checkpoint back; re-verify the certificates to clear them.
7. **Export proof.** The *Assurance* tab exports the report as a signed certificate.
   *Verify a certificate* accepts the file back and checks both the signature and that
   it was signed by this server's key.

## Bringing your own artifacts

Use **Ingest** in the top bar:

- **Contributor**: anyone who supplies data or models.
- **Dataset**: a `.zip` or `.tar(.gz)` of images (or a single image). Every image is
  hashed, pHashed and sealed into the Merkle root; non-images are ignored.
- **Model**: ONNX is inspected and executed inside the sandbox. `.pt/.pth/.safetensors`
  are hash-tracked only and never loaded, because unpickling runs code. Pick the dataset
  it was trained on to complete the chain.
- **Inference**: choose a model, an input image and a runtime config; the result is
  signed immediately.

ONNX models are fed NCHW RGB at their declared input size, ImageNet-normalised unless
the model sets the metadata property `visentra.preprocess=unit`. Exporting a
penultimate layer as a second graph output, named in `visentra.penultimate`, gives
Stage 2 white-box activations; otherwise it falls back to logits.

## Views

| View | What it is for |
|---|---|
| **Lineage** | the live graph; click any node to drill in. Deep links: `#dataset=<id>`, `#model=<id>`, `#inference=<id>` |
| **Assurance** | the four-pillar report, certificate export and verification |
| **Benchmark** | VisentraBench results: recall by attack variant and recall against cost |
| **Audit trail** | every change, with actor and before/after values |

## API

The OpenAPI docs live at `http://localhost:8000/docs`. The most used endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /chain/{contributor_id}` | lineage graph |
| `POST /datasets` · `/datasets/{id}/analyze` · `/datasets/{id}/verify` | Pillar I |
| `POST /models` · `/models/{id}/verify` · `/models/{id}/backdoor-scan` | Pillars II and III |
| `POST /inference` · `/inference/{id}/reverify` · `GET /keys/public` | Pillar IV |
| `GET /report/{id}` · `/report/{id}/certificate` · `POST /report/certificate/verify` | scoring and certificates |
| `GET /audit` · `GET /bench/latest` · `WS /ws/status` | audit trail, benchmark, live updates |

Send `X-Visentra-Actor: <name>` with mutating requests to attribute them in the audit trail.
