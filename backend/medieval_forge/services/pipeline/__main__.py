"""argparse CLI shim per RESEARCH §1.

Usage:
    python -m medieval_forge.services.pipeline --region iberia_868 --out /tmp/out
"""

import argparse
import pathlib

from . import run_pipeline
from .regions import REGIONS


if __name__ == "__main__":
    p = argparse.ArgumentParser(prog="python -m medieval_forge.services.pipeline")
    p.add_argument("--region", required=True, choices=list(REGIONS.keys()))
    p.add_argument("--out", required=True)
    args = p.parse_args()
    cfg = REGIONS[args.region]()
    cfg.output_dir = str(pathlib.Path(args.out).resolve())
    run_pipeline(cfg)
