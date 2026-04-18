import { describe, it, expect, vi } from 'vitest'
import {
  applyPanClamp,
  makeDragBoundFunc,
  makeWheelHandler,
  panToGeoCenter,
  SCALE_BY,
  MAX_SCALE_MULTIPLIER,
} from './useZoomPan'
import { buildProjectionConfig, geoToCanvas } from '../lib/projection'

// Minimal Konva.Stage stub covering every method the helpers touch.
function makeStage(init: {
  w?: number; h?: number; scale?: number; x?: number; y?: number
} = {}) {
  let sx = init.scale ?? 1
  let sy = init.scale ?? 1
  let px = init.x ?? 0
  let py = init.y ?? 0
  const w = init.w ?? 1000
  const h = init.h ?? 800

  const stage = {
    width: () => w,
    height: () => h,
    scaleX: () => sx,
    scaleY: () => sy,
    x: () => px,
    y: () => py,
    scale: vi.fn((v: { x: number; y: number }) => { sx = v.x; sy = v.y }),
    position: vi.fn((v: { x: number; y: number }) => { px = v.x; py = v.y }),
    getPointerPosition: vi.fn(() => ({ x: 0, y: 0 })),
    batchDraw: vi.fn(),
  }
  // getStage returns self (canonical Konva behavior)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(stage as any).getStage = () => stage
  return stage
}

describe('useZoomPan: constants', () => {
  it('exports SCALE_BY = 1.05 and MAX_SCALE_MULTIPLIER = 4', () => {
    expect(SCALE_BY).toBe(1.05)
    expect(MAX_SCALE_MULTIPLIER).toBe(4)
  })
})

describe('makeWheelHandler — cursor-anchored zoom', () => {
  it('zooms in on wheel-up, anchored at the pointer position', () => {
    const stage = makeStage({ scale: 1, x: 0, y: 0 })
    stage.getPointerPosition = vi.fn(() => ({ x: 500, y: 400 }))

    const handler = makeWheelHandler(0.1, 4, { mapW: 2000, mapH: 1600 })
    const preventDefault = vi.fn()
    // Cast through unknown — KonvaEventObject is a complex type and the handler
    // only touches evt.deltaY/preventDefault + target.getStage().
    handler({
      evt: { deltaY: -1, preventDefault } as unknown as WheelEvent,
      target: { getStage: () => stage },
    } as never)
    expect(preventDefault).toHaveBeenCalled()
    expect(stage.scale).toHaveBeenCalled()
    const { x } = stage.scale.mock.calls.at(-1)![0]
    expect(x).toBeCloseTo(1 * 1.05, 6)
  })

  it('clamps at minScale on repeated zoom-out', () => {
    const stage = makeStage({ scale: 0.1, x: 0, y: 0 })
    stage.getPointerPosition = vi.fn(() => ({ x: 500, y: 400 }))
    const handler = makeWheelHandler(0.1, 4, { mapW: 2000, mapH: 1600 })
    handler({
      evt: { deltaY: 1, preventDefault: vi.fn() } as unknown as WheelEvent,
      target: { getStage: () => stage },
    } as never)
    // Already at min, no scale change should happen
    expect(stage.scale).not.toHaveBeenCalled()
  })

  it('clamps at maxScale on repeated zoom-in', () => {
    const stage = makeStage({ scale: 4, x: 0, y: 0 })
    stage.getPointerPosition = vi.fn(() => ({ x: 500, y: 400 }))
    const handler = makeWheelHandler(0.1, 4, { mapW: 2000, mapH: 1600 })
    handler({
      evt: { deltaY: -1, preventDefault: vi.fn() } as unknown as WheelEvent,
      target: { getStage: () => stage },
    } as never)
    expect(stage.scale).not.toHaveBeenCalled()
  })
})

describe('applyPanClamp — keeps map inside viewport', () => {
  it('centers map horizontally when scaled width <= viewport width', () => {
    const stage = makeStage({ scale: 0.1, x: -1000, y: 0 })
    applyPanClamp(stage as never, 0.1, { mapW: 2000, mapH: 1600 })
    // scaledW = 200 <= 1000; x = (1000 - 200) / 2 = 400
    expect(stage.position).toHaveBeenCalledWith({ x: 400, y: (800 - 160) / 2 })
  })

  it('clamps pan when scaled width > viewport width', () => {
    const stage = makeStage({ scale: 2, x: 500, y: 500 })  // x pushed positive
    applyPanClamp(stage as never, 2, { mapW: 2000, mapH: 1600 })
    // scaledW = 4000 > 1000 → x clamped to Math.min(0, Math.max(1000-4000, 500)) = 0
    // scaledH = 3200 > 800  → y clamped similarly = 0
    expect(stage.position).toHaveBeenCalledWith({ x: 0, y: 0 })
  })
})

describe('makeDragBoundFunc', () => {
  it('clamps returned position when scaled size exceeds viewport', () => {
    const stage = makeStage({ scale: 2 })
    // Konva binds dragBoundFunc to the Node via `this`; test invokes via .call
    const bound = makeDragBoundFunc({ mapW: 2000, mapH: 1600 }, () => 2)
    const out = bound.call(stage as never, { x: 500, y: 500 })
    expect(out).toEqual({ x: 0, y: 0 })
  })

  it('centers returned position when scaled size fits inside viewport', () => {
    const stage = makeStage({ scale: 0.1 })
    const bound = makeDragBoundFunc({ mapW: 2000, mapH: 1600 }, () => 0.1)
    const out = bound.call(stage as never, { x: 999, y: 999 })
    // scaledW = 200; x = (1000 - 200) / 2 = 400
    expect(out).toEqual({ x: 400, y: (800 - 160) / 2 })
  })
})

describe('panToGeoCenter — RESEARCH §Pitfall 5', () => {
  it('positions stage so (lon, lat) lands at viewport center at the given scale', () => {
    // Project with map = 2000 x 1600, lon [-10, 0], lat [40, 50]
    const projection = buildProjectionConfig(
      { lonMin: -10, lonMax: 0, latMin: 40, latMax: 50 },
      2000,
      1600,
    )
    const stage = makeStage({ w: 1000, h: 800, scale: 1, x: 0, y: 0 })

    // Lugo fixture: lon=-7.55, lat=43.01
    const lon = -7.55, lat = 43.01
    const [cx, cy] = geoToCanvas(lon, lat, projection)

    panToGeoCenter(stage as never, lon, lat, projection, 1, { mapW: 2000, mapH: 1600 })

    // At scale=1 the target position is (vw/2 - cx, vh/2 - cy) before clamp.
    // Since scaledW=2000 > vw=1000, the clamp can only pull x into [-1000, 0].
    // The pre-clamp x = 500 - cx. Compute the expected clamped x:
    const preX = 1000 / 2 - cx * 1
    const preY = 800 / 2 - cy * 1
    const scaledW = 2000; const scaledH = 1600
    const expX = scaledW <= 1000 ? (1000 - scaledW) / 2 : Math.min(0, Math.max(1000 - scaledW, preX))
    const expY = scaledH <= 800  ? (800 - scaledH) / 2  : Math.min(0, Math.max(800 - scaledH, preY))

    // scale() is called first (panToGeoCenter sets scale deterministically)
    expect(stage.scale).toHaveBeenCalledWith({ x: 1, y: 1 })
    // position() is called twice: once pre-clamp, once inside applyPanClamp.
    // Assert the LAST call reflects the clamped target.
    const lastPos = stage.position.mock.calls.at(-1)![0]
    expect(lastPos.x).toBeCloseTo(expX, 6)
    expect(lastPos.y).toBeCloseTo(expY, 6)
  })
})
