// lib/hooks/useGroqStatus.ts
'use client'
import { useQuery } from '@tanstack/react-query'

export function useGroqStatus() {
  const q = useQuery({
    queryKey: ['groq-status'],
    queryFn: async () => {
      const res = await fetch('/api/groq/status')
      if (!res.ok) return { enabled: false }
      return (await res.json()) as { enabled: boolean }
    },
    staleTime: Infinity,
    gcTime: Infinity,
    refetchOnWindowFocus: false,
  })
  return { enabled: q.data?.enabled ?? false, isLoading: q.isLoading }
}
