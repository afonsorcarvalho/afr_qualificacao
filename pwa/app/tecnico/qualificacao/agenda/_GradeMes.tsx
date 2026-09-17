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
 * Label completo da célula: dia por extenso + contagem/nomes das visitas +
 * sufixo de conflito + prefixo de fora-do-mês. Cor sozinha não carrega
 * nenhuma dessas informações — o `aria-label` é a fonte de verdade pra quem
 * usa leitor de tela.
 */
function labelCelula(dia: PontosDia, dentro: boolean): string {
  const prefixo = dentro ? '' : 'fora do mês, '
  const corpo = dia.total === 0
    ? 'sem visitas'
    : `${dia.total} ${dia.total === 1 ? 'visita' : 'visitas'}: ${dia.pontos.map((p) => p.name).join(', ')}`
  const sufixo = dia.conflito ? ', com conflito' : ''
  return `${prefixo}${rotuloDia(dia.date)}, ${corpo}${sufixo}`
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
              aria-label={labelCelula(dia, dentro)}
              onClick={() => onSelecionar(dia.date)}
              className={clsx(
                'flex min-h-[44px] flex-col items-center justify-center gap-0.5 rounded-md p-1',
                // Esmaecido só pelo token semântico — nada de opacidade nua
                // sobre texto (guarda de tema: muted com opacidade reduzida
                // cai abaixo do piso AA; opacity-N em cima do token puro
                // teria o mesmo efeito por outro caminho).
                dentro ? 'text-foreground' : 'text-muted-foreground',
                ehSelecionado && 'bg-accent font-semibold',
                // Anel de "hoje" é independente do fundo de seleção: os dois
                // podem coexistir e cada um marca uma coisa diferente (o
                // Google Calendar também distingue os dois visualmente).
                ehHoje && 'ring-2 ring-inset ring-primary',
              )}
            >
              <span className="text-xs leading-none">{dia.date.slice(8, 10)}</span>
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
