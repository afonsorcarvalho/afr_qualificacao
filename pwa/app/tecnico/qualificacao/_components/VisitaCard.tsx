'use client'
import { Lock, AlertTriangle, Clock, MapPin } from 'lucide-react'
import { clsx } from 'clsx'
import type { VisitaAgenda } from '@/lib/odoo/agenda'

/** 8.5 → "08:30". Horas fracionárias do Odoo, sem tocar no fuso. */
export function horaOdoo(h: number): string {
  const hh = Math.floor(h)
  const mm = Math.round((h - hh) * 60)
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
}

function Corpo({ visita }: { visita: VisitaAgenda }) {
  return (
    <>
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Clock className="h-4 w-4 shrink-0" aria-hidden />
        {horaOdoo(visita.time_start)}–{horaOdoo(visita.time_stop)}
        <span className="truncate">{visita.os_name}</span>
      </div>
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <MapPin className="h-4 w-4 shrink-0" aria-hidden />
        <span className="truncate">
          {visita.partner_name}
          {visita.city ? ` · ${visita.city}` : ''}
        </span>
      </div>
      {!visita.is_mine && (
        <p className="text-xs text-muted-foreground">Técnico: {visita.tecnico_name}</p>
      )}
      {visita.equipment_list.length > 0 && (
        <p className="truncate text-xs text-muted-foreground">
          {visita.equipment_list.join(', ')}
        </p>
      )}
      {visita.conflict && visita.conflict_msg && (
        <p className="flex items-start gap-1.5 text-xs text-danger">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          {visita.conflict_msg}
        </p>
      )}
    </>
  )
}

export function VisitaCard({
  visita,
  onSelect,
}: {
  visita: VisitaAgenda
  onSelect: (visita: VisitaAgenda) => void
}) {
  const base = 'flex w-full min-h-[44px] flex-col gap-1 rounded-lg border border-border bg-card p-3 text-left'
  // `lock_reason` é frase pronta do servidor. O front não decide nada aqui —
  // se decidisse, a regra viveria em dois lugares.
  if (!visita.editable) {
    return (
      <div className={clsx(base, 'opacity-70')}>
        <Corpo visita={visita} />
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Lock className="h-3.5 w-3.5 shrink-0" aria-hidden />
          {visita.lock_reason}
        </p>
      </div>
    )
  }
  return (
    <button type="button" onClick={() => onSelect(visita)} className={clsx(base, 'hover:bg-accent')}>
      <Corpo visita={visita} />
    </button>
  )
}
