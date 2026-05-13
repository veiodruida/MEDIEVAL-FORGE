---
phase: 05
plan: 14
subsystem: cross-cutting
tags: [parity, a11y, pitfall-9, dataclasses-replace, radix-themes, toast]
requirements: [SC-1, SC-2]
requirements_addressed: [SC-1, SC-2]
dependency_graph:
  requires:
    - 05-13 (cross-AI review consolidation — WR-02 + LOW nits surfaced)
    - 05-01 (region_loader + load_region cache contract)
    - 05-08 (NewProjectModal D-07 implementation)
  provides:
    - Pitfall 9-clean Iberia parity fixture (pytest-xdist safe)
    - Accessible NewProjectModal (label↔input pairs via htmlFor/id)
    - Finite Toast duration (no Radix warning)
  affects:
    - backend/tests/parity/test_iberia_868_yaml.py (fixture body refactor)
    - frontend/src/components/projects/NewProjectModal.tsx (4 prop changes)
tech_stack:
  added: []
  patterns:
    - "dataclasses.replace(load_region(key), output_dir=...) uniformly across all parity/e2e fixtures"
    - "Label htmlFor ↔ input id pairing for Radix Themes form controls (accessible name resolution)"
key_files:
  created: []
  modified:
    - backend/tests/parity/test_iberia_868_yaml.py
    - frontend/src/components/projects/NewProjectModal.tsx
decisions:
  - "WR-02 fix uses dataclasses.replace exactly as test_france_1066_export_contract.py:60 already does — uniform pattern across the Phase 05 test surface."
  - "Direct `id` prop chosen on TextField.Root and Select.Trigger (no Box-wrap fallback needed). TextField.Root extends ComponentPropsWithout<'input', ...>; Select.Trigger extends ComponentPropsWithout<typeof SelectPrimitive.Trigger, ...>. Both accept native `id`."
  - "Toast duration set to 1000 * 60 * 60 * 24 (24h) — long enough for any plausible session, finite enough for Radix not to warn."
  - "Vitest suite required no updates: existing tests use placeholder/role-based selectors (`getByPlaceholderText(/Ex\\./)`, `getByRole('button', { name: 'Criar projeto' })`, `getByTestId('region-select')`). None depended on defaultValue or missing htmlFor."
metrics:
  duration_minutes: ~3
  completed_date: "2026-05-13"
  tasks_completed: 2
  files_modified: 2
  tests_added_or_updated: 0
  tests_green:
    backend_parity: "12 passed, 6 xfailed, 4 xpassed (Iberia 868 yaml: 11 pass)"
    frontend_vitest: "226 passed (NewProjectModal: 8 pass)"
    frontend_build: "tsc + vite build clean"
---

# Phase 05 Plan 14: Pitfall 9 Cleanup + NewProjectModal a11y Nits Summary

Closed WR-02 (cross-AI consensus 3/3) by replacing direct `cfg.output_dir = str(out)` singleton mutation in `test_iberia_868_yaml.py` with `dataclasses.replace(load_region("iberia_868"), output_dir=str(out))`, and folded three LOW-severity NewProjectModal review nits (dead `defaultValue`, missing `htmlFor`/`id` label pairs, non-idiomatic `duration={Infinity}` Toast) into a single atomic commit on the same file.

## What changed

### Task 1 — WR-02: replace() in Iberia parity fixture (commit `74cffb7`)

**Diff size:** 1 import added + 1 fixture line edited (plus 6 lines of traceability comment explaining the Pitfall 9 rationale).

**Before** (`backend/tests/parity/test_iberia_868_yaml.py:42-43`):
```python
cfg = load_region("iberia_868")
cfg.output_dir = str(out)   # ← Pitfall 9 / T-05-04-04 violation
```

**After** (lines 43-49):
```python
# WR-02 fix (Plan 05-14): dataclasses.replace() builds a fresh per-call copy.
# Direct cfg.output_dir = ... mutates the cached singleton (Pitfall 9 /
# T-05-04-04) — clear_region_cache_between_tests autouse hides this in
# serial CI, but pytest-xdist parallel workers would corrupt each other's
# output_dir. Match the replace() pattern established in
# test_france_1066_export_contract.py and api/v3/render.py:137-141.
cfg = replace(load_region("iberia_868"), output_dir=str(out))
```

Import added at line 20: `from dataclasses import replace`.

**Verification:**
- `cd backend && pytest tests/parity/test_iberia_868_yaml.py -q` → **11 passed in 34.51s** ✅
- `cd backend && pytest tests/parity -q` → **12 passed, 6 xfailed, 4 xpassed in 125.85s** ✅ (same signature documented in STATE.md)
- `grep -nE "^\s*cfg\.output_dir\s*=" backend/tests/parity/test_iberia_868_yaml.py` → 0 matches (only the comment mentions the old pattern).

### Task 2 — NewProjectModal a11y + Toast duration (commit `3615291`)

**Diff size:** 4 in-place prop edits + 1 comment, all confined to `frontend/src/components/projects/NewProjectModal.tsx`.

**Changes:**

1. **Drop dead `defaultValue`** on `Select.Root` (line 144 before, 144 after — `defaultValue="iberia_868"` line removed). The `useEffect` at lines 42-46 already wires the initial `regionKey` via `defaultRegionKey(regions)`; the controlled `value={regionKey}` covers steady state.

2. **htmlFor ↔ id pair: "Nome do projeto" → TextField.Root**
   - Line 120: `<Text as="label" ... htmlFor="project-name-input">`
   - Line 125: `<TextField.Root id="project-name-input" ...>`

3. **htmlFor ↔ id pair: "Região" → Select.Trigger**
   - Line 141: `<Text as="label" ... htmlFor="region-select-trigger">`
   - Line 151: `<Select.Trigger id="region-select-trigger" data-testid="region-select" ...>`
   - The `data-testid="region-select"` is preserved verbatim — Playwright `getByTestId('region-select')` continues to resolve.

4. **Toast duration finite** (line 212):
   - Before: `<Toast.Root ... duration={Infinity}>`
   - After: `<Toast.Root ... duration={1000 * 60 * 60 * 24}>` with explanatory comment on line 211.

**Approach taken for `id` prop:** Direct prop on both `TextField.Root` and `Select.Trigger`. Confirmed via reading `frontend/node_modules/@radix-ui/themes/dist/cjs/components/text-field.d.ts:12-15` (TextFieldRoot extends `ComponentPropsWithout<'input', ...>` → accepts native `id`) and `select.d.ts:13-15` (SelectTrigger extends `ComponentPropsWithout<typeof SelectPrimitive.Trigger, ...>` → accepts `id` on HTMLButtonElement). No Box-wrap fallback required.

**Vitest update needed?** No. The existing test suite uses:
- `screen.getByPlaceholderText(/Ex\./)` for the name input
- `screen.getByTestId('region-select')` for the region trigger
- `screen.getByRole('button', { name: 'Criar projeto' })` for the submit button

None of these depend on `defaultValue`, `htmlFor`, or `duration` semantics, so all 8 NewProjectModal cases pass unchanged.

**Verification:**
- `cd frontend && npm test -- --run NewProjectModal` → **8 passed in 339ms** ✅
- `cd frontend && npm test -- --run` → **226 passed (36 files) in 7.56s** ✅
- `cd frontend && npm run build` → **tsc + vite build clean, 465 modules transformed in 1.86s** ✅

## Deviations from Plan

None — plan executed exactly as written. Both `id` props landed directly on `TextField.Root` / `Select.Trigger` without any TypeScript fallback. No vitest test required updates (the plan's <action> Step 2 said "ONLY make these changes if the tests fail" — they didn't).

## Acceptance Criteria Status

### Task 1
- [x] `grep -nE "from dataclasses import replace" backend/tests/parity/test_iberia_868_yaml.py` → 1 match (line 20)
- [x] `grep -nE 'replace\(load_region\("iberia_868"\), output_dir=str\(out\)\)' backend/tests/parity/test_iberia_868_yaml.py` → 1 match (line 49)
- [x] `grep -nE "^\s*cfg\.output_dir\s*=" backend/tests/parity/test_iberia_868_yaml.py` → 0 matches (mutation gone)
- [x] `grep -nE "WR-02 fix \(Plan 05-14\)" backend/tests/parity/test_iberia_868_yaml.py` → 1 match (line 43, traceability)
- [x] `pytest tests/parity/test_iberia_868_yaml.py -q` → 11 passed
- [x] `pytest tests/parity -q` → 12 passed / 6 xfailed / 4 xpassed (unchanged signature)

### Task 2
- [x] `grep -nE 'defaultValue="iberia_868"'` → 0 matches
- [x] `grep -nE 'htmlFor="project-name-input"'` → 1 match (line 120)
- [x] `grep -nE 'id="project-name-input"'` → 1 match (line 125)
- [x] `grep -nE 'htmlFor="region-select-trigger"'` → 1 match (line 141)
- [x] `grep -nE 'id="region-select-trigger"'` → 1 match (line 151)
- [x] `grep -nE 'duration=\{Infinity\}'` → 0 matches
- [x] `grep -nE 'duration=\{1000 \* 60 \* 60 \* 24\}'` → 1 match (line 212)
- [x] 3 data-testid attributes preserved (lines 100, 104, 152)
- [x] `npm test -- --run NewProjectModal` → 8 passed
- [x] `npm test -- --run` → 226 passed
- [x] `npm run build` → exit 0, TypeScript clean

## Success Criteria

- [x] **WR-02 closed:** Iberia parity fixture uses `replace()`; pytest-xdist parallel workers would now be safe. Cached singleton (`load_region("iberia_868")`) is never mutated by the fixture.
- [x] **Modal a11y nits closed:** Label↔input pairs are wired; `getByLabel` becomes a viable selector for future Playwright specs without breaking the existing `getByTestId` selectors.
- [x] **Modal lint-clean:** Dead `defaultValue` removed; Toast `duration` is finite (no React DevTools warning).
- [x] **Iberia parity invariant preserved:** All 11 parametrised parity tests still green; full parity suite signature unchanged.
- [x] **Pitfall 9 / `dataclasses.replace()` contract uniformly enforced** across the Phase 05 test surface (parity `test_iberia_868_yaml.py` now matches e2e `test_france_1066_export_contract.py` and the production paths `api/v3/render.py:137-141` and `api/v3/generate.py:138-141`).

## Commits

| Hash      | Type | Scope  | Subject                                                                   |
| --------- | ---- | ------ | ------------------------------------------------------------------------- |
| `74cffb7` | fix  | 05-14  | replace() in iberia 868 yaml parity fixture — close Pitfall 9 (WR-02)     |
| `3615291` | fix  | 05-14  | NewProjectModal a11y + Toast duration (LOW nits from cross-AI review)     |

## Known Stubs

None. No placeholder text, no hardcoded empty data flows, no UI components rendering mock/empty props.

## Self-Check: PASSED

**Files modified verified:**
- ✅ `backend/tests/parity/test_iberia_868_yaml.py` exists, contains `from dataclasses import replace` (line 20) and `replace(load_region("iberia_868"), output_dir=str(out))` (line 49).
- ✅ `frontend/src/components/projects/NewProjectModal.tsx` exists, contains all 4 required edits (no `defaultValue="iberia_868"`, no `duration={Infinity}`, both `htmlFor`/`id` pairs wired, finite `duration={1000 * 60 * 60 * 24}`).

**Commits verified:**
- ✅ `74cffb7` present in `git log` — fix(05-14): replace() in iberia 868 yaml parity fixture
- ✅ `3615291` present in `git log` — fix(05-14): NewProjectModal a11y + Toast duration

**Tests verified (re-run after edits):**
- ✅ `pytest tests/parity/test_iberia_868_yaml.py -q` → 11 passed
- ✅ `pytest tests/parity -q` → 12 passed / 6 xfailed / 4 xpassed
- ✅ `npm test -- --run` → 226 passed (36 files)
- ✅ `npm run build` → TypeScript + vite build clean

No missing artifacts.
