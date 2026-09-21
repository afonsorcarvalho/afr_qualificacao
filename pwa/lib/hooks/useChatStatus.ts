// lib/hooks/useChatStatus.ts
'use client'
import { useQuery } from '@tanstack/react-query'

export function useChatStatus() {
  const q = useQuery({
    queryKey: ['chat-status'],
    queryFn: async () => {
      const res = await fetch('/api/chat/status')
      if (!res.ok) return { enabled: false }
      return (await res.json()) as { enabled: boolean }
    },
    staleTime: Infinity,
    gcTime: Infinity,
    refetchOnWindowFocus: false,
  })
  return { enabled: q.data?.enabled ?? false, isLoading: q.isLoading }
}
