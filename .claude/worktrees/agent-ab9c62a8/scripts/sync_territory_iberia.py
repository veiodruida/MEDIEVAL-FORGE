#!/usr/bin/env python3
"""
Deterministic exporter: inicio/territory_data_v3.py → backend/medieval_forge/services/territory_iberia.json

Run from repo root:
    python scripts/sync_territory_iberia.py

Re-running produces a byte-identical file (idempotent).
"""
import importlib.util
import json
import pathlib
import sys


def main() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    inicio_dir = repo_root / "inicio"
    out_path = repo_root / "backend" / "medieval_forge" / "services" / "territory_iberia.json"

    # Load territory_data_v3 without polluting sys.modules permanently
    sys.path.insert(0, str(inicio_dir))
    try:
        spec = importlib.util.spec_from_file_location(
            "territory_data_v3", inicio_dir / "territory_data_v3.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(inicio_dir))

    data = {
        "kingdoms": dict(mod.KINGDOMS),
        "duchies": {k: [v[0], v[1]] for k, v in mod.DUCHIES.items()},
        "condados": [
            [c[0], c[1], c[2], c[3], c[4],
             [[b[0], b[1], b[2]] for b in c[5]]]
            for c in mod.CONDADOS
        ],
    }

    n_kingdoms = len(data["kingdoms"])
    n_duchies = len(data["duchies"])
    n_condados = len(data["condados"])
    n_baronies = sum(len(c[5]) for c in data["condados"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(
        f"synced: {n_kingdoms} kingdoms / {n_duchies} duchies / "
        f"{n_condados} condados / {n_baronies} baronies"
    )


if __name__ == "__main__":
    main()
