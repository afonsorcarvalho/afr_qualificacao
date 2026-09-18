'use client'
import { VisitaCard } from '../_components/VisitaCard'
import { GradeMes } from './_GradeMes'
import { corDoTecnico, COR_SEM_TECNICO } from './mes'
import type { PontosDia, PontosInstrumentoDia, PontoInstrumento } from './mes'
import type { InstrumentoDoDia } from './carga'
import type { VisitaAgenda, VisitaVals, Opcao } from '@/lib/odoo/agenda'

/**
 * Uma faixa de legenda: rótulo curto + lista de itens com a marca da frente.
 *
 * As duas faixas (técnico e instrumento) eram ~55 linhas de JSX quase
 * idêntico num componente de 232 — diferiam só no id do rótulo, no texto e na
 * marca. Extraídas, a a11y das duas passa a ser uma coisa só:
 * `role="group"` + `aria-labelledby` ligando cada lista ao seu PRÓPRIO
 * rótulo de forma programática, não só por ordem de leitura no DOM — um
 * leitor de tela anuncia o grupo pelo nome antes de entrar nos itens, em vez
 * de concatenar "Técnicos: Ana Silva, Instrumentos: Q001" num fluxo só (fix
 * round 1, achado 3). O rótulo em si é ganho de clareza de domínio, não
 * correção de a11y por item: cada chip já carrega o nome em texto puro, então
 * cor/forma nunca foram o único portador — só a fronteira ENTRE os dois
 * grupos era ambígua sem ele.
 *
 * Faixa sem item não renderiza nada: rótulo órfão ("Instrumentos:" seguido de
 * vazio) é ruído que afirma o que não há (brief 3b).
 */
function FaixaLegenda({
  id,
  rotulo,
  itens,
  marca,
}: {
  /** Id do `<span>` do rótulo, alvo do `aria-labelledby` do grupo. */
  id: string
  rotulo: string
  itens: { chave: string | number; cor: string; nome: string }[]
  /** Bolinha = técnico, triângulo = instrumento — a FORMA é o que separa os
   *  dois domínios na grade, e a legenda repete a mesma convenção. */
  marca: 'bolinha' | 'triangulo'
}) {
  if (itens.length === 0) return null
  return (
    <div
      role="group"
      aria-labelledby={id}
      className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1 text-xs text-muted-foreground"
    >
      <span id={id} className="font-medium text-foreground">
        {rotulo}
      </span>
      {itens.map((item) => (
        <span key={item.chave} className="flex items-center gap-1.5">
          {marca === 'bolinha' ? (
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: item.cor }}
              aria-hidden
            />
          ) : (
            <svg aria-hidden className="h-2 w-2 shrink-0" viewBox="0 0 10 10">
              <polygon points="5,0.5 9.5,9.5 0.5,9.5" fill={item.cor} />
            </svg>
          )}
          {item.nome}
        </span>
      ))}
    </div>
  )
}

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
  legendaInstrumentos,
  instrumentosDoDia,
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
   * Instrumentos distintos da janela de 42 dias, deduplicados e já ordenados
   * pela página com a MESMA função que ordena a célula (`ordenarInstrumentos`)
   * — legenda e grade não podem listar o mesmo conjunto em sequências
   * diferentes, senão só a cor casaria as duas, e cor sozinha não carrega
   * informação (Global Constraint #4).
   */
  legendaInstrumentos: PontoInstrumento[]
  /**
   * Seção "Instrumentos do dia": derivada da entrada de `instrumentos`
   * correspondente ao dia selecionado, acrescida dos usos. Mesma fonte da
   * grade e da legenda de propósito — as três superfícies não podem
   * discordar sobre quais instrumentos o dia tem.
   */
  instrumentosDoDia: InstrumentoDoDia[]
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

      {/* Duas faixas, mesma mecânica (`FaixaLegenda`): a de técnicos leva
          "Sem técnico" no fim quando alguma visita DA JANELA (os 42 dias,
          inclusive o transbordo esmaecido pros meses vizinhos que a própria
          grade desenha) não tem `tecnico_id` — mesmo escopo dos chips acima,
          não só o mês estrito. */}
      <FaixaLegenda
        id="legenda-mes-tecnicos"
        rotulo="Técnicos:"
        marca="bolinha"
        itens={[
          ...legenda.map((t) => ({ chave: t.id, cor: corDoTecnico(t.id), nome: t.name })),
          ...(temSemTecnico
            ? [{ chave: 'sem-tecnico', cor: COR_SEM_TECNICO, nome: 'Sem técnico' }]
            : []),
        ]}
      />

      <FaixaLegenda
        id="legenda-mes-instrumentos"
        rotulo="Instrumentos:"
        marca="triangulo"
        itens={legendaInstrumentos.map((i) => ({ chave: i.id, cor: i.cor, nome: i.name }))}
      />

      {erroAjuste && <p className="text-sm text-danger">{erroAjuste}</p>}

      {/* "Instrumentos do dia": mesma fonte da grade e da legenda (a entrada
          de `instrumentosPorDia` do dia selecionado, já com os usos
          pendurados pela página) — é isso que impede as duas metades da tela
          de se contradizerem sobre quais instrumentos o dia tem, inclusive
          quando o id usado não está no catálogo (instrumento arquivado
          depois de usado), caso em que as duas mostram `Instrumento #<id>`.
          Uma linha por instrumento, com o triângulo da cor, o nome e os usos
          (faixa de horário + OS/técnico). Sem instrumento no dia, a seção nem
          aparece: o "Nenhuma visita neste dia." abaixo já cobre o dia vazio.
          Deliberadamente sem aviso de calibração vencida — fora de escopo por
          escolha do usuário (brief). */}
      {instrumentosDoDia.length > 0 && (
        <div className="space-y-1 rounded-lg border border-border bg-card p-2">
          <h3 className="px-1 text-xs font-semibold uppercase text-muted-foreground">
            Instrumentos do dia
          </h3>
          {instrumentosDoDia.map((i) => (
            <div key={i.id} className="flex min-h-[44px] items-start gap-2 px-1 py-1 text-sm">
              <svg aria-hidden className="mt-1.5 h-2 w-2 shrink-0" viewBox="0 0 10 10">
                <polygon points="5,0.5 9.5,9.5 0.5,9.5" fill={i.cor} />
              </svg>
              {/* Nome QUEBRA em vez de truncar (e ainda leva `title` pro
                  desktop): a 390px o `truncate` cortava tudo acima de ~10
                  caracteres, e o outro portador de identidade — a cor — se
                  repete a cada 12 ids, então o nome cortado não tinha
                  substituto. `title` sozinho não resolveria: num PWA de toque
                  não existe hover. */}
              <span className="w-20 shrink-0 break-words font-medium" title={i.name}>
                {i.name}
              </span>
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
