import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import type { ReactNode } from 'react'
import { GenerateStatusBadge } from '../GenerateStatusBadge'

function wrap(node: ReactNode) {
  return <Theme>{node}</Theme>
}

describe('GenerateStatusBadge', () => {
  it('runState=idle (no artifacts) → gray + "Pronto"', () => {
    render(
      wrap(
        <GenerateStatusBadge
          runState="idle"
          currentStage={null}
          hasArtifacts={false}
          onClick={() => {}}
        />,
      ),
    )
    const badge = screen.getByTestId('generate-status-badge')
    expect(badge).toHaveTextContent('Pronto')
    expect(badge.getAttribute('data-color')).toBe('gray')
  })

  it('runState=idle (artifacts present) → grass + "Mapa gerado"', () => {
    render(
      wrap(
        <GenerateStatusBadge
          runState="idle"
          currentStage={null}
          hasArtifacts={true}
          onClick={() => {}}
        />,
      ),
    )
    const badge = screen.getByTestId('generate-status-badge')
    expect(badge).toHaveTextContent('Mapa gerado')
    expect(badge.getAttribute('data-color')).toBe('grass')
  })

  it('runState=generating + currentStage=voronoi → amber + "Gerando: voronoi"', () => {
    render(
      wrap(
        <GenerateStatusBadge
          runState="generating"
          currentStage="voronoi"
          hasArtifacts={false}
          onClick={() => {}}
        />,
      ),
    )
    const badge = screen.getByTestId('generate-status-badge')
    expect(badge).toHaveTextContent('Gerando: voronoi')
    expect(badge.getAttribute('data-color')).toBe('amber')
  })

  it('runState=generated → grass + "Mapa gerado"', () => {
    render(
      wrap(
        <GenerateStatusBadge
          runState="generated"
          currentStage={null}
          hasArtifacts={true}
          onClick={() => {}}
        />,
      ),
    )
    const badge = screen.getByTestId('generate-status-badge')
    expect(badge).toHaveTextContent('Mapa gerado')
    expect(badge.getAttribute('data-color')).toBe('grass')
  })

  it('runState=error → red + "Erro"', () => {
    render(
      wrap(
        <GenerateStatusBadge
          runState="error"
          currentStage={null}
          hasArtifacts={false}
          onClick={() => {}}
        />,
      ),
    )
    const badge = screen.getByTestId('generate-status-badge')
    expect(badge).toHaveTextContent('Erro')
    expect(badge.getAttribute('data-color')).toBe('red')
  })

  it('clicking the badge calls onClick', () => {
    const onClick = vi.fn()
    render(
      wrap(
        <GenerateStatusBadge
          runState="idle"
          currentStage={null}
          hasArtifacts={false}
          onClick={onClick}
        />,
      ),
    )
    fireEvent.click(screen.getByTestId('generate-status-badge'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})
