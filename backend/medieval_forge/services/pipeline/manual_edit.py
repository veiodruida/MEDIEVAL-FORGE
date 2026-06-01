"""Phase 08 D-17 + D-18: manual_edit stage — identity pass-through when log empty.

Slotted between 'merge' and 'hierarchy' in DAG_ORDER. When manual_edit_log_hash == ""
(no user edits), compute() returns the input array unchanged (byte-equal) so parity
tests stay green (Phase 01 D-09 + Phase 04 D-17 carry-forward).

Plan 08-07c (BLOCKER-1 closure): non-empty log → vectorise raster, replay ops,
rasterise back. snapshot_loader is injected by the DAG walker / orchestrator so
compute() can fetch the edit log without leaking DB dependencies into cfg.

D-18 token formula (BLOCKER-2 fix):
  sha256("manual_edit" + f"count={edit_op_count}" + f"loghash={log_hash}" + sorted(upstream))[:16]

The count term is a SEPARATE explicit term in the formula, not derived from the hash,
so two different edit sequences that happen to produce the same hash but have different
lengths still yield distinct tokens.

Plan 08-07: replay helpers replay_split / replay_merge / replay_translate.
These are PURE FUNCTIONS — no DB access, no HTTP. They are invoked from compute()
in plan 08-07c (DAG stage replay), NOT from the HTTP handler /editor/apply.
The HTTP handler only persists the op and bumps hash+count (BLOCKER-1 contract / D-17).
"""
from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np
import rasterio.features
from rasterio.transform import from_bounds
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry import shape as shapely_shape
from shapely.ops import split as shapely_split
from shapely.ops import unary_union

from .contracts import RegionConfig


# ---------------------------------------------------------------------------
# Plan 08.2-02: coordinate conversion for ring re-rasterisation.
# geo_to_pixel (contracts.py:185) uses int() truncation, which causes ~34px
# drift per barony ring.  This helper uses round() + rasterio y-flip so the
# reconstructed ring is byte-equal to the source ring.  See Wave 0 decision
# "A1 Coordinate Contract" and test _lonlat_to_rasterio_xy.
# geo_to_pixel is parity-frozen and MUST NOT be modified.
# ---------------------------------------------------------------------------

def _lonlat_to_rasterio_xy(lon: float, lat: float, cfg: RegionConfig,
                            W: int, H: int) -> tuple[float, float]:
    """Convert WGS84 lon/lat to rasterio world (x, rasterio_y) using round().

    from_bounds(0,0,W,H,W,H) defines a coordinate system where:
    - x grows left→right (0 = left edge, W = right edge)
    - rasterio_y grows bottom→top (0 = bottom, H = top)

    py_row (0=top, grows DOWN) is converted: rasterio_y = H - py_row.
    CRITICAL: round() NOT int() — int() causes ~34px drift (A1 contract).
    """
    span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale
    x = round((lon - cfg.lon_min) * cfg.lon_scale / span * W)
    py_row = round((1.0 - (lat - cfg.lat_min) / (cfg.lat_max - cfg.lat_min)) * H)
    rasterio_y = H - py_row
    return (x, rasterio_y)


def compute(input_array: np.ndarray, cfg: RegionConfig,
            barony_name_to_idx: dict[str, int] | None = None) -> tuple[np.ndarray, list[dict]]:
    """D-17 closure: edits are the OUTPUT of this stage (plan 08-07c BLOCKER-1 fix).

    Empty log_hash → identity (D-17 carry-forward; Iberia parity stays green).
    Non-empty log_hash → vectorise input raster via rasterio.features.shapes,
    apply edit log in order via replay helpers, rasterise back via
    rasterio.features.rasterize with all_touched=False (Gemini LOW: explicit
    cell-centroid semantics; prevents sub-pixel aliasing that would break
    Unity byOriginalIdx shader).

    Plan 08.2-02: barony_name_to_idx (optional) enables vertex-op replay.
    Built backend-side from bars[] at both orchestrator call sites — NOT from
    a snapshot field (A2/A4 eliminated). Only consumed when vertex ops are
    present (Pitfall 4 — BEZ-CONV-04 discriminator).

    Args:
        input_array: int16 barony raster from the 'merge' stage (H×W).
        cfg: RegionConfig with manual_edit_log_hash, manual_edit_log_count,
             branch_id (for loader key), and snapshot_loader (injected by
             orchestrator; MUST NOT be None when log_hash is non-empty).
        barony_name_to_idx: mapping {barony_name: raster_index} built from
             bars[] by the orchestrator. Required for vertex-op replay;
             None disables ring re-rasterisation (zero-edit path safe).

    Returns:
        Edited int16 raster (same shape as input_array).

    Raises:
        RuntimeError: if cfg.manual_edit_log_hash is non-empty but
                      cfg.snapshot_loader is None.
    """
    if not cfg.manual_edit_log_hash:
        # Empty hash → identity pass-through. No copy; same object is returned
        # so downstream numpy views are unaffected and parity tests stay byte-equal.
        return input_array, []

    if cfg.snapshot_loader is None:
        raise RuntimeError(
            "snapshot_loader required when manual_edit_log_hash is set "
            "(BLOCKER-1 fix: DAG walker must inject cfg.snapshot_loader before "
            "invoking manual_edit.compute())"
        )

    # Loader is keyed by branch_id (cfg.branch_id already exists per 08-01/contracts.py).
    snapshot = cfg.snapshot_loader(cfg.branch_id)
    # Pitfall 0 (belt-and-suspenders): accept both snake_case and camelCase edit_log keys.
    # snapshots.ts sends editLog (camelCase); the Apply handler normalises to edit_log, but
    # the auto-snapshot path may use camelCase until Plan 03 lands.
    edit_log = snapshot.get("edit_log") or snapshot.get("editLog") or []
    if not edit_log:
        return input_array, []

    # Pitfall 4 (BEZ-CONV-04 discriminator): only enter ring re-rasterisation when the
    # log contains vertex-level ops. A landmask-only branch (non-empty hash, zero vertex
    # ops) must return byte-identical output; entering the rasterise-back path would
    # degrade barony boundaries and break parity on landmask-only branches.
    _VERTEX_OPS = frozenset({"move", "add", "delete", "multi_delete"})
    vertex_ops_present = any(op.get("op") in _VERTEX_OPS for op in edit_log)
    # Phase 08.3 Plan 01: 'create' ops must enter rasterisation even without vertex ops.
    create_ops_present = any(op.get("op") == "create" for op in edit_log)
    # Phase 08.3 Plan 07: 'carve' ops must also enter rasterisation regardless of vertex ops.
    carve_ops_present = any(op.get("op") == "carve" for op in edit_log)

    # 1) Vectorise int16 raster into per-barony polygons.
    #    Use an affine derived from the raster dimensions — pipeline operates in
    #    raster coordinates throughout. from_bounds(0,0,W,H,W,H) maps pixel (0,0)
    #    to world (0,H) with y-flip; used symmetrically for shapes→rasterize roundtrip.
    H, W = input_array.shape
    transform = from_bounds(0, 0, W, H, W, H)
    shapes_iter = rasterio.features.shapes(input_array.astype(np.int16), transform=transform)
    polygons_by_id: dict[int, list[Polygon]] = {}
    for geom_dict, value in shapes_iter:
        value = int(value)
        if value < 0 or value == 9999:
            # Skip ocean (-1) and ignore (9999) sentinels per CLAUDE.md rule #5.
            # They will be restored from input_array after rasterise.
            continue
        poly = shapely_shape(geom_dict)
        if isinstance(poly, Polygon) and poly.area > 0:
            polygons_by_id.setdefault(value, []).append(poly)

    # 2) Apply edit log in order via replay helpers (defined below in this module).
    #    /editor/apply (08-07) validates ops server-side BEFORE persisting, so any
    #    exception here is a bug — propagate it.
    _geometry_modified = False  # tracks whether any op mutated polygons_by_id
    new_barony_meta: list[dict] = []  # Phase 08.3: metadata for CREATE/split children
    # FIX (2026-06-01 "carve-enclave-edit-leaves-hole", part 2 — shrink-N orphan pixels):
    # Snapshot of N's polygon AS SET BY THE CARVE OP (before any vertex-ring replay).
    # Used in the D-25 re-apply loop to reconstruct parent_original correctly when N is
    # later shrunk by a vertex op.  Key: (parent_idx, n_idx), value: N_original Polygon.
    _carve_n_original: dict[tuple[int, int], Polygon] = {}
    for op in edit_log:
        op_type = op["op"]
        if op_type == "split":
            parent_id = int(op["parentId"])
            cut = LineString(op["cutLineCoords"])
            parents = polygons_by_id.get(parent_id, [])
            if not parents:
                continue  # parent already merged away in a later op — skip
            new_pieces = replay_split(parents[0], cut)
            child_id = int(op["allocated_original_idx"])
            polygons_by_id[parent_id] = [new_pieces[0]]
            polygons_by_id.setdefault(child_id, []).append(new_pieces[1])
            _geometry_modified = True
            # Phase 08.3 Plan 01 (BUG 2 fix for split): append child metadata so
            # orchestrator can extend bars/bc/bd/bk/nb before build_hierarchy_maps.
            # Inherit parent's hierarchy from payload (if present) or fall back to
            # safe defaults so existing split ops without these fields don't crash.
            parent_meta = op.get("barony_meta", {})
            new_barony_meta.append({
                "original_idx": child_id,
                "name": op.get("childName", f"Split-{child_id}"),
                "condado_idx": parent_meta.get("condado_idx", -1),
                "duchy_id": parent_meta.get("duchy_id", ""),
                "kingdom_id": parent_meta.get("kingdom_id", ""),
            })
        elif op_type == "merge":
            a_id, b_id = int(op["firstId"]), int(op["secondId"])
            a_polys = polygons_by_id.get(a_id, [])
            b_polys = polygons_by_id.get(b_id, [])
            if not a_polys or not b_polys:
                continue
            merged = replay_merge(a_polys[0], b_polys[0])
            polygons_by_id[a_id] = [merged]
            polygons_by_id[b_id] = []  # D-08: loser idx freed but NEVER reused
            _geometry_modified = True
        elif op_type == "translate":
            poly_id = int(op["polygonId"])
            dLat, dLon = float(op["dLat"]), float(op["dLon"])
            polys = polygons_by_id.get(poly_id, [])
            if polys:
                polygons_by_id[poly_id] = [replay_translate(p, dLat, dLon) for p in polys]
                _geometry_modified = True
        elif op_type == "create":
            # Phase 08.3 Plan 01 (BUG 1 + BUG 2 fix): rasterise new hand-drawn ring.
            # T-08.3-01-01: ring-length guard (DoS cap enforced upstream in Plan 04).
            new_idx = int(op["allocated_original_idx"])
            ring_coords = op.get("ring", [])
            if len(ring_coords) < 3:
                continue
            pixel_coords = [
                _lonlat_to_rasterio_xy(p["lon"], p["lat"], cfg, W, H)
                for p in ring_coords
            ]
            try:
                poly = Polygon(pixel_coords)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                    # buffer(0) may fragment into MultiPolygon — largest-area guard
                    # (08.2-05 pattern; T-08.3-01-03 mitigate).
                    if isinstance(poly, MultiPolygon):
                        parts = [g for g in poly.geoms if g.area > 0]
                        if not parts:
                            continue
                        poly = max(parts, key=lambda g: g.area)
                # D-07 clip: subtract existing neighbours so overlap is zero.
                # T-08.3-01-03: apply largest-component guard after difference() too.
                if polygons_by_id:
                    neighbours_union = unary_union([
                        p for idx, polys in polygons_by_id.items()
                        for p in polys
                        if p is not None and idx != new_idx
                    ])
                    if not neighbours_union.is_empty:
                        poly = poly.difference(neighbours_union)
                        if isinstance(poly, MultiPolygon):
                            parts = [g for g in poly.geoms if g.area > 0]
                            poly = max(parts, key=lambda g: g.area) if parts else None
                if poly and not poly.is_empty and poly.area > 0:
                    polygons_by_id[new_idx] = [poly]
                    barony_meta = op.get("barony_meta", {})
                    new_barony_meta.append({
                        "original_idx": new_idx,
                        "name": barony_meta.get("name", f"Baronato-{new_idx}"),
                        "condado_idx": barony_meta.get("condado_idx", -1),
                        "duchy_id": barony_meta.get("duchy_id", ""),
                        "kingdom_id": barony_meta.get("kingdom_id", ""),
                    })
                    _geometry_modified = True
            except Exception:  # noqa: BLE001 — degenerate ring; skip silently
                continue
        elif op_type == "carve":
            # Phase 08.3 Plan 07: enclave carve — N = drawn∩parent, parent' = parent−N.
            # MUST NOT call .difference(neighbours_union) on N (that is the 'create' D-07 clip
            # which subtracts the parent and would clip N to empty for an interior loop).
            parent_idx = int(op["parent_id"])
            new_idx = int(op["allocated_original_idx"])
            ring_coords = op.get("ring", [])
            if len(ring_coords) < 3:
                continue

            # Resolve parent polygon (may already carry interiors from a prior carve)
            parents = polygons_by_id.get(parent_idx, [])
            if not parents:
                continue
            parent = parents[0]

            # Build drawn loop using _lonlat_to_rasterio_xy (A1 contract: round() not int())
            pixel_coords = [
                _lonlat_to_rasterio_xy(p["lon"], p["lat"], cfg, W, H)
                for p in ring_coords
            ]
            try:
                drawn = Polygon(pixel_coords)
                if not drawn.is_valid:
                    drawn = drawn.buffer(0)
                    # buffer(0) may fragment — largest-area guard PRESERVES interiors
                    if isinstance(drawn, MultiPolygon):
                        parts = [g for g in drawn.geoms if g.area > 0]
                        if not parts:
                            continue
                        drawn = max(parts, key=lambda g: g.area)

                # D-24 CARVE FORMULA: N = drawn∩parent (clip to parent — N⊆parent guaranteed)
                # parent.difference(N) produces the donut (polygon-with-hole)
                N = drawn.intersection(parent)
                if isinstance(N, MultiPolygon):
                    parts = [g for g in N.geoms if g.area > 0]
                    N = max(parts, key=lambda g: g.area) if parts else N

                parent_prime = parent.difference(N)
                if isinstance(parent_prime, MultiPolygon):
                    # Largest-area guard WITHOUT discarding interior rings:
                    # unary_union can introduce MultiPolygon when the donut exterior
                    # is split; take max-area component but preserve its interiors.
                    parts = [g for g in parent_prime.geoms if g.area > 0]
                    parent_prime = max(parts, key=lambda g: g.area) if parts else parent_prime

                # Degenerate guard: drawn was outside or tangent to parent
                if N.is_empty or N.area <= 0 or parent_prime.is_empty:
                    continue

                polygons_by_id[parent_idx] = [parent_prime]   # polygon-with-hole
                polygons_by_id[new_idx] = [N]
                # Snapshot N as set by THIS carve op (before any vertex-ring replay).
                # D-25 fix part 2: needed to reconstruct parent_original in the re-apply loop.
                _carve_n_original[(parent_idx, new_idx)] = N

                barony_meta = op.get("barony_meta", {})
                new_barony_meta.append({
                    "original_idx": new_idx,
                    "name": barony_meta.get("name", f"Baronato-{new_idx}"),
                    "condado_idx": barony_meta.get("condado_idx", -1),
                    "duchy_id": barony_meta.get("duchy_id", ""),
                    "kingdom_id": barony_meta.get("kingdom_id", ""),
                })
                _geometry_modified = True
            except Exception:  # noqa: BLE001 — degenerate geometry; skip silently
                continue

        # vertex-level ops (move/add/delete/multi_delete) are handled via
        # ring re-rasterisation AFTER this loop (they carry no usable geometry
        # in the op payload — the full ring is in snapshot.vertices).

    # 2b) Ring re-rasterisation for vertex ops (Plan 08.2-02).
    # Only entered when the log contains at least one vertex op AND the caller
    # provided barony_name_to_idx (the authoritative backend-side mapping from bars[]).
    # Guard: vertex_ops_present ensures landmask-only branches remain byte-identical
    # (Pitfall 4 / BEZ-CONV-04).
    # Phase 08.3: create_ops_present does NOT require ring re-rasterisation — the
    # create branch above already handled rasterisation directly in the loop.
    #
    # FIX (2026-06-01 "carve-enclave-edit-leaves-hole"):
    # barony_name_to_idx is built from bars[] BEFORE compute() is called (orchestrator
    # __init__.py line 428).  A freshly-carved enclave N is appended to bars[] only
    # AFTER compute() returns (lines 441-463) — so "Baronato-<ts>" is never in the
    # caller-supplied map.  If the user edits N's contour in the same Apply pass
    # (carve op + move op on N's vertices), replay_vertex_ring("Baronato-<ts>") finds
    # None → silent return → N keeps the original intersection ring, not the edited one.
    #
    # Fix: after the op loop, extend barony_name_to_idx with every entry in
    # new_barony_meta (name → original_idx).  The caller's map is immutable, so we
    # make a local copy.  This is safe because new_barony_meta only covers baronies
    # allocated in THIS compute() call — no pre-existing entry is overwritten.
    if barony_name_to_idx is not None and new_barony_meta:
        barony_name_to_idx = dict(barony_name_to_idx)  # local copy — do not mutate caller's map
        for entry in new_barony_meta:
            bname = entry.get("name")
            bidx = entry.get("original_idx")
            if bname and bidx is not None and bname not in barony_name_to_idx:
                barony_name_to_idx[bname] = bidx

    vertices_dict = snapshot.get("vertices") or {}
    if vertex_ops_present and barony_name_to_idx and vertices_dict:
        barony_names = {k.split("#")[0] for k in vertices_dict if "#" in k}
        for bname in barony_names:
            replay_vertex_ring(bname, barony_name_to_idx, vertices_dict,
                               polygons_by_id, cfg, W, H)
        _geometry_modified = True

    # D-25 LOAD-BEARING FIX (test_carve_then_parent_edit_does_not_refill_hole):
    # replay_vertex_ring rebuilds a parent barony from exterior-only vertices_dict keys
    # (format "<baronyName>#<index>"), which OVERWRITES polygons_by_id[parent_idx] with
    # a plain exterior Polygon — silently refilling any interior ring (hole) that was
    # carved into that parent by a prior carve op in this same edit_log replay.
    #
    # Fix: after the replay_vertex_ring loop, re-derive parent_final from the FINAL N.
    # Invariant: parent_final ∪ N_final == parent_original  (no orphan pixels).
    #
    # Original D-25 formula (broken for shrink case):
    #   reapplied = parent'[after replay].difference(N_final)
    # parent' already has the N_original hole.  When N_final ⊊ N_original (user shrunk N),
    # the annulus N_original − N_final belongs to neither → falls through to ocean (-1).
    #
    # Corrected formula:
    #   parent_original = parent'[after replay] ∪ N_original   (restore the carve-era parent)
    #   parent_final    = parent_original.difference(N_final)   (re-apply hole with FINAL N)
    #
    # _carve_n_original[(p_idx, n_idx)] was captured immediately after the carve op set
    # polygons_by_id[n_idx] = N (before any vertex-ring replay modified it).
    # Guard: skip if either polygon is missing (carve op may have been degenerate/skipped).
    # Citing: D-25 part b + 2026-06-01 shrink-N regression.
    if carve_ops_present:
        for op in edit_log:
            if op.get("op") != "carve":
                continue
            p_idx = int(op.get("parent_id", -1))
            n_idx = int(op.get("allocated_original_idx", -1))
            if p_idx < 0 or n_idx < 0:
                continue
            parent_polys = polygons_by_id.get(p_idx, [])
            n_polys = polygons_by_id.get(n_idx, [])
            if not parent_polys or not n_polys:
                continue
            try:
                n_final = n_polys[0]
                n_original = _carve_n_original.get((p_idx, n_idx))
                if n_original is not None and not n_original.equals(n_final):
                    # N was edited (vertex replay changed it): reconstruct parent_original
                    # first, then subtract the FINAL N to avoid orphan pixels.
                    parent_rebuilt = parent_polys[0].union(n_original)
                    reapplied = parent_rebuilt.difference(n_final)
                else:
                    # N unchanged (no vertex op on N, or no snapshot available):
                    # original D-25 formula is correct — parent already has the right hole.
                    reapplied = parent_polys[0].difference(n_final)
                if not reapplied.is_empty and reapplied.area > 0:
                    polygons_by_id[p_idx] = [reapplied]
            except Exception:  # noqa: BLE001 — degenerate; skip silently
                continue

    # Short-circuit: if no op modified geometry (e.g. landmask-only branch with
    # non-empty hash — Pitfall 4 / BEZ-CONV-04), return input byte-identical.
    # This avoids rasterio round-trip loss on branches that only carry landmask_replace.
    # Phase 08.3 Plan 01: tuple return shape — new_barony_meta is empty here (no create ops).
    if not _geometry_modified:
        return input_array, []

    # 3) Rasterise back to int16.
    #    all_touched=False: standard cell-centroid semantics (Gemini LOW review).
    #    Prevents sub-pixel aliasing / orphan border pixels that would break
    #    Unity byOriginalIdx shader. Default is False but made explicit so a
    #    future rasterio API change cannot silently flip semantics.
    #    fill=-1: ocean sentinel per CLAUDE.md rule #5.
    shapes_to_rasterise = [
        (poly, idx)
        for idx, polys in polygons_by_id.items()
        for poly in polys
        if poly is not None and not poly.is_empty
    ]
    out = rasterio.features.rasterize(
        shapes=shapes_to_rasterise,
        out_shape=(H, W),
        transform=transform,
        fill=-1,  # ocean sentinel per CLAUDE.md rule #5
        dtype=np.int16,
        all_touched=False,  # Gemini LOW: explicit; prevents sub-pixel border leakage.
    )

    # Restore ocean (-1) and ignore (9999) sentinels from input where rasterise
    # produced fill — preserves CLAUDE.md rule #5 contract.
    # Phase 08.3 Plan 01: CREATE pixels may land on positions that were ocean in the
    # input raster. Only restore ocean/ignore where rasterise also produced fill (-1),
    # i.e. where no barony (including new CREATE baronies) painted the pixel.
    ocean_mask = (input_array == -1) & (out == -1)
    ignore_mask = (input_array == 9999)
    out[ocean_mask] = -1
    out[ignore_mask] = 9999
    # Phase 08.3 Plan 01: return tuple (array, sorted new_barony_entries).
    # Sorted by original_idx so orchestrator extension loop is always sequential
    # (Q3 / Assumption A4 — two CREATEs before one Apply land at correct indices).
    sorted_entries = sorted(new_barony_meta, key=lambda e: e["original_idx"])
    return out, sorted_entries


def manual_edit_token(cfg: RegionConfig, upstream_tokens: Iterable[str]) -> str:
    """D-18 token formula including count as a separate term (BLOCKER-2 fix).

    Formula: sha256("manual_edit" | f"count={N}" | f"loghash={hash}" | sorted(upstream))[:16]

    Empty log_hash + count=0 produces a stable identity token that still depends on
    upstream tokens, so any upstream change (e.g. smooth-σ slider) cascades correctly
    through manual_edit to hierarchy and beyond.

    The count term is explicit and separate from loghash so that two edit sequences
    with the same hash but different op counts produce different tokens (D-18 contract).

    Args:
        cfg: RegionConfig carrying manual_edit_log_hash and manual_edit_log_count.
        upstream_tokens: Tokens from parent stages (typically just 'merge' token).

    Returns:
        16-char hex digest (matching the Phase 04 pattern from compute_version_token).
    """
    parts: list[str] = [
        "manual_edit",
        f"count={cfg.manual_edit_log_count}",
        f"loghash={cfg.manual_edit_log_hash}",
    ]
    for tok in sorted(upstream_tokens):
        parts.append(tok)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Plan 08-07: Replay helpers — PURE FUNCTIONS (no DB, no HTTP).
# Invoked by compute() in plan 08-07c DAG replay. NOT called from /editor/apply.
# ---------------------------------------------------------------------------

def replay_split(parent: Polygon, cut: LineString) -> list[Polygon]:
    """D-02 / EDIT-POLYGON-01: split parent polygon along cut line.

    Returns exactly 2 non-empty Polygon pieces whose union equals parent area.
    Raises ValueError("SPLIT_INVALID: ...") if cut does not bisect the polygon
    into exactly 2 pieces (e.g. cut misses polygon, tangent-only cut).

    This is a PURE FUNCTION — no DB access, no side effects.
    Invoked from compute() in plan 08-07c, NOT from HTTP handler.
    """
    result = shapely_split(parent, cut)
    pieces = [g for g in result.geoms if isinstance(g, Polygon) and g.area > 0]
    if len(pieces) != 2:
        raise ValueError(
            f"SPLIT_INVALID: cut produced {len(pieces)} piece(s); expected 2. "
            "Ensure the line crosses the polygon interior at two distinct boundary points."
        )
    return pieces


def replay_merge(a: Polygon, b: Polygon) -> Polygon:
    """D-02 / EDIT-POLYGON-02: merge two adjacent baronies into one polygon.

    D-08: winner = first-selected (caller decides which is 'a').
    D-09: cross-condado merge allowed — adjacency is the ONLY constraint.
    Pitfall 2: raises ValueError("NOT_ADJACENT") if a.touches(b) is False.

    Returns a single Polygon (never MultiPolygon).
    Raises ValueError("NOT_ADJACENT") if polygons are not adjacent (touches == False).
    Raises ValueError("MERGE_INVALID: ...") if union produces non-Polygon geometry.

    This is a PURE FUNCTION — no DB access, no side effects.
    Invoked from compute() in plan 08-07c, NOT from HTTP handler.
    """
    if not a.touches(b):
        raise ValueError("NOT_ADJACENT")
    union = unary_union([a, b])
    if isinstance(union, Polygon):
        return union
    raise ValueError(
        f"MERGE_INVALID: union of adjacent polygons produced {type(union).__name__}; "
        "expected Polygon. This may indicate a topology issue (sliver gap or overlap)."
    )


def replay_translate(polygon: Polygon, d_lat: float, d_lon: float) -> Polygon:
    """D-02 / EDIT-POLYGON-03: translate a polygon by (d_lat, d_lon) delta.

    Applies uniform offset to all vertices. Shared-vertex coupling is handled
    by the HTTP handler / frontend before calling this; replay_translate operates
    on one polygon at a time.

    Returns a new Polygon with all vertices shifted by (d_lat, d_lon).

    This is a PURE FUNCTION — no DB access, no side effects.
    Invoked from compute() in plan 08-07c, NOT from HTTP handler.
    """
    from shapely.affinity import translate as shapely_translate
    # d_lon = xoff (longitude = x-axis), d_lat = yoff (latitude = y-axis)
    return shapely_translate(polygon, xoff=d_lon, yoff=d_lat)


def replay_vertex_ring(
    barony_name: str,
    barony_name_to_idx: dict[str, int],
    vertices_dict: dict[str, dict],
    polygons_by_id: dict[int, list[Polygon]],
    cfg: RegionConfig,
    W: int,
    H: int,
) -> None:
    """Plan 08.2-02: re-rasterise one barony ring from snapshot vertices.

    Rebuilds the Shapely Polygon for `barony_name` from the vertices dict
    (keys in the form "<baronyName>#<index>") and replaces the entry in
    polygons_by_id so the rasterise-back step uses the updated geometry.

    Coordinate conversion uses round() + rasterio y-flip (A1 contract).
    geo_to_pixel (int() truncation) is parity-frozen and MUST NOT be used here.

    Guards:
    - Returns silently if barony_name not in barony_name_to_idx (unknown name).
    - Pitfall 2: returns silently if fewer than 3 ring keys (degenerate ring).
    - Returns silently if Shapely reports invalid or empty geometry.

    Side-effects: mutates polygons_by_id[raster_idx] in-place.

    This is a PURE FUNCTION modulo the polygons_by_id mutation — no DB, no HTTP.
    """
    raster_idx = barony_name_to_idx.get(barony_name)
    if raster_idx is None:
        return

    ring_keys = sorted(
        [k for k in vertices_dict if k.startswith(barony_name + "#")],
        key=lambda x: int(x.split("#")[1]) if "#" in x else 0,
    )

    # Pitfall 2: degenerate ring guard — need at least 3 distinct vertices
    if len(ring_keys) < 3:
        return

    pixel_coords = [
        _lonlat_to_rasterio_xy(
            vertices_dict[k]["lon"],
            vertices_dict[k]["lat"],
            cfg, W, H,
        )
        for k in ring_keys
    ]

    try:
        poly = Polygon(pixel_coords)
        # Attempt to heal self-intersections (e.g. non-convex rings with add/delete
        # ops that produce a bowtie). buffer(0) is the canonical Shapely fix.
        # Security: Pitfall 2 guard (len < 3) already rejects degenerate inputs.
        if not poly.is_valid:
            poly = poly.buffer(0)
            # buffer(0) can fragment a non-convex ring into multiple pieces, returning a
            # MultiPolygon. A MultiPolygon stored in polygons_by_id causes the barony to
            # disappear from baronies.geojson on the SECOND Apply because
            # build_baronies_geojson_sidecar's masked shapes() extraction cannot recover
            # it from the accumulated raster — violating CLAUDE.md rule #4
            # (original_idx in every territory / byOriginalIdx contract).
            # Fix: take the largest-area component so polygons_by_id always holds a Polygon.
            if isinstance(poly, MultiPolygon):
                parts = [g for g in poly.geoms if g.area > 0]
                if not parts:
                    return
                poly = max(parts, key=lambda g: g.area)
    except Exception:  # noqa: BLE001 — malformed ring; skip silently
        return

    if not poly.is_empty and poly.area > 0:
        polygons_by_id[raster_idx] = [poly]


__all__ = [
    "compute",
    "manual_edit_token",
    "replay_split",
    "replay_merge",
    "replay_translate",
    "replay_vertex_ring",
]
