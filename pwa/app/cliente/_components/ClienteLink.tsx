'use client'
import type { ReactNode } from 'react'
import { clienteUrl, goCliente, type ClienteNavState } from '@/lib/cliente/nav'

/** Link entre estados de `/cliente`: `pushState`, sem buscar RSC. Ctrl/meta-clique abre em nova aba. */
export function ClienteLink({
  to, children, className, ...rest
}: { to: ClienteNavState; children: ReactNode; className?: string; 'aria-label'?: string }) {
  return (
    <a
      href={clienteUrl(to)}
      className={className}
      {...rest}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
        e.preventDefault()
        goCliente(to)
      }}
    >
      {children}
    </a>
  )
}
