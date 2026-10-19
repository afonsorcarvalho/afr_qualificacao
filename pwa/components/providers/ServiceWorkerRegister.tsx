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
 *
 * ESCOPO. Padrão `/`: o PWA agora atende também `/cliente`, fora de
 * `/tecnico/`, e precisa funcionar offline. As regras de runtimeCaching do
 * `next.config.mjs` só tratam navegações do próprio app e deixam `/api/` em
 * NetworkOnly (ver spec §8.3).
 *
 * `NEXT_PUBLIC_SW_SCOPE` existe para o dia em que o PWA precisar restringir o escopo
 * (ex.: `/tecnico/`).
 */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production') return
    if (!('serviceWorker' in navigator)) return

    const register = () => {
      const scope = process.env.NEXT_PUBLIC_SW_SCOPE || '/'
      navigator.serviceWorker.register('/sw.js', { scope }).catch((err) => {
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
