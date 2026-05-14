/**
 * Phase 07 Plan 10 Task 1 — i18n/exportErrors.ts contract tests.
 *
 * Asserts the 6 stable codes from UI-SPEC §Surface 3 are present and that
 * every string is a non-empty PT-BR sentence (no English-fallback leakage).
 */
import { describe, it, expect } from 'vitest'
import { EXPORT_ERROR_PT_BR } from '../exportErrors'

const EXPECTED_CODES = [
  'SCHEMA_INVALID',
  'COLOR_COLLISION',
  'OCEAN_LEAK',
  'MISSING_ORIGINAL_IDX',
  'TERRITORY_TOO_SMALL',
  'PIXEL_CENTER_OUT_OF_RANGE',
] as const

describe('EXPORT_ERROR_PT_BR', () => {
  it('contains exactly the 6 stable error codes from UI-SPEC §Surface 3', () => {
    const actual = Object.keys(EXPORT_ERROR_PT_BR).sort()
    const expected = [...EXPECTED_CODES].sort()
    expect(actual).toEqual(expected)
  })

  it('maps every code to a non-empty PT-BR string', () => {
    for (const code of EXPECTED_CODES) {
      const value = EXPORT_ERROR_PT_BR[code]
      expect(value, `expected ${code} to be defined`).toBeTruthy()
      expect(value.length).toBeGreaterThan(10)
    }
  })

  it('contains no English-fallback substrings ("Failed", "Error", "Unable to")', () => {
    const banned = ['Failed', 'Error:', 'Unable to', 'Invalid color', 'leaked into']
    for (const code of EXPECTED_CODES) {
      const value = EXPORT_ERROR_PT_BR[code]
      for (const word of banned) {
        expect(
          value.includes(word),
          `${code} unexpectedly contains English word "${word}": "${value}"`,
        ).toBe(false)
      }
    }
  })
})
