'use client'
import { useEffect, useRef } from 'react'
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

/** Limiar de arrasto (px) acima do qual o toque em andamento vira rolagem,
 *  não gesto — a faixa quebra em várias linhas e rola no celular (brief). */
const LIMIAR_ARRASTO_PX = 10
/** Duração do toque longo (ms) até isolar. */
const DURACAO_TOQUE_LONGO_MS = 500

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
 *
 * A MARCA (bolinha/triângulo) obedece ao mesmo vocabulário, e isso não era
 * verdade até a review final (achado 2): ela ficava na cor cheia do recurso
 * mesmo com o chip desligado — e a marca é o elemento visual DOMINANTE do
 * chip, então o chip apagado continuava lendo como ligado, o mesmo defeito
 * que o fix round 1 corrigiu no fundo e na borda. Desligado, a marca vira
 * CONTORNO (bolinha sem preenchimento, triângulo com `fill="none"` e traço):
 * é a extensão natural do "ligado = preenchido", e não um segundo
 * vocabulário — dessaturar por filtro (`grayscale`) introduziria um. A cor
 * do contorno continua sendo a do recurso porque ela nunca foi o único
 * portador de identidade aqui: o nome vai em texto puro ao lado.
 */
function FaixaLegenda<T extends number | false>({
  id,
  rotulo,
  rotuloTodos,
  itens,
  marca,
  selecionado,
  onAlternar,
  onTodos,
  onIsolar,
}: {
  /** Id do `<span>` do rótulo, alvo do `aria-labelledby` do grupo. */
  id: string
  rotulo: string
  /**
   * Nome ACESSÍVEL do badge "Todos" desta faixa ("Todos os técnicos"). O
   * texto visível continua o "Todos" curto — a faixa é estreita e o rótulo
   * do grupo está ao lado. O nome longo existe porque as duas faixas
   * convivem na mesma tela: `role="group"` + `aria-labelledby` separa as
   * duas na leitura em FLUXO, mas a navegação por LISTA de botões (o rotor
   * do leitor de tela) anuncia só o nome do botão, e dois "Todos" ali são
   * indistinguíveis (review final, achado 5).
   */
  rotuloTodos: string
  itens: ItemLegenda<T>[]
  /** Bolinha = técnico, triângulo = instrumento — a FORMA é o que separa os
   *  dois domínios na grade, e a legenda repete a mesma convenção. */
  marca: 'bolinha' | 'triangulo'
  /** `null` = "Todos" (faixa sem restrição, nada desligado). */
  selecionado: Set<T> | null
  onAlternar: (id: T) => void
  onTodos: () => void
  /**
   * Toque longo (ou `Alt+Enter`/`Alt+clique`, o equivalente de teclado):
   * isola aquele item — a faixa passa a ter só ele ligado. Chamar de novo no
   * item já isolado é reversível por si mesmo (a `page.tsx` decide voltar
   * pra "Todos" quando `id` já é o único do `Set`) — a faixa aqui só avisa
   * QUAL id foi tocado, sem saber se o resultado vai ser isolar ou reverter.
   */
  onIsolar: (id: T) => void
}) {
  /**
   * Estado do toque longo em andamento — no máximo um por vez nesta faixa
   * (as duas faixas são instâncias separadas do componente, então isolar
   * num instrumento nunca compartilha timer com um toque em andamento na
   * faixa de técnicos). Fica em `ref`, não em `state`: o `pointermove`
   * dispara a cada pixel de arrasto, e um `setState` aí recriaria a faixa
   * inteira a torto e a direito só pra checar um limiar de distância.
   *
   * `suprimirClique` é o que resolve a ordem real dos eventos num toque:
   * `pointerdown` → (500ms) → `pointerup` → `click` — o `click` é disparado
   * pelo NAVEGADOR depois que este componente já reagiu ao `pointerup`, e
   * não há como o `pointerup` "cancelar" um `click` que ainda nem existe.
   * Por isso o `onClick` do item consulta esta flag antes de alternar: se o
   * toque longo já isolou (ou se foi arrasto, não toque), o `click` que vem
   * a seguir é engolido — senão o mesmo toque que isolou desligaria o
   * próprio item isolado um instante depois (brief: "toque longo não pode
   * disparar também o toque simples").
   */
  const toqueRef = useRef<{
    timer: ReturnType<typeof setTimeout>
    x: number
    y: number
    suprimirClique: boolean
  } | null>(null)

  // A armadilha clássica deste componente: um timer solto. Se a faixa
  // desmontar (troca de mês, de modo, ou a própria navegação da agenda) com
  // o toque longo ainda armado, o `setTimeout` dispara depois — chamando
  // `onIsolar` num id que já não corresponde a nada visível na tela. Limpo
  // em TODO caminho de saída, inclusive aqui, na desmontagem.
  useEffect(() => {
    return () => {
      if (toqueRef.current) clearTimeout(toqueRef.current.timer)
    }
  }, [])

  function iniciarToqueLongo(itemId: T, evento: React.PointerEvent<HTMLButtonElement>) {
    if (toqueRef.current) clearTimeout(toqueRef.current.timer)
    const timer = setTimeout(() => {
      onIsolar(itemId)
      // O toque ainda pode estar pressionado quando o timer dispara — o
      // `pointerup` (e o `click` que o segue) ainda vêm. Marcar aqui, não
      // esperar o `pointerup`, é o que garante a supressão mesmo que o
      // usuário solte o dedo bem em cima dos 500ms.
      if (toqueRef.current) toqueRef.current.suprimirClique = true
    }, DURACAO_TOQUE_LONGO_MS)
    toqueRef.current = { timer, x: evento.clientX, y: evento.clientY, suprimirClique: false }
  }

  function moverToqueLongo(evento: React.PointerEvent<HTMLButtonElement>) {
    const estado = toqueRef.current
    if (!estado || estado.suprimirClique) return
    const dx = evento.clientX - estado.x
    const dy = evento.clientY - estado.y
    if (Math.hypot(dx, dy) > LIMIAR_ARRASTO_PX) {
      // Arrasto: cancela o isolar pendente E impede o click de alternar em
      // seguida — foi rolagem, não toque (brief).
      clearTimeout(estado.timer)
      estado.suprimirClique = true
    }
  }

  function soltarToqueLongo() {
    // Só limpa o TIMER (caso o toque tenha sido curto e ele ainda não tenha
    // disparado) — o objeto em si sobrevive até o `onClick`, que é quem
    // precisa ler `suprimirClique` pra decidir se alterna ou não.
    if (toqueRef.current) clearTimeout(toqueRef.current.timer)
  }

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
        aria-label={rotuloTodos}
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
            // `aria-keyshortcuts` é o token padrão (não traduzido — é lido
            // por ferramentas, não por prosa), e o `title` carrega a mesma
            // informação em pt-BR pra quem só tem o rato/toque (brief).
            aria-keyshortcuts="Alt+Enter"
            title="Toque e segure (ou Alt+clique, ou Alt+Enter) para ver só este"
            onClick={(evento) => {
              // O `click` chega DEPOIS do `pointerup` — se o toque longo já
              // isolou (ou se foi arrasto), este `click` é o mesmo gesto
              // "vazando" como toque simples, e precisa ser engolido. Ver
              // comentário de `toqueRef` acima.
              if (toqueRef.current?.suprimirClique) {
                toqueRef.current = null
                return
              }
              if (evento.altKey) {
                onIsolar(item.id)
                return
              }
              onAlternar(item.id)
            }}
            onKeyDown={(evento) => {
              // Equivalente de teclado do toque longo — sem isto o gesto
              // simplesmente não existe pra quem navega por teclado ou
              // leitor de tela (brief).
              if (evento.altKey && (evento.key === 'Enter' || evento.key === ' ')) {
                evento.preventDefault()
                onIsolar(item.id)
              }
            }}
            onContextMenu={(evento) => evento.preventDefault()}
            onPointerDown={(evento) => iniciarToqueLongo(item.id, evento)}
            onPointerMove={moverToqueLongo}
            onPointerUp={soltarToqueLongo}
            onPointerCancel={soltarToqueLongo}
            className={clsx(
              // `select-none` + `touch-manipulation`: suprime a seleção de
              // texto e o menu de contexto que o toque longo dispara nativo
              // no mobile — sem isso o gesto concorre com o comportamento
              // do navegador (brief).
              'flex min-h-[44px] select-none items-center gap-1.5 rounded-md border px-2 touch-manipulation',
              ligado
                ? 'border-transparent bg-accent font-semibold text-foreground'
                : 'border-dashed border-border text-muted-foreground',
            )}
          >
            {/* A marca segue o MESMO vocabulário de peso do chip: cheia
                quando ligado, só contorno quando desligado. Ver o bloco de
                comentário do componente. */}
            {marca === 'bolinha' ? (
              <span
                className="h-2 w-2 shrink-0 rounded-full border"
                style={{
                  backgroundColor: ligado ? item.cor : 'transparent',
                  borderColor: item.cor,
                }}
                aria-hidden
              />
            ) : (
              <svg aria-hidden className="h-2 w-2 shrink-0" viewBox="0 0 10 10">
                <polygon
                  points="5,0.5 9.5,9.5 0.5,9.5"
                  fill={ligado ? item.cor : 'none'}
                  stroke={item.cor}
                  strokeWidth={ligado ? 0 : 1.5}
                />
              </svg>
            )}
            {item.nome}
          </button>
        )
      })}
      {/* Dica textual do gesto — sem ela o toque longo é invisível (brief).
          Em texto apagado, não é instrução crítica pra usar a faixa (o toque
          simples de sempre continua funcionando sem ler isto), por isso não
          leva `role`/`aria-live` nenhum: é reforço, não anúncio. */}
      <span className="basis-full text-[11px] text-muted-foreground">
        Segure um para ver só ele
      </span>
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
  onIsolarTecnico,
  onIsolarInstrumento,
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
   * Toque longo (ou `Alt+Enter`/`Alt+clique`) num chip: isola aquele
   * recurso, ou — se ele já é o único ligado — reverte pra "Todos" (Task 1).
   * A decisão de isolar vs. reverter mora na `page.tsx`, dona dos dois
   * `Set`: esta função só recebe o `id` tocado.
   */
  onIsolarTecnico: (id: number | false) => void
  onIsolarInstrumento: (id: number) => void
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
        rotuloTodos="Todos os técnicos"
        marca="bolinha"
        itens={legendaTecnicos}
        selecionado={tecnicosSel}
        onAlternar={onAlternarTecnico}
        onTodos={onTodosTecnicos}
        onIsolar={onIsolarTecnico}
      />

      <FaixaLegenda
        id="legenda-mes-instrumentos"
        rotulo="Instrumentos:"
        rotuloTodos="Todos os instrumentos"
        marca="triangulo"
        itens={legendaInstrumentos.map((i) => ({ chave: i.id, id: i.id, cor: i.cor, nome: i.name }))}
        selecionado={instrumentosSel}
        onAlternar={onAlternarInstrumento}
        onTodos={onTodosInstrumentos}
        onIsolar={onIsolarInstrumento}
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
