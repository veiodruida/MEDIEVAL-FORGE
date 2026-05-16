import { Navigate, Route, Routes } from 'react-router-dom'
import { ProjectList } from './pages/ProjectList'
import { ProjectNew } from './pages/ProjectNew'
import { ProjectDetail } from './pages/ProjectDetail'
import { ErrorBoundary } from './components/ErrorBoundary'
import { CanvasRadixOverlaySmoke } from './components/canvas/__smoke__/CanvasRadixOverlaySmoke'
import { ResearchDialogHarness } from './test-routes/research-dialog'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route path="/projects" element={<ProjectList />} />
      <Route path="/projects/new" element={<ProjectNew />} />
      <Route
        path="/projects/:id"
        element={
          <ErrorBoundary>
            <ProjectDetail />
          </ErrorBoundary>
        }
      />
      {import.meta.env.DEV && (
        <>
          <Route path="/canvas-smoke" element={<CanvasRadixOverlaySmoke />} />
          {/* UAT test harness — renders ResearchDialog directly without canvas */}
          <Route path="/test-research-dialog" element={<ResearchDialogHarness />} />
        </>
      )}
    </Routes>
  )
}
