"""Manual entrypoint for refreshing the live-ingestion parity snapshot (D-09 + D-10).

Runs build_dataset_from_osm against real OSM Overpass once, writes the
adapter outputs to tests/fixtures/iberia_868/live-ingestion/, and prints a
diff summary + the commit command.

USAGE
-----
    py -3.14 scripts/refresh_live_snapshot.py --region iberia_868

Does NOT auto-commit. Review the diff before:
    git diff --stat tests/fixtures/iberia_868/live-ingestion/
    git add tests/fixtures/iberia_868/live-ingestion/
    git commit -m "docs(parity): refresh live snapshot"

After commit, run:
    py -3.14 -m pytest backend/tests/parity/test_iberia_868_live.py -m parity -x

If the parity test fails: the snapshot may have drifted from the golden
contract due to OSM data updates. Per Plan 03 <approach> waiver loop:
  1. Re-run this refresh script (>=1 hour later to allow Overpass to settle).
  2. Inspect diff vs commit; if changes are non-trivial, escalate to a
     Phase 02 D-09-style waiver — do NOT relax SSIM thresholds in the test.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from medieval_forge.services.pipeline.adapters.osm import build_dataset_from_osm  # noqa: E402

LIVE_SNAPSHOT_DIR = REPO_ROOT / "tests" / "fixtures" / "iberia_868" / "live-ingestion"

# Iberia 868 bbox (matches PRESETS["Península Ibérica (Portugal + Espanha)"]).
# Format: (lat_min, lon_min, lat_max, lon_max).
IBERIA_BBOX = (36.0, -9.5, 44.0, 4.3)
IBERIA_ISO = ["PT", "ES"]


async def _refresh_iberia(use_temp_projects_root: bool) -> tuple[Path, Path]:
    """Run the adapter against real OSM. Returns (pt_path, es_path) inside live-ingestion/."""
    LIVE_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # Adapter writes to projects/<uuid>/inputs/. Use a temp PROJECTS_ROOT so we don't
    # pollute the developer's DATA_DIR.
    if use_temp_projects_root:
        from medieval_forge.services import paths as paths_mod
        tmpdir = Path(tempfile.mkdtemp(prefix="refresh_live_"))
        paths_mod.PROJECTS_ROOT = tmpdir / "projects"

    project_uuid = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    print(f"[refresh] OSM Overpass call (bbox={IBERIA_BBOX}, iso={IBERIA_ISO})...")

    # Drain queue messages to stdout in parallel with the fetch.
    drain_task = asyncio.create_task(_drain(queue))
    try:
        ds = await build_dataset_from_osm(project_uuid, IBERIA_BBOX, IBERIA_ISO, queue)
    finally:
        await queue.put(None)
        await drain_task

    # Copy from project temp dir into the committed snapshot location.
    pt_dest = LIVE_SNAPSHOT_DIR / "pt_concelhos_live.geojson"
    es_dest = LIVE_SNAPSHOT_DIR / "es_municipalities_live.geojson"
    shutil.copy2(ds.pt_geojson, pt_dest)
    shutil.copy2(ds.es_input, es_dest)
    return pt_dest, es_dest


async def _drain(queue: asyncio.Queue) -> None:
    # Windows default stdout is cp1252 and chokes on the Unicode arrows the
    # SSE messages use (e.g. "→"). Re-encode each message through stdout's
    # actual encoding with backslash-escape replacement so the script never
    # crashes mid-fetch. UTF-8 terminals are unaffected.
    enc = (sys.stdout.encoding or "ascii").lower()
    while True:
        msg = await queue.get()
        if msg is None:
            return
        try:
            sys.stdout.write(msg)
        except UnicodeEncodeError:
            safe = msg.encode(enc, errors="backslashreplace").decode(enc, errors="replace")
            sys.stdout.write(safe)
        sys.stdout.flush()


def _summarize(pt_path: Path, es_path: Path) -> None:
    pt = json.loads(pt_path.read_text(encoding="utf-8"))
    es = json.loads(es_path.read_text(encoding="utf-8"))
    pt_size = pt_path.stat().st_size
    es_size = es_path.stat().st_size
    print()
    print(f"[refresh] Wrote: {pt_path.relative_to(REPO_ROOT)} ({pt_size:,} B, {len(pt['features'])} features)")
    print(f"[refresh] Wrote: {es_path.relative_to(REPO_ROOT)} ({es_size:,} B, {len(es['features'])} features)")
    print()
    print("[refresh] Next steps:")
    print("  git diff --stat tests/fixtures/iberia_868/live-ingestion/")
    print("  git add tests/fixtures/iberia_868/live-ingestion/")
    print("  git commit -m 'docs(parity): refresh live snapshot'")
    print()
    print("  py -3.14 -m pytest backend/tests/parity/test_iberia_868_live.py -m parity -x")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument("--region", required=True, choices=["iberia_868"])
    args = parser.parse_args()

    if args.region == "iberia_868":
        pt_path, es_path = asyncio.run(_refresh_iberia(use_temp_projects_root=True))
        _summarize(pt_path, es_path)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
