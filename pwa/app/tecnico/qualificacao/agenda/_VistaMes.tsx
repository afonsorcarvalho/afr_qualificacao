'use client'
import { clsx } from 'clsx'
import { VisitaCard } from '../_components/VisitaCard'
import { GradeMes } from './_GradeMes'
import type { PontosDia, PontosInstrumentoDia, PontoInstrumento } from './mes'
import type { InstrumentoDoDia } from './carga'
import type { VisitaAgenda, VisitaVals } from '@/lib/odoo/agenda'

/** Item de uma faixa de legenda/filtro: marca + nome + o `id` que participa
 *  do `Set` de seleção (número, ou `false` para "sem técnico"). `chave` é
 *  só a key do React — precisa ser distinta de `id` porque `false` não é
 *  chave válida. */
interface ItemLegenda<T extends number | false> {
  chave: string | number
  id: T
  cor: string
  nome: string
}

/**
 * Uma faixa de legenda/filtro: rótulo curto + badge "Todos" + um botão por
 * item, cada um alternando se aquele recurso entra no filtro da grade.
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
 * Faixa sem item E sem restrição não renderiza nada: rótulo órfão
 * ("Instrumentos:" seguido de vazio) é ruído que afirma o que não há (brief
 * 3b), e nesse caso não há filtro pra limpar mesmo. Mas quando HÁ uma
 * restrição ativa (`selecionado !== null`) e a janela simplesmente não tem
 * item pra mostrar — ex.: o Gestor restringiu instrumentos em setembro e
 * navegou pra um mês sem nenhuma visita instrumentada —, a faixa CONTINUA
 * renderizada, só com o rótulo e o badge "Todos": é a única saída visível
 * pra uma restrição que sobrou de outro mês (fix round 1, achado 1 — a
 * MESMA classe de defeito que o `instrumentosComFalha` já fechava sozinho
 * pra falha de catálogo, agora fechada por inteiro).
 *
 * Estado ligado/desligado nunca é só cor: `aria-pressed` carrega o estado
 * pra leitor de tela, e visualmente é PESO — ligado é preenchido
 * (`bg-accent`, igual ao "Todos" ativo), desligado fica apagado (sem fundo,
 * contorno tracejado, texto em `text-muted-foreground`) — nunca o
 * contrário: um chip desligado com MAIS peso visual que os ligados lê como
 * "selecionado" pro olho, o oposto do que `aria-pressed=false` diz (achado
 * de validação em navegador, fix round 1). A cor de `text-muted-foreground`
 * é o "token puro" que `temaTokens.test.ts` pede no lugar de opacidade — a
 * regra da guarda continua sendo respeitada porque nenhuma classe daqui é
 * `opacity-N` nu.
 */
function FaixaLegenda<T extends number | false>({
  id,
  rotulo,
  itens,
  marca,
  selecionado,
  onAlternar,
  onTodos,
}: {
  /** Id do `<span>` do rótulo, alvo do `aria-labelledby` do grupo. */
  id: string
  rotulo: string
  itens: ItemLegenda<T>[]
  /** Bolinha = técnico, triângulo = instrumento — a FORMA é o que separa os
   *  dois domínios na grade, e a legenda repete a mesma convenção. */
  marca: 'bolinha' | 'triangulo'
  /** `null` = "Todos" (faixa sem restrição, nada desligado). */
  selecionado: Set<T> | null
  onAlternar: (id: T) => void
  onTodos: () => void
}) {
  if (itens.length === 0 && selecionado === null) return null
  return (
    <div
      role="group"
      aria-labelledby={id}
      className="flex flex-wrap items-center gap-x-1.5 gap-y-1 px-1 text-xs"
    >
      <span id={id} className="font-medium text-foreground">
        {rotulo}
      </span>
      <button
        type="button"
        aria-pressed={selecionado === null}
        onClick={onTodos}
        className={clsx(
          'flex min-h-[44px] items-center rounded-md border px-2',
          selecionado === null
            ? 'border-transparent bg-accent font-semibold text-foreground'
            : 'border-dashed border-border text-muted-foreground',
        )}
      >
        Todos
      </button>
      {itens.map((item) => {
        const ligado = selecionado === null || selecionado.has(item.id)
        return (
          <button
            key={item.chave}
            type="button"
            aria-pressed={ligado}
            onClick={() => onAlternar(item.id)}
            className={clsx(
              'flex min-h-[44px] items-center gap-1.5 rounded-md border px-2',
              ligado
                ? 'border-transparent bg-accent font-semibold text-foreground'
                : 'border-dashed border-border text-muted-foreground',
            )}
          >
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
          </button>
        )
      })}
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
  legendaTecnicos,
  legendaInstrumentos,
  tecnicosSel,
  instrumentosSel,
  onAlternarTecnico,
  onAlternarInstrumento,
  onTodosTecnicos,
  onTodosInstrumentos,
  instrumentosDoDia,
  ancora,
  hoje,
  diaSel,
  onSelecionarDia,
  podeAjustar,
  emAjuste,
  alvoAtivo,
  onAjustar,
  onAlternarAjuste,
  erroAjuste,
  onSelecionarVisita,
}: {
  visitas: VisitaAgenda[]
  /**
   * Marcas da grade (bolinhas) JÁ FILTRADAS pelas duas faixas — a página
   * calcula esta lista a partir de `visitasVisiveis`, não de `visitas`. A
   * faixa de legenda abaixo usa uma fonte SEPARADA (`legendaTecnicos`, não
   * filtrada) — senão desligar um técnico o tiraria da própria faixa, e não
   * haveria como religá-lo (Task 2).
   */
  dias: PontosDia[]
  /** Instrumentos usados por dia, nos 42 dias da grade — também já FILTRADO
   *  pelas duas faixas (mesmo raciocínio de `dias` acima). */
  instrumentos: PontosInstrumentoDia[]
  /**
   * Itens da faixa "Técnicos:" — TODOS os técnicos com visita na janela
   * visível (os 42 dias da grade), ligados ou desligados no filtro: a faixa
   * lista o universo inteiro, senão não haveria como religar quem foi
   * desligado (Task 2). Inclui "Sem técnico" (`id: false`) quando alguma
   * visita da janela não tem `tecnico_id`.
   */
  legendaTecnicos: { chave: string | number; id: number | false; cor: string; nome: string }[]
  /**
   * Instrumentos distintos da janela de 42 dias, deduplicados e já ordenados
   * pela página com a MESMA função que ordena a célula (`ordenarInstrumentos`)
   * — legenda e grade não podem listar o mesmo conjunto em sequências
   * diferentes, senão só a cor casaria as duas, e cor sozinha não carrega
   * informação (Global Constraint #4). Também não filtrado pelo `instrumentosSel`,
   * mesmo raciocínio de `legendaTecnicos`.
   */
  legendaInstrumentos: PontoInstrumento[]
  /** `null` = "Todos" (faixa de técnicos sem restrição). Estado em memória,
   *  na página (Task 2) — troca de modo ou reload zera. */
  tecnicosSel: Set<number | false> | null
  /** `null` = "Todos" (faixa de instrumentos sem restrição). */
  instrumentosSel: Set<number> | null
  onAlternarTecnico: (id: number | false) => void
  onAlternarInstrumento: (id: number) => void
  onTodosTecnicos: () => void
  onTodosInstrumentos: () => void
  /**
   * Seção "Instrumentos do dia": derivada da entrada correspondente ao dia
   * selecionado, acrescida dos usos, a partir da lista de visitas COMPLETA
   * (não filtrada pelas faixas) — o filtro altera só as marcas da grade
   * (Task 2 brief), esta seção e os `VisitaCard`s abaixo continuam mostrando
   * tudo.
   */
  instrumentosDoDia: InstrumentoDoDia[]
  ancora: string
  hoje: string | null
  diaSel: string
  onSelecionarDia: (date: string) => void
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
  /** Toque num dia da grade com visita em ajuste: chamado com `{ date }` —
   * quem decide se isso arma o diálogo de confirmação de data ou grava
   * direto é a `page.tsx` (Task 1: hoje sempre arma, nunca grava aqui). */
  onAjustar: (vals: VisitaVals) => void
  /** Toque em "Ajustar"/"Concluir" no card: liga/desliga o ajuste daquela visita. */
  onAlternarAjuste: (visita: VisitaAgenda) => void
  erroAjuste: string
  onSelecionarVisita: (visita: VisitaAgenda) => void
}) {
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

      {/* Duas faixas, mesma mecânica (`FaixaLegenda`): cada chip é um botão
          de filtro (`aria-pressed`) que liga/desliga aquele recurso nas
          marcas da grade acima — a faixa de técnicos inclui "Sem técnico"
          (`id: false`) quando alguma visita DA JANELA (os 42 dias, inclusive
          o transbordo esmaecido pros meses vizinhos que a própria grade
          desenha) não tem `tecnico_id`; ele participa do filtro como os
          demais. */}
      <FaixaLegenda
        id="legenda-mes-tecnicos"
        rotulo="Técnicos:"
        marca="bolinha"
        itens={legendaTecnicos}
        selecionado={tecnicosSel}
        onAlternar={onAlternarTecnico}
        onTodos={onTodosTecnicos}
      />

      <FaixaLegenda
        id="legenda-mes-instrumentos"
        rotulo="Instrumentos:"
        marca="triangulo"
        itens={legendaInstrumentos.map((i) => ({ chave: i.id, id: i.id, cor: i.cor, nome: i.name }))}
        selecionado={instrumentosSel}
        onAlternar={onAlternarInstrumento}
        onTodos={onTodosInstrumentos}
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
