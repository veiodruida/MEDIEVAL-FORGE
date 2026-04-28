import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { StepCard } from './StepCard'

function renderCard(props: Partial<React.ComponentProps<typeof StepCard>> = {}) {
  const defaults = {
    title: 'Test Title',
    children: <div>Step body content</div>,
  }
  return render(
    <Theme>
      <StepCard {...defaults} {...props} />
    </Theme>,
  )
}

describe('StepCard', () => {
  it('renders title text', () => {
    renderCard({ title: 'My Step Title' })
    expect(screen.getByText('My Step Title')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    renderCard({ description: 'This is a description' })
    expect(screen.getByText('This is a description')).toBeInTheDocument()
  })

  it('does not render description when omitted', () => {
    renderCard({ description: undefined })
    // title should still be there
    expect(screen.getByText('Test Title')).toBeInTheDocument()
  })

  it('renders children content', () => {
    renderCard({ children: <span data-testid="child">Hello child</span> })
    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.getByText('Hello child')).toBeInTheDocument()
  })

  it('renders footer slot when provided', () => {
    renderCard({ footer: <button type="button">Action</button> })
    expect(screen.getByRole('button', { name: 'Action' })).toBeInTheDocument()
  })

  it('does not render footer when omitted', () => {
    renderCard({ footer: undefined })
    // No button with name 'Action' should exist
    expect(screen.queryByRole('button', { name: 'Action' })).not.toBeInTheDocument()
  })
})
