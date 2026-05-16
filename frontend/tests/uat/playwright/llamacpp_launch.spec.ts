import { test } from '@playwright/test'

test.describe('llama.cpp launch flow (Wave 0 scaffold)', () => {
  test.skip('happy path: open AuthSetupSheet → select model → Levantar servidor → status active → Parar servidor', async () => {})
  test.skip('empty-models hint shown when dropdown disabled', async () => {})
  test.skip('409 conflict renders PT-BR error when different model already running', async () => {})
})
