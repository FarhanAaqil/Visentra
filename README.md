# VISENTRA

> **SIH26228 — "From Data to Decision, Proving AI Integrity"**  
> An open-source forensic assurance platform for Computer Vision supply chains. Provides immutable cryptographic verification across **datasets, model checkpoints, and inference outputs** to detect tampering, pixel backdoors (Trojan shortcuts), and data anomalies before deployment.

---

## Forensic Lab Instrument Showcase

The VISENTRA interface embodies a physical forensic workstation—utilizing a warm paper canvas, crisp hairline borders, zero cosmetic drop-shadows, and high-density monospace evidentiary diffs.

### 1. Interactive Lineage Graph
The graph **is** the interface. It maps the end-to-end provenance chain from `Contributor → Dataset → Model → Inference Evidence → Assurance Certificate` with dynamic status-indicator stripes and orthogonal routing.

![VISENTRA Lineage Graph Overview](docs/images/01_lineage_graph_overview.png)

---

### 2. Live Supply-Chain Tamper Detection
Injecting corrupted bytes or altering model weights triggers an immediate cryptographic digest divergence. The lineage edge pulses red, the node switches to `[TAMPERED]`, and the collapsible bottom event drawer streams live forensic telemetry over WebSockets.

![Tamper Demo Live Reaction](docs/images/02_tamper_demo_live_reaction.png)

---

### 3. Model Interrogation & Cryptographic Diff Room
Clicking any model node slides out a full-height forensic panel:
- **Left Column**: Character-by-character visual diff between the registered SHA-256 and disk binary digest.
- **Right Column**: Neural Trojan test bench testing synthetic trigger perturbations (`checkerboard`, `blend`, `corner_patch`) with real-time confidence-shift dials and anomaly index scoring.

![Model Interrogation Panel](docs/images/03_model_interrogation_diff.png)

---

### 4. Dataset Inspector: Near-Duplicate Detection & OOD Screening
Clicking any dataset node triggers automated spatial quality analysis:
- **Near-Duplicates**: Pairwise 64-bit perceptual hashing ($d\text{Hash} / p\text{Hash}$) isolates sample pairs within a Hamming distance $\le 8$.
- **Out-of-Distribution (OOD)**: 96-dimensional color/spatial feature vectors fed into Isolation Forest / Mahalanobis estimators flag anomalous samples with outlier ratings.

| Near-Duplicate Clustering | Out-of-Distribution Anomalies |
|---|---|
| ![Dataset Inspector Near Duplicates](docs/images/04_dataset_inspector_near_duplicates.png) | ![Dataset Inspector OOD Anomalies](docs/images/05_dataset_inspector_ood_anomalies.png) |

---

### 5. Auditable Cryptographic Assurance Certificate
Clicking **`Assurance Report`** generates an exportable, high-resolution audit certificate with a four-pillar weighted breakdown, vulnerability disclosures, and technical limitations.

![Assurance Report Certificate](docs/images/06_cryptographic_assurance_report.png)

---

## Core Verification Pillars

| Pillar | Focus | Technique | Metric / Threshold |
|---|---|---|---|
| **I. Dataset Quality** | Deduplication & OOD Detection | 64-bit perceptual hashing & Isolation Forest | Hamming $\le 8$ bits; Anomaly Score $> 0.80$ |
| **II. Model Authenticity** | Binary Tampering & Bitflips | SHA-256 Content-Addressing & Architecture Digest | Exact character-by-character hex diff |
| **III. Trojan Interrogation** | Black-box Backdoor Detection | Trigger injection (`checkerboard`, `blend`, etc.) | Anomaly Index $> 2.0$; Class Flip Rate |
| **IV. Inference Proof** | Prediction Non-repudiation | Cryptographic binding tuple $(D, M, I, C)$ | Sealed HMAC-SHA256 evidence record |

$$\text{Overall Assurance Score} = 0.20 \cdot S_{\text{data}} + 0.30 \cdot S_{\text{model}} + 0.25 \cdot S_{\text{backdoor}} + 0.25 \cdot S_{\text{inference}}$$

---

## Quick Start Guide

### 1. Prerequisites
- **Python**: 3.10+ (64-bit)
- **Node.js**: 18.x or 20.x

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/FarhanAaqil/Visentra.git
cd Visentra

# Set up Python virtual environment
python -m venv .venv
.\.venv\Scripts\activate        # On Windows
# source .venv/bin/activate     # On Linux / macOS

# Install backend dependencies
pip install -r backend/requirements.txt

# Start FastAPI server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Setup
```bash
# In a new terminal:
cd Visentra/frontend
npm install
npm run dev -- --host 127.0.0.1
```
Open **`http://127.0.0.1:5173/`** in your browser.

### 4. Seed Forensic Demo Data
To populate the database with a pre-configured supply chain, model checkpoint, and dataset anomalies:
```bash
python scripts/seed_demo.py
```

---

## Complete User Guide & Architectural Flowcharts

For an exhaustive technical breakdown, sequence flowcharts, trigger algorithms, and operational walkthroughs, refer to the full manual:

📖 **[Read the VISENTRA System Architecture & Forensic User Guide](USER_GUIDE.md)**

---

## Technology Stack

- **Frontend**: React 18, TypeScript, Vite, React Flow, IBM Plex Mono, Inter
- **Backend API**: Python, FastAPI, Pydantic v2, WebSockets
- **ML & CV Engine**: ONNXRuntime, PyTorch, OpenCV, scikit-learn, imagehash, Pillow, NumPy
- **Persistence & CAS**: SQLite (with AsyncPG / PostgreSQL support), local content-addressed storage (CAS)

---

## License

MIT License. Developed for SIH26228.
