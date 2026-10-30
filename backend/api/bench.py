"""Serves the latest VisentraBench results written by scripts/run_visentrabench.py."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.config import PROJECT_ROOT, settings

router = APIRouter(prefix="/bench", tags=["benchmark"])


def results_path() -> Path:
    return (
        Path(settings.bench_results)
        if settings.bench_results
        else PROJECT_ROOT / "docs/benchmark/visentrabench_results.json"
    )


@router.get("/latest")
async def latest_results():
    path = results_path()
    if not path.exists():
        raise HTTPException(
            status_code=404, detail="No benchmark results yet; run scripts/run_visentrabench.py"
        )
    return json.loads(path.read_text())
