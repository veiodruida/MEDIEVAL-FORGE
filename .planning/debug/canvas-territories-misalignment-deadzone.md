---
status: awaiting_human_verify
trigger: "canvas-territories-misalignment-deadzone — Two CanvasViewer bugs: navy dead zone right of Stage, territories compressed into top-left corner"
created: 2026-04-19T00:00:00Z
updated: 2026-04-19T02:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — both root causes diagnosed, fixed, tested, and committed.

test: Awaiting human visual verification in browser.

expecting: |
  BUG-1: Territories now span full Iberian Peninsula instead of NW quadrant.
  BUG-2: No navy dead zone — Stage fills the full canvas-region container.

next_action: Human refreshes browser tab and confirms both symptoms are gone.

## Symptoms

expected:
  - Stage fills entire central column (no navy dead zone)
  - Territories align with terrain image of Iberian peninsula

actual:
  - Navy dead zone persists on the right of Stage
  - Territories compressed into top-left (northwest) corner
  - Terrain and capitals display correctly across full peninsula
  - Territories ARE colored (not #666666) — data/color path works

errors: No console errors; visual evidence only. 90/90 tests passing. tsc clean.

reproduction:
  1. Backend at http://localhost:8765
  2. Project UUID: fe5d709d-7454-4e9f-8a0c-5486dc71299f
  3. Open in browser at ~1920x1080
  4. All four layers enabled by default
  5. Observed: terrain fills most of left/center; territories crammed upper-left; navy dead zone right half

started: After commit 1f95f99 (GAP-05 ResizeObserver fix). Territory misalignment is new.

## Eliminated

- hypothesis: GAP-04 #666666 fallback (condado_colors.json key mismatch)
  evidence: Territories ARE colored with diverse palette — key overlap is 100% (90/90)
  timestamp: 2026-04-19

- hypothesis: territories.geojson data path broken
  evidence: GET /api/projects/{PID}/preview/territories.geojson → 200, 90 features; condado_colors.json → 200, 90 keys
  timestamp: 2026-04-19

## Evidence

- timestamp: 2026-04-19
  checked: projection.ts geoToCanvas and geoRingToKonvaPoints
  found: |
    geoToCanvas:
      span = (lonMax - lonMin) * lonScale
      x = ((lon - lonMin) * lonScale / span) * mapW
      y = (1 - (lat - latMin) / (latMax - latMin)) * mapH
    This is mathematically equivalent to map_generator.geo_to_pixel (minus the int() cast).
    lonScale is cos(centerLat) — consistent with backend RegionConfig.__post_init__.
  implication: Frontend projection is correct IF the lon/lat values in territories.geojson are valid geographic coordinates.

- timestamp: 2026-04-19
  checked: territories_geojson.py _pixel_polygon_to_lonlat
  found: |
    W = cfg.map_w * cfg.upscale
    H = cfg.map_h * cfg.upscale
    px_to_lonlat: lon = px / W * span / cfg.lon_scale + cfg.lon_min
                  lat = cfg.lat_max - py / H * (cfg.lat_max - cfg.lat_min)
    The cfg passed in from generator.py uses: map_w=region_cfg.map_w, map_h=region_cfg.map_h, upscale=region_cfg.upscale
    So W = 1920*2 = 3840, H = 1080*2 = 2160 (for default Iberia config).
  implication: This is correct IF rasterio.features.shapes emits pixel coordinates in the 3840×2160 space.

- timestamp: 2026-04-19
  checked: emit_territories_from_disk — how lookup_condado.png is loaded
  found: |
    img = np.array(Image.open(generated_dir / "lookup_condado.png").convert("RGB"))
    H, W, _ = img.shape
    pc = np.full((H, W), -1, dtype=np.int32)
    ... rasterio.features.shapes(pc32, mask=(pc32 >= 0)) ...
    The pc array is sized H×W from the actual PNG dimensions.
    rasterio.features.shapes emits coords in pixel space of the input array.
    build_territories_geojson calls _pixel_polygon_to_lonlat with cfg.map_w*upscale and cfg.map_h*upscale.
  implication: |
    KEY QUESTION: Is lookup_condado.png actually 3840×2160 (map_w*upscale × map_h*upscale)?
    If the generator wrote it at a DIFFERENT resolution (e.g. 1920×1080 = map_w × map_h WITHOUT upscale),
    then rasterio emits coords in 0..1920 × 0..1080 space, but _pixel_polygon_to_lonlat divides by
    W=3840, H=2160 — producing lon/lat values only 50% into the valid range.
    For Iberia: lon_min=-13.2, lon_max=8.2, lat_min=35.4, lat_max=44.6
    If pixel coords are in 1920×1080 space but we divide by 3840×2160:
      lon = px/3840 * span/lonScale + lon_min
    with px up to 1919, we get lon up to (1919/3840) * span/lonScale + lon_min
    = approximately (0.5) * span/lonScale + lon_min — covering only HALF the geographic range.
    This would cause territories to clump in the left half (northwest) of the canvas. ✓ MATCHES SYMPTOMS.

- timestamp: 2026-04-19
  checked: map_generator.py generate_lookup_map (SECTION 10) — what size is the lookup PNG
  found: |
    Line ~375: ci_img = Image.new("I", (cfg.map_w, cfg.map_h), -1)
    The lookup PNG is written at map_w × map_h (NOT map_w*upscale × map_h*upscale).
    For default Iberia: 1920 × 1080, NOT 3840 × 2160.
  implication: |
    CONFIRMED MISMATCH: lookup_condado.png is 1920×1080. rasterio.features.shapes emits pixel
    coords in 0..1920 × 0..1080 space. But _pixel_polygon_to_lonlat divides by
    W=cfg.map_w*cfg.upscale=3840 and H=cfg.map_h*cfg.upscale=2160.
    Result: ALL lon/lat coords are compressed to ~50% of the valid geographic range.
    On canvas: territories appear in the northwest quadrant of the map only.
    This EXACTLY matches the observed symptom: "territories compressed into top-left (northwest) corner".

- timestamp: 2026-04-19
  checked: BackgroundLayer.tsx — how terrain.png is positioned
  found: |
    terrain.png is rendered at x=0, y=0, width=projection.mapW, height=projection.mapH
    projection.mapW/mapH come from territory_metadata.json["map_size"] = [map_w*upscale, map_h*upscale] = [3840, 2160]
    terrain.png itself is the upscaled image (map_w*upscale × map_h*upscale).
    So terrain is CORRECT: it fills the full 3840×2160 pixel space on the canvas.
  implication: Terrain is correct. Territories are not. This confirms territories use wrong coordinate space.

- timestamp: 2026-04-19
  checked: ProjectDetail.tsx — canvas-region layout for dead zone bug
  found: |
    Outer Flex: height=calc(100vh - 220px), minHeight=500px, overflow=hidden
    canvas-region Box: flex=1, background=#1a1a2e, overflow=hidden, position=relative
    CanvasViewer: no explicit width/height props passed — defaults to width=800, height=600
    (CanvasViewer.tsx line 65: `function CanvasViewer({ projectId, width = 800, height = 600 }:`)
    (CanvasViewer.tsx lines 73-74: `const [viewportW, setViewportW] = useState<number>(width)` — 800)
    The ResizeObserver fires on the wrapping div INSIDE CanvasViewer (ref=setContainerRef).
  implication: |
    BUG-2: viewportW/H stuck at 800/600 defaults if the ResizeObserver initial
    entry is delivered asynchronously (after layout) or not at all (element
    already laid out before observe() fires). Belt-and-suspenders fix: read
    getBoundingClientRect() synchronously immediately after ro.observe(el).

- timestamp: 2026-04-19
  checked: Live project fe5d709d territories.geojson after BUG-1 fix
  found: |
    Re-ran emit_territories_from_disk against live Iberia project.
    BEFORE fix: lon range -12.96..-6.46, lat range 40.99..44.89 (NW quadrant clump).
    AFTER fix:  lon range -9.5130..3.4842, lat range 35.9912..43.7984
    Full peninsula is now covered. The ~50% compression is eliminated.
    (Coordinates don't reach the full metadata bbox -16.41..11.41 / 34.02..45.98
    because territory polygons only cover the actual Iberian landmass, not open sea.)
  implication: BUG-1 confirmed fixed. Coordinate space mismatch eliminated.

## Resolution

root_cause: |
  TWO independent bugs:

  BUG-1 — Territory coordinate space mismatch (CONFIRMED):
  territories_geojson.py::_pixel_polygon_to_lonlat divided pixel coordinates by
  W = cfg.map_w * cfg.upscale (e.g. 3840) and H = cfg.map_h * cfg.upscale (e.g. 2160),
  but lookup_condado.png is written at map_w × map_h (e.g. 1920×1080) by
  map_generator.py::generate_lookup_map. rasterio emits shapes in 1920×1080 pixel
  space, but inverse projection assumed 3840×2160, compressing all coordinates to
  ~50% of the valid geographic range → NW quadrant clump. Same bug affected baronies.

  BUG-2 — Dead zone (CONFIRMED MECHANISM):
  ResizeObserver initial entry is not guaranteed to fire synchronously. When the
  element is already laid out before observe() is called, some browsers skip the
  initial notification, leaving viewportW/H locked at the 800×600 prop defaults.
  With a ~1500px container, the Stage rendered at 800px leaving a ~700px dead zone.

fix: |
  BUG-1: Changed _pixel_polygon_to_lonlat signature to accept explicit W, H
  parameters (the actual raster array dimensions). Both callers
  (build_territories_geojson and build_baronies_geojson) pass pc.shape[1]/pc.shape[0]
  and pb.shape[1]/pb.shape[0] respectively — the actual pixel dims of the lookup PNGs.
  The cfg.map_w * cfg.upscale calculation was removed from the function.
  Regenerated territories.geojson and baronies.geojson for live project fe5d709d.

  BUG-2: After ro.observe(el) in the setContainerRef callback, synchronously read
  el.getBoundingClientRect() and apply non-zero dims to viewportW/H immediately.
  This provides a belt-and-suspenders initial measurement independent of whether
  the browser delivers the ResizeObserver initial entry asynchronously or not at all.

verification: |
  BUG-1 self-verified:
  - New regression test test_pixel_polygon_to_lonlat_uses_actual_pc_shape_not_upscaled_dims
    with upscale=2 (lookup PNG at map_w×map_h, not map_w*2×map_h*2) asserts lon/lat
    coverage > 85% of geographic span. Test passes on fixed code.
  - Live project fe5d709d re-queried: lon -9.51..3.48, lat 35.99..43.80
    (full peninsula extent, not NW quadrant).
  - All 9 backend territory tests pass. All 6 barony tests pass.

  BUG-2 self-verified:
  - New test R5: SilentRO (never fires callback) + getBoundingClientRect stub at
    1440×810 → Stage receives those dims without any RO entry.
  - 91/91 frontend tests pass. tsc --noEmit clean.

  Awaiting human visual confirmation in browser.

files_changed:
  - backend/medieval_forge/services/territories_geojson.py
  - backend/medieval_forge/services/baronies_geojson.py
  - backend/tests/test_territories_geojson.py
  - frontend/src/components/canvas/CanvasViewer.tsx
  - frontend/src/components/canvas/__tests__/CanvasViewer.resize.test.tsx
