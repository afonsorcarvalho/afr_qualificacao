'use client'
import { useState } from 'react'
import { CloudDownload, CheckCircle2, Clock } from 'lucide-react'
import { ClienteLink } from './ClienteLink'
import { GlassCard } from '@/components/ui/GlassCard'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { SyncErrorBadge } from './SyncErrorBadge'

export interface ClienteItem {
  /** Chave local: id do servidor (string) ou `tmp:<uuid>`. */
  key: string
  /** Id real no servidor; ausente para cliente criado em campo ainda não enviado. */
  id?: number
  name: string
  vat?: string
  city?: string
  /** Baixado para uso offline (existe no banco local). */
  offline: boolean
  /** Criado/alterado aqui e ainda não enviado. */
  pendente: boolean
  /** Envio falhou (registro local em `erro`). */
  syncErro?: boolean
  syncError?: string
}

export function ClienteRow({
  cliente,
  onBaixar,
}: {
  cliente: ClienteItem
  onBaixar: (c: ClienteItem) => Promise<void>
}) {
  const [baixando, setBaixando] = useState(false)
  const [erro, setErro] = useState(false)
  const podeBaixar = !cliente.offline && cliente.id !== undefined

  async function baixar() {
    setBaixando(true)
    setErro(false)
    try {
      await onBaixar(cliente)
    } catch {
      setErro(true)
    } finally {
      setBaixando(false)
    }
  }

  return (
    <li className="flex items-stretch gap-2">
      <div className="min-w-0 flex-1">
        <ClienteLink to={{ id: cliente.key }} className="block">
          <GlassCard variant="hover" noPadding className="cursor-pointer p-3">
            <div className="flex items-center justify-between gap-2">
              <strong className="truncate text-sm text-foreground">{cliente.name}</strong>
              {cliente.offline && (
                <StatusBadge tone="done" size="sm">
                  <CheckCircle2 className="mr-1 inline h-3 w-3" aria-hidden />
                  Offline
                </StatusBadge>
              )}
            </div>
            <p className="mt-1 truncate text-sm text-muted-foreground">
              {[cliente.vat, cliente.city].filter(Boolean).join(' · ') || '—'}
            </p>
            {cliente.pendente && (
              <p className="mt-1 inline-flex items-center gap-1 text-xs text-warn">
                <Clock className="h-3 w-3" aria-hidden />
                Aguardando envio
              </p>
            )}
            {erro && <p className="mt-1 text-xs text-danger">Falha ao baixar. Tente de novo.</p>}
          </GlassCard>
        </ClienteLink>
        {cliente.syncErro && (
          <div className="mt-1">
            <SyncErrorBadge error={cliente.syncError} recordKey={cliente.key} recordKind="partner" />
          </div>
        )}
      </div>
      {podeBaixar && (
        <button
          type="button"
          aria-label={`Baixar ${cliente.name} para offline`}
          disabled={baixando}
          onClick={baixar}
          className="flex min-h-[44px] w-11 shrink-0 items-center justify-center rounded-md border border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50"
        >
          <CloudDownload className={baixando ? 'h-5 w-5 animate-pulse' : 'h-5 w-5'} aria-hidden />
        </button>
      )}
    </li>
  )
}
