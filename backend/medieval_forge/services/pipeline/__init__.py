"""v3 deterministic pipeline — verbatim port of inicio/map_generator.py.

Wave 1 (Plan 02) wires `run_pipeline` to call landmask -> border -> voronoi ->
cleanup -> render -> lookup -> export in the order from inicio §13
(`generate_maps`, lines 798-944).

Three signature substitutions from inicio per CONTEXT.md:
  - generate_maps -> run_pipeline (D-03)
  - territory_module=... arg dropped (D-13: cfg.kingdoms/duchies/condados)
  - draw_names=... arg dropped (D-03: cfg.draw_names; default False per Q10)

The hardcoded RNG seed at inicio:537 + 904 is replaced with
`np.random.default_rng(cfg.rng_seed)` inside render.py (Task 7); this orchestrator
itself performs the same substitution at line ~144 below for the mountain-noise
overlay (porting inicio:904 verbatim with the cfg.rng_seed swap).

Output filenames follow the 12-file Unity contract (CLAUDE.md). The 12 files
produced for every region:

    lookup_barony.png, lookup_condado.png,
    lookup_barony_colors.json, lookup_condado_colors.json,
    terrain_lookup.png, terrain_types.json,
    territory_metadata.json,
    visual_condado.png, visual_barony.png,
    mountains_mask.png, rivers_overlay.png,
    mountain_river_data.json

Phase 04 additions:
  - run_pipeline gains optional project_id param to populate _STAGE_CACHE
    (D-13: prior arrays available for /render cancel revert)
  - _write_outputs_to_disk extracted as shared helper (D-17: both paths use it)
  - run_pipeline_incremental: DAG-walking variant (Plan 04-02 Task 2)
  - _VORONOI_CACHE: side-table for non-array voronoi intermediates
    (bars, bpx, bc, bd, bk, nb, nc, land_2x — these are not numpy arrays
    and cannot live in StageEntry.array; cached separately per project)
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Optional

import numpy as np
from PIL import Image

from .contracts import RegionConfig
from .landmask import load_municipalities, build_land_mask
from .border import build_border_mask
from .voronoi import setup_baronies, rasterize_baronies, build_hierarchy_maps
from .cleanup import (
    apply_median, remove_fragments, smooth_per_territory, merge_small_blobs,
)
from .render import render_map, render_mountains, render_rivers
from .lookup import generate_lookup_map
from .export import export_metadata
from .terrain import render_terrain_lookup, build_terrain_types_json
from .cache import _VORONOI_CACHE, cache_get, cache_put  # noqa: F401


def _emit(cfg: RegionConfig, stage: str, evt: str) -> None:
    """Fire-and-forget pipeline-stage callback (Plan 03-01).

    Invokes `cfg.on_stage(stage, evt)` if a callback is registered. Default
    `cfg.on_stage = None` preserves Phase 01 parity exactly — this is a
    no-op in that case. Exceptions raised by the callback propagate; the
    SSE producer in Plan 02 wraps and reports them.
    """
    if cfg.on_stage is not None:
        cfg.on_stage(stage, evt)


def _write_outputs_to_disk(
    cfg: RegionConfig,
    result: np.ndarray,
    land: np.ndarray,
    land_2x: np.ndarray,
    pc: np.ndarray,
    pd: np.ndarray,
    pk: np.ndarray,
    bc: np.ndarray,
    bd: np.ndarray,
    bk: np.ndarray,
    nb: int,
    nc: int,
    bars: list,
    condados: list,
    duchies: dict,
    kingdoms: dict,
    *,
    affected: Optional[list] = None,
) -> dict[str, dict]:
    """Write the 10 Unity contract files + canvas sidecars to cfg.output_dir.

    Verbatim extraction of the file-write block from run_pipeline (inicio §13,
    lines 145-258 of this module). Called from BOTH run_pipeline and
    run_pipeline_incremental so D-17 byte-equal is guaranteed by construction.

    Option A (selective writes): when `affected` is provided (non-None), each
    write block is gated on whether its upstream stages appear in `affected`.
    Empty `affected` list → no writes (warm no-change baseline ~0s I/O).
    When `affected` is None (full generate path), all blocks always run.

    Stop-event interleaving: each gate checks cfg.stop_event between blocks to
    give SC-4 cancel a sub-second exit from a long write sequence.

    Stage → write-block membership:
      - 'render' block (visual PNGs): triggered by any of smooth/merge/hierarchy
      - 'lookup' block (lookup PNGs + JSON): same as render
      - 'metadata' block (territory_metadata.json): same as render
      - 'export' block (mountains, rivers, sidecars): mountains+rivers only if
        landmask or voronoi recomputed; canvas sidecars if hierarchy recomputed

    Returns cmaps dict (needed by canvas sidecars caller; {} when fully skipped).
    """
    # ---------------------------------------------------------------------------
    # Helper: should we run this block?
    # ---------------------------------------------------------------------------
    def _needs_write(stages: list[str]) -> bool:
        """True when any of `stages` appears in `affected` (or affected=None → always)."""
        if affected is None:
            return True
        return any(s in affected for s in stages)

    def _check_cancel() -> None:
        """Raise StageCancelled (a pseudo-cancel) if stop_event is set mid-write."""
        if cfg.stop_event is not None and cfg.stop_event.is_set():
            from .cleanup import StageCancelled
            raise StageCancelled("write")

    W2, H2 = cfg.map_w * cfg.upscale, cfg.map_h * cfg.upscale
    os.makedirs(cfg.output_dir, exist_ok=True)

    cmaps: dict[str, dict] = {}  # captured for canvas sidecars (Plan 03-01)

    # Stages that, when dirty, require the render/lookup/metadata blocks to re-run.
    # σ change → smooth+merge+hierarchy dirty → render block runs.
    _RENDER_TRIGGERS = ["smooth", "merge", "hierarchy"]
    # Mountains/rivers only change if the land mask or voronoi changed.
    _MASK_TRIGGERS = ["landmask", "voronoi"]

    # 9. Render visual maps (D-03: draw_names from cfg.draw_names inside render_map)
    if _needs_write(_RENDER_TRIGGERS):
        _check_cancel()
        _emit(cfg, "render", "start")
        print("[10] Rendering visual maps...")
        for mt in ["condado", "barony"]:
            print(f"     {mt}...")
            img = render_map(result, pc, pd, pk, bc, bd, bk, nb, nc,
                            condados, duchies, kingdoms, land, cfg,
                            map_type=mt, land_2x=land_2x)
            Image.fromarray(img).save(f"{cfg.output_dir}/visual_{mt}.png")
        _emit(cfg, "render", "done")
    else:
        print("[10] Skipping visual maps (not dirty)")

    # 10. Lookup maps
    if _needs_write(_RENDER_TRIGGERS):
        _check_cancel()
        _emit(cfg, "lookup", "start")
        print("[11] Generating lookup maps...")
        for label, level_map, n_items in [("barony", result, nb), ("condado", pc, nc)]:
            lk, cmap = generate_lookup_map(result, level_map, n_items, cfg, label)
            cmaps[label] = cmap
            Image.fromarray(lk).save(f"{cfg.output_dir}/lookup_{label}.png")
            with open(f"{cfg.output_dir}/lookup_{label}_colors.json", 'w') as f:
                json.dump(cmap, f, indent=2)
        # 11b. Terrain lookup + types — Phase 05 Plan 11 (SC-3 closure).
        # CLAUDE.md §"v3 Pipeline Contract" rows 5 + 6: 1920×1080 RGB PNG +
        # RGB→{name, movement, defense, attack} JSON. Single-terrain palette
        # ("plains" everywhere on land, "ocean" sentinel for water) ships the
        # full 12-file contract without DEM ingestion. Phase 06's validation
        # gate will extend the palette if/when DEM lands.
        terrain_arr = render_terrain_lookup(land, cfg)
        Image.fromarray(terrain_arr, "RGB").save(f"{cfg.output_dir}/terrain_lookup.png")
        with open(f"{cfg.output_dir}/terrain_types.json", 'w', encoding='utf-8') as f:
            json.dump(build_terrain_types_json(cfg), f, indent=2)
        _emit(cfg, "lookup", "done")
    else:
        print("[11] Skipping lookup maps (not dirty)")

    # 11. Metadata
    if _needs_write(_RENDER_TRIGGERS):
        _check_cancel()
        _emit(cfg, "metadata", "start")
        print("[12] Exporting metadata...")
        metadata = export_metadata(condados, duchies, kingdoms, bars, result, pc, cfg)
        with open(f"{cfg.output_dir}/territory_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        _emit(cfg, "metadata", "done")
    else:
        print("[12] Skipping metadata (not dirty)")

    # 12. Mountains (rule #6 + P-4: independent 2x render — pass land_2x in)
    # Mountains/rivers only need re-rendering if the land mask or voronoi changed.
    _emit(cfg, "export", "start")
    if _needs_write(_MASK_TRIGGERS):
        _check_cancel()
        print("[13] Mountains...")
        mtn_mask = render_mountains(cfg, land_2x)
        if mtn_mask is not None:
            # Save as white-on-black mask (white = impassable)
            mtn_img = np.zeros((H2, W2), dtype=np.uint8)
            mtn_img[mtn_mask] = 255
            Image.fromarray(mtn_img).save(f"{cfg.output_dir}/mountains_mask.png")
            print(f"    Mountain pixels: {np.sum(mtn_mask):,}")

            # Also apply mountains to visual maps (P-9 + rule #7: cfg.rng_seed)
            # Only valid when render block already ran (both triggered by _RENDER_TRIGGERS);
            # if render skipped but mask recomputed (shouldn't happen in practice —
            # mask triggers ⊆ render triggers when upstream changes propagate), skip.
            if _needs_write(_RENDER_TRIGGERS):
                for mt in ["condado", "barony"]:
                    vis = np.array(Image.open(f"{cfg.output_dir}/visual_{mt}.png"))
                    mc = cfg.mountain_color_visual
                    noise = np.random.default_rng(cfg.rng_seed).integers(
                        -cfg.mountain_noise, cfg.mountain_noise, (H2, W2))
                    for ch in range(3):
                        vis[:,:,ch][mtn_mask] = np.clip(
                            mc[ch] + noise[mtn_mask], 30, 220).astype(np.uint8)
                    Image.fromarray(vis).save(f"{cfg.output_dir}/visual_{mt}.png")

        # 13. Rivers
        _check_cancel()
        print("[14] Rivers...")
        rivers_img = render_rivers(cfg)
        if rivers_img is not None:
            rivers_img.save(f"{cfg.output_dir}/rivers_overlay.png")

            # Also composite rivers on visual maps (only if render block ran)
            if _needs_write(_RENDER_TRIGGERS):
                for mt in ["condado", "barony"]:
                    vis = Image.open(f"{cfg.output_dir}/visual_{mt}.png").convert("RGBA")
                    vis.paste(rivers_img, (0, 0), rivers_img)
                    vis.convert("RGB").save(f"{cfg.output_dir}/visual_{mt}.png")

        # 14. Copy mountain_river_data.json into output (10th contract file).
        mr_path = cfg.dataset.mountain_river_json if cfg.dataset is not None else None
        if mr_path and os.path.exists(mr_path):
            shutil.copy2(mr_path,
                         os.path.join(cfg.output_dir, "mountain_river_data.json"))
    else:
        print("[13] Skipping mountains/rivers (not dirty)")

    # 15. Canvas sidecars (Plan 03-01 BLOCKER fix — Pitfall 10).
    # Emit-only, parity-safe: the 10-file Unity contract is unaffected; these
    # four files (territories.geojson + baronies.geojson + condado_colors.json
    # + barony_colors.json) feed the Phase 03 read-only canvas hydrator.
    if _needs_write(_RENDER_TRIGGERS):
        _check_cancel()
        print("[15] Emitting canvas sidecars...")
        from ..canvas_sidecars import (
            build_baronies_geojson_sidecar,
            build_territories_geojson_sidecar,
        )
        # cmaps must have been populated by the lookup block above
        if cmaps:
            build_territories_geojson_sidecar(
                pc=pc,
                condados=condados,
                duchies=duchies,
                cfg=cfg,
                condado_cmap=cmaps["condado"],
                out_dir=cfg.output_dir,
            )
            build_baronies_geojson_sidecar(
                result=result,
                bars=bars,
                cfg=cfg,
                barony_cmap=cmaps["barony"],
                out_dir=cfg.output_dir,
            )
    else:
        print("[15] Skipping canvas sidecars (not dirty)")
    _emit(cfg, "export", "done")

    return cmaps


def run_pipeline(cfg: RegionConfig, project_id: Optional[str] = None) -> None:
    """Main pipeline: generates all map files for Unity.

    Verbatim port of inicio/map_generator.py:798-934 (`generate_maps`) with
    these substitutions per CONTEXT.md:
      - renamed to run_pipeline (D-03)
      - territory_module argument dropped (D-13: cfg.kingdoms/duchies/condados)
      - draw_names argument dropped (D-03: cfg.draw_names)
      - hardcoded RNG seed replaced inside render.py (P-9 + rule #7)

    Phase 04: optional project_id parameter — if given, each stage result is
    written to _STAGE_CACHE via cache_put so that the FIRST /render after a
    /generate has prior arrays to swap back to on cancel (D-13).
    """
    if cfg is None:
        cfg = RegionConfig()

    os.makedirs(cfg.output_dir, exist_ok=True)

    print(f"{'='*60}")
    print(f"MAP GENERATOR — {cfg.name.upper()}")
    print(f"{'='*60}")

    # Phase 04: import cache helpers only when project_id is given (preserves
    # Phase 01 CLI parity — no cache machinery imported when project_id=None).
    if project_id is not None:
        from .cache import cache_put
        from .dag import compute_version_token, STAGE_READS, DAG_PARENTS
        tokens: dict[str, str] = {}

        def _token(stage: str) -> str:
            upstream = [tokens[p] for p in DAG_PARENTS[stage]]
            tok = compute_version_token(stage, STAGE_READS[stage], cfg, upstream)
            tokens[stage] = tok
            return tok

        def _cache_put(stage: str, array: np.ndarray) -> None:
            cache_put(project_id, stage, tokens[stage], array)
    else:
        def _token(stage: str) -> str:  # type: ignore[misc]
            return ""

        def _cache_put(stage: str, array: np.ndarray) -> None:  # type: ignore[misc]
            pass

    # 1. Load territory data — D-13: lives directly on cfg.
    print("[1] Loading territory data...")
    kingdoms = cfg.kingdoms
    duchies = cfg.duchies
    condados = cfg.condados
    nc = len(condados)

    print("[2] Loading municipalities...")
    pt_data, es_municipalities = load_municipalities(cfg)

    # 2. Build land mask at 1x
    _emit(cfg, "landmask", "start")
    print("[3] Building land mask (1x)...")
    _token("landmask")
    land = build_land_mask(pt_data, es_municipalities, cfg)
    _cache_put("landmask", land)
    print(f"    Land: {np.sum(land):,} px")

    # 3. Build land mask at 2x (for post-upscale masking — rule #6 + P-4)
    print("[4] Building land mask (2x)...")
    W2, H2 = cfg.map_w * cfg.upscale, cfg.map_h * cfg.upscale
    land_2x = build_land_mask(pt_data, es_municipalities, cfg, W2, H2)
    print(f"    Land 2x: {np.sum(land_2x):,} px")
    _emit(cfg, "landmask", "done")

    # 4. Border mask
    _emit(cfg, "border", "start")
    print("[5] Building border mask...")
    _token("border")
    border_mask = build_border_mask(cfg)
    _cache_put("border", border_mask)
    _emit(cfg, "border", "done")

    # 5. Setup baronies (D-14: cfg now carries condados/duchies/kingdoms)
    _emit(cfg, "voronoi", "start")
    print("[6] Setting up baronies...")
    bars, bpx, bc, bd, bk, pi, ei, tp, te = setup_baronies(cfg)
    nb = len(bars)

    # 6. Rasterize
    print("[7] Rasterizing baronies...")
    _token("voronoi")
    raw = rasterize_baronies(pt_data, es_municipalities, bars,
                             pi, ei, tp, te, land, border_mask, cfg)
    _cache_put("voronoi", raw)
    _emit(cfg, "voronoi", "done")

    # Populate voronoi side-table for /render incremental reuse (D-13)
    if project_id is not None:
        _VORONOI_CACHE[project_id] = {
            "bars": bars, "bpx": bpx, "bc": bc, "bd": bd, "bk": bk,
            "nb": nb, "nc": nc, "land_2x": land_2x,
            "pt_data": pt_data, "es_municipalities": es_municipalities,
        }

    # 7. Cleanup & smooth — 4 separately cacheable stages (Plan 04-01 D-01).
    # Each split function emits a real start/done pair; PIPELINE_STAGES on the
    # frontend has 12 entries to match (research finding #7).
    _emit(cfg, "median", "start")
    print("[8a] Median filter passes...")
    _token("median")
    med = apply_median(raw, land, nb, cfg)
    _cache_put("median", med)
    _emit(cfg, "median", "done")

    _emit(cfg, "fragment", "start")
    print("[8b] Fragment removal...")
    _token("fragment")
    frag = remove_fragments(med, land, nb, cfg)
    _cache_put("fragment", frag)
    _emit(cfg, "fragment", "done")

    _emit(cfg, "smooth", "start")
    print("[8c] Per-territory Gaussian smoothing...")
    _token("smooth")
    sm = smooth_per_territory(frag, land, cfg)
    _cache_put("smooth", sm)
    _emit(cfg, "smooth", "done")

    _emit(cfg, "merge", "start")
    print("[8d] Merging small blobs...")
    _token("merge")
    result = merge_small_blobs(sm, land, nb, cfg)
    _cache_put("merge", result)
    _emit(cfg, "merge", "done")

    # 8. Hierarchy
    _emit(cfg, "hierarchy", "start")
    print("[9] Building hierarchy...")
    _token("hierarchy")
    pc, pd, pk = build_hierarchy_maps(result, bc, bd, bk, nb)
    land = result >= 0  # update land to match result (verbatim inicio:860)
    _cache_put("hierarchy", pc)  # cache the condado map (primary output)
    _emit(cfg, "hierarchy", "done")

    na = sum(1 for i in range(nb) if np.sum(result == i) > 0)
    nc_active = sum(1 for i in range(nc) if np.sum(pc == i) > 0)
    print(f"    Active: {na} baronies, {nc_active} condados")

    # Steps 9-15: write all output files to disk (extracted to shared helper
    # so run_pipeline_incremental uses identical code — D-17 byte-equal).
    _write_outputs_to_disk(
        cfg=cfg,
        result=result,
        land=land,
        land_2x=land_2x,
        pc=pc,
        pd=pd,
        pk=pk,
        bc=bc,
        bd=bd,
        bk=bk,
        nb=nb,
        nc=nc,
        bars=bars,
        condados=condados,
        duchies=duchies,
        kingdoms=kingdoms,
    )

    print(f"\n{'='*60}")
    print(f"DONE — {na} baronies, {nc_active} condados")
    print(f"Output: {cfg.output_dir}/")
    print(f"{'='*60}")


def run_pipeline_incremental(cfg: RegionConfig, project_id: str) -> list[str]:
    """DAG-walking variant of run_pipeline (Plan 04-02 Task 2).

    Algorithm:
      1. Walk DAG_ORDER. For each stage, compute new_token.
      2. If new_token != cached token (or no cache entry): recompute, cache_put.
      3. Skip stages whose token matches (array already cached — cheap path).
      4. After all stages, write output files to disk via _write_outputs_to_disk.

    Returns the list of stage names that were recomputed (used by SSE producer
    to surface as affected_stages). Raises StageCancelled if cfg.stop_event is
    set mid-run; caller catches and emits stage_cancel SSE events.

    Cache typing strategy (advisor item 1):
      - StageEntry.array holds numpy arrays for: landmask, border, voronoi (raw),
        median, fragment, smooth, merge, hierarchy (pc map).
      - Non-array voronoi intermediates (bars, bpx, bc, bd, bk, nb, nc, land_2x)
        live in _VORONOI_CACHE[project_id] (a separate side-table). This avoids
        widening StageEntry.array to Any while keeping the cache pattern clean.
      - On cold cache: all stages run and _VORONOI_CACHE is populated fresh.
      - On warm cache: voronoi intermediates come from _VORONOI_CACHE if the
        voronoi token matches (common case for slider-only changes).
    """
    from .cache import cache_get, cache_put
    from .dag import DAG_ORDER, DAG_PARENTS, STAGE_READS, compute_version_token

    affected: list[str] = []
    tokens: dict[str, str] = {}

    os.makedirs(cfg.output_dir, exist_ok=True)

    kingdoms = cfg.kingdoms
    duchies = cfg.duchies
    condados = cfg.condados
    nc = len(condados)

    def _compute_token(stage: str) -> str:
        upstream = [tokens[p] for p in DAG_PARENTS[stage]]
        tok = compute_version_token(stage, STAGE_READS[stage], cfg, upstream)
        tokens[stage] = tok
        return tok

    def _is_dirty(stage: str) -> bool:
        new_tok = _compute_token(stage)
        cached = cache_get(project_id, stage)
        return cached is None or cached.token != new_tok

    # ---- Stage: landmask ----
    W2, H2 = cfg.map_w * cfg.upscale, cfg.map_h * cfg.upscale
    if _is_dirty("landmask"):
        affected.append("landmask")
        _emit(cfg, "landmask", "start")
        print("[INC] landmask recomputing...")
        pt_data, es_municipalities = load_municipalities(cfg)
        land = build_land_mask(pt_data, es_municipalities, cfg)
        land_2x = build_land_mask(pt_data, es_municipalities, cfg, W2, H2)
        cache_put(project_id, "landmask", tokens["landmask"], land)
        _emit(cfg, "landmask", "done")
    else:
        land = cache_get(project_id, "landmask").array
        # Re-load municipalities (not cached — cheap re-parse, same bytes)
        pt_data, es_municipalities = load_municipalities(cfg)
        # land_2x from voronoi side-table if available, else recompute
        vc = _VORONOI_CACHE.get(project_id)
        land_2x = vc["land_2x"] if vc is not None else build_land_mask(
            pt_data, es_municipalities, cfg, W2, H2)

    # ---- Stage: border ----
    if _is_dirty("border"):
        affected.append("border")
        _emit(cfg, "border", "start")
        print("[INC] border recomputing...")
        border_mask = build_border_mask(cfg)
        cache_put(project_id, "border", tokens["border"], border_mask)
        _emit(cfg, "border", "done")
    else:
        border_mask = cache_get(project_id, "border").array

    # ---- Stage: voronoi ----
    if _is_dirty("voronoi"):
        affected.append("voronoi")
        _emit(cfg, "voronoi", "start")
        print("[INC] voronoi recomputing...")
        bars, bpx, bc, bd, bk, pi, ei, tp, te = setup_baronies(cfg)
        nb = len(bars)
        raw = rasterize_baronies(pt_data, es_municipalities, bars,
                                 pi, ei, tp, te, land, border_mask, cfg)
        cache_put(project_id, "voronoi", tokens["voronoi"], raw)
        # Update voronoi side-table
        _VORONOI_CACHE[project_id] = {
            "bars": bars, "bpx": bpx, "bc": bc, "bd": bd, "bk": bk,
            "nb": nb, "nc": nc, "land_2x": land_2x,
            "pt_data": pt_data, "es_municipalities": es_municipalities,
        }
        _emit(cfg, "voronoi", "done")
    else:
        raw = cache_get(project_id, "voronoi").array
        vc = _VORONOI_CACHE.get(project_id)
        if vc is not None:
            bars = vc["bars"]; bpx = vc["bpx"]; bc = vc["bc"]
            bd = vc["bd"]; bk = vc["bk"]; nb = vc["nb"]
            land_2x = vc["land_2x"]
        else:
            # Cold voronoi side-table (shouldn't happen after any /generate run)
            # Recompute from scratch to keep the pipeline correct.
            bars, bpx, bc, bd, bk, pi, ei, tp, te = setup_baronies(cfg)
            nb = len(bars)
            _VORONOI_CACHE[project_id] = {
                "bars": bars, "bpx": bpx, "bc": bc, "bd": bd, "bk": bk,
                "nb": nb, "nc": nc, "land_2x": land_2x,
                "pt_data": pt_data, "es_municipalities": es_municipalities,
            }

    # ---- Stage: median ----
    if _is_dirty("median"):
        affected.append("median")
        _emit(cfg, "median", "start")
        print("[INC] median recomputing...")
        med = apply_median(raw, land, nb, cfg)  # raises StageCancelled if stop_event set
        cache_put(project_id, "median", tokens["median"], med)
        _emit(cfg, "median", "done")
    else:
        med = cache_get(project_id, "median").array

    # ---- Stage: fragment ----
    if _is_dirty("fragment"):
        affected.append("fragment")
        _emit(cfg, "fragment", "start")
        print("[INC] fragment recomputing...")
        frag = remove_fragments(med, land, nb, cfg)
        cache_put(project_id, "fragment", tokens["fragment"], frag)
        _emit(cfg, "fragment", "done")
    else:
        frag = cache_get(project_id, "fragment").array

    # ---- Stage: smooth ----
    if _is_dirty("smooth"):
        affected.append("smooth")
        _emit(cfg, "smooth", "start")
        print("[INC] smooth recomputing...")
        sm = smooth_per_territory(frag, land, cfg)
        cache_put(project_id, "smooth", tokens["smooth"], sm)
        _emit(cfg, "smooth", "done")
    else:
        sm = cache_get(project_id, "smooth").array

    # ---- Stage: merge ----
    if _is_dirty("merge"):
        affected.append("merge")
        _emit(cfg, "merge", "start")
        print("[INC] merge recomputing...")
        result = merge_small_blobs(sm, land, nb, cfg)
        cache_put(project_id, "merge", tokens["merge"], result)
        _emit(cfg, "merge", "done")
    else:
        result = cache_get(project_id, "merge").array

    # ---- Stage: hierarchy ----
    if _is_dirty("hierarchy"):
        affected.append("hierarchy")
        _emit(cfg, "hierarchy", "start")
        print("[INC] hierarchy recomputing...")
        pc, pd, pk = build_hierarchy_maps(result, bc, bd, bk, nb)
        land = result >= 0
        cache_put(project_id, "hierarchy", tokens["hierarchy"], pc)
        _emit(cfg, "hierarchy", "done")
    else:
        pc_entry = cache_get(project_id, "hierarchy")
        pc = pc_entry.array
        land = result >= 0
        # pd, pk must be recomputed from pc since they aren't separately cached.
        # build_hierarchy_maps is cheap relative to cleanup stages.
        _, pd, pk = build_hierarchy_maps(result, bc, bd, bk, nb)

    na = sum(1 for i in range(nb) if np.sum(result == i) > 0)
    nc_active = sum(1 for i in range(nc) if np.sum(pc == i) > 0)
    print(f"    [INC] Active: {na} baronies, {nc_active} condados; affected={affected}")

    # Write output files (Option A selective writes).
    # affected list gates each write block — empty list skips all I/O (warm no-change
    # baseline drops from 6.8s to ~0s). Full generate path passes affected=None
    # (run_pipeline) to always write everything (D-17 parity preserved).
    _write_outputs_to_disk(
        cfg=cfg,
        result=result,
        land=land,
        land_2x=land_2x,
        pc=pc,
        pd=pd,
        pk=pk,
        bc=bc,
        bd=bd,
        bk=bk,
        nb=nb,
        nc=nc,
        bars=bars,
        condados=condados,
        duchies=duchies,
        kingdoms=kingdoms,
        affected=affected,
    )

    print(f"\n[INC] DONE — affected={affected}")
    return affected


__all__ = ["RegionConfig", "run_pipeline", "run_pipeline_incremental"]
