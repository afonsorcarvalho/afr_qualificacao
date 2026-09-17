'use client'
import { clsx } from 'clsx'
import { noMes } from './mes'
import type { PontosDia, PontosInstrumentoDia, PontoInstrumento } from './mes'

// Não é a semana de "hoje" — é só uma âncora fixa (domingo conhecido) pra
// derivar as siglas D S T Q Q S S via `Intl`, em vez de hardcoded num array
// literal. `Date.UTC` com argumentos explícitos não lê o relógio do
// aparelho.
const SIGLAS_SEMANA: string[] = Array.from({ length: 7 }, (_, i) => {
  const dt = new Date(Date.UTC(2026, 0, 4 + i)) // 2026-01-04 é domingo
  return new Intl.DateTimeFormat('pt-BR', { weekday: 'narrow', timeZone: 'UTC' }).format(dt)
})

/** "2026-09-17" → "17 de setembro", pt-BR, `timeZone: 'UTC'`. */
function rotuloDia(date: string): string {
  const [a, m, d] = date.split('-').map(Number)
  const dt = new Date(Date.UTC(a, m - 1, d))
  return new Intl.DateTimeFormat('pt-BR', { day: 'numeric', month: 'long', timeZone: 'UTC' }).format(dt)
}

/**
 * Label completo da célula: dia por extenso + "hoje" + contagem/nomes das
 * visitas + sufixo de conflito + prefixo de fora-do-mês. Cor sozinha não
 * carrega nenhuma dessas informações — o `aria-label` é a fonte de verdade
 * pra quem usa leitor de tela.
 *
 * `hoje` entrou no fix round 2 (achado 3): o anel `ring-primary` marcava o
 * dia de hoje SÓ visualmente, o que é violação direta da Global Constraint
 * #4 (cor nunca é o único portador) — e das quatro informações da célula era
 * justamente a que não tinha equivalente textual.
 *
 * A contagem por técnico (`Ana Silva (2)`) também é do round 2 (achado 6):
 * um técnico com duas visitas no mesmo dia rendia UM ponto, e o label saía
 * com menos nomes que o total ("3 visitas: Ana Silva, João Lima"), sem nada
 * dizendo de quem era a terceira. Só aparece quando `visitas > 1` — pendurar
 * "(1)" em todo mundo é ruído e ainda quebraria os labels exatos.
 *
 * Instrumentos entram como segundo grupo, separado por "; ", DEPOIS do
 * sufixo de conflito — não antes: ", com conflito" qualifica as visitas
 * (`corpo`), então tem que ficar colado nelas; se viesse depois de
 * "instrumentos: ...", um leitor de tela ouviria o conflito como se fosse
 * dos instrumentos, e não é. Sem contagem por item (diferente dos nomes de
 * técnico): a granularidade que importa pro leitor de tela é "quais
 * instrumentos", a contagem de uso por instrumento não muda a ação do
 * técnico no dia. Dia sem instrumento não escreve a parte — não existe
 * "instrumentos: " pendurado vazio.
 */
function labelCelula(
  dia: PontosDia,
  instrumentos: PontoInstrumento[],
  dentro: boolean,
  ehHoje: boolean,
): string {
  const prefixo = dentro ? '' : 'fora do mês, '
  const marca = ehHoje ? ', hoje' : ''
  const nomes = dia.pontos
    .map((p) => (p.visitas > 1 ? `${p.name} (${p.visitas})` : p.name))
    .join(', ')
  const corpo = dia.total === 0
    ? 'sem visitas'
    : `${dia.total} ${dia.total === 1 ? 'visita' : 'visitas'}: ${nomes}`
  const parteInstrumentos =
    instrumentos.length > 0 ? `; instrumentos: ${instrumentos.map((i) => i.name).join(', ')}` : ''
  const sufixo = dia.conflito ? ', com conflito' : ''
  return `${prefixo}${rotuloDia(dia.date)}${marca}, ${corpo}${sufixo}${parteInstrumentos}`
}

// Até 4 marcas (técnico + instrumento juntos) cabem soltas na célula; a
// partir da 5ª, mostra só 3 + rótulo textual "+N" — 4 marcas disputando
// espaço com um "+1" ficariam ambíguas, e o aria-label já carrega a lista
// completa dos dois grupos.
const MAX_PONTOS_SOLTOS = 4
const PONTOS_COM_MAIS = 3

/**
 * Reparte as `PONTOS_COM_MAIS` (3) marcas visíveis entre técnicos e
 * instrumentos quando a célula excede `MAX_PONTOS_SOLTOS`.
 *
 * Se só um dos dois grupos tem item, ele leva as 3. Se os dois têm, cada um
 * recebe 1 slot GARANTIDO e o slot restante vai para o grupo com mais itens
 * (empate → técnicos) — sem essa garantia, um dia com poucos técnicos e
 * muitos instrumentos (ou o inverso) escondia um grupo inteiro atrás do
 * "+N", que é justamente o que a marca de instrumento existe para evitar.
 */
function repartirMarcas(
  nTecnicos: number,
  nInstrumentos: number,
): { slotsTecnicos: number; slotsInstrumentos: number; restantes: number } {
  const total = nTecnicos + nInstrumentos
  if (total <= MAX_PONTOS_SOLTOS) {
    return { slotsTecnicos: nTecnicos, slotsInstrumentos: nInstrumentos, restantes: 0 }
  }
  const restantes = total - PONTOS_COM_MAIS
  if (nTecnicos > 0 && nInstrumentos > 0) {
    let slotsTecnicos = 1
    let slotsInstrumentos = 1
    // O slot restante (o 3º) vai para quem tem mais itens; empate → técnicos.
    if (nTecnicos >= nInstrumentos) {
      slotsTecnicos += 1
    } else {
      slotsInstrumentos += 1
    }
    return { slotsTecnicos, slotsInstrumentos, restantes }
  }
  if (nTecnicos > 0) {
    return { slotsTecnicos: PONTOS_COM_MAIS, slotsInstrumentos: 0, restantes }
  }
  return { slotsTecnicos: 0, slotsInstrumentos: PONTOS_COM_MAIS, restantes }
}

export function GradeMes({
  dias,
  instrumentos,
  ancora,
  hoje,
  selecionado,
  onSelecionar,
}: {
  dias: PontosDia[]
  /**
   * Na MESMA ordem de `dias` (as duas listas vêm de `gradeDoMes`), mas o
   * casamento aqui dentro é por `date`, nunca por posição — a ordem do
   * chamador nunca é uma dependência real.
   */
  instrumentos: PontosInstrumentoDia[]
  ancora: string
  hoje: string | null
  selecionado: string
  onSelecionar: (date: string) => void
}) {
  // Casado por `date`, nunca por posição: as duas listas hoje vêm de
  // `gradeDoMes` na mesma ordem, mas nada nesta função pode depender disso.
  const instrumentosPorData = new Map(instrumentos.map((i) => [i.date, i.instrumentos]))

  return (
    <div className="rounded-lg border border-border bg-card p-1">
      <div
        className="grid grid-cols-7 gap-0.5 pb-1 text-center text-[10px] uppercase leading-none text-muted-foreground"
        aria-hidden
      >
        {SIGLAS_SEMANA.map((sigla, i) => (
          // Sigla sozinha ("S" cai tanto em segunda quanto em sábado) não
          // identifica o dia sem o número ao lado — por isso o cabeçalho é
          // decorativo e cada célula carrega a data completa no próprio
          // aria-label.
          <span key={i}>{sigla}</span>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-0.5">
        {dias.map((dia) => {
          const dentro = noMes(dia.date, ancora)
          const ehSelecionado = dia.date === selecionado
          const ehHoje = hoje !== null && dia.date === hoje
          const instrumentosDoDia = instrumentosPorData.get(dia.date) ?? []
          const { slotsTecnicos, slotsInstrumentos, restantes } = repartirMarcas(
            dia.pontos.length,
            instrumentosDoDia.length,
          )
          const pontosVisiveis = dia.pontos.slice(0, slotsTecnicos)
          const instrumentosVisiveis = instrumentosDoDia.slice(0, slotsInstrumentos)

          return (
            <button
              key={dia.date}
              type="button"
              aria-pressed={ehSelecionado}
              aria-label={labelCelula(dia, instrumentosDoDia, dentro, ehHoje)}
              onClick={() => onSelecionar(dia.date)}
              className={clsx(
                'flex min-h-[44px] flex-col items-center justify-center gap-0.5 rounded-md p-1',
                // Tinta do dia selecionado: fundo SÓLIDO, não `bg-accent`
                // (fix round 2, achado 4). A grade tinha herdado o
                // `bg-accent` da `_FaixaDias`, mas sem o parceiro de
                // contraste que faz aquilo funcionar lá — na faixa o
                // não-selecionado é `text-muted-foreground` e o selecionado
                // `text-foreground`; aqui todo dia do mês já é
                // `text-foreground`, e `--accent` sobre `--card` mede 1.08:1
                // no claro e 1.05:1 no escuro, contra os 3:1 que a WCAG
                // 1.4.11 pede de indicador de estado. `--primary` sobre
                // `--card` mede ~14:1 nos dois temas (medido em
                // `GradeMes.test.tsx`), e inverte o texto junto — por isso o
                // token de texto é um ternário EXCLUSIVO: duas classes
                // `text-*` na mesma string dependeriam da ordem de emissão
                // do Tailwind pra decidir quem ganha.
                ehSelecionado
                  ? 'bg-primary text-primary-foreground'
                  : dentro ? 'text-foreground' : 'text-muted-foreground',
                // Anel de "hoje" é independente do fundo de seleção: os dois
                // podem coexistir e cada um marca uma coisa diferente (o
                // Google Calendar também distingue os dois visualmente).
                // Sobre o fundo sólido da seleção o anel inverte junto, senão
                // seria `--primary` em cima de `--primary` — invisível.
                ehHoje && 'ring-2 ring-inset',
                ehHoje && (ehSelecionado ? 'ring-primary-foreground' : 'ring-primary'),
              )}
            >
              <span
                data-testid="numero"
                className={clsx(
                  'leading-none',
                  // Segundo portador do "fora do mês", além do token de
                  // texto (achado deferido da validação manual: a diferença
                  // só de token é fraca nos DOIS temas). Não adianta caçar
                  // 3:1 entre dentro e fora: no tema claro o `--card` é
                  // branco puro, e qualquer fundo que chegasse a 3:1 seria
                  // um cinza médio que rouba a cena do mês que interessa.
                  // Então a diferença é de TIPOGRAFIA — corpo e peso —, que
                  // não depende de tema nem de percepção de cor.
                  ehSelecionado
                    ? 'text-xs font-semibold'
                    : dentro ? 'text-xs font-medium' : 'text-[10px] font-normal',
                )}
              >
                {dia.date.slice(8, 10)}
              </span>
              <span className="flex h-2 items-center justify-center gap-0.5" aria-hidden>
                {pontosVisiveis.map((p, i) => (
                  <span
                    key={i}
                    data-testid="ponto"
                    className={clsx(
                      'h-1.5 w-1.5 shrink-0 rounded-full',
                      // Contorno de perigo além da cor: cor sozinha não
                      // chega a quem não a distingue.
                      dia.conflito && 'ring-1 ring-danger',
                    )}
                    style={{ backgroundColor: p.cor }}
                  />
                ))}
                {instrumentosVisiveis.map((inst, i) => (
                  // Triângulo em SVG inline com `fill` (não borda CSS) —
                  // FORMA distingue instrumento de técnico, cor sozinha não
                  // (Global Constraint de a11y: cor E forma nunca são o
                  // único portador). Tamanho equivalente ao `h-1.5 w-1.5`
                  // das bolinhas. Sem o `ring-1 ring-danger` de conflito que
                  // as bolinhas ganham: conflito é propriedade da VISITA
                  // (technico x horário), não do instrumento, e o
                  // `aria-label` já carrega ", com conflito" independente de
                  // quem está com anel — um anel quadrado atrás de um
                  // triângulo também leria mal visualmente.
                  <svg
                    key={`t-${i}`}
                    data-testid="triangulo"
                    aria-hidden
                    className="h-1.5 w-1.5 shrink-0"
                    viewBox="0 0 10 10"
                  >
                    <polygon points="5,0.5 9.5,9.5 0.5,9.5" fill={inst.cor} />
                  </svg>
                ))}
                {restantes > 0 && (
                  <span data-testid="mais" className="text-[9px] font-medium leading-none">
                    +{restantes}
                  </span>
                )}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
