'use client'
import { CloudOff } from 'lucide-react'
import type { ClienteNavState } from '@/lib/cliente/nav'
import { ClienteLink } from './ClienteLink'

/** Deep link para registro que não está no aparelho e não pôde ser buscado. */
export function EmptyOffline({ volta, voltaLabel }: { volta: ClienteNavState; voltaLabel: string }) {
  return (
    <div role="status" className="mx-auto flex max-w-[720px] flex-col items-center gap-3 py-8 text-center text-sm text-muted-foreground">
      <CloudOff className="h-6 w-6" aria-hidden />
      <p>Registro não disponível offline</p>
      <ClienteLink to={volta} className="text-primary underline">{voltaLabel}</ClienteLink>
    </div>
  )
}
