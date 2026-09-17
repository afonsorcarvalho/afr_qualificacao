'use client'
import { VisitaCard } from '../_components/VisitaCard'
import { GradeMes } from './_GradeMes'
import { corDoTecnico, COR_SEM_TECNICO } from './mes'
import type { PontosDia } from './mes'
import type { VisitaAgenda, VisitaVals, Opcao } from '@/lib/odoo/agenda'

/**
 * Modo Mês — monta o que a `page.tsx` já calculou: `GradeMes` + legenda de
 * técnicos + os `VisitaCard`s do dia selecionado. Sem hooks de dados, sem
 * fetch, sem estado de janela/âncora — tudo isso mora na página (ver ruling
 * do controlador no brief: passar `ancoraMes` para cá só para este
 * componente escrever de volta inverteria o fluxo de dados dos outros
 * modos).
 */
export function VistaMes({
  visitas,
  dias,
  ancora,
  hoje,
  diaSel,
  onSelecionarDia,
  roster,
  podeAjustar,
  emAjuste,
  onAjustar,
  onAlternarAjuste,
  erroAjuste,
  onSelecionarVisita,
}: {
  visitas: VisitaAgenda[]
  dias: PontosDia[]
  ancora: string
  hoje: string | null
  diaSel: string
  onSelecionarDia: (date: string) => void
  /** Roster já unificado (`rosterTecnicos`) — fonte da legenda. */
  roster: Opcao[]
  podeAjustar: boolean
  /** Visita em ajuste, já resincronizada com o payload (ou `null`). */
  emAjuste: VisitaAgenda | null
  /** Toque num dia da grade com visita em ajuste: grava `{ date }`. */
  onAjustar: (vals: VisitaVals) => void
  /** Toque em "Ajustar"/"Concluir" no card: liga/desliga o ajuste daquela visita. */
  onAlternarAjuste: (visita: VisitaAgenda) => void
  erroAjuste: string
  onSelecionarVisita: (visita: VisitaAgenda) => void
}) {
  // Legenda: só técnico com visita na janela visível (os 42 dias da
  // grade) — o roster inteiro pode ter gente sem nenhuma visita no mês, e
  // um chip por cada um deles é ruído puro, não informação (brief 3d).
  // "Sem técnico" entra à parte, no fim, só quando alguma visita do mês não
  // tem `tecnico_id`.
  const idsNaJanela = new Set(dias.flatMap((d) => d.pontos.map((p) => p.id)))
  const legenda = roster.filter((t) => idsNaJanela.has(t.id))
  const temSemTecnico = idsNaJanela.has(false)

  const doDia = visitas.filter((v) => v.date === diaSel)

  return (
    <>
      <GradeMes
        dias={dias}
        ancora={ancora}
        hoje={hoje}
        selecionado={diaSel}
        onSelecionar={(date) => (emAjuste ? onAjustar({ date }) : onSelecionarDia(date))}
      />

      {(legenda.length > 0 || temSemTecnico) && (
        <div className="flex flex-wrap gap-x-3 gap-y-1 px-1 text-xs text-muted-foreground">
          {legenda.map((t) => (
            <span key={t.id} className="flex items-center gap-1.5">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: corDoTecnico(t.id) }}
                aria-hidden
              />
              {t.name}
            </span>
          ))}
          {temSemTecnico && (
            <span className="flex items-center gap-1.5">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: COR_SEM_TECNICO }}
                aria-hidden
              />
              Sem técnico
            </span>
          )}
        </div>
      )}

      {erroAjuste && <p className="text-sm text-danger">{erroAjuste}</p>}

      {doDia.map((v) => (
        <VisitaCard
          key={v.id}
          visita={v}
          onSelect={onSelecionarVisita}
          onAjustar={podeAjustar ? onAlternarAjuste : undefined}
          emAjuste={emAjuste?.id === v.id}
        />
      ))}
      {doDia.length === 0 && (
        <p className="py-6 text-center text-muted-foreground">Nenhuma visita neste dia.</p>
      )}
    </>
  )
}
