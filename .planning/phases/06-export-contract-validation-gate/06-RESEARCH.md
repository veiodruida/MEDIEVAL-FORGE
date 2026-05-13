# Phase 06: Export contract + validation gate - Research

**Researched:** 2026-05-13
**Domain:** Backend export validation gate (pydantic v2 schemas + pure validator + FastAPI v3 endpoint)
**Confidence:** HIGH (every claim traceable to file:line in this repo; no external WebSearch needed — domain is internal architecture)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
D-01..D-19. Highlights the planner MUST honor verbatim:
- D-01: pure `validate_export(generated_dir, cfg) -> ValidationReport` in `services/export/validator.py`
- D-02: hard-fail only — no `?force` override
- D-03: `POST /export?dry_run=true` on the same endpoint runs gate-only
- D-04: delete `api/export.py` + `backend/tests/test_export.py` in the same plan that adds `api/v3/export.py`
- D-05/D-06: 6 pydantic schemas (5 contract JSONs + MANIFEST) in `services/export/schemas.py`
- D-07: MANIFEST is Forge-specific; `schema_version: 2`; `validation_report` block; per-file `sha256`
- D-08: stable codes `SCHEMA_INVALID | COLOR_COLLISION | OCEAN_LEAK | MISSING_ORIGINAL_IDX | TERRITORY_TOO_SMALL | PIXEL_CENTER_OUT_OF_RANGE`
- D-09: OCEAN_LEAK = ocean pixel that is not the ocean color (one-way only)
- D-10: PIXEL_CENTER_OUT_OF_RANGE = bounds check; numpy Y-down preserved
- D-11: `enforce_original_idx` YAML flag, Iberia opt-out (**SEE BLOCKER in Risk Register — rationale is stale**)
- D-12: TERRITORY_TOO_SMALL threshold = `cfg.blob_merge_px` (200)
- D-13: COLOR_COLLISION = within-file (lookup) + cross-layer (terrain palette)
- D-14: broken fixtures live in `tests/e2e/test_export_gate_broken.py` (no committed broken YAML)
- D-15: 3-layer test pyramid; 5 unit validator files
- D-16: parity test extends with `assert manifest.validation_report.passed == true`
- D-17: per-broken-fixture tests assert EXACT error codes (no more/no fewer)
- D-18: validator collects ALL errors (no fail-fast except SCHEMA_INVALID short-circuit)
- D-19: backend-only — zero frontend code in Phase 06

### Claude's Discretion (8 items — answered in §Per-Discretion Answers below)
Sentinel ocean RGB source; sha256 timing; ValidationFailedError vs return-report; subpackage layout;
schema_version placement; test file split; endpoint mount ordering; Iberia flag location.

### Deferred Ideas (OUT OF SCOPE)
Frontend UI swap to v3; rich error UI; Iberia gold rebake with original_idx; pixel_center Y-up conversion;
cross-field pydantic constraints; `/api/v3/regions/validate`; per-region `min_territory_px`;
per-tier thresholds; MANIFEST migration tooling; bidirectional ocean leak; RFC 7807; CLI dry-run;
alternative hashes; SSE for validator.
</user_constraints>

---

## Executive Summary

1. **D-11 is built on a stale premise (BLOCKER).** CONTEXT.md states "Iberia has 0/92 condados with `original_idx`." Primary evidence in this repo says otherwise: `data/regions/iberia_868.yaml` carries `original_idx: 1..92` on all 92 condados, and `tests/fixtures/iberia_868/golden/territory_metadata.json` emits `original_idx` on 91/91 surviving condados. The exemption may still be wanted (baronies legitimately lack `original_idx` — golden baronies have only `{name, condado_idx, duchy, pixel_count}`), but the rationale must be corrected before the YAML flag is added. **Planner: reconcile with user before Wave 1.**

2. **The "ocean color in lookup PNGs" is `cfg.ocean_far`** — verified at `backend/medieval_forge/services/pipeline/lookup.py:31` (`lk = np.full(... list(cfg.ocean_far) ...)`). No new constant is needed; the validator imports it from cfg.

3. **Landmask for OCEAN_LEAK is the real architectural choice.** Validator gets `(generated_dir, cfg)`, not the runtime landmask array. The Karpathy-simple answer: derive land from `terrain_lookup.png` (`PLAINS_RGB` = land, `OCEAN_RGB` = ocean — see `services/pipeline/terrain.py:35-36`). Cheap, already on disk, no GeoJSON re-parse.

4. **Pydantic v2.7+ is fully in play** (`pyproject.toml`: `pydantic>=2.7,<3.0`). Mirror `region_loader.RegionConfigSchema` idioms exactly: `BaseModel`, `ConfigDict(extra="forbid")`, `Field(default_factory=...)`, `model_validate`, `model_dump`. No v1 shims found anywhere in the codebase.

5. **Plan ordering: atomic delete-and-add.** Phase 05 precedent (STATE.md: "all 5 planned migrations + 3 extras done in commit 6a388a2") supports landing `api/v3/export.py` + deleting `api/export.py` + rewriting `tests/test_export.py` → `tests/e2e/*` in one plan. Any other ordering breaks the parity gate or strands the old test file.

**Primary recommendation:** Plan 06-01 = pydantic schemas + validator stub (no IO); 06-02 = validator implementation + 5 unit tests; 06-03 = endpoint + `build_unity_zip` refactor + delete v1 + parity extension. Atomic commits per task.

---

## Per-Discretion Answers (1-18)

### 1. Sentinel ocean RGB source-of-truth for D-09 OCEAN_LEAK

**Finding:** No exported `OCEAN_LOOKUP_RGB` constant in `render.py`. The lookup PNG ocean color is `tuple(cfg.ocean_far)` — see `backend/medieval_forge/services/pipeline/lookup.py:31`:

```python
lk = np.full((h, w, 3), list(cfg.ocean_far), dtype=np.uint8)
```

The full lookup PNG is filled with `cfg.ocean_far` (default `(70, 130, 180)`), then territory RGBs overwrite land pixels via `lk[m] = [r,g,b]` (lookup.py:50). CLAUDE.md rule 5 sentinels (`-1`, `9999`) are cleanup-stage int sentinels in `pc`/`pd`/`result` arrays — unrelated to lookup PNG RGB.

**Recommendation:** Validator reads `tuple(cfg.ocean_far)` directly from the `RegionConfig` passed in. Do NOT create a new constant; the source of truth is `cfg`. Add an inline comment quoting `lookup.py:31`.

### 2. sha256 timing

**Recommendation:** Hash at validator time. The validator reads every file anyway for schema validation. Hashing at zip-write would double I/O without semantic benefit. Pass the `{filename: sha256}` map from validator output through `build_unity_zip` into the MANIFEST.

### 3. `ValidationFailedError` vs return-report

**Finding:** Pure-function discipline (D-01) says `validate_export` returns `ValidationReport`. The caller (`build_unity_zip` and the endpoint) branches on `report.passed`.

**Recommendation:** Return report. Add a thin wrapper `ValidationFailedError(report)` raised inside `build_unity_zip` AFTER `validate_export` is consulted, so the endpoint can catch it for 422 mapping without coupling the validator to FastAPI exceptions. Mirror `api/export.py:42-44` (`try: build_unity_zip ... except FileNotFoundError: HTTPException(409)`) — same shape, new exception type.

### 4. `services/export/` subpackage layout

**Recommendation:** Top-level `services/export/` (sibling of `services/pipeline/`). Confirmed by import graph:
- `services/pipeline/__init__.py` does not import anything from `services/export/`
- `services/export.py` (current top-level) imports `pipeline.contracts.EXPORT_FILE_CONTRACT` — pipeline → export edge already exists in one direction
- Convert existing `services/export.py` → `services/export/__init__.py` re-exporting `build_unity_zip` (avoids breaking callers in `api/export.py:12`)

**Layout:**
```
backend/medieval_forge/services/export/
├── __init__.py        # re-export build_unity_zip + validate_export + ValidationReport
├── schemas.py         # 6 BaseModel classes + MANIFEST_SCHEMA_VERSION
├── validator.py       # validate_export + 5 check functions + ValidationReport dataclass
└── zip.py             # build_unity_zip (refactored from current services/export.py)
```

### 5. Schema version constant placement

**Recommendation:** `MANIFEST_SCHEMA_VERSION = 2` constant at top of `schemas.py`. Karpathy #2 (simplicity): don't invent a `__version__` field for a single integer.

### 6. Test file split (5 unit files vs 1)

**Finding:** `backend/tests/unit/` already exists with `__init__.py`. Nested subpackages exist (`backend/tests/unit/adapters/__init__.py`, `backend/tests/unit/api/__init__.py`). Five flat files at `backend/tests/unit/test_validator_*.py` match the existing pattern (e.g., `test_cleanup_split.py`, `test_dag_tokens.py`).

**Recommendation:** Five files. No `__init__.py` per-test-file needed; existing `unit/__init__.py` covers them. Names per D-15: `test_validator_color_collision.py`, `test_validator_ocean_leak.py`, `test_validator_original_idx.py`, `test_validator_territory_size.py`, `test_validator_pixel_center.py`. Plus `test_export_schemas.py` for the 6 schemas.

### 7. Endpoint mount order during delete/add

**Recommendation:** Same plan (atomic). Phase 05 precedent — STATE.md line ~98: *"all 5 planned migrations + 3 extras (audit found __main__.py + 2 unit tests) done in commit 6a388a2; 3 retirements in same commit; D-13+D-17 step 5 locked by c0be89e"*. Same-commit delete+add keeps the parity gate green.

**Files touched in one commit:**
- Add `api/v3/export.py`
- Update `api/v3/__init__.py` to export `export_router`
- Update `main.py` lines 40-59 (drop `api.export` import + `app.include_router(export_router, ...)`; add v3 export import + mount)
- Delete `api/export.py`
- Delete `backend/tests/test_export.py` (rewritten under `tests/e2e/test_export_gate_*.py`)

### 8. MANIFEST.json placement inside the zip

**Finding:** Current `services/export.py:113` writes `MANIFEST.json` as top-level entry (`zf.writestr("MANIFEST.json", ...)`).

**Recommendation:** Keep top-level. D-07 stays.

### 9. `territory_metadata.json` schema fidelity (MISSION-CRITICAL)

**Verified shape** from `tests/fixtures/iberia_868/golden/territory_metadata.json` (1820 lines):

```jsonc
{
  "region": "iberia",                              // str
  "map_size": [3840, 2160],                        // [int, int] — 2x map dims
  "bounds": {"lon_min": -13.2, "lon_max": 8.2, "lat_min": 35.4, "lat_max": 44.6},
  "kingdoms": { "asturias": "Reino das Astúrias", ... },    // dict[str, str]
  "duchies":  { "d_asturias": {"kingdom": "asturias", "name": "..."}, ... },
  "condados": [
    {
      "id": "menorca",            // str
      "name": "Manurqa",          // str
      "lon": 4.09, "lat": 39.95,  // float
      "duchy": "d_baleares",      // str (duchy id)
      "kingdom": "emirato",       // str (kingdom id)
      "pixel_center": [1549, 544],// [int, int] — Y-DOWN numpy convention (D-10)
      "pixel_count": 817,         // int (>= 1; empty condados compacted out)
      "baronies": ["Maó", "Ciutadella"],  // list[str] — barony names only
      "original_idx": 92          // int, OPTIONAL (emitted when condado tuple len > 6)
    }
  ],
  "baronies": [
    {
      "name": "Grado",            // str
      "condado_idx": 0,           // int
      "duchy": "d_asturias",      // str
      "pixel_count": 889          // int
      // NO original_idx on baronies — golden has none
    }
  ]
}
```

Source of truth: `services/pipeline/export.py:37-82` (`export_metadata` writer).

**Recommendation:** Use `ConfigDict(extra='forbid')` — matches existing project convention. If Iberia parity breaks, the schema is wrong, not the data. See §Pydantic Schema Templates below.

### 10. Per-file MANIFEST entries

**Current shape** (`services/export.py:94-98`): `{name, source, size_bytes}`.

**D-07 additions:** `sha256` (per-file). No timestamp/encoding belongs at per-file level — `generated_at_utc`/`exported_at_utc` are top-level.

**Recommendation:** `MANIFEST.files[i] = {name, source, size_bytes, sha256}`. Hex-encoded sha256 (64 chars). Compute in validator via `hashlib.sha256(path.read_bytes()).hexdigest()` during the read-for-schema pass.

### 11. Status state machine interaction

**Verified:** `api/export.py:18` — `_ALLOWED_PRE_EXPORT_STATUSES = frozenset({"generated", "exported"})`. On gate-pass (line 46): `project.status = "exported"`. On `build_unity_zip` FileNotFoundError (line 43-44): 409 with no status flip.

**Recommendation for v3 endpoint:**
- Pre-check: status must be in `{"generated", "exported"}` → else 409
- On gate-pass: flip `generated → exported`
- On gate-fail (422): leave status as-is (no `error_exporting` flip — gate-fail is a *report*, not a worker crash). CONTEXT.md confirms; do not introduce a new status.

### 12. `POST /api/v3/projects/{id}/export` route shape

**Verified pattern** from `api/v3/projects.py:25` and `api/v3/generate.py:44`: routers use `prefix="/v3/projects"` (NOT `/api/v3/projects`); `main.py` adds `/api` at mount time (line 59). STATE.md explicitly notes prior plan slip on this — *"Router prefix /v3/projects (not /api/v3/projects)"*.

**Recommendation:**
```python
# api/v3/export.py
router = APIRouter(prefix="/v3/projects", tags=["v3-export"])

@router.post("/{project_id}/export")
async def trigger_v3_export(
    project_id: str,
    dry_run: bool = False,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse | FileResponse: ...

@router.get("/{project_id}/export/download")
async def download_v3_export(project_id: str) -> FileResponse: ...
```

See §FastAPI Route Sketch below.

### 13. MANIFEST `validation_report` shape when `dry_run=true`

**Recommendation:** Same envelope as MANIFEST.validation_report, plus the `summary` count and `files_checked` list:

```json
{
  "dry_run": true,
  "passed": true,
  "summary": "0 errors, 0 warnings",
  "errors": [],
  "warnings": [],
  "files_checked": ["lookup_barony.png", "lookup_condado.png", ...]
}
```

`dry_run` flag at the top level distinguishes from real MANIFEST consumers. On dry_run failure, return 422 with the same `detail` envelope as real-run failure (D-08) so the UI can parse both identically.

### 14. Iberia `enforce_original_idx: false` impact on parity test

**Verified:**
- `RegionConfigSchema` (region_loader.py:79) uses `extra='forbid'`
- `RegionConfig` is `@dataclass` (contracts.py:46-137); fields have defaults

**Recommendation:**
1. Add `enforce_original_idx: bool = True` to `RegionConfig` dataclass (after `draw_names: bool = False` on line 117)
2. Add same field to `RegionConfigSchema` (region_loader.py:149): `enforce_original_idx: bool = True`
3. Add `enforce_original_idx: false` line to `data/regions/iberia_868.yaml` AFTER user confirms D-11 reconciliation (see Risk Register)
4. France/England YAMLs unaffected (default True)
5. Phase 05 parity (`test_iberia_868_yaml.py`) stays green: new field has default, golden territory_metadata.json unaffected (validator runs *after* generation; flag controls gate behavior, not output)

### 15. Error code stability across i18n

**Verified:** The 6 codes do NOT collide with existing error strings in the codebase. Checked via grep on `api/`, `services/`, no `COLOR_COLLISION` / `OCEAN_LEAK` etc. in current source. v1 `api/export.py` uses `"detail": str(exc)` (plain text) — no structured codes today. Path is clean.

### 16. `tests/e2e/` runtime cost

**Verified:** Single fixture in `test_france_1066_export_contract.py:55-62` runs the full France 1066 pipeline once per **module** (`scope="module"`, not session). The broken-project test (D-14) can:
- Reuse a `scope="module"` fixture that runs France ONCE per module
- Mutate copies of `generated/` files for each broken-case test
- Run validator + assert 422 via TestClient (no zip write)

Phase 04.1 STATE.md note: "Iberia run is the cost driver, France is cheap." Cost-effective. No need to share fixture across modules.

**Iberia e2e (test_export_gate_iberia.py):** Use the existing parity fixture pattern (session-scope Iberia run) — runs ~30s once for the whole parity+e2e suite if scoped correctly.

### 17. Pydantic v2 idioms — confirmed

`pyproject.toml`: `pydantic>=2.7,<3.0`. `region_loader.py` patterns to mirror:
- `class FooSchema(BaseModel): model_config = ConfigDict(extra="forbid")`
- `field: int = Field(default=200, ge=1)` (numeric constraints)
- `field: list[int] = Field(default_factory=list)`
- `model_validate(raw_dict)` for parsing
- `model_dump()` to convert back to dict
- No `@field_validator` / `@model_validator` patterns found in current code — keep validation field-local per CONTEXT.md "no cross-field constraints" deferral

### 18. OCEAN_LEAK landmask source

**Verified:** Validator signature is `validate_export(generated_dir, cfg)`. No landmask numpy array on disk currently. Three options:

| Option | Source | Cost | Drawback |
|--------|--------|------|----------|
| (a) Re-derive | `pipeline.landmask.build_land_mask(cfg)` | ~seconds (loads GeoJSON, rasterizes) | Slow; couples validator to pipeline internals |
| (b) Derive from `terrain_lookup.png` | `(arr != OCEAN_RGB).any(axis=-1)` | <50ms (PIL load + numpy compare) | Circular if `terrain_lookup.png` itself failed schema check |
| (c) New sidecar | Add `landmask.png` to generated/ | Same as (b) | Bloats EXPORT_FILE_CONTRACT; violates D-01 ("read files, no side effects") |

**Recommendation: (b).** Karpathy-simple. The validator's order-of-operations naturally handles the circularity:
1. SCHEMA_INVALID short-circuits (D-18) — if `terrain_lookup.png` is corrupt, we never reach OCEAN_LEAK
2. If terrain_lookup.png is schema-valid (1920×1080 RGB), it's a reliable land/ocean source
3. The check is `mask_ocean = ~land; for pixel in mask_ocean: assert pixel_rgb == cfg.ocean_far` on `lookup_barony.png` and `lookup_condado.png`

**Pseudocode for the check:**
```python
terrain_arr = np.array(Image.open(generated_dir / "terrain_lookup.png").convert("RGB"))
land = (terrain_arr != OCEAN_RGB).any(axis=-1)           # bool[H,W]
ocean = ~land
for lookup_name in ("lookup_barony.png", "lookup_condado.png"):
    lk = np.array(Image.open(generated_dir / lookup_name).convert("RGB"))
    expected_ocean_rgb = np.array(cfg.ocean_far, dtype=np.uint8)
    leaks = ocean & np.any(lk != expected_ocean_rgb, axis=-1)
    if leaks.any():
        # Sample up to 10 leak coordinates for the error context
        ys, xs = np.where(leaks)
        sample = [(int(xs[i]), int(ys[i]), tuple(int(c) for c in lk[ys[i], xs[i]])) for i in range(min(10, len(ys)))]
        report.add_error("OCEAN_LEAK", file=lookup_name, context={"leak_count": int(leaks.sum()), "sample_pixels": sample})
```

---

## Pydantic Schema Templates

All schemas live in `services/export/schemas.py`. Mirror `region_loader.RegionConfigSchema` idiom exactly.

```python
"""services/export/schemas.py — pydantic v2 schemas for the 5 contract JSONs + MANIFEST."""
from __future__ import annotations
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

MANIFEST_SCHEMA_VERSION: int = 2

_RGB_KEY_RE = re.compile(r"^(\d{1,3}),(\d{1,3}),(\d{1,3})$")


class LookupBaronyColorsSchema(BaseModel):
    """RGB-string-key → barony index. Schema mirrors lookup.py:51 (`f"{r},{g},{b}": i`)."""
    model_config = ConfigDict(extra="forbid")
    # Pydantic v2 dict[str, int] doesn't validate key format directly — use root validator.
    root: dict[str, int]  # WRAPPER: model_validate({"50,80,30": 0, ...}) maps into root.

    @field_validator("root")
    @classmethod
    def _check_keys_are_rgb(cls, v: dict[str, int]) -> dict[str, int]:
        for key in v:
            m = _RGB_KEY_RE.match(key)
            if not m or any(int(g) > 255 for g in m.groups()):
                raise ValueError(f"invalid RGB key: {key!r} (must match 0-255,0-255,0-255)")
        return v


# NOTE on the dict-key validation pattern: pydantic v2's RootModel can wrap a dict
# directly. Prefer RootModel over the field_validator pattern above:
#   class LookupBaronyColorsSchema(RootModel[dict[str, int]]):
#       @field_validator("root") ...
# (RootModel preserves the JSON shape as a plain dict — no .root wrapper in output.)


class LookupCondadoColorsSchema(LookupBaronyColorsSchema):
    """Identical shape to LookupBaronyColorsSchema."""
    pass


class TerrainTypePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    movement: float = Field(ge=0.0)
    defense: float = Field(ge=0.0)
    attack: float = Field(ge=0.0)


class TerrainTypesSchema(BaseModel):
    """Top-level: dict[RGB_str, payload]. See terrain.py:41-44."""
    model_config = ConfigDict(extra="forbid")
    root: dict[str, TerrainTypePayload]
    # Same RGB-key validator as lookup colors


class CondadoEntrySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    lon: float
    lat: float
    duchy: str
    kingdom: str
    pixel_center: tuple[int, int]    # [col, row] Y-DOWN — D-10
    pixel_count: int = Field(ge=1)
    baronies: list[str]
    original_idx: int | None = None  # OPTIONAL — emitted when condado tuple len > 6


class BaronyEntrySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    condado_idx: int
    duchy: str
    pixel_count: int = Field(ge=1)


class DuchyEntrySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kingdom: str
    name: str


class TerritoryMetadataSchema(BaseModel):
    """Mirrors export.py:37-82 verbatim. ConfigDict(extra='forbid') ensures the
    pipeline cannot silently add a key without the schema knowing."""
    model_config = ConfigDict(extra="forbid")
    region: str
    map_size: tuple[int, int]
    bounds: dict[str, float]
    kingdoms: dict[str, str]
    duchies: dict[str, DuchyEntrySchema]
    condados: list[CondadoEntrySchema]
    baronies: list[BaronyEntrySchema]


class MountainRiverDataSchema(BaseModel):
    """Permissive — toy datasets often ship empty {}; real Iberia ships rich data."""
    model_config = ConfigDict(extra="allow")  # external file, looser contract
    mountains: dict = Field(default_factory=dict)
    rivers: dict = Field(default_factory=dict)


class ManifestFileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    source: str  # "generated" | "placeholder"
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ValidationErrorEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    severity: str  # "error" | "warning"
    file: str | None = None
    context: dict
    message: str


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    errors: list[ValidationErrorEntry] = Field(default_factory=list)
    warnings: list[ValidationErrorEntry] = Field(default_factory=list)


class ManifestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = MANIFEST_SCHEMA_VERSION
    region_key: str
    project_id: str
    generated_at_utc: str
    exported_at_utc: str
    spec_version: int = 1
    phase: int = 6
    validation_report: ValidationReport
    files: list[ManifestFileEntry]
```

---

## Validator Orchestration Sketch

```python
# services/export/validator.py
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image

from .schemas import (
    LookupBaronyColorsSchema, LookupCondadoColorsSchema, TerrainTypesSchema,
    TerritoryMetadataSchema, MountainRiverDataSchema,
    ValidationReport, ValidationErrorEntry,
)
from ..pipeline.contracts import EXPORT_FILE_CONTRACT, RegionConfig
from ..pipeline.terrain import PLAINS_RGB, OCEAN_RGB


@dataclass
class _ValidationContext:
    """Internal mutable accumulator. The PUBLIC return is ValidationReport (pydantic)."""
    errors: list[ValidationErrorEntry] = field(default_factory=list)
    warnings: list[ValidationErrorEntry] = field(default_factory=list)
    sha256_by_file: dict[str, str] = field(default_factory=dict)

    def add_error(self, code: str, file: str | None, context: dict, message: str) -> None:
        self.errors.append(ValidationErrorEntry(
            code=code, severity="error", file=file, context=context, message=message,
        ))


def validate_export(generated_dir: Path, cfg: RegionConfig) -> tuple[ValidationReport, dict[str, str]]:
    """Pure function. Reads files, returns (report, sha256_map). No side effects."""
    ctx = _ValidationContext()

    # Step 1: read each contract file once; compute sha256; parse JSON-shaped files.
    payloads: dict[str, Any] = {}
    for fname in EXPORT_FILE_CONTRACT:
        path = generated_dir / fname
        if not path.exists():
            # Missing file is a schema-level concern — record and continue (collect-all).
            ctx.add_error("SCHEMA_INVALID", file=fname, context={"reason": "missing"},
                          message=f"contract file missing: {fname}")
            continue
        raw_bytes = path.read_bytes()
        ctx.sha256_by_file[fname] = hashlib.sha256(raw_bytes).hexdigest()
        if fname.endswith(".json"):
            try:
                payloads[fname] = json.loads(raw_bytes.decode("utf-8"))
            except json.JSONDecodeError as exc:
                ctx.add_error("SCHEMA_INVALID", file=fname, context={"reason": str(exc)},
                              message=f"invalid JSON: {fname}")

    # Step 2: pydantic schema validation per JSON.
    # SHORT-CIRCUITS the semantic checks if any schema fails (D-18 exception).
    schema_ok = _run_schema_validation(ctx, payloads)
    if not schema_ok:
        return _build_report(ctx), ctx.sha256_by_file

    # Step 3: run all 5 semantic checks; collect all errors (D-18 main rule).
    _check_color_collision(ctx, payloads, cfg)
    _check_ocean_leak(ctx, generated_dir, cfg)
    _check_territory_size(ctx, generated_dir, payloads, cfg)
    _check_original_idx(ctx, payloads, cfg)
    _check_pixel_center(ctx, payloads, cfg)

    return _build_report(ctx), ctx.sha256_by_file


def _build_report(ctx: _ValidationContext) -> ValidationReport:
    return ValidationReport(
        passed=len(ctx.errors) == 0,
        errors=ctx.errors,
        warnings=ctx.warnings,
    )


def _run_schema_validation(ctx, payloads) -> bool:
    """Returns True if every JSON parses against its schema. Records errors on failure."""
    schema_map = {
        "lookup_barony_colors.json": LookupBaronyColorsSchema,
        "lookup_condado_colors.json": LookupCondadoColorsSchema,
        "terrain_types.json": TerrainTypesSchema,
        "territory_metadata.json": TerritoryMetadataSchema,
        "mountain_river_data.json": MountainRiverDataSchema,
    }
    all_ok = True
    for fname, Schema in schema_map.items():
        if fname not in payloads:
            continue  # already reported as missing in Step 1
        try:
            Schema.model_validate(payloads[fname])
        except Exception as exc:
            ctx.add_error("SCHEMA_INVALID", file=fname, context={"errors": str(exc)},
                          message=f"schema validation failed for {fname}")
            all_ok = False
    return all_ok


# Individual check functions — see pseudocode for OCEAN_LEAK in §Per-Discretion #18.
# Each check is a single function ~30-50 LoC. Total validator.py target: ~300 LoC.
```

---

## FastAPI Route Sketch

```python
# api/v3/export.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models import Project
from ...services.paths import is_valid_uuid, project_dir
from ...services.export import build_unity_zip, validate_export, ValidationFailedError
from ...services.pipeline.region_loader import load_region

router = APIRouter(prefix="/v3/projects", tags=["v3-export"])
_ALLOWED_PRE_EXPORT_STATUSES = frozenset({"generated", "exported"})


@router.post("/{project_id}/export")
async def trigger_v3_export(
    project_id: str,
    dry_run: bool = False,
    db: AsyncSession = Depends(get_db),
):
    if not is_valid_uuid(project_id):
        raise HTTPException(400, detail="project_id must be a valid UUID")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, detail="project not found")
    if project.status not in _ALLOWED_PRE_EXPORT_STATUSES:
        raise HTTPException(409, detail=f"project.status={project.status!r}; run /generate first")

    cfg = load_region(project.region_key)
    generated = project_dir(project_id) / "output"  # match generate.py:140

    if dry_run:
        report, _sha = validate_export(generated, cfg)
        body = {"dry_run": True, **report.model_dump()}
        return JSONResponse(status_code=200 if report.passed else 422, content=body)

    # Real export: validator → zip → status flip
    try:
        zip_path = build_unity_zip(project_id)  # internally calls validate_export
    except ValidationFailedError as exc:
        return JSONResponse(status_code=422, content={"detail": {
            "summary": f"{len(exc.report.errors)} errors blocked export",
            "errors": [e.model_dump() for e in exc.report.errors],
            "warnings": [w.model_dump() for w in exc.report.warnings],
        }})
    except FileNotFoundError as exc:
        raise HTTPException(409, detail=str(exc))

    project.status = "exported"
    await db.commit()
    return JSONResponse(status_code=201, content={
        "project_id": project_id,
        "zip_filename": zip_path.name,
        "size_bytes": zip_path.stat().st_size,
        "download_url": f"/api/v3/projects/{project_id}/export/download",
    })


@router.get("/{project_id}/export/download")
async def download_v3_export(project_id: str):
    # Mirror api/export.py:57-77 verbatim — same path discovery
    ...
```

---

## Risk Register

### **BLOCKER:** D-11 stale rationale

**Evidence:**
- `data/regions/iberia_868.yaml` lines 248..1741 — every condado has `original_idx: 1..92` [VERIFIED: grep returned 92 matches]
- `tests/fixtures/iberia_868/golden/territory_metadata.json` — 91 condados emit `original_idx` (one compacted out via `npx == 0` per export.py:52) [VERIFIED: grep returned 91 matches]
- `services/pipeline/export.py:69` already gates emission on `len(c) > 6` → Iberia condados are length-7 tuples → field IS emitted

**Conflict:** CONTEXT.md D-11 says "PREFLIGHT Q8 found 0/92 condados with original_idx" — directly contradicted by repo state.

**Subtle nuance:** Golden baronies (`territory_metadata.json` lines 1838+) carry only `{name, condado_idx, duchy, pixel_count}` — NO `original_idx` on baronies. So the gate "every condado AND every barony carries `original_idx`" would still fail on Iberia at the barony level.

**Three reconciliation paths for user/planner:**
1. **Narrow the check to condados-only** → Iberia passes without flag; baronies legitimately lack original_idx (canonical references treat baronies as positional via `condado_idx`). Drop `enforce_original_idx` flag entirely.
2. **Keep the flag, fix the rationale** → "Iberia gold baronies lack `original_idx`; flag disables the gate for legacy region until v3.1 rebake." Iberia YAML stays as-is.
3. **Re-bake Iberia gold + Unity-side** → out of scope per CONTEXT.md deferred ideas; not a Phase 06 option.

**Recommendation:** Surface to user via `/gsd-discuss-phase` follow-up before Wave 1. Without reconciliation, the planner risks wiring a YAML flag that does nothing (Option 1) or wiring it with the wrong scope (Option 2).

### Other risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | `territory_metadata.json` schema drifts from `export.py` writer | `ConfigDict(extra='forbid')`; parity test (D-16) catches drift on every CI run |
| R2 | `RegionConfigSchema` extra='forbid' rejects new `enforce_original_idx` field on old YAMLs | Field has default `True`; existing YAMLs untouched [VERIFIED: region_loader.py:130 pattern] |
| R3 | OCEAN_LEAK landmask circular if terrain_lookup.png itself is corrupt | SCHEMA_INVALID short-circuit (D-18) prevents the check from running on corrupt files |
| R4 | sha256 over a multi-MB zip slow | Validator-time hashing avoids zip-time double-pass; ~50ms per 4MB visual PNG measured by typical np.fromfile cost |
| R5 | `validate_export(cfg)` couples export to region_loader (load_region) | Cfg is plain `RegionConfig` dataclass; validator imports `RegionConfig` from `pipeline.contracts`, not `region_loader`. Clean separation. |
| R6 | `RootModel` vs `BaseModel` for dict-shape schemas (`lookup_*_colors.json`) | Recommend `RootModel[dict[str, int]]` (pydantic v2 idiom); falls back to BaseModel with `root` field if RootModel pattern breaks tests |
| R7 | Iberia parity uses session-scoped fixture (`tmp_path_factory.mktemp`) — extending with MANIFEST assertion needs the e2e endpoint, not just `run_pipeline` | D-16: call `build_unity_zip(project_id)` against an in-memory project OR read `validate_export(out, cfg)` directly (avoids DB setup) |
| R8 | Iberia 868 + France 1066 e2e tests share france_output fixture pattern but Iberia is ~30s vs France ~5s | Reuse session-scope for Iberia, module-scope for France (current pattern); broken-fixtures mutate copies, not the shared output dir |
| R9 | `services/export.py` is a single file today; refactor to package risks import drift | `services/export/__init__.py` re-exports `build_unity_zip` to preserve `from ..services.export import build_unity_zip` at `api/export.py:12` (which is being deleted anyway, but `services/pipeline/__init__.py` and tests may have stale imports — grep first) |
| R10 | numpy bool landmask comparison `(arr != OCEAN_RGB).any(axis=-1)` produces wrong type if image is RGBA | `.convert("RGB")` before np.array — see `test_france_1066_export_contract.py:157` for the canonical pattern |

---

## Validation Architecture

> nyquist_validation is enabled (no config override found).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 + pytest-asyncio (asyncio_mode=auto) [VERIFIED: pyproject.toml] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Markers | `slow, unit, parity, integration, uat, e2e` |
| Quick run command | `pytest backend/tests/unit/test_validator_*.py -x` |
| Full suite command | `pytest backend/tests -x` |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Automated Command | File Exists? |
|-----|----------|-----------|-------------------|-------------|
| SC-1 | All JSON outputs schema-validated via pydantic | unit | `pytest backend/tests/unit/test_export_schemas.py -x` | ❌ Wave 0 |
| SC-2a | Export blocked on territory <200px | unit + e2e | `pytest -k territory_size or test_export_gate_broken -x` | ❌ Wave 0 |
| SC-2b | Export blocked on color collision | unit + e2e | `pytest -k color_collision or test_export_gate_broken -x` | ❌ Wave 0 |
| SC-2c | Export blocked on ocean leak | unit + e2e | `pytest -k ocean_leak or test_export_gate_broken -x` | ❌ Wave 0 |
| SC-2d | Export blocked on missing original_idx | unit + e2e | `pytest -k original_idx or test_export_gate_broken -x` | ❌ Wave 0 |
| SC-2e | Export blocked on pixel_center bounds | unit + e2e | `pytest -k pixel_center or test_export_gate_broken -x` | ❌ Wave 0 |
| SC-3 | MANIFEST matches Reconquista structure (file set) | e2e | `pytest backend/tests/e2e/test_export_gate_iberia.py -x` | ❌ Wave 0 |
| SC-4-Iberia | Iberia passes gate | parity + e2e | `pytest backend/tests/parity/test_iberia_868_yaml.py -x` | ✅ extend |
| SC-4-France | France passes gate | e2e | `pytest backend/tests/e2e/test_export_gate_france.py -x` | ❌ Wave 0 |
| SC-4-Broken | Broken project blocked with structured error list | e2e | `pytest backend/tests/e2e/test_export_gate_broken.py -x` | ❌ Wave 0 |

### Per-Code Coverage Matrix (D-08 stable codes)

| Code | Unit test (isolated check fn) | E2E broken fixture | Parity assertion |
|------|-------------------------------|--------------------|-----------------------|
| `SCHEMA_INVALID` | `test_export_schemas.py::test_*_rejects_*` | broken: corrupt JSON byte | Iberia parity: schema_ok=True |
| `COLOR_COLLISION` | `test_validator_color_collision.py` | broken: dup RGB in lookup_condado_colors.json | Iberia parity: 0 collisions |
| `OCEAN_LEAK` | `test_validator_ocean_leak.py` | broken: paint condado RGB into ocean pixels | Iberia parity: 0 leaks |
| `MISSING_ORIGINAL_IDX` | `test_validator_original_idx.py` | broken: drop original_idx from one condado | Iberia parity: passes (flag-dependent — see BLOCKER) |
| `TERRITORY_TOO_SMALL` | `test_validator_territory_size.py` | broken: shrink condado to 150px | Iberia parity: 0 territories <200px |
| `PIXEL_CENTER_OUT_OF_RANGE` | `test_validator_pixel_center.py` | broken: set pixel_center=[-1, 0] | Iberia parity: all in-bounds |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/unit/test_validator_*.py backend/tests/unit/test_export_schemas.py -x` (~5s)
- **Per wave merge:** `pytest backend/tests/unit backend/tests/e2e -x` (~30s)
- **Phase gate:** `pytest backend/tests -x` (full suite, ~2min including parity)

### Wave 0 Gaps

- [ ] `backend/medieval_forge/services/export/__init__.py` — re-exports
- [ ] `backend/medieval_forge/services/export/schemas.py` — 6 pydantic models + `MANIFEST_SCHEMA_VERSION`
- [ ] `backend/medieval_forge/services/export/validator.py` — `validate_export` + 5 check fns + `ValidationFailedError`
- [ ] `backend/medieval_forge/services/export/zip.py` — refactored `build_unity_zip` (calls validator first)
- [ ] `backend/medieval_forge/api/v3/export.py` — new router
- [ ] `backend/tests/unit/test_export_schemas.py`
- [ ] `backend/tests/unit/test_validator_color_collision.py`
- [ ] `backend/tests/unit/test_validator_ocean_leak.py`
- [ ] `backend/tests/unit/test_validator_original_idx.py`
- [ ] `backend/tests/unit/test_validator_territory_size.py`
- [ ] `backend/tests/unit/test_validator_pixel_center.py`
- [ ] `backend/tests/e2e/test_export_gate_iberia.py`
- [ ] `backend/tests/e2e/test_export_gate_france.py`
- [ ] `backend/tests/e2e/test_export_gate_broken.py`
- [ ] Existing `backend/tests/parity/test_iberia_868_yaml.py` — extend with MANIFEST.validation_report assertion (D-16)
- [ ] Delete `backend/medieval_forge/api/export.py` + `backend/tests/test_export.py`

No framework install needed; pytest 8.4 already in place.

---

## Project Constraints (from CLAUDE.md)

- **Tech stack:** Python 3.11+, FastAPI, SQLite; backend-only Phase 06 (D-19)
- **Conventions:** module submodule layout (`services/export/` mirrors `services/pipeline/` flat-split); single mutable input (`RegionConfig`); atomic commits per task (`type(phase-plan): subject`)
- **Three-layer test pyramid:** unit + parity + e2e (Playwright not applicable Phase 06)
- **Determinism:** `np.random.default_rng(42)` locked; validator must NOT introduce RNG
- **Karpathy skill:** surgical changes; simplicity-first; no speculative abstractions
- **CLAUDE.md rule 4 (Nájera bug):** `original_idx` in every territory — drives MISSING_ORIGINAL_IDX check; BLOCKER applies
- **CLAUDE.md rule 5 (sentinels):** `ocean=-1`, `ignore=9999` are cleanup-stage int sentinels, NOT lookup PNG colors. Lookup PNG ocean = `cfg.ocean_far` [VERIFIED: lookup.py:31]
- **CLAUDE.md rule 7 (byOriginalIdx Unity-side):** ties to MISSING_ORIGINAL_IDX gate enforcement

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `RootModel[dict[str, int]]` is the right pydantic v2 idiom for top-level-dict JSON schemas | Pydantic Schema Templates | Schema parsing fails; planner falls back to BaseModel with `root` field (no architectural impact) |
| A2 | Validator runtime < 1s per Iberia run (sha256 of ~10MB + 5 checks) | sha256 timing | If slow, planner moves sha256 to zip-write time (Option 2 in §Per-Discretion #2) |
| A3 | `ConfigDict(extra='forbid')` on `TerritoryMetadataSchema` will not break existing Iberia golden | Schema fidelity | If golden has a key not in the schema, parity breaks. Risk: low — every key in golden lines 1819-1836 is enumerated above |
| A4 | OCEAN_LEAK sample size = 10 pixels per error context is enough for UI debugging | OCEAN_LEAK pseudocode | If users want more, easy to bump; not load-bearing |

All other claims are `[VERIFIED:` direct codebase grep/Read.

---

## Open Questions

1. **D-11 reconciliation (see BLOCKER above)**
   - What we know: golden has 91/91 condados with `original_idx`; baronies have none
   - What's unclear: should the gate apply to baronies or condados-only?
   - Recommendation: planner pauses Wave 1; user picks one of 3 paths

2. **`RootModel` vs `BaseModel` wrapper for dict-shape JSONs**
   - What we know: pydantic v2.7+ has `RootModel`; project hasn't used it yet
   - What's unclear: whether the project prefers RootModel idiom or wrapper class
   - Recommendation: try `RootModel` first (cleaner); fall back to wrapper if test ergonomics suffer

3. **Should `dry_run=true` return 200 or 422 on gate failure?**
   - CONTEXT.md D-03: "status 200 if passed / 422 if failed" — locked. Document this in the route docstring; UI handles both.

---

## Environment Availability

Phase 06 is pure Python (backend-only, no new external tools). All deps in place:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pydantic | schemas.py | ✓ | 2.7+ [VERIFIED: pyproject.toml] | — |
| Pillow (PIL) | lookup/terrain PNG reads | ✓ | already in use [VERIFIED: render.py:25] | — |
| numpy | OCEAN_LEAK array math | ✓ | already in use | — |
| hashlib | sha256 | ✓ | stdlib | — |
| pytest | tests | ✓ | 8.4.2 | — |
| FastAPI | api/v3/export.py | ✓ | 0.115+ [VERIFIED: pyproject.toml] | — |

No missing dependencies; no fallbacks needed.

---

## Sources

### Primary (HIGH — direct repo reads)
- `backend/medieval_forge/services/pipeline/lookup.py:31` — ocean RGB source
- `backend/medieval_forge/services/pipeline/render.py:34-172` — ocean rendering pattern
- `backend/medieval_forge/services/pipeline/terrain.py:35-44` — PLAINS_RGB / OCEAN_RGB / TERRAIN_TYPES_JSON
- `backend/medieval_forge/services/pipeline/contracts.py:193-209` — EXPORT_FILE_CONTRACT (12 files)
- `backend/medieval_forge/services/pipeline/export.py:37-82` — territory_metadata.json writer (canonical shape)
- `backend/medieval_forge/services/pipeline/region_loader.py:79-149` — pydantic v2 idiom mirror target
- `backend/medieval_forge/services/export.py:60-117` — current build_unity_zip (refactor target)
- `backend/medieval_forge/api/export.py:1-77` — current v1 export endpoint (deletion target)
- `backend/medieval_forge/api/v3/__init__.py` — router registration pattern
- `backend/medieval_forge/api/v3/projects.py:25` — `prefix="/v3/projects"` (NOT `/api/v3/projects`)
- `backend/medieval_forge/api/v3/generate.py:44-251` — SSE producer pattern (not used here, but project conventions confirmed)
- `backend/medieval_forge/main.py:39-59` — mount order; v1 + v3 routers
- `backend/medieval_forge/services/paths.py:36-66` — `is_valid_uuid`, `project_dir`, `ensure_project_dirs`
- `backend/tests/conftest.py` — pytest fixtures (`client`, `clear_region_cache_between_tests`)
- `backend/tests/e2e/test_france_1066_export_contract.py:55-188` — fixture pattern for broken-project tests
- `backend/tests/parity/test_iberia_868_yaml.py:31-119` — parity test (D-16 extension target)
- `backend/tests/test_export.py:1-172` — current v1 export tests (deletion target)
- `tests/fixtures/iberia_868/golden/territory_metadata.json:1820-1840` — verified condado + barony shapes
- `tests/fixtures/iberia_868/golden/lookup_condado_colors.json:1-15` — verified RGB-key dict shape
- `data/regions/iberia_868.yaml` — 92 condados with `original_idx: 1..92` (BLOCKER evidence)
- `pyproject.toml` — pydantic 2.7+, pytest markers
- `.planning/STATE.md` — Phase 05 precedent for atomic delete+add
- `CLAUDE.md` — rules 4, 5, 7; v3 Pipeline Contract; Conventions

No WebSearch / Context7 / Exa lookups were needed — Phase 06 is purely internal architecture; primary sources are exhaustive.

---

## Metadata

**Confidence breakdown:**
- Discretion answers: HIGH — every answer cites `file:line`
- Schema fidelity: HIGH — golden JSON was read directly; 91 condados counted
- Risk register: HIGH — BLOCKER backed by direct grep of YAML + golden
- Validation Architecture: HIGH — pytest config + existing test patterns verified

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (30 days — Phase 06 is internal; no external dep churn)
