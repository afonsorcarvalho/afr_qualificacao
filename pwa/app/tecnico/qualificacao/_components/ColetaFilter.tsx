'use client'
import { clsx } from 'clsx'

export type SegmentoColeta = 'pendentes' | 'feitas'

/**
 * Filtro da lista de coletas: pendentes de um lado, feitas do outro.
 *
 * Não é aba, e o ARIA diz isso: `role="group"` com dois botões `aria-pressed`,
 * não `tablist`/`tab`. A distinção não é cosmética — aba anuncia "outra
 * página", e aqui a lista é a mesma, só filtrada. O DESIGN.md proíbe aba
 * (parece backoffice de ERP); filtro segmentado é o que ele permite.
 *
 * A contagem do segmento inativo fica visível de propósito: é ela que diz
 * que existe algo do outro lado — sem isso o técnico não teria motivo pra
 * tocar no segundo botão.
 *
 * O `sticky` vale em toda largura desde que o invólucro do app tenha altura
 * definida — até 2026-09-05 ele usava `min-h-screen`, crescia com o conteúdo
 * e deixava todo `sticky` de dentro do `<main>` inerte abaixo de 1024px.
 */
export function ColetaFilter({
  segmento,
  onChange,
  pendentes,
  feitas,
}: {
  segmento: SegmentoColeta
  onChange: (s: SegmentoColeta) => void
  pendentes: number
  feitas: number
}) {
  const opcoes: { id: SegmentoColeta; label: string; count: number }[] = [
    { id: 'pendentes', label: 'Pendentes', count: pendentes },
    { id: 'feitas', label: 'Realizadas', count: feitas },
  ]

  return (
    <div
      role="group"
      aria-label="Filtrar coletas"
      // `top-0` em qualquer largura: quem rola é o `<main>` do layout do
      // técnico (ou a coluna da lista, em ≥1024px), e o cabeçalho do app está
      // FORA desse scrollport — dentro dele o topo é zero. O `top-14` que
      // havia aqui compensava um cabeçalho que nunca esteve no caminho.
      // Fundo opaco: sobre conteúdo rolando, translúcido deixaria os cartões
      // atravessarem o rótulo.
      className="sticky top-0 z-[5] -mx-1 mb-1 flex gap-1 rounded-lg border border-border bg-background p-1"
    >
      {opcoes.map((o) => {
        const ativo = o.id === segmento
        return (
          <button
            key={o.id}
            type="button"
            aria-pressed={ativo}
            onClick={() => onChange(o.id)}
            className={clsx(
              'min-h-[44px] flex-1 rounded-md px-3 text-sm font-medium transition-colors',
              ativo
                ? 'bg-accent text-foreground ring-1 ring-foreground/20'
                : 'text-muted-foreground hover:bg-accent/50',
            )}
          >
            {o.label}{' '}
            <span className="tabular-nums text-muted-foreground">{o.count}</span>
          </button>
        )
      })}
    </div>
  )
}
