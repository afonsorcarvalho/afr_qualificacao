'use client'
import { clsx } from 'clsx'
import { AlertTriangle } from 'lucide-react'
import type { CargaTecnico, UsoInstrumento } from './carga'

export type Dimensao = 'tecnico' | 'instrumento'

const LINHA = 'flex min-h-[44px] w-full items-center gap-3 rounded-md px-3 py-1.5 text-left text-sm'

/**
 * Envolve cada linha. Sem alvo ativo (nenhuma visita em ajuste, ou usuário sem
 * `can_manage`) a linha é texto: oferecer toque que não faz nada é pior que não
 * oferecer.
 */
function Linha({
  ativo, pressionado, aoTocar, children, className,
}: {
  ativo: boolean
  pressionado?: boolean
  aoTocar: () => void
  children: React.ReactNode
  className?: string
}) {
  if (!ativo) return <div className={clsx(LINHA, className)}>{children}</div>
  return (
    <button
      type="button"
      aria-pressed={pressionado ?? false}
      onClick={aoTocar}
      className={clsx(LINHA, 'hover:bg-accent', pressionado && 'bg-accent', className)}
    >
      {children}
    </button>
  )
}

export function PainelRecursos({
  dimensao,
  onTrocarDimensao,
  tecnicos,
  instrumentos,
  instrumentoIdsDaVisita,
  tecnicoIdDaVisita,
  alvoAtivo,
  onTocarTecnico,
  onTocarInstrumento,
}: {
  dimensao: Dimensao
  onTrocarDimensao: (d: Dimensao) => void
  tecnicos: CargaTecnico[]
  instrumentos: UsoInstrumento[]
  instrumentoIdsDaVisita: number[]
  /** Dono atual da visita em ajuste — marca a linha do técnico correspondente. */
  tecnicoIdDaVisita?: number
  alvoAtivo: boolean
  onTocarTecnico: (id: number) => void
  onTocarInstrumento: (id: number) => void
}) {
  // Escala relativa ao mais cheio da vista: o modelo não define jornada padrão,
  // e fixar 8h aqui seria número fingido.
  const pico = Math.max(1, ...tecnicos.map((t) => t.horas))
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex gap-1 border-b border-border p-1">
        {(['tecnico', 'instrumento'] as const).map((d) => (
          <button
            key={d}
            type="button"
            aria-pressed={dimensao === d}
            onClick={() => onTrocarDimensao(d)}
            className={clsx(
              'min-h-[44px] flex-1 rounded-md text-sm',
              dimensao === d ? 'bg-accent font-semibold' : 'text-muted-foreground',
            )}
          >
            {d === 'tecnico' ? 'Técnico' : 'Instrumento'}
          </button>
        ))}
      </div>

      <div className="p-1">
        {dimensao === 'tecnico' && tecnicos.map((t) => (
          <Linha
            key={t.id}
            ativo={alvoAtivo}
            pressionado={t.id === tecnicoIdDaVisita}
            aoTocar={() => onTocarTecnico(t.id)}
          >
            <span className="w-28 shrink-0 truncate">{t.name}</span>
            <span className="h-2 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden>
              <span
                className="block h-full rounded-full bg-primary"
                style={{ width: `${(t.horas / pico) * 100}%` }}
              />
            </span>
            <span className="w-16 shrink-0 text-right text-xs text-muted-foreground">
              {t.horas > 0 ? `${Number(t.horas.toFixed(1))}h` : 'livre'}
            </span>
          </Linha>
        ))}

        {dimensao === 'instrumento' && instrumentos.map((i) => (
          <Linha
            key={i.id}
            ativo={alvoAtivo}
            pressionado={instrumentoIdsDaVisita.includes(i.id)}
            aoTocar={() => onTocarInstrumento(i.id)}
          >
            <span className="w-20 shrink-0 truncate">{i.name}</span>
            {i.usos.length === 0 ? (
              <span className="min-w-0 flex-1 text-xs text-muted-foreground">livre</span>
            ) : (
              // Uma linha por uso, nunca uma string concatenada: o horário é o
              // que prova que o instrumento não está livre naquela faixa, e
              // truncar a linha inteira (Fix round 1, item 2) podia esconder
              // um turno inteiro atrás de "…". A faixa fica sempre visível;
              // só o nome da OS/técnico trunca por linha.
              <span className="flex min-w-0 flex-1 flex-col gap-0.5 text-xs text-muted-foreground">
                {i.usos.map((u) => (
                  <span key={u.visitaId} className="flex min-w-0 items-baseline gap-1">
                    <span className="shrink-0">{u.faixa}</span>
                    <span className="min-w-0 truncate">· {u.osName}/{u.tecnicoName}</span>
                  </span>
                ))}
              </span>
            )}
            {/* O aviso é dito em texto, não só em cor: cor sozinha não chega a
                quem não a distingue, e o card fica em tela pequena ao sol. */}
            {i.vencido && (
              <span className="flex shrink-0 items-center gap-1 text-xs text-danger">
                <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
                calibração vencida
              </span>
            )}
          </Linha>
        ))}
      </div>
    </div>
  )
}
