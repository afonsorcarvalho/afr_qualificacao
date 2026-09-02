'use client'

import { useEffect } from 'react'

/**
 * Captura erros não-tratados do browser (window.onerror + unhandledrejection)
 * e também console.error(), e envia para /api/debug-log.
 * O endpoint imprime tudo no stdout do Next, visível em /tmp/next-dev.log.
 */
export function ErrorReporter() {
  useEffect(() => {
    if (typeof window === 'undefined') return

    let sending = false
    const queue: Array<Record<string, unknown>> = []

    const flush = () => {
      if (sending || queue.length === 0) return
      sending = true
      const batch = queue.splice(0, queue.length)
      Promise.all(
        batch.map((p) =>
          fetch('/api/debug-log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(p),
            keepalive: true,
          }).catch(() => {})
        )
      ).finally(() => {
        sending = false
        if (queue.length > 0) flush()
      })
    }

    const base = () => ({
      url: window.location.href,
      userAgent: navigator.userAgent,
      timestamp: Date.now(),
    })

    const onError = (e: ErrorEvent) => {
      queue.push({
        ...base(),
        kind: 'error',
        message: e.message,
        source: e.filename,
        lineno: e.lineno,
        colno: e.colno,
        stack: e.error?.stack ?? String(e.error),
      })
      flush()
    }

    const onRejection = (e: PromiseRejectionEvent) => {
      const r = e.reason
      queue.push({
        ...base(),
        kind: 'unhandledrejection',
        message: typeof r === 'string' ? r : r?.message ?? JSON.stringify(r),
        stack: r?.stack,
      })
      flush()
    }

    // Patch console.error para ecoar para o servidor
    const origError = console.error.bind(console)
    const origWarn  = console.warn.bind(console)

    console.error = (...args: unknown[]) => {
      origError(...args)
      try {
        // Ignora bailout esperado de useSearchParams sem Suspense em prerender
        const digest = args.find((a) => a instanceof Error)
        if (digest && (digest as Error & { digest?: string }).digest === 'BAILOUT_TO_CLIENT_SIDE_RENDERING') return

        queue.push({
          ...base(),
          kind: 'console.error',
          message: args
            .map((a) => {
              if (a instanceof Error) return `${a.message}\n${a.stack}`
              if (typeof a === 'string') return a
              try { return JSON.stringify(a) } catch { return String(a) }
            })
            .join(' '),
        })
        flush()
      } catch { /* noop */ }
    }

    console.warn = (...args: unknown[]) => {
      origWarn(...args)
      try {
        queue.push({
          ...base(),
          kind: 'console.warn',
          message: args
            .map((a) => (typeof a === 'string' ? a : JSON.stringify(a)))
            .join(' '),
        })
        flush()
      } catch { /* noop */ }
    }

    window.addEventListener('error', onError)
    window.addEventListener('unhandledrejection', onRejection)

    return () => {
      window.removeEventListener('error', onError)
      window.removeEventListener('unhandledrejection', onRejection)
      console.error = origError
      console.warn = origWarn
    }
  }, [])

  return null
}
