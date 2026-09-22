'use client'
import { User, Wrench, Lock, AlertTriangle, Clock, MapPin } from 'lucide-react'
import { clsx } from 'clsx'
import type { VisitaAgenda } from '@/lib/odoo/agenda'
import { corDoTecnico, corDoInstrumento } from '../agenda/mes'

/** 8.5 → "08:30". Horas fracionárias do Odoo, sem tocar no fuso. */
export function horaOdoo(h: number): string {
  const hh = Math.floor(h)
  const mm = Math.round((h - hh) * 60)
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
}

function Corpo({
  visita,
  tecnicoColorPorId,
  instrumentoColorPorId,
}: {
  visita: VisitaAgenda
  tecnicoColorPorId?: Map<number, number | undefined>
  instrumentoColorPorId?: Map<number, number | undefined>
}) {
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
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <User
            className="h-3.5 w-3.5 shrink-0"
            style={{ color: corDoTecnico(visita.tecnico_id, tecnicoColorPorId?.get(visita.tecnico_id === false ? -1 : visita.tecnico_id)) }}
            aria-hidden
          />
          {visita.tecnico_name}
        </p>
      )}
      {/* Metadado secundário: equipamento fica texto puro (padrão do
          InstrumentBadges vizinho, "Ciclo:", "Malha:"), fora do escopo desta
          task. Instrumento ganhou ícone+cor por item logo abaixo. */}
      {visita.equipment_list.length > 0 && (
        <p className="truncate text-xs text-muted-foreground">
          Equip.: {visita.equipment_list.join(', ')}
        </p>
      )}
      {visita.instrument_list.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
          {visita.instrument_list.map((nome, idx) => {
            const id = visita.instrument_ids[idx]
            return (
              <span key={id ?? nome} className="flex min-w-0 items-center gap-1">
                <Wrench
                  className="h-3.5 w-3.5 shrink-0"
                  style={{ color: corDoInstrumento(id, instrumentoColorPorId?.get(id)) }}
                  aria-hidden
                />
                <span className="truncate">{nome}</span>
              </span>
            )
          })}
        </div>
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
  onAjustar,
  emAjuste = false,
  tecnicoColorPorId,
  instrumentoColorPorId,
}: {
  visita: VisitaAgenda
  onSelect: (visita: VisitaAgenda) => void
  /** Só o modo Semana passa isto; sem ele, não há botão. */
  onAjustar?: (visita: VisitaAgenda) => void
  emAjuste?: boolean
  /** Índice `color` configurado no Odoo, por id — vem do roster/catálogo de `page.tsx`. */
  tecnicoColorPorId?: Map<number, number | undefined>
  instrumentoColorPorId?: Map<number, number | undefined>
}) {
  const base = 'flex w-full min-h-[44px] flex-col gap-1 rounded-lg border border-border bg-card p-3 text-left'
  // `lock_reason` é frase pronta do servidor. O front não decide nada aqui —
  // se decidisse, a regra viveria em dois lugares.
  if (!visita.editable) {
    return (
      <div className={clsx(base, 'opacity-70')}>
        <Corpo visita={visita} tecnicoColorPorId={tecnicoColorPorId} instrumentoColorPorId={instrumentoColorPorId} />
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Lock className="h-3.5 w-3.5 shrink-0" aria-hidden />
          {visita.lock_reason}
        </p>
      </div>
    )
  }
  return (
    <div className={clsx('flex flex-col gap-1', emAjuste && 'rounded-lg ring-2 ring-primary')}>
      <button type="button" onClick={() => onSelect(visita)} className={clsx(base, 'hover:bg-accent')}>
        <Corpo visita={visita} tecnicoColorPorId={tecnicoColorPorId} instrumentoColorPorId={instrumentoColorPorId} />
      </button>
      {onAjustar && (
        <button
          type="button"
          onClick={() => onAjustar(visita)}
          className="min-h-[44px] rounded-md border border-border px-3 text-sm font-medium"
        >
          {emAjuste ? 'Concluir' : 'Ajustar'}
        </button>
      )}
    </div>
  )
}
