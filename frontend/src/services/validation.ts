import type {
  ValidationIssue,
  Position,
  ProjectGeometryState,
} from '../types/editing'

/**
 * Per-operation validation (D-06). Affects only touched territories + their
 * direct neighbors. Not a full map scan — that lives in Phase 6 VALIDATE-01..07.
 *
 * Rules checked:
 *   - empty_polygon    (severity=error)  — exterior ring is empty
 *   - polygon_invalid  (severity=error)  — < 4 vertices OR duplicate consecutive points
 *   - capital_outside  (severity=error)  — capital [lon,lat] fails point-in-polygon test
 */
export function validateTerritories(
  affectedIds: string[],
  state: ProjectGeometryState,
): ValidationIssue[] {
  const issues: ValidationIssue[] = []

  for (const id of affectedIds) {
    const geom = state.territories[id]
    if (!geom) continue

    if (geom.type === 'Polygon') {
      const exterior = geom.coordinates[0] ?? []

      // empty_polygon
      if (exterior.length === 0) {
        issues.push({
          condado_id: id,
          severity: 'error',
          rule: 'empty_polygon',
          message: 'Território sem geometria',
        })
        continue
      }

      // polygon_invalid — pragmatic checks: < 4 coords
      if (exterior.length < 4) {
        issues.push({
          condado_id: id,
          severity: 'error',
          rule: 'polygon_invalid',
          message: 'Polígono inválido: menos de 4 vértices',
        })
        continue
      }

      // polygon_invalid — duplicate consecutive points
      let hasDuplicate = false
      for (let i = 1; i < exterior.length; i++) {
        if (
          exterior[i][0] === exterior[i - 1][0] &&
          exterior[i][1] === exterior[i - 1][1]
        ) {
          hasDuplicate = true
          break
        }
      }
      if (hasDuplicate) {
        issues.push({
          condado_id: id,
          severity: 'error',
          rule: 'polygon_invalid',
          message: 'Polígono inválido: vértices duplicados consecutivos',
        })
        continue
      }

      // capital_outside — ray-casting test
      const capital = state.capitals[id]
      if (capital && !pointInPolygon(capital, exterior)) {
        issues.push({
          condado_id: id,
          severity: 'error',
          rule: 'capital_outside',
          message: 'Capital fora do território',
        })
      }
    } else if (geom.type === 'MultiPolygon') {
      // For MultiPolygon: check each ring and capital-in-any-ring
      const capital = state.capitals[id]
      let capitalFound = !capital // if no capital, skip capital check
      for (const polygon of geom.coordinates) {
        const exterior = polygon[0] ?? []
        if (exterior.length === 0) {
          issues.push({
            condado_id: id,
            severity: 'error',
            rule: 'empty_polygon',
            message: 'Território sem geometria (MultiPolygon com anel vazio)',
          })
          break
        }
        if (capital && pointInPolygon(capital, exterior)) {
          capitalFound = true
        }
      }
      if (capital && !capitalFound) {
        issues.push({
          condado_id: id,
          severity: 'error',
          rule: 'capital_outside',
          message: 'Capital fora do território',
        })
      }
    }
  }

  return issues
}

/** Ray-casting point-in-polygon test for a single ring (GeoJSON exterior). */
function pointInPolygon(point: Position, ring: Position[]): boolean {
  const [x, y] = point
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    // T-04-08-01: avoid division by zero with epsilon guard
    const intersect =
      yi > y !== yj > y &&
      x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-12) + xi
    if (intersect) inside = !inside
  }
  return inside
}
