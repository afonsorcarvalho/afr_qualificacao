'use client'
import { clsx } from 'clsx'
import { noMes } from './mes'
import type { PontosDia } from './mes'

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
 */
function labelCelula(dia: PontosDia, dentro: boolean, ehHoje: boolean): string {
  const prefixo = dentro ? '' : 'fora do mês, '
  const marca = ehHoje ? ', hoje' : ''
  const nomes = dia.pontos
    .map((p) => (p.visitas > 1 ? `${p.name} (${p.visitas})` : p.name))
    .join(', ')
  const corpo = dia.total === 0
    ? 'sem visitas'
    : `${dia.total} ${dia.total === 1 ? 'visita' : 'visitas'}: ${nomes}`
  const sufixo = dia.conflito ? ', com conflito' : ''
  return `${prefixo}${rotuloDia(dia.date)}${marca}, ${corpo}${sufixo}`
}

// Até 4 pontinhos cabem soltos na célula; a partir do 5º técnico distinto,
// mostra só 3 + rótulo textual "+N" — 4 pontinhos disputando espaço com um
// "+1" ficariam ambíguos, e o aria-label já carrega a lista completa.
const MAX_PONTOS_SOLTOS = 4
const PONTOS_COM_MAIS = 3

export function GradeMes({
  dias,
  ancora,
  hoje,
  selecionado,
  onSelecionar,
}: {
  dias: PontosDia[]
  ancora: string
  hoje: string | null
  selecionado: string
  onSelecionar: (date: string) => void
}) {
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
          const excedeu = dia.pontos.length > MAX_PONTOS_SOLTOS
          const pontosVisiveis = excedeu ? dia.pontos.slice(0, PONTOS_COM_MAIS) : dia.pontos
          const restantes = excedeu ? dia.pontos.length - PONTOS_COM_MAIS : 0

          return (
            <button
              key={dia.date}
              type="button"
              aria-pressed={ehSelecionado}
              aria-label={labelCelula(dia, dentro, ehHoje)}
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
