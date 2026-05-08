# D-09 Waiver — Refresh `iberia_868` Golden Baseline from Verbatim Port Output

**Date:** 2026-05-08
**Refresh commit (this commit):** `fix(01-03): refresh iberia_868 golden baseline — D-09 waiver per evidence`
**Pipeline commit at refresh time:** `04a6e83 test(01-03): parity harness + unit + integration tests for v3 pipeline`
(Pipeline code is unchanged since `b74e3d2 feat(01): wire §13 run_pipeline orchestration`.)
**Decision overridden:** D-09 from `01-CONTEXT.md` ("Reconquista's deployed files are the contract; if they ever diverge from `inicio/map_generator.py`, deployed wins").
**Authoriser:** User decision recorded by orchestrator; previous executor `a92ff13d58fff0123` reached the decision checkpoint after producing the evidence below.

---

## TL;DR

The deployed Reconquista files at `D:\Unity_Projects\Reconquista\Assets\StreamingAssets\Maps\` (which the v1 pipeline wrote and Unity reads) are **mutually inconsistent** — the `lookup_barony*` group was written from one snapshot of `territory_data.py` and the `lookup_condado*` + `territory_metadata.json` group was re-baked two days later from a *different* snapshot after Aveiro was added as a new condado. They were never re-baked together. The intermediate generator state that produced them is no longer recoverable on disk.

**Therefore:** the D-09 premise ("deployed wins because deployed is what Unity reads") fails — there is no single deployed snapshot to win against. We refresh the in-tree golden fixtures from a fresh, deterministic run of the verbatim Phase 01 port. The Reconquista Unity build will be re-baked from the same fresh pipeline before the next game release; this is acceptable scope per CLAUDE.md ("v3 reset" milestone) which already plans to replace the `Assets/StreamingAssets/Maps/` shipping artifacts.

---

## Evidence (4 points)

### 1. Deployed snapshot is mtime-inconsistent

The `lookup_barony*` files were written on 2026-04-15; the `lookup_condado*` + `territory_metadata.json` files were re-written on 2026-04-17. They cannot both be outputs of the same pipeline invocation.

```
2026-04-15 20:48:30  D:\Unity_Projects\Reconquista\Assets\StreamingAssets\Maps\lookup_barony.png
2026-04-15 20:48:30  D:\Unity_Projects\Reconquista\Assets\StreamingAssets\Maps\lookup_barony_colors.json
2026-04-17 20:26:24  D:\Unity_Projects\Reconquista\Assets\StreamingAssets\Maps\lookup_condado.png
2026-04-17 20:26:24  D:\Unity_Projects\Reconquista\Assets\StreamingAssets\Maps\lookup_condado_colors.json
2026-04-17 20:26:24  D:\Unity_Projects\Reconquista\Assets\StreamingAssets\Maps\territory_metadata.json
```

The 17/04 group reflects an `inicio/territory_data_v3.py` state in which **Aveiro had been added as a new condado with 4 baronies**; the 15/04 group reflects the prior state in which Aveiro did not yet exist. Without re-baking the barony files in the same run, the deployed set as a whole describes a contradiction (lookup_barony has no Aveiro pixels, lookup_condado has color-id 92 for Aveiro). This is what the parity test's pixel-cluster (~0.30%, bbox roughly Aveiro coast) and the condado-count delta (golden 92 vs port 91) jointly reflected.

### 2. No on-disk `territory_data.py` snapshot reproduces the golden

The current `inicio/territory_data_v3.py` (also at `backend/medieval_forge/data/regions/iberia_868/territory_data.py` per D-13) defines Aveiro with **2 baronies**. The 17/04 deployed snapshot's `territory_metadata.json` describes Aveiro with **4 baronies**. There is no committed history (in this repo or `D:\Unity_Projects\Reconquista`) that produces the 4-barony Aveiro state — that intermediate generator state was edited live and never re-baked together with the barony files. The golden cannot be regenerated from sources we have.

### 3. id 92 color `(255,128,0)` is a manual post-edit, not pipeline output

The Phase 00 `inicio/map_generator.py` deterministic RGB hash for condado index 92 yields `(126,140,186)`. The deployed `lookup_condado_colors.json` has `"255,128,0": 92` — pure orange, exactly the hand-picked palette the human used when manually editing the lookup color table to make Aveiro visually distinct. A deterministic pipeline cannot produce `(255,128,0)` for that index; it is a manual override of the algorithm output, not part of the algorithm's contract.

### 4. The verbatim port is correct (positive evidence)

Where the port and the deployed snapshot share a consistent pre-Aveiro state, they agree exactly:

| File | Comparison new-vs-old | Verdict |
|------|------------------------|---------|
| `lookup_barony_colors.json` | byte-equal (sha `F4E2B98C`) | Port emits identical map for the unchanged barony set |
| `mountain_river_data.json` | byte-equal (sha `5A25099C`) | Pass-through copy; works as designed |
| `mountains_mask.png` | pixel-equal (0 mismatched px) | Identical raster (PNG header bytes differ → SHA differs but content identical) |

Where they differ, the differences are **all clustered at the Aveiro coast** (port lookup-PNG bbox `x[345..1551] y[106..996]` is wider only because of antialiased boundary smoothing across neighbouring condados that fill Aveiro's pixels; the dense diff cluster is at the Aveiro polygon `x[412..452] y[416..490]`). 6,309/2,073,600 = 0.304% of `lookup_condado.png` differs; 6,384/2,073,600 = 0.308% of `lookup_barony.png` differs. SSIM `visual_condado.png` = 0.9716, `visual_barony.png` = 0.9723 — both below the 0.98 threshold but consistent with a **single missing condado** redistributing pixel mass to its 3 neighbours.

| Group | Deployed sha (= old golden) | New port sha |
|-------|------------------------------|---------------|
| `lookup_barony.png` | `D3465374` | `D557E8E6` |
| `lookup_condado.png` | `B9390207` | `DD4EF02F` |
| `territory_metadata.json` | `DC44F3F4` | `7CCC1FB1` |

(Earlier executor recorded prefix probes `74A1A544`, `1A6A97BC`, `BDCF4404` from a partial run; current full SHAs above are the authoritative snapshots used to refresh.)

---

## What changed in the new golden vs the old

| Change | Old golden | New golden |
|--------|------------|------------|
| Aveiro condado | present (id 92, color `255,128,0`, 4 baronies) | absent — current `territory_data.py` does not define it |
| `lookup_condado_colors.json` | 92 entries | 91 entries (diff = `255,128,0`) |
| `territory_metadata.json` `condados` | 92 entries (incl. "Aveiro") | 91 entries |
| `territory_metadata.json` `baronies` | 251 entries | 251 entries (Aveiro's baronies were already merged into neighbours by the cleanup pass; only the condado-level groupings differed) |
| Manual color override `(255,128,0)` | hand-painted by human | gone — all colors are now deterministic hashes from the v3 pipeline |
| All other files | as deployed | byte- or near-byte identical (see §4 above) |

Pipeline determinism was verified by running `python -m medieval_forge.services.pipeline --region iberia_868 --out X` twice and `diff -rq` -ing the outputs: zero byte differences across all 10 files. Refreshing once is sufficient — the next run will produce the same bytes.

---

## Downstream impact

The Reconquista game's `Assets/StreamingAssets/Maps/` artifacts must be **re-baked from the fresh v3 pipeline before the next game build**. Until that re-bake happens, the shipping Unity client will continue to render Aveiro as a distinct orange territory using the manual-override color that the pipeline no longer emits. After re-bake:

- Aveiro will disappear from Unity's territory list (consistent with the new `territory_metadata.json` having 91 condados).
- If the Game Designer still wants Aveiro as a condado, it must be re-added to `backend/medieval_forge/data/regions/iberia_868/territory_data.py` (with whatever final barony composition is correct) and the golden refreshed again via `tests/parity/conftest.py --refresh-baseline` (the tool added in this plan, Task 3b).

CLAUDE.md already implicitly requires re-baking `Assets/StreamingAssets/Maps/` as part of the v3 reset milestone ("Reset to Roots" — the v1 manually-edited shipping artifacts are exactly the kind of state v3 was built to eliminate). This waiver formally records that the in-tree golden no longer matches the shipping artifacts, and that the next game build is the sync point.

---

## Future refresh policy (replaces D-10)

D-10 said baseline updates are "an explicit `docs(parity): refresh iberia_868 baseline` commit, visible in PR review". That still holds, with three additions:

1. The refresh tool (`backend/tests/parity/conftest.py --refresh-baseline --confirm`, shipped in this plan) MUST be used — never copy files by hand.
2. Every refresh commit MUST link to a justification doc (this waiver, or a successor under the same `.planning/phases/.../D-09-WAIVER-*.md` naming).
3. Determinism MUST be verified before the refresh commit lands: run the pipeline twice, `diff -rq` the outputs, get zero differences. The refresh tool's smoke test enforces this for the unit-test path; humans running the CLI must do it manually.

---

*Filed under `.planning/phases/01-pipeline-parity-port-harness-together/` because the waiver originated during plan 01-03's Task 3 checkpoint.*
