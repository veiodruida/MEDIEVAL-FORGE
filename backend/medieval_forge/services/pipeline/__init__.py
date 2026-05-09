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

Output filenames follow the 12-file Unity contract (CLAUDE.md), minus the two
deferred to Phase 06 (terrain_lookup.png + terrain_types.json — P-2). The 10
files produced for iberia_868:

    lookup_barony.png, lookup_condado.png,
    lookup_barony_colors.json, lookup_condado_colors.json,
    territory_metadata.json,
    visual_condado.png, visual_barony.png,
    mountains_mask.png, rivers_overlay.png,
    mountain_river_data.json
"""

from __future__ import annotations

import json
import os
import shutil

import numpy as np
from PIL import Image

from .contracts import RegionConfig
from .landmask import load_municipalities, build_land_mask
from .border import build_border_mask
from .voronoi import setup_baronies, rasterize_baronies, build_hierarchy_maps
from .cleanup import cleanup_and_smooth
from .render import render_map, render_mountains, render_rivers
from .lookup import generate_lookup_map
from .export import export_metadata


def _emit(cfg: RegionConfig, stage: str, evt: str) -> None:
    """Fire-and-forget pipeline-stage callback (Plan 03-01).

    Invokes `cfg.on_stage(stage, evt)` if a callback is registered. Default
    `cfg.on_stage = None` preserves Phase 01 parity exactly — this is a
    no-op in that case. Exceptions raised by the callback propagate; the
    SSE producer in Plan 02 wraps and reports them.
    """
    if cfg.on_stage is not None:
        cfg.on_stage(stage, evt)


def run_pipeline(cfg: RegionConfig) -> None:
    """Main pipeline: generates all map files for Unity.

    Verbatim port of inicio/map_generator.py:798-934 (`generate_maps`) with
    these substitutions per CONTEXT.md:
      - renamed to run_pipeline (D-03)
      - territory_module argument dropped (D-13: cfg.kingdoms/duchies/condados)
      - draw_names argument dropped (D-03: cfg.draw_names)
      - hardcoded RNG seed replaced inside render.py (P-9 + rule #7)
    """
    if cfg is None:
        cfg = RegionConfig()

    os.makedirs(cfg.output_dir, exist_ok=True)

    print(f"{'='*60}")
    print(f"MAP GENERATOR — {cfg.name.upper()}")
    print(f"{'='*60}")

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
    land = build_land_mask(pt_data, es_municipalities, cfg)
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
    border_mask = build_border_mask(cfg)
    _emit(cfg, "border", "done")

    # 5. Setup baronies (D-14: cfg now carries condados/duchies/kingdoms)
    _emit(cfg, "voronoi", "start")
    print("[6] Setting up baronies...")
    bars, bpx, bc, bd, bk, pi, ei, tp, te = setup_baronies(cfg)
    nb = len(bars)

    # 6. Rasterize
    print("[7] Rasterizing baronies...")
    raw = rasterize_baronies(pt_data, es_municipalities, bars,
                             pi, ei, tp, te, land, border_mask, cfg)
    _emit(cfg, "voronoi", "done")

    # 7. Cleanup & smooth
    # Plan 03-01: cleanup_and_smooth covers cleanup + per-territory Gaussian
    # smooth + small-blob merge in one call. We emit three rapid start/done
    # markers around the single call so the SSE checklist can light up the
    # corresponding rows; finer-grained timing is Phase 04 territory.
    _emit(cfg, "cleanup", "start")
    print("[8] Cleanup & smoothing...")
    _emit(cfg, "cleanup", "done")
    _emit(cfg, "smooth", "start")
    _emit(cfg, "smooth", "done")
    _emit(cfg, "merge", "start")
    result = cleanup_and_smooth(raw, land, nb, cfg)
    _emit(cfg, "merge", "done")

    # 8. Hierarchy
    _emit(cfg, "hierarchy", "start")
    print("[9] Building hierarchy...")
    pc, pd, pk = build_hierarchy_maps(result, bc, bd, bk, nb)
    land = result >= 0  # update land to match result (verbatim inicio:860)
    _emit(cfg, "hierarchy", "done")

    na = sum(1 for i in range(nb) if np.sum(result == i) > 0)
    nc_active = sum(1 for i in range(nc) if np.sum(pc == i) > 0)
    print(f"    Active: {na} baronies, {nc_active} condados")

    # 9. Render visual maps (D-03: draw_names from cfg.draw_names inside render_map)
    _emit(cfg, "render", "start")
    print("[10] Rendering visual maps...")
    for mt in ["condado", "barony"]:
        print(f"     {mt}...")
        img = render_map(result, pc, pd, pk, bc, bd, bk, nb, nc,
                        condados, duchies, kingdoms, land, cfg,
                        map_type=mt, land_2x=land_2x)
        Image.fromarray(img).save(f"{cfg.output_dir}/visual_{mt}.png")
    _emit(cfg, "render", "done")

    # 10. Lookup maps
    _emit(cfg, "lookup", "start")
    print("[11] Generating lookup maps...")
    cmaps: dict[str, dict] = {}  # captured for canvas sidecars (Plan 03-01)
    for label, level_map, n_items in [("barony", result, nb), ("condado", pc, nc)]:
        lk, cmap = generate_lookup_map(result, level_map, n_items, cfg, label)
        cmaps[label] = cmap
        Image.fromarray(lk).save(f"{cfg.output_dir}/lookup_{label}.png")
        with open(f"{cfg.output_dir}/lookup_{label}_colors.json", 'w') as f:
            json.dump(cmap, f, indent=2)
    _emit(cfg, "lookup", "done")

    # 11. Metadata
    _emit(cfg, "metadata", "start")
    print("[12] Exporting metadata...")
    metadata = export_metadata(condados, duchies, kingdoms, bars, result, pc, cfg)
    with open(f"{cfg.output_dir}/territory_metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    _emit(cfg, "metadata", "done")

    # 12. Mountains (rule #6 + P-4: independent 2x render — pass land_2x in)
    _emit(cfg, "export", "start")
    print("[13] Mountains...")
    mtn_mask = render_mountains(cfg, land_2x)
    if mtn_mask is not None:
        # Save as white-on-black mask (white = impassable)
        mtn_img = np.zeros((H2, W2), dtype=np.uint8)
        mtn_img[mtn_mask] = 255
        Image.fromarray(mtn_img).save(f"{cfg.output_dir}/mountains_mask.png")
        print(f"    Mountain pixels: {np.sum(mtn_mask):,}")

        # Also apply mountains to visual maps (P-9 + rule #7: cfg.rng_seed)
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
    print("[14] Rivers...")
    rivers_img = render_rivers(cfg)
    if rivers_img is not None:
        rivers_img.save(f"{cfg.output_dir}/rivers_overlay.png")

        # Also composite rivers on visual maps
        for mt in ["condado", "barony"]:
            vis = Image.open(f"{cfg.output_dir}/visual_{mt}.png").convert("RGBA")
            vis.paste(rivers_img, (0, 0), rivers_img)
            vis.convert("RGB").save(f"{cfg.output_dir}/visual_{mt}.png")

    # 14. Copy mountain_river_data.json into output (10th contract file).
    # The deployed Reconquista folder ships this file alongside the others; it
    # is the same bytes as the input. Plan 03's parity test reads it from output.
    mr_path = cfg.dataset.mountain_river_json if cfg.dataset is not None else None
    if mr_path and os.path.exists(mr_path):
        shutil.copy2(mr_path,
                     os.path.join(cfg.output_dir, "mountain_river_data.json"))

    # 15. Canvas sidecars (Plan 03-01 BLOCKER fix — Pitfall 10).
    # Emit-only, parity-safe: the 10-file Unity contract is unaffected; these
    # four files (territories.geojson + baronies.geojson + condado_colors.json
    # + barony_colors.json) feed the Phase 03 read-only canvas hydrator.
    print("[15] Emitting canvas sidecars...")
    from ..canvas_sidecars import (
        build_baronies_geojson_sidecar,
        build_territories_geojson_sidecar,
    )
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
    _emit(cfg, "export", "done")

    print(f"\n{'='*60}")
    print(f"DONE — {na} baronies, {nc_active} condados")
    print(f"Output: {cfg.output_dir}/")
    print(f"{'='*60}")


__all__ = ["RegionConfig", "run_pipeline"]
