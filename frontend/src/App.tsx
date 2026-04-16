import { Navigate, Route, Routes } from 'react-router-dom'
import { ProjectList } from './pages/ProjectList'
import { ProjectNew } from './pages/ProjectNew'
import { ProjectDetail } from './pages/ProjectDetail'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route path="/projects" element={<ProjectList />} />
      <Route path="/projects/new" element={<ProjectNew />} />
      <Route path="/projects/:id" element={<ProjectDetail />} />
    </Routes>
  )
}
