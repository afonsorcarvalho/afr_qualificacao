'use client'
import { VisitaCard } from '../_components/VisitaCard'
import { GradeMes } from './_GradeMes'
import { corDoTecnico, corDoInstrumento, COR_SEM_TECNICO } from './mes'
import type { PontosDia, PontosInstrumentoDia, PontoInstrumento } from './mes'
import type { UsoInstrumento } from './carga'
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
  instrumentos,
  usoInstrumentosDia,
  ancora,
  hoje,
  diaSel,
  onSelecionarDia,
  roster,
  podeAjustar,
  emAjuste,
  alvoAtivo,
  onAjustar,
  onAlternarAjuste,
  erroAjuste,
  onSelecionarVisita,
}: {
  visitas: VisitaAgenda[]
  dias: PontosDia[]
  /** Instrumentos usados por dia, nos 42 dias da grade (`instrumentosPorDia`). */
  instrumentos: PontosInstrumentoDia[]
  /**
   * Usos do instrumento no dia SELECIONADO, já filtrados para quem tem uso
   * (`usoPorInstrumento` de `carga.ts`, a mesma agregação do painel da
   * Semana) — a seção "Instrumentos do dia" só lista quem está de fato
   * marcado, ao contrário do painel da Semana, que também mostra "livre".
   */
  usoInstrumentosDia: UsoInstrumento[]
  ancora: string
  hoje: string | null
  diaSel: string
  onSelecionarDia: (date: string) => void
  /** Roster já unificado (`rosterTecnicos`) — fonte da legenda. */
  roster: Opcao[]
  podeAjustar: boolean
  /** Visita em ajuste, já resincronizada com o payload (ou `null`). */
  emAjuste: VisitaAgenda | null
  /**
   * `true` só quando a visita em ajuste está DENTRO da grade visível. Separado
   * de `emAjuste` porque o card (anel + "Concluir") continua marcando a visita
   * armada onde quer que ela esteja, enquanto o toque num dia só pode gravar
   * enquanto o alvo está à vista — navegar de mês com uma visita armada
   * reagendava a visita no primeiro toque, em silêncio (fix round 2, achado 2).
   */
  alvoAtivo: boolean
  /** Toque num dia da grade com visita em ajuste: grava `{ date }`. */
  onAjustar: (vals: VisitaVals) => void
  /** Toque em "Ajustar"/"Concluir" no card: liga/desliga o ajuste daquela visita. */
  onAlternarAjuste: (visita: VisitaAgenda) => void
  erroAjuste: string
  onSelecionarVisita: (visita: VisitaAgenda) => void
}) {
  // Legenda: só técnico com visita na janela visível (os 42 dias da
  // grade) — o roster inteiro pode ter gente sem nenhuma visita na janela, e
  // um chip por cada um deles é ruído puro, não informação (brief 3d).
  // "Sem técnico" entra à parte, no fim, só quando alguma visita DA JANELA
  // (os 42 dias, inclusive o transbordo esmaecido pros meses vizinhos que a
  // própria grade desenha) não tem `tecnico_id` — mesmo escopo dos chips
  // de técnico acima, não só o mês estrito.
  const idsNaJanela = new Set(dias.flatMap((d) => d.pontos.map((p) => p.id)))
  const legenda = roster.filter((t) => idsNaJanela.has(t.id))
  const temSemTecnico = idsNaJanela.has(false)

  // Legenda de instrumentos: mesmo critério da de técnicos, "usado nos 42
  // dias da janela", não o mês estrito. Sem `roster` equivalente pra
  // instrumento (a página não passa `pwa_instrumento_options` cru pra cá —
  // ruling do controlador, este componente só recebe dados já agregados),
  // a lista distinta sai de `instrumentos` mesmo, deduplicada por id — nome
  // e cor já são estáveis por id (`corDoInstrumento`), então dedupar por id
  // não perde nem embaralha informação. Ordenada por nome (`localeCompare`
  // pt-BR) DEPOIS do dedupe, mesmo padrão de `rosterTecnicos` em
  // `carga.ts` — sem o sort, a ordem seria a de primeira aparição
  // cronológica pelos 42 dias da grade, que reordena a cada navegação de
  // mês conforme o conjunto de instrumentos usados muda (fix round 1,
  // achado 2: `PontoInstrumento` já carrega `name`, não é preciso nenhuma
  // prop nova pra isso).
  const legendaInstrumentos: PontoInstrumento[] = []
  const idsInstrumentoNaLegenda = new Set<number>()
  for (const d of instrumentos) {
    for (const inst of d.instrumentos) {
      if (idsInstrumentoNaLegenda.has(inst.id)) continue
      idsInstrumentoNaLegenda.add(inst.id)
      legendaInstrumentos.push(inst)
    }
  }
  legendaInstrumentos.sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'))

  const doDia = visitas.filter((v) => v.date === diaSel)

  return (
    <>
      <GradeMes
        dias={dias}
        instrumentos={instrumentos}
        ancora={ancora}
        hoje={hoje}
        selecionado={diaSel}
        onSelecionar={(date) => (alvoAtivo ? onAjustar({ date }) : onSelecionarDia(date))}
      />

      {/* As duas faixas (técnico e instrumento) leem igual: rótulo curto +
          lista, `role="group"`/`aria-labelledby` ligando cada uma ao seu
          próprio rótulo de forma programática, não só por ordem de leitura
          no DOM — um leitor de tela anuncia o grupo pelo nome antes de
          entrar nos itens, em vez de só concatenar "Técnicos: Ana Silva,
          Instrumentos: Q001" num fluxo só (fix round 1, achado 3). O
          rótulo em si é ganho de clareza de domínio, não correção de a11y:
          cada chip já carrega o nome em texto puro, então cor/forma nunca
          foram o único portador por item — só a fronteira ENTRE os dois
          grupos era ambígua sem ele. */}
      {(legenda.length > 0 || temSemTecnico) && (
        <div
          role="group"
          aria-labelledby="legenda-mes-tecnicos"
          className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1 text-xs text-muted-foreground"
        >
          <span id="legenda-mes-tecnicos" className="font-medium text-foreground">
            Técnicos:
          </span>
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

      {/* Segunda faixa, só de instrumento — mesma regra da de técnico:
          nada de rótulo órfão quando nenhum instrumento tem uso na janela
          visível (brief 3b). */}
      {legendaInstrumentos.length > 0 && (
        <div
          role="group"
          aria-labelledby="legenda-mes-instrumentos"
          className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1 text-xs text-muted-foreground"
        >
          <span id="legenda-mes-instrumentos" className="font-medium text-foreground">
            Instrumentos:
          </span>
          {legendaInstrumentos.map((inst) => (
            <span key={inst.id} className="flex items-center gap-1.5">
              <svg aria-hidden className="h-2 w-2 shrink-0" viewBox="0 0 10 10">
                <polygon points="5,0.5 9.5,9.5 0.5,9.5" fill={inst.cor} />
              </svg>
              {inst.name}
            </span>
          ))}
        </div>
      )}

      {erroAjuste && <p className="text-sm text-danger">{erroAjuste}</p>}

      {/* "Instrumentos do dia" (brief 3c): acima dos `VisitaCard`s, uma
          linha por instrumento com uso no dia selecionado, com o triângulo
          da cor, o nome e os usos (OS + faixa de horário) — reusa
          `usoPorInstrumento` de `carga.ts`, já filtrado pela página pra só
          quem tem uso. Sem instrumento no dia, a seção nem aparece: o
          "Nenhuma visita neste dia." abaixo já cobre o dia vazio.
          Deliberadamente sem aviso de calibração vencida, mesmo que
          `UsoInstrumento.vencido` esteja disponível — fora de escopo por
          escolha do usuário (brief). */}
      {usoInstrumentosDia.length > 0 && (
        <div className="space-y-1 rounded-lg border border-border bg-card p-2">
          <h3 className="px-1 text-xs font-semibold uppercase text-muted-foreground">
            Instrumentos do dia
          </h3>
          {usoInstrumentosDia.map((i) => (
            <div key={i.id} className="flex min-h-[44px] items-start gap-2 px-1 py-1 text-sm">
              <svg aria-hidden className="mt-1.5 h-2 w-2 shrink-0" viewBox="0 0 10 10">
                <polygon points="5,0.5 9.5,9.5 0.5,9.5" fill={corDoInstrumento(i.id)} />
              </svg>
              <span className="w-20 shrink-0 truncate font-medium">{i.name}</span>
              <span className="flex min-w-0 flex-1 flex-col gap-0.5 text-xs text-muted-foreground">
                {i.usos.map((u) => (
                  <span key={u.visitaId} className="flex min-w-0 items-baseline gap-1">
                    <span className="shrink-0">{u.faixa}</span>
                    <span className="min-w-0 truncate">· {u.osName}/{u.tecnicoName}</span>
                  </span>
                ))}
              </span>
            </div>
          ))}
        </div>
      )}

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
