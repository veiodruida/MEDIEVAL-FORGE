# Phase 04: Parameter studio (live re-render) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 04-parameter-studio-live-re-render
**Areas discussed:** DAG + cache topology, Slider UX, Stage output toggles, Cancel + undo

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| DAG + cache topology | SC-1/SC-2 BLOCKER. Stage granularity, version_token derivation, in-memory cache structure, per-project lifetime, endpoint shape | ✓ |
| Slider UX surface | Which 4 sliders, panel slot, debounce vs commit, value display | ✓ |
| Stage output toggles | Visualization vs bypass; which stages; UI slot | ✓ |
| Cancel + undo scope | SC-4 prior-state restore; zundo in/out of scope; per-slider revert | ✓ |

**User's choice:** All four selected (multi-select).

---

## DAG + cache topology

### Granularidade dos stages cacheados?

| Option | Description | Selected |
|--------|-------------|----------|
| Split em 4 (median/fragment/smooth/merge) | Refactor `cleanup_and_smooth` into 4 separately-cacheable functions; 14 cacheable units total. σ slider invalidates only smooth+merge. (Recommended) | ✓ |
| Manter 11 + sub-cache interno | Monolithic `cleanup_and_smooth` keeps internal checkpoints; less refactor but state leaks via API | |
| Cache máximo (todo median pass) | Each of the 8 median passes becomes a cache point; extreme granularity, little benefit | |

**User's choice:** Split em 4 (recommended)

### Derivação do version_token por stage?

| Option | Description | Selected |
|--------|-------------|----------|
| Hash(stage + dependencies declaradas + upstream tokens) | Each stage declares `reads: set[str]`; token = sha256(stage_name + sorted(cfg[reads]) + upstream_tokens). Auto-derives invalidation DAG. (Recommended) | ✓ |
| Counter incremental por stage | Manual bump per affected stage; fragile (forgotten bump = silent stale cache) | |
| Hash de cfg inteiro | Token = hash(full cfg); any change invalidates everything; kills SC-3 | |

**User's choice:** Hash(stage + reads + upstream) (recommended)

### Estrutura + lifetime do cache?

| Option | Description | Selected |
|--------|-------------|----------|
| Dict in-memory por projeto, latest+prior por stage | `_STAGE_CACHE[project_id][stage_name] = {token, array, prior_token, prior_array}`. ~80MB per project, no disk. (Recommended) | ✓ |
| Disk-backed (.npy em project_dir/cache/) | Survives restarts; more I/O; Phase 06 territory | |
| RAM só, latest-only sem prior | Lighter; cancel needs re-run to restore — breaks SC-4 <500ms | |

**User's choice:** Dict in-memory latest+prior (recommended)

### Shape do endpoint incremental?

| Option | Description | Selected |
|--------|-------------|----------|
| Single POST /v3/projects/{id}/render + SSE pair | Body `{cfg_overrides}`; backend diffs cfg, computes affected stages via DAG, streams SSE. Reuses _make_on_stage + _RUN_QUEUES. (Recommended) | ✓ |
| Múltiplos endpoints por stage | POST /render/cleanup, /render/smooth, etc.; client knows DAG | |
| Reusar /generate com from_stage param | Mixes full and incremental in one endpoint; ambiguous status | |

**User's choice:** Single POST /render + SSE pair (recommended)

### Continue or move on?

**User's choice:** "Esqueci de comentar anteriormente mas se for selecionado nas camadas baronies, deve aparecer o nome das baronies tbm. Dito isto proxima area" — captured as a side-note polish item (later folded into Stage toggles area as D-12). User chose to advance to next area.

---

## Slider UX

### Quais sliders entram no painel?

| Option | Description | Selected |
|--------|-------------|----------|
| Só os 4 do ROADMAP | smooth_sigma (3.0–4.5), median_passes (1–12), fragment_min_px (0–2000), blob_merge_px (0–500). (Recommended) | ✓ |
| 4 + island_min_px | Adds island_min_px (0–800); +1 dependency edge | |
| 4 + island + mountain_threshold + mountain_noise | 6 sliders total; UI overload risk | |

**User's choice:** Só os 4 do ROADMAP (recommended)

### Onde vive o painel de sliders?

| Option | Description | Selected |
|--------|-------------|----------|
| Sidebar esquerda colapsável (~320px) | Mirrors InspectorSidebar (right). Standard Figma layout. (Recommended) | ✓ |
| Expansão do WorkspaceToolbar | Toolbar grows with sliders; compromises canvas vertical space | |
| Floating overlay (canto) | Floating card; obstructs canvas | |

**User's choice:** Sidebar esquerda colapsável (recommended)

### Trigger de re-render quando usuário mexe slider?

| Option | Description | Selected |
|--------|-------------|----------|
| Debounce 250ms latest-wins, auto re-render | Slider drag fires debounce; new POST /render. In-flight cancelled by next change. (Recommended) | ✓ |
| Commit-on-release (no debounce) | Re-render on slider release only; less alive | |
| Botão Apply manual | Manual apply button; loses parameter-studio spirit | |

**User's choice:** Debounce 250ms latest-wins (recommended)

### Como exibir valor + range + default?

| Option | Description | Selected |
|--------|-------------|----------|
| Slider + numeric input + tick default | Slider with bounds visible; numeric input alongside; default-tick mark; reset button. (Recommended) | ✓ |
| Só slider com label numérico | No editable input; harder to set exact int values | |
| Numeric input só, sem slider | No fluid affordance; rejected | |

**User's choice:** Slider + numeric input + tick default (recommended)

---

## Stage output toggles

### Semântica do "toggle per-stage output"?

| Option | Description | Selected |
|--------|-------------|----------|
| Visualização intermediária (canvas mostra estado X) | Toggle re-routes canvas hydrator to a different cached array. Pipeline always runs full. Debug-friendly. (Recommended) | ✓ |
| Bypass-stage (skip stage no pipeline) | Toggle disables a stage; risk of producing invalid arrays | |
| Ambos | Visualization + bypass; doubles UI surface | |

**User's choice:** Visualização intermediária (recommended)

### Quais stages podem ser visualizados via toggle?

| Option | Description | Selected |
|--------|-------------|----------|
| 5 chave: landmask, voronoi-raw, cleanup, smooth, render-final | Inflection points worth seeing. Fragment/merge/hierarchy don't offer relevant visual diff. (Recommended) | ✓ |
| Todos os 14 stages cacháveis | Maximum granularity; UI overload | |
| Só final + 1 "raw" antes-de-cleanup | Minimal; loses useful gradients | |

**User's choice:** 5 chave (recommended)

### Onde vive o seletor de stage view?

| Option | Description | Selected |
|--------|-------------|----------|
| No painel de sliders (esquerda) | Sliders + stage toggles share "pipeline parameters" context. (Recommended) | ✓ |
| No LayerTogglePanel existente | Mixes layer (visual) and stage (algorithmic) semantics | |
| Toolbar superior | Dropdown on toolbar; far from sliders that cause changes | |

**User's choice:** No painel de sliders (recommended)

### Side note: barony names quando layer Baronies ligado

| Option | Description | Selected |
|--------|-------------|----------|
| Polish menor dentro de Phase 04 | Adds barony-name labels via Konva Text; small task fits Phase 04. (Recommended) | ✓ |
| Quick task separado fora de Phase 04 | Open /gsd-quick before Phase 04 plan | |
| Backlog v3.1 | Defer | |

**User's choice:** Polish menor dentro de Phase 04 (recommended)

---

## Cancel + undo

### SC-4 "cancel restores prior state" — o que exatamente restaura?

| Option | Description | Selected |
|--------|-------------|----------|
| Swap O(1) pro prior_token do cache | Cancel pulls prior_token from D-03 cache; canvas swaps instantly; slider rolls back to prior value. <50ms. (Recommended) | ✓ |
| Re-run com cfg anterior | Save prior cfg, kill in-flight, POST new /render with prior cfg; ~500ms | |
| Stop sem rollback | Stop only; canvas may be partial/inconsistent. Doesn't satisfy SC-4 | |

**User's choice:** Swap O(1) (recommended)

### Mecânica do cancel mid-render?

| Option | Description | Selected |
|--------|-------------|----------|
| stop_event polled por stage; checkpoint entre stages | Cooperative; each stage checks cfg.stop_event at top. Worst-case latency = current stage duration. Uses _RUN_TASKS slot reserved P03 D-04. (Recommended) | ✓ |
| Kill task imediato (asyncio.Task.cancel) | Doesn't propagate into CPU-bound thread; same effective latency without cooperativity | |
| Esperar stage done, então parar | Queued cancel; may run to end if cancelled at last stage | |

**User's choice:** stop_event polled por stage (recommended)

### Undo composto via zundo temporal — in-scope Phase 04 ou deferido?

| Option | Description | Selected |
|--------|-------------|----------|
| Deferido + cancel+reset-slider apenas | PROJECT.md Out of Scope defers compound undo; CLAUDE.md only fixes zundo as contract IF undo lands. Phase 04 ships cancel + per-slider reset only. (Recommended) | ✓ |
| Full zundo temporal in Phase 04 | Wires zundo middleware; Cmd+Z/Cmd+Shift+Z; contradicts PROJECT.md | |
| Per-slider single-step undo (último valor) | Each slider remembers last value; minimal beyond cancel | |

**User's choice:** Deferido (recommended)

### Onde vive o botão Cancel quando render in-flight?

| Option | Description | Selected |
|--------|-------------|----------|
| Status badge da toolbar vira "Cancel" durante render | WorkspaceToolbar status badge becomes clickable Cancel button. Reuses Phase 03 shell. (Recommended) | ✓ |
| Botão cancel no header do painel de sliders | Adjacent to sliders; more discoverable contextually | |
| Floating cancel sobre canvas | Floating card; obstructs viewing area | |

**User's choice:** Status badge vira Cancel (recommended)

---

## Wrap-up

**User's choice:** "Pronto pra criar CONTEXT" — proceed to write_context.

## Claude's Discretion

- Slider value persistence across sessions (DB column vs localStorage vs ephemeral)
- Cache eviction policy beyond latest+prior
- Stage-view → endpoint shape for non-final rasters (PNG colormap vs raw npy)
- POST /render/cancel vs DELETE /render
- Stage-view ↔ LayerTogglePanel interaction (intermediate views vs decoration layers)
- Failure mode mid-render (stage_error envelope + swap to prior)
- Konva.clearCache() invocation site (per-layer hook vs centralized)
- useRunStore extension vs sibling useRenderStore
- stage_view cfg field placement (RegionConfig vs client-only)
- Barony name label rendering primitive (Konva Text vs DOM overlay)
- Border/hierarchy stage cacheability hints

## Deferred Ideas

- zundo temporal compound undo across slider history
- Disk-backed stage cache survival across restarts
- Sliders for island_min_px / mountain_threshold / mountain_noise / coast_inner_width
- Region YAML loader (Phase 05)
- Schema validation on incremental renders (Phase 06)
- LLM-assisted parameter recommendation (Phase 07)
- Per-project slider value persistence
- LRU eviction policy
- Stage-view radio for border/hierarchy/lookup/metadata/export
- Bypass-stage capability
- Hard-kill cancel via asyncio.Task.cancel
- Concurrent /render coalescing strategy beyond debounce
- Compound-undo toolbar button
