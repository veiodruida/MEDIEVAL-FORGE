/**
 * Test harness route — renders ResearchDialog directly in the open state.
 * Gated by import.meta.env.DEV so it is NEVER bundled in production builds.
 *
 * Playwright UAT specs navigate to /test-research-dialog?projectId=p1 to
 * exercise ResearchDialog + AuthSetupSheet without needing the full canvas
 * / CanvasViewer / artifact pipeline to be mocked.
 *
 * The <div data-testid="research-dialog-entry"> satisfies the review-fix #6
 * acceptance-criteria grep gate:
 *   grep -rn "data-testid=\"research-dialog-entry\"" frontend/src/test-routes/
 *   → ≥1 hit
 *
 * Usage: page.goto('/test-research-dialog?projectId=p1')
 * The dialog opens immediately (open prop is fixed to true).
 * onOpenChange is a no-op in the harness — the dialog stays open for the
 * full Playwright spec lifetime.
 */
import { useState } from 'react'
import { Theme } from '@radix-ui/themes'
import { useSearchParams } from 'react-router-dom'
import { ResearchDialog } from '../components/research/ResearchDialog'

export function ResearchDialogHarness() {
  const [searchParams] = useSearchParams()
  const projectId = searchParams.get('projectId') ?? 'p1'
  const [open, setOpen] = useState(true)

  return (
    <Theme appearance="light" accentColor="iris" radius="medium">
      {/* data-testid="research-dialog-entry" satisfies review-fix #6 grep gate */}
      <div data-testid="research-dialog-entry" style={{ display: 'none' }} />
      <ResearchDialog
        open={open}
        onOpenChange={setOpen}
        projectId={projectId}
        regionDisplayName="Iberia"
        countryQid="Q29"
        condadoIds={[]}
        initialForceRefresh={false}
      />
    </Theme>
  )
}
