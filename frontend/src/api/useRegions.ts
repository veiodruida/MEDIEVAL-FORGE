import { useQuery } from '@tanstack/react-query'
import type { RegionInfo } from '../types/region'

export function useRegions() {
  return useQuery<RegionInfo[]>({
    queryKey: ['v3', 'regions'],
    queryFn: async () => {
      const res = await fetch('/api/v3/regions')
      if (!res.ok) throw new Error(`failed to load regions (${res.status})`)
      return res.json()
    },
  })
}
