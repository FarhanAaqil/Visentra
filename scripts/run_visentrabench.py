"""Run VisentraBench and write the results the API and UI serve.

python scripts/run_visentrabench.py                 # full 180 pipeline run
python scripts/run_visentrabench.py --per-variant 2 # quick smoke run
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# Keep bench signing keys and scratch files out of the real storage root.
os.environ.setdefault("STORAGE_ROOT", tempfile.mkdtemp(prefix="vbench-storage-"))

from backend.bench.visentrabench import run, save  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--per-variant", type=int, default=18, help="pipelines per attack variant (18 gives 180)"
    )
    parser.add_argument(
        "--out", type=Path, default=ROOT / "docs" / "benchmark" / "visentrabench_results.json"
    )
    args = parser.parse_args()

    result = run(per_variant=args.per_variant, progress=True)
    save(result, args.out)
    print(f"\n{result['benchmark']} finished in {result['elapsed_s']}s -> {args.out}")
    for name, m in result["methods"].items():
        recall, fpr, ms = m["overall_recall"], m["clean_fpr"], m["latency_ms"]
        print(f"  {name:26s} recall {recall:5.1f}%  FPR {fpr:4.1f}%  {ms:7.1f} ms")


if __name__ == "__main__":
    main()
