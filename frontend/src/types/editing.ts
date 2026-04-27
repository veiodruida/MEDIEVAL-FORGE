// Backend payload contracts (must match Pydantic schemas in Plan 04)
export interface MoveCapitalRequest {
  lon: number   // -180 .. 180
  lat: number   // -90 .. 90
}

export interface MoveCapitalResponse {
  updated_territories: Record<string, GeoJSONPolygon> // id -> new polygon
  affected_ids: string[]  // ids that were recomputed (moved condado + neighbors)
}

export interface MergeRequest {
  condado_ids: string[]       // length >= 2; primary_id MUST be first
  primary_id: string          // inherits name from this condado (highest area)
}

export interface MergeResponse {
  merged_id: string                          // id of result (primary_id)
  merged_territory: GeoJSONPolygon | GeoJSONMultiPolygon
  removed_ids: string[]                      // ids no longer in territory set
  warning: 'non_adjacent_multipolygon' | null
}

export interface SplitRequest {
  cut_line: [number, number][]  // array of [lon, lat]; minimum 2 points
  mode: 'snap' | 'polyline' | 'freehand'
}

export interface SplitResponse {
  original_id: string
  new_territory_a: { id: string; geometry: GeoJSONPolygon }
  new_territory_b: { id: string; geometry: GeoJSONPolygon }
}

export interface ReshapeGeometryRequest {
  geometry: GeoJSONPolygon  // caller pre-validates is_valid on frontend
}

// GeoJSON minimal shapes (avoid external @types/geojson dep)
export type Position = [number, number]
export interface GeoJSONPolygon {
  type: 'Polygon'
  coordinates: Position[][]  // exterior ring + optional holes
}
export interface GeoJSONMultiPolygon {
  type: 'MultiPolygon'
  coordinates: Position[][][]
}

// Zustand store shapes
export interface ProjectGeometryState {
  territories: Record<string, GeoJSONPolygon | GeoJSONMultiPolygon>
  capitals: Record<string, Position>  // condado_id -> [lon, lat]
  terrain_types?: Record<string, TerrainType>  // Phase 5 addition — optional for backward compat with existing callers
}

export type TerrainType = 'mountain' | 'forest' | 'plains' | 'river' | 'arid'
export const TERRAIN_TYPES = ['mountain', 'forest', 'plains', 'river', 'arid'] as const

export interface PaintTerrainRequest {
  territory_ids: string[]
  terrain_type: TerrainType
}

export interface PaintTerrainResponse {
  painted_ids: string[]
  skipped_ids: string[]
}

export const TERRAIN_LABELS_PT: Record<TerrainType, string> = {
  mountain: 'Montanha',
  forest: 'Floresta',
  plains: 'Planície',
  river: 'Rio',
  arid: 'Árido',
}

export const TERRAIN_EMOJI: Record<TerrainType, string> = {
  mountain: '⛰️',
  forest: '🌲',
  plains: '🌾',
  river: '🌊',
  arid: '🏜️',
}

export const TERRAIN_HEX: Record<TerrainType, string> = {
  mountain: '#9e9e9e',
  forest: '#2d6a2d',
  plains: '#c8b870',
  river: '#5b8db8',
  arid: '#c27b3a',
}

export const TERRAIN_UNPAINTED_HEX = '#d4d4d4'

export type ToolMode = 'none' | 'select' | 'capital' | 'vertex' | 'split' | 'paint'
export type SplitSubMode = 'snap' | 'polyline' | 'freehand'

export interface EditorState {
  editMode: boolean              // D-09 global edit mode gate
  activeTool: ToolMode
  splitSubMode: SplitSubMode
  vertexEditCondadoId: string | null
  rubberBandSelectionIds: string[]
  // Parallel label stack for undo/redo (Pitfall 7 — NOT stored in temporal history)
  undoLabels: string[]
  redoLabels: string[]
}

// Named undo/redo labels (D-05)
export type UndoLabel = string  // e.g. "Mover capital de León", "Fundir 3 territórios"

// Validation (D-06)
export interface ValidationIssue {
  condado_id: string
  severity: 'error' | 'warning'
  rule: 'polygon_invalid' | 'capital_outside' | 'empty_polygon' | 'non_adjacent_merge'
  message: string
}

// Save strategy (D-07)
export type SaveStrategy = 'auto' | 'per_op' | 'explicit'
export type SaveStatus = 'saved' | 'saving' | 'unsaved'
