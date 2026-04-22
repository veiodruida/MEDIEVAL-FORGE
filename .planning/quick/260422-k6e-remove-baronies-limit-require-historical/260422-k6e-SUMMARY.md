---
quick_id: 260422-k6e
description: Remove baronies limit + require historical documentation refs + rebuild frontend
date: 2026-04-22
status: complete
commits:
  - 3a48164
---

# Quick Task 260422-k6e — Summary

## Changes

**`backend/medieval_forge/services/llm/prompt.py`:**

- **Rule 9 (BARONY COVERAGE)** — removed the "1-3" upper bound. Prompt now says "1 ou mais; NÃO HÁ LIMITE SUPERIOR" and encourages generating multiple baronies per condado when historical references are abundant.
- **Rule 11 (BARONY HISTORICAL BASIS)** — strengthened to require historical attestation. LLM must only generate baronies that are attested localities, villages, castles, or lordships with documental references (chronicles, cartas régias, fueros, diplomas, foros, tumbos, cartulários). Explicitly forbids generic "Baronia de \<condado\>" placeholders.
- **Rule 12 (BARONY LANGUAGE)** — new rule. Names must be in the regional vernacular of the period (Portuguese, Castilian, Galician, Catalan, Leonese, Asturian), never in English. Examples provided.

## Frontend rebuild

Ran `npm run build` in `frontend/` — regenerated `backend/medieval_forge/static/` bundle so the `Baixar prompt` and `Carregar arquivo` buttons from task i0q now appear in the running app.

`static/` is gitignored (build artifact) — the rebuild is effective locally and will be regenerated during packaging.

## Why this matters

User tested the manual provider with ChatGPT and got only 4 baronies out of ~91 condados, some with fake coordinates (0.0, 0.0), and generic names like "Baronia de Oviedo". The original rules were too permissive. This update forces:

1. **Full coverage** — every condado must have at least 1 barony.
2. **Historical attestation** — no more generic placeholders.
3. **Regional language** — no more anglicized names.

## Verification

- Commit: `3a48164`
- Frontend build: succeeded (452 modules, 1.87s)
