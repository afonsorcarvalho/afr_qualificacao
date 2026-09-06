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
 * ESCOPO. O app é servido no MESMO domínio do Odoo do cliente
 * (`labquali.afrsistemas.com.br/tecnico`), atrás do Apache que já atende o
 * backend. Registrado na raiz, o service worker interceptaria também as
 * páginas do Odoo e passaria a servi-las do cache — por isso o escopo é
 * `/tecnico/`. Um script em `/sw.js` pode reivindicar escopo mais estreito
 * que a própria pasta sem header nenhum; o caminho contrário é que exigiria
 * `Service-Worker-Allowed`.
 *
 * `NEXT_PUBLIC_SW_SCOPE` existe para o dia em que o PWA ganhar subdomínio
 * próprio: lá o escopo passa a ser `/`.
 */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production') return
    if (!('serviceWorker' in navigator)) return

    const register = () => {
      const scope = process.env.NEXT_PUBLIC_SW_SCOPE || '/tecnico/'
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
