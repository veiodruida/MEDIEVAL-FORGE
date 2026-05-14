/**
 * Phase 07 Plan 10 — PT-BR strings for the 6 stable export-validation codes
 * emitted by `backend/medieval_forge/services/export/validator.py` (D-08
 * envelope). The map is authoritative — `ExportErrorDialog` MUST consume it
 * via `EXPORT_ERROR_PT_BR[e.code] ?? e.message` (server `message` is only the
 * forward-compat fallback when an unknown code lands before the frontend ships
 * the matching string).
 *
 * Strings copied verbatim from 07-UI-SPEC §Surface 3 / §Copywriting (lines
 * 211-216). Do NOT update without re-syncing UI-SPEC.
 */
export const EXPORT_ERROR_PT_BR: Record<string, string> = {
  SCHEMA_INVALID:
    'Arquivo JSON inválido — o pipeline gerou conteúdo malformado.',
  COLOR_COLLISION:
    'Duas regiões compartilham a mesma cor — exportação inválida para o Unity.',
  OCEAN_LEAK:
    'Pixels de oceano contêm cor de território — vazamento de máscara.',
  MISSING_ORIGINAL_IDX:
    'Condado sem original_idx — o jogo não consegue identificá-lo (regra 4 / 7 do CLAUDE.md).',
  TERRITORY_TOO_SMALL:
    'Território com menos de 200 pixels — abaixo do mínimo do contrato.',
  PIXEL_CENTER_OUT_OF_RANGE: 'Coordenada de centro fora dos limites do mapa.',
}
