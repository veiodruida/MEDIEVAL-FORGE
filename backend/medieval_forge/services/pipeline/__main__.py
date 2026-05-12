"""argparse CLI shim per RESEARCH §1.

Usage:
    python -m medieval_forge.services.pipeline --region iberia_868 --out /tmp/out
"""

import argparse
import pathlib
from dataclasses import replace

from . import run_pipeline
from .region_loader import load_region

# Discover available region keys from data/regions/*.yaml at import time.
# File depth: backend/medieval_forge/services/pipeline/__main__.py
#              4         3            2        1        0
# parents[4] = repo root (DO NOT change — same anchor as region_loader.py)
_REGIONS_DIR = pathlib.Path(__file__).resolve().parents[4] / "data" / "regions"
_AVAILABLE_REGIONS = sorted(p.stem for p in _REGIONS_DIR.glob("*.yaml"))

if __name__ == "__main__":
    p = argparse.ArgumentParser(prog="python -m medieval_forge.services.pipeline")
    p.add_argument("--region", required=True, choices=_AVAILABLE_REGIONS)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    cfg = replace(load_region(args.region), output_dir=str(pathlib.Path(args.out).resolve()))
    run_pipeline(cfg)
