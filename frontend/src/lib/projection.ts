/**
 * Affine projection mirroring inicio/map_generator.py geo_to_pixel / pixel_to_geo.
 * Sub-pixel floats are PRESERVED (unlike Python's int(...) cast). RESEARCH §Pattern 1.
 *
 * Python reference (lines 152–171 of map_generator.py):
 *   geo_to_pixel: px = int((lon - lon_min) * lon_scale / span * w)
 *                 py = int((1.0 - (lat - lat_min) / (lat_max - lat_min)) * h)
 *   pixel_to_geo: lon = px / w * span / lon_scale + lon_min
 *                 lat = lat_max - py / h * (lat_max - lat_min)
 *
 * The int(...) cast is a Python rasterization artifact — we drop it here so
 * round-trip error stays within floating-point precision (< 1e-9).
 */

export interface ProjectionConfig {
  lonMin: number
  lonMax: number
  latMin: number
  latMax: number
  mapW: number   // pixel width of terrain.png (map_w * upscale from metadata)
  mapH: number   // pixel height of terrain.png (map_h * upscale from metadata)
  lonScale: number  // cos((latMin+latMax)/2 * pi/180)
}

export function buildProjectionConfig(
  bounds: { lonMin: number; lonMax: number; latMin: number; latMax: number },
  mapW: number,
  mapH: number,
): ProjectionConfig {
  const centerLat = (bounds.latMin + bounds.latMax) / 2
  const lonScale = Math.cos((centerLat * Math.PI) / 180)
  return { ...bounds, mapW, mapH, lonScale }
}

export function geoToCanvas(lon: number, lat: number, c: ProjectionConfig): [number, number] {
  const span = (c.lonMax - c.lonMin) * c.lonScale
  const x = ((lon - c.lonMin) * c.lonScale / span) * c.mapW
  const y = (1 - (lat - c.latMin) / (c.latMax - c.latMin)) * c.mapH
  return [x, y]
}

export function canvasToGeo(x: number, y: number, c: ProjectionConfig): [number, number] {
  const span = (c.lonMax - c.lonMin) * c.lonScale
  const lon = (x / c.mapW) * span / c.lonScale + c.lonMin
  const lat = c.latMax - (y / c.mapH) * (c.latMax - c.latMin)
  return [lon, lat]
}

export function geoRingToKonvaPoints(ring: [number, number][], c: ProjectionConfig): number[] {
  const out = new Array<number>(ring.length * 2)
  for (let i = 0; i < ring.length; i++) {
    const [x, y] = geoToCanvas(ring[i][0], ring[i][1], c)
    out[2 * i] = x
    out[2 * i + 1] = y
  }
  return out
}

export function computeFitToView(
  bboxMapW: number,
  bboxMapH: number,
  viewportW: number,
  viewportH: number,
  paddingPct = 0.05,
): { scale: number; x: number; y: number } {
  const usableW = viewportW * (1 - paddingPct)
  const usableH = viewportH * (1 - paddingPct)
  const scale = Math.min(usableW / bboxMapW, usableH / bboxMapH)
  const x = (viewportW - bboxMapW * scale) / 2
  const y = (viewportH - bboxMapH * scale) / 2
  return { scale, x, y }
}
