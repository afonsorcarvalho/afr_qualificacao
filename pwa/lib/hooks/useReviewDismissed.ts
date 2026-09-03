'use client'
import { useCallback, useEffect, useState } from 'react'

const KEY = (relId: number) => `groq-review-dismissed-${relId}`

export interface DismissedIssue {
  item_id: number | null
  type: string
}

function read(relId: number): DismissedIssue[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(KEY(relId))
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed)
      ? parsed.filter((d) => d && typeof d.type === 'string')
      : []
  } catch {
    return []
  }
}

function write(relId: number, list: DismissedIssue[]) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(KEY(relId), JSON.stringify(list))
  } catch {
    /* quota / privacy mode → ignora */
  }
}

export function isDismissed(list: DismissedIssue[], d: DismissedIssue): boolean {
  return list.some((x) => x.type === d.type && x.item_id === d.item_id)
}

export function useReviewDismissed(relId: number) {
  const [list, setList] = useState<DismissedIssue[]>([])

  useEffect(() => {
    if (!relId) return
    setList(read(relId))
  }, [relId])

  const dismiss = useCallback((d: DismissedIssue) => {
    setList((prev) => {
      if (isDismissed(prev, d)) return prev
      const next = [...prev, d]
      write(relId, next)
      return next
    })
  }, [relId])

  const restore = useCallback((d: DismissedIssue) => {
    setList((prev) => {
      const next = prev.filter((x) => !(x.type === d.type && x.item_id === d.item_id))
      write(relId, next)
      return next
    })
  }, [relId])

  const clear = useCallback(() => {
    setList([])
    write(relId, [])
  }, [relId])

  return { dismissed: list, dismiss, restore, clear, isDismissed: (d: DismissedIssue) => isDismissed(list, d) }
}
