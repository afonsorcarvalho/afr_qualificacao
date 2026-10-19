'use client'
import { Clock, ImageOff } from 'lucide-react'
import { ClienteLink } from './ClienteLink'
import { GlassCard } from '@/components/ui/GlassCard'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { SyncErrorBadge } from './SyncErrorBadge'

export interface EquipCardData {
  key: string
  titulo: string
  detalhe: string
  capaUrl?: string
  ciclos: number
  semPlaqueta: boolean
  sync: 'ok' | 'pendente' | 'erro'
  syncError?: string
}

export function EquipCard({ clienteKey, eq }: { clienteKey: string; eq: EquipCardData }) {
  return (
    <li className="space-y-1">
      <ClienteLink to={{ id: clienteKey, eq: eq.key }} className="block">
        <GlassCard variant="hover" noPadding className="cursor-pointer p-3">
          <div className="flex items-center gap-3">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted">
              {eq.capaUrl ? (
                // Blob local (miniatura/foto do aparelho): next/image não otimiza object URL.
                // eslint-disable-next-line @next/next/no-img-element
                <img src={eq.capaUrl} alt="" className="h-full w-full object-cover" />
              ) : (
                <ImageOff className="h-5 w-5 text-muted-foreground" aria-hidden />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <strong className="block truncate text-sm text-foreground">{eq.titulo}</strong>
              <p className="truncate text-sm text-muted-foreground">{eq.detalhe || '—'}</p>
              <p className="text-xs text-muted-foreground">
                {eq.ciclos === 1 ? '1 ciclo' : `${eq.ciclos} ciclos`}
              </p>
            </div>
          </div>
          {(eq.semPlaqueta || eq.ciclos === 0 || eq.sync === 'pendente') && (
            <div className="mt-2 flex flex-wrap gap-1">
              {eq.semPlaqueta && <StatusBadge tone="waiting">sem foto plaqueta</StatusBadge>}
              {eq.ciclos === 0 && <StatusBadge tone="waiting">sem ciclos</StatusBadge>}
              {eq.sync === 'pendente' && (
                <span className="inline-flex items-center gap-1 text-xs text-warn">
                  <Clock className="h-3 w-3" aria-hidden />
                  Aguardando envio
                </span>
              )}
            </div>
          )}
        </GlassCard>
      </ClienteLink>
      {eq.sync === 'erro' && <SyncErrorBadge error={eq.syncError} recordKey={eq.key} recordKind="equipment" />}
    </li>
  )
}
