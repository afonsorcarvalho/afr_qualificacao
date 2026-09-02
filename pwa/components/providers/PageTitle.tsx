'use client'

import { useEffect } from 'react'
import { useAuthStore } from '@/lib/store/authStore'

export function PageTitle() {
  const companyName = useAuthStore((s) => s.companyName)

  useEffect(() => {
    document.title = companyName ? `frontend - ${companyName}` : 'frontend'
  }, [companyName])

  return null
}
