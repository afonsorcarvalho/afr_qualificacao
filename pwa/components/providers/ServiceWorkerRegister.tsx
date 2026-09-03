'use client'

import { useEffect } from 'react'

/**
 * Registra o service worker gerado pelo `next-pwa`.
 *
 * O `register: true` do `next-pwa` 5.6 só injeta o script de registro pelo
 * Pages Router (`_app`); com o App Router o `sw.js` é gerado em `public/` mas
 * ninguém o registra — o app servia manifesto e ícones sem nunca ficar
 * instalável nem offline. Em desenvolvimento o `next-pwa` desliga a geração
 * (`disable: NODE_ENV === 'development'`), então aqui também não registramos:
 * um `sw.js` inexistente só encheria o console de 404.
 */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production') return
    if (!('serviceWorker' in navigator)) return

    const register = () => {
      navigator.serviceWorker.register('/sw.js').catch((err) => {
        console.warn('[pwa] falha ao registrar o service worker:', err)
      })
    }

    if (document.readyState === 'complete') {
      register()
    } else {
      window.addEventListener('load', register)
      return () => window.removeEventListener('load', register)
    }
  }, [])

  return null
}
