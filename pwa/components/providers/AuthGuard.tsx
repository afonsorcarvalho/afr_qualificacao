'use client'

import { useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { odooClient } from '@/lib/odoo/client'
import { useAuthStore } from '@/lib/store/authStore'
import { preloadSchemas } from '@/lib/odoo/schema'
import { buildPostLogoutLoginPath } from '@/lib/utils/loginUrlParams'

const PUBLIC_PATHS = ['/login']

async function forceLogout() {
  try {
    await odooClient.logout()
  } catch {
    // Se o servidor estiver offline, destrói o cookie manualmente via proxy
    try {
      await fetch('/api/odoo/web/session/destroy', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} }),
      })
    } catch {
      /* noop */
    }
  }
  useAuthStore.getState().logout()
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const [hydrated, setHydrated] = useState(false)
  const [checked, setChecked] = useState(false)

  const isPublic = PUBLIC_PATHS.some((p) => pathname?.startsWith(p))

  useEffect(() => {
    if (useAuthStore.persist.hasHydrated()) {
      setHydrated(true)
      return
    }
    const unsub = useAuthStore.persist.onFinishHydration(() => setHydrated(true))
    return () => unsub()
  }, [])

  useEffect(() => {
    if (!hydrated || isPublic) return

    let cancelled = false
    const { serverUrl, dbName } = useAuthStore.getState()
    const loginPath = buildPostLogoutLoginPath(serverUrl, dbName)

    if (!serverUrl) {
      forceLogout().finally(() => {
        if (!cancelled) router.replace(loginPath)
      })
      return () => {
        cancelled = true
      }
    }

    async function validate() {
      try {
        const info = await odooClient.getSession()
        if (cancelled) return
        if (!info || !info.uid) {
          await forceLogout()
          if (!cancelled) router.replace(loginPath)
          return
        }
        try { await preloadSchemas() } catch { /* tolera falhas de rede */ }
        if (!cancelled) setChecked(true)
      } catch {
        await forceLogout()
        if (!cancelled) router.replace(loginPath)
      }
    }

    validate()
    return () => {
      cancelled = true
    }
  }, [hydrated, pathname, isPublic, router])

  if (isPublic) return <>{children}</>
  if (hydrated && checked) return <>{children}</>

  return (
    <div className="fixed inset-0 flex items-center justify-center pointer-events-none">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-white" />
    </div>
  )
}
