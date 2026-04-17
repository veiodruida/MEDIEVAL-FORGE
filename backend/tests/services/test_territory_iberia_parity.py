"""
Parity tests: ensure backend/medieval_forge/services/territory_iberia.json
stays in sync with inicio/territory_data_v3.py.

If territory_data_v3.py is edited without re-running the sync script,
test_v3_matches_json will fail with a message pinpointing the first drift.
"""
import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> pathlib.Path:
    """Walk up from __file__ until we find a dir containing both inicio/ and backend/."""
    p = pathlib.Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "inicio").is_dir() and (parent / "backend").is_dir():
            return parent
    raise RuntimeError("Cannot locate repo root from test file path.")


def _load_v3(repo_root: pathlib.Path):
    """Import territory_data_v3 module from inicio/ without permanently modifying sys.path."""
    inicio_dir = repo_root / "inicio"
    sys.path.insert(0, str(inicio_dir))
    try:
        spec = importlib.util.spec_from_file_location(
            "territory_data_v3_test", inicio_dir / "territory_data_v3.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(inicio_dir))


def _load_json(repo_root: pathlib.Path) -> dict:
    json_path = repo_root / "backend" / "medieval_forge" / "services" / "territory_iberia.json"
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_counts_match():
    """JSON must have exactly 4 kingdoms / 26 duchies / 92 condados / 257 baronies."""
    repo_root = _repo_root()
    data = _load_json(repo_root)

    assert len(data["kingdoms"]) == 4, (
        f"Expected 4 kingdoms, got {len(data['kingdoms'])}"
    )
    assert len(data["duchies"]) == 26, (
        f"Expected 26 duchies, got {len(data['duchies'])}"
    )
    assert len(data["condados"]) == 92, (
        f"Expected 92 condados, got {len(data['condados'])}"
    )
    total_baronies = sum(len(c[5]) for c in data["condados"])
    assert total_baronies == 257, (
        f"Expected 257 baronies, got {total_baronies}"
    )


def test_v3_matches_json():
    """Structural equality between v3 source and the JSON export."""
    repo_root = _repo_root()
    mod = _load_v3(repo_root)
    data = _load_json(repo_root)

    # --- kingdoms ---
    for kid, kname in mod.KINGDOMS.items():
        assert kid in data["kingdoms"], f"Kingdom {kid!r} missing from JSON"
        assert data["kingdoms"][kid] == kname, (
            f"Kingdom {kid!r} name mismatch: v3={kname!r}, json={data['kingdoms'][kid]!r}"
        )

    # --- duchies ---
    for did, (kingdom_id, display) in mod.DUCHIES.items():
        assert did in data["duchies"], f"Duchy {did!r} missing from JSON"
        json_d = data["duchies"][did]
        assert json_d[0] == kingdom_id, (
            f"Duchy {did!r} kingdom_id mismatch: v3={kingdom_id!r}, json={json_d[0]!r}"
        )
        assert json_d[1] == display, (
            f"Duchy {did!r} display mismatch: v3={display!r}, json={json_d[1]!r}"
        )

    # --- condados + baronies ---
    assert len(mod.CONDADOS) == len(data["condados"]), (
        f"Condado count mismatch: v3={len(mod.CONDADOS)}, json={len(data['condados'])}"
    )
    for i, (v3c, jc) in enumerate(zip(mod.CONDADOS, data["condados"])):
        cid, cname, clon, clat, cdid = v3c[0], v3c[1], v3c[2], v3c[3], v3c[4]
        assert jc[0] == cid,   f"condados[{i}] id mismatch: v3={cid!r}, json={jc[0]!r}"
        assert jc[1] == cname, f"condados[{i}] name mismatch: v3={cname!r}, json={jc[1]!r}"
        assert jc[2] == clon,  f"condados[{i}] lon mismatch: v3={clon}, json={jc[2]}"
        assert jc[3] == clat,  f"condados[{i}] lat mismatch: v3={clat}, json={jc[3]}"
        assert jc[4] == cdid,  f"condados[{i}] duchy_id mismatch: v3={cdid!r}, json={jc[4]!r}"

        v3_bars = v3c[5]
        j_bars = jc[5]
        assert len(v3_bars) == len(j_bars), (
            f"condados[{i}] ({cid!r}) barony count mismatch: v3={len(v3_bars)}, json={len(j_bars)}"
        )
        for bi, (vb, jb) in enumerate(zip(v3_bars, j_bars)):
            bname, blon, blat = vb[0], vb[1], vb[2]
            assert jb[0] == bname, (
                f"condados[{i}].baronies[{bi}] name mismatch: v3={bname!r}, json={jb[0]!r}"
            )
            assert jb[1] == blon, (
                f"condados[{i}].baronies[{bi}] lon mismatch: v3={blon}, json={jb[1]}"
            )
            assert jb[2] == blat, (
                f"condados[{i}].baronies[{bi}] lat mismatch: v3={blat}, json={jb[2]}"
            )


def test_sync_script_is_idempotent():
    """Running the sync script again must not change the JSON file."""
    repo_root = _repo_root()
    script = repo_root / "scripts" / "sync_territory_iberia.py"

    if not script.exists():
        pytest.skip("scripts/sync_territory_iberia.py not found — skipping idempotency check")

    json_path = repo_root / "backend" / "medieval_forge" / "services" / "territory_iberia.json"
    before = json_path.read_bytes()

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert result.returncode == 0, (
        f"Sync script exited with {result.returncode}:\n{result.stderr}"
    )

    after = json_path.read_bytes()
    assert before == after, (
        "Sync script produced different bytes on second run — not idempotent.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
