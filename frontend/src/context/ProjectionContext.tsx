import { createContext, useContext, type ReactNode } from 'react'
import type { ProjectionConfig } from '../lib/projection'

const ProjectionContext = createContext<ProjectionConfig | null>(null)

export function ProjectionProvider({
  children,
  value,
}: {
  children: ReactNode
  value: ProjectionConfig
}) {
  return (
    <ProjectionContext.Provider value={value}>
      {children}
    </ProjectionContext.Provider>
  )
}

export function useProjection(): ProjectionConfig {
  const ctx = useContext(ProjectionContext)
  if (!ctx) {
    throw new Error('useProjection must be used inside <ProjectionProvider>')
  }
  return ctx
}
