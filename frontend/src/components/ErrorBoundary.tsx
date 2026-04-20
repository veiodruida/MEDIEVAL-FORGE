import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button, Card, Flex, Heading, Text } from '@radix-ui/themes'
import { Link } from 'react-router-dom'
import { useUIStore } from '../stores/uiStore'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * Class-based React error boundary (quick-task 260420-hkr).
 *
 * Wraps ProjectDetail so a runtime throw inside the canvas subtree shows a
 * recoverable fallback card instead of a blank page. "Limpar seleção" clears
 * the UIStore selection that triggered the crash; the Link+onClick combo
 * navigates back to the project list AND resets the boundary state so the
 * user can re-enter a project immediately.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary] Captured:', error, info)
  }

  private reset = () => {
    useUIStore.getState().select(null)
    this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children
    const msg = this.state.error.message.slice(0, 300)
    return (
      <Flex align="center" justify="center" style={{ minHeight: '100vh', padding: 24 }}>
        <Card style={{ maxWidth: 520 }}>
          <Flex direction="column" gap="3">
            <Heading size="4">Algo correu mal</Heading>
            <Text size="2" color="gray" style={{ whiteSpace: 'pre-wrap' }}>
              {msg}
            </Text>
            <Flex gap="2">
              <Button onClick={this.reset}>Limpar seleção</Button>
              <Link to="/projects">
                <Button variant="soft" onClick={this.reset}>
                  Voltar à lista de projetos
                </Button>
              </Link>
            </Flex>
          </Flex>
        </Card>
      </Flex>
    )
  }
}
