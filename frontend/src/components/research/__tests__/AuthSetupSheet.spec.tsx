import { describe, it } from 'vitest'

describe('AuthSetupSheet — llama.cpp panel (Wave 0 scaffold)', () => {
  it.skip('renders Tabs shell with Llama.cpp local tab active and Claude/Ollama disabled', () => {})
  it.skip('dropdown populates from useLlamacppHealth().available_models alphabetically', () => {})
  it.skip('dropdown disabled with PT-BR hint when available_models is empty array', () => {})
  it.skip('"Levantar servidor" disabled when llama-server binary missing with orange warning', () => {})
  it.skip('"Levantar servidor" click calls useLlamacppLaunch with selected model', () => {})
  it.skip('button label swaps to "Parar servidor" when server running with green badge', () => {})
  it.skip('HTTP 409 conflict renders PT-BR inline error "Modelo ... já está ativo"', () => {})
  it.skip('"Parar servidor" click sends DELETE and resets status to "Nenhum servidor ativo"', () => {})
})
