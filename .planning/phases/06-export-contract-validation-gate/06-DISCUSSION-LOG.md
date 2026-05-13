# Phase 06: Export contract + validation gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 06-export-contract-validation-gate
**Areas discussed:** Arquitetura gate+endpoint, Schema+manifest, Definições 5 checks, Fixture+test pyramid

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Arquitetura do gate + endpoint | Onde validador roda; hard-fail vs ?force; dry-run; v3 vs v1 endpoint | ✓ |
| Schema pydantic + manifest | Cobertura pydantic; localização modelos; MANIFEST shape; envelope erro | ✓ |
| Definições precisas dos 5 checks | Ocean leak; pixel_center Y; original_idx Iberia; <200px | ✓ |
| Fixture broken project + test pyramid | Forma broken; test pyramid; parity gate; frontend escopo | ✓ |

**User's choice:** All four areas selected.

---

## Area 1 — Arquitetura do gate + endpoint

### Q1.1 — Onde o código do validador deve viver?

| Option | Description | Selected |
|--------|-------------|----------|
| Novo `services/pipeline/validator.py` (Recommended) | Módulo dedicado, função pura, reuso CLI/UI | ✓ |
| Inline em `services/export.py` | Acoplado ao zipper; dry-run awkward | |
| Pipeline stage no DAG | Estágio 'validate' após 'export'; overkill | |

**User's choice:** Validator module (final location refined to `services/export/validator.py` in D-01 to keep export subpackage flat).
**Notes:** Recommended; mirrors `adapters/` subpackage pattern.

### Q1.2 — Gate falha hard ou aceita ?force=true override?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-fail apenas (Recommended) | 422 com lista erros; sem override | ✓ |
| ?force=true permite zip | MANIFEST.errors[] mas zip entregue | |
| Severity tiers (error blocks, warning passes) | Erros block, warnings pass + manifest | |

**User's choice:** Hard-fail only.
**Notes:** SC #4 "broken is blocked" → no override. Karpathy anti-pattern: don't design for hypothetical future. Warnings slot wired in envelope but unused in Phase 06.

### Q1.3 — Endpoint suporta dry-run?

| Option | Description | Selected |
|--------|-------------|----------|
| `POST /export?dry_run=true` (Recommended) | Mesmo endpoint, query param | ✓ |
| Endpoint separado `GET /export/validate` | Verb-correct mas rota extra | |
| Sem dry-run | UI tenta + captura 422 | |

**User's choice:** Same endpoint, `?dry_run=true` query parameter.

### Q1.4 — Endpoint v3 substitui v1 ou coexiste?

| Option | Description | Selected |
|--------|-------------|----------|
| Substitui v1 (delete `api/export.py`) (Recommended) | Per D-V3-04; v3 frontend já não usa v1 outras rotas | ✓ |
| Coexiste; v1 redirect 308 → v3 | Pre-existing test_export.py preservado | |
| Adiciona v3, deixa v1 in-place | Duas rotas mesma função; viola D-V3-04 | |

**User's choice:** Replace; delete `api/export.py`. Frontend UI swap deferred (D-19).

---

## Area 2 — Schema pydantic + manifest

### Q2.1 — Cobertura pydantic em quais JSONs?

| Option | Description | Selected |
|--------|-------------|----------|
| Todos 5 JSONs do contrato (Recommended) | + MANIFEST; defense-in-depth | ✓ |
| Apenas territory_metadata + MANIFEST | Outros 4 são flat dicts | |
| Modelos pydantic apenas onde há nesting | TypedDict pra resto | |

**User's choice:** Schemas para todos 5 contract JSONs + MANIFEST (6 BaseModels).

### Q2.2 — Onde os modelos pydantic vivem?

| Option | Description | Selected |
|--------|-------------|----------|
| Novo `services/export/schemas.py` (Recommended) | Subpacote dedicado; mirror adapters/ | ✓ |
| Estende `services/pipeline/contracts.py` | Cresce arquivo grande | |
| Co-localizado por módulo | Espalha modelos | |

**User's choice:** New `services/export/` subpackage with `schemas.py` + `validator.py`.

### Q2.3 — Formato do MANIFEST.json?

| Option | Description | Selected |
|--------|-------------|----------|
| Manter MANIFEST forge-específico, melhorar fields | + schema_version, region_key, sha256, validation_report | ✓ |
| Dropar MANIFEST (byte-parity Reconquista) | Reconquista sem manifest hoje | |
| Re-shape p/ matchar lookup_*_colors pattern | Flat dict {filename: {...}} | |

**User's choice:** Keep + extend MANIFEST.
**Notes:** Reconquista StreamingAssets/Maps não tem MANIFEST hoje; SC #3 "matches Reconquista structure" interpretado como file *set* (já enforced por EXPORT_FILE_CONTRACT). Schema bumps to v2.

### Q2.4 — Envelope de erro do endpoint 422?

| Option | Description | Selected |
|--------|-------------|----------|
| Lista estruturada custom (Recommended) | `{detail: {summary, errors: [{code, severity, file?, context, message}], warnings}}` | ✓ |
| FastAPI 422 padrão (loc/msg/type) | Pydantic ValidationError shape; awkward para gate de regra | |
| RFC 7807 problem+json | Overkill single-user local | |

**User's choice:** Custom structured-list with stable codes.
**Notes:** Codes (SCHEMA_INVALID, COLOR_COLLISION, OCEAN_LEAK, MISSING_ORIGINAL_IDX, TERRITORY_TOO_SMALL, PIXEL_CENTER_OUT_OF_RANGE) são i18n-stable.

---

## Area 3 — Definições precisas dos 5 checks

### Q3.1 — Definição de OCEAN_LEAK?

| Option | Description | Selected |
|--------|-------------|----------|
| Cor território em pixel oceânico do landmask (Recommended) | One-way (land color in water) | ✓ |
| Bidirecional (cor terra em água + cor água em terra) | Falsos positivos em lagos | |
| Pixel painted como condado cuja coord geo cai no oceano | Reprojection cara, redundante | |

**User's choice:** One-way; landmask-based.

### Q3.2 — pixel_center Y-axis: o que o gate verifica?

| Option | Description | Selected |
|--------|-------------|----------|
| Range check + documenta numpy Y-down (Recommended) | 0 ≤ y < map_h; sem conversão; Unity inverts on load | ✓ |
| Converter p/ Unity Y-up no export.py | Quebra byte-parity Iberia gold | |
| Schema apenas (sem run-time check) | Field(ge=0, le=...) — sem semantic check | |

**User's choice:** Range check only; preserve numpy Y-down.
**Notes:** v1-archive PROJECT.md sugestão de "convert on export" explicitly rejected (D-10).

### Q3.3 — original_idx: Iberia gold não tem. Como gate trata?

| Option | Description | Selected |
|--------|-------------|----------|
| Iberia gold isenta; gate strict para France/autogen (Recommended) | YAML flag `enforce_original_idx: false`; v3.1 re-bake | ✓ |
| Strict para todos; re-bake gold + Reconquista | Coordinated Unity-side update | |
| Strict só para autogen; per-region YAML opt-in | Idêntico ao recomendado, framing alternativo | |

**User's choice:** Iberia exemption via YAML flag.

### Q3.4 — Limiar TERRITORY_TOO_SMALL?

| Option | Description | Selected |
|--------|-------------|----------|
| 200px = blob_merge_px (atual cfg) (Recommended) | ROADMAP literal "<200px"; constante existe | ✓ |
| fragment_min_px (600) ou island_min_px (300) | Limiares maiores; inconsistente com pipeline | |
| Novo cfg.export_min_territory_px com default 200 | Configurável; trabalho adicional | |

**User's choice:** Use existing `blob_merge_px = 200`.

---

## Area 4 — Fixture broken project + test pyramid

### Q4.1 — Forma do projeto deliberadamente quebrado?

| Option | Description | Selected |
|--------|-------------|----------|
| Fixture .py constrói diretório generated/ inválido (Recommended) | Pytest fixtures mutam artefatos após gen France | ✓ |
| data/regions/broken_test.yaml dedicado | Polui data dir; YAML evolve com schema | |
| Monkeypatch unit-test isolado | Granular mas sem e2e wide; SC #4 exige endpoint | |

**User's choice:** .py fixtures in tests/e2e/test_export_gate_broken.py.

### Q4.2 — Test pyramid?

| Option | Description | Selected |
|--------|-------------|----------|
| Unit cada check + E2E gate + parity Iberia (Recommended) | 5 unit files + 3 e2e + parity extension | ✓ |
| Apenas E2E + parity (sem unit por check) | Localizar bug requer leitura envelope | |
| Unit per check + Playwright UAT (sem e2e backend) | Frontend não toca em Phase 06 | |

**User's choice:** Full pyramid: unit per check + e2e gate + parity extension.

### Q4.3 — Iberia parity test após gate ativo?

| Option | Description | Selected |
|--------|-------------|----------|
| Parity passa + manifest.validation_report.passed=true (Recommended) | Gate failure on Iberia = parity break | ✓ |
| Parity ignora gate (só bytes) | Risco: gate quebra Iberia silenciosamente | |
| Parity opt-in para gate via param | 2x CI time | |

**User's choice:** Parity asserts gate passes (with Iberia exemption active).

### Q4.4 — Frontend UI mostra erros do gate?

| Option | Description | Selected |
|--------|-------------|----------|
| Backend-only (Phase 06); UI defere (Recommended) | Karpathy: no scope creep | ✓ |
| Inclui troca UI v1→v3 + toast simples | Plan extra + Playwright UAT | |
| Inclui UI rica (modal + dry-run preview) | Escope creep — vira Phase 06.1 | |

**User's choice:** Backend-only. UI swap deferred to Phase 06.1 / 07.
**Notes:** Trade-off explicit: v1 endpoint deletion + UI still calls v1 means Export button temporarily broken until UI swap. User accepted; mitigation is UI swap PR follows Phase 06 immediately.

---

## Claude's Discretion

- Sentinel ocean color in OCEAN_LEAK (render.py vs validator constant)
- MANIFEST sha256 computation point (validator-time vs zip-time)
- Subpackage layout (`services/export/` vs `services/pipeline/export/`)
- Exception type from `validate_export` failure
- MANIFEST schema_version mechanism (constant vs `__version__`)
- Test file split (5 files vs 1 file with TestCase classes)
- Endpoint mount order (same plan vs sequenced)
- Iberia `enforce_original_idx: false` location (YAML flag vs hard-coded)

## Deferred Ideas

- Frontend UI swap to v3 endpoint (Phase 06.1 / 07)
- Frontend rich error UI (modal, dry-run preview, i18n per code)
- Re-bake of Reconquista Iberia gold with `original_idx` (v3.1)
- pixel_center Y-up conversion at export (rejected)
- Cross-field pydantic constraints (v3.1)
- `POST /api/v3/regions/validate` (separate work)
- Configurable per-region `min_territory_px`
- Per-territory-tier thresholds
- MANIFEST schema_version forward-compat migration tooling
- Bidirectional ocean leak (water inside polygon)
- RFC 7807 problem+json (rejected)
- CLI `medieval-forge validate-export` wrapper
- Hashing beyond SHA-256
- Validation report SSE streaming
