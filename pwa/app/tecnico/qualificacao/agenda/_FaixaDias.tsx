'use client'
import { clsx } from 'clsx'
import type { CargaDia } from './carga'

/** "2026-09-17" → { sigla: "qua", num: "17" }, em UTC. */
function rotulo(iso: string) {
  const [a, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(a, m - 1, d))
  return {
    sigla: new Intl.DateTimeFormat('pt-BR', { weekday: 'short', timeZone: 'UTC' })
      .format(dt).replace('.', ''),
    num: String(d).padStart(2, '0'),
  }
}

/** Horas com no máximo uma casa, sem ".0" pendurado. */
function horasCurtas(h: number): string {
  return `${Number(h.toFixed(1))}h`
}

export function FaixaDias({
  dias,
  selecionado,
  onSelecionar,
}: {
  dias: CargaDia[]
  selecionado: string
  onSelecionar: (date: string) => void
}) {
  return (
    <div className="flex gap-1 rounded-lg border border-border bg-card p-1">
      {dias.map((d) => {
        const { sigla, num } = rotulo(d.date)
        const ativo = d.date === selecionado
        return (
          <button
            key={d.date}
            type="button"
            aria-pressed={ativo}
            aria-label={`${sigla} ${num}, ${horasCurtas(d.horas)}${d.conflito ? ', com conflito' : ''}`}
            onClick={() => onSelecionar(d.date)}
            className={clsx(
              'flex min-h-[44px] flex-1 flex-col items-center justify-center rounded-md px-0.5 py-1',
              ativo ? 'bg-accent font-semibold text-foreground' : 'text-muted-foreground',
            )}
          >
            <span className="text-[10px] uppercase leading-none">{sigla}</span>
            <span className="text-sm leading-tight">{num}</span>
            {/* Dia vazio não escreve "0h": ruído que compete com o que tem carga. */}
            <span className={clsx('text-[10px] leading-none', d.conflito && 'text-danger')}>
              {d.horas > 0 ? horasCurtas(d.horas) : '—'}
            </span>
          </button>
        )
      })}
    </div>
  )
}
