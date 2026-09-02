'use client'
import { useCallback, useEffect, useState } from 'react'
import type { ReviewResponse } from '@/app/api/groq/review/route'

const KEY = (relId: number) => `groq-review-result-${relId}`

interface CachedReview {
  data: ReviewResponse
  fetched_at: number // epoch ms
}

function read(relId: number): CachedReview | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(KEY(relId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as CachedReview
    if (!parsed?.data || typeof parsed.fetched_at !== 'number') return null
    return parsed
  } catch {
    return null
  }
}

function write(relId: number, cached: CachedReview) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(KEY(relId), JSON.stringify(cached))
  } catch { /* quota → ignora */ }
}

export function useReviewCache(relId: number) {
  const [cached, setCached] = useState<CachedReview | null>(null)
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    if (!relId) {
      setHydrated(true)
      return
    }
    setCached(read(relId))
    setHydrated(true)
  }, [relId])

  const save = useCallback((data: ReviewResponse) => {
    const next: CachedReview = { data, fetched_at: Date.now() }
    setCached(next)
    write(relId, next)
  }, [relId])

  const clear = useCallback(() => {
    if (typeof window !== 'undefined') {
      try { window.localStorage.removeItem(KEY(relId)) } catch { /* ignora */ }
    }
    setCached(null)
  }, [relId])

  return {
    data: cached?.data ?? null,
    fetchedAt: cached?.fetched_at ?? null,
    hydrated,
    save,
    clear,
  }
}
