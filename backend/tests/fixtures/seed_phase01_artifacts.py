"""Seed a project's `output/` directory with Phase 01 artifacts (Plan 03-08 T1).

Helper used by the Plan 03-08 Playwright UAT: takes a `source_dir`
containing the 14 ARTIFACT_FILES (10 Phase 01 Unity-contract files + 4
Phase 03-01 canvas-sidecar files) and copies them byte-for-byte to
`projects/<project_id>/output/`.

Single source of truth for the 14-file allowlist: `ARTIFACT_FILES` from
`medieval_forge.api.v3.artifacts` — same frozenset the artifact-serving
endpoint uses (T-03-UAT-01 mitigation: any drift between seed + serve
becomes a hard import-time error).

Containment via `paths.project_dir(project_id)`: refuses any
non-UUID-v4 string and any resolved path outside `PROJECTS_ROOT`
(T-03-UAT-01 — Tampering: prevents leaking deployed Reconquista artifacts
into a wrong path).

Idempotent: copying twice produces identical state. Uses `shutil.copy2`
so mtime + size are preserved; the parity test's byte-exact comparison
still works after a round-trip through this helper.

CLI usage (invoked from Playwright globalSetup):

.. code-block:: bash

   py -3.14 backend/tests/fixtures/seed_phase01_artifacts.py <project_id> <source_dir>

Prints the resolved output dir on success; exits non-zero with a
diagnostic on any failure.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from medieval_forge.api.v3.artifacts import ARTIFACT_FILES
from medieval_forge.services.paths import project_dir


def seed_phase01_artifacts(project_id: str, source_dir: Path) -> Path:
    """Copy the 14 ARTIFACT_FILES from `source_dir` into `projects/<id>/output/`.

    Args:
        project_id: UUID v4 string. Validated via paths.project_dir
            (raises ValueError on bad UUID or PROJECTS_ROOT escape).
        source_dir: Directory holding all 14 ARTIFACT_FILES at its
            top level. Missing files raise FileNotFoundError.

    Returns:
        Path to the populated `output/` dir.

    Raises:
        ValueError: invalid project_id (delegated to paths.project_dir).
        FileNotFoundError: any of the 14 files missing from source_dir.
        NotADirectoryError: source_dir is not an existing directory.
    """
    source = Path(source_dir)
    if not source.is_dir():
        raise NotADirectoryError(f"source_dir does not exist: {source}")

    # Delegates UUID + containment validation. Raises ValueError on bad input.
    root = project_dir(project_id)
    output = root / "output"
    output.mkdir(parents=True, exist_ok=True)

    for name in sorted(ARTIFACT_FILES):
        src = source / name
        if not src.is_file():
            raise FileNotFoundError(
                f"missing artifact in source_dir: {name} (looked in {source})"
            )
        # copy2 preserves mtime — the parity round-trip stays byte-exact.
        shutil.copy2(src, output / name)

    return output


def _main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(
            "usage: py -3.14 seed_phase01_artifacts.py <project_id> <source_dir>\n"
        )
        return 2
    _, project_id, source_dir = argv
    try:
        out = seed_phase01_artifacts(project_id, Path(source_dir))
    except (ValueError, NotADirectoryError, FileNotFoundError) as exc:
        sys.stderr.write(f"seed_phase01_artifacts: {exc}\n")
        return 1
    sys.stdout.write(f"{out}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv))
