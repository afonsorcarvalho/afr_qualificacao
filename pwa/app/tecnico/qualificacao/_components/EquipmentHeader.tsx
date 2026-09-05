'use client'
import { clsx } from 'clsx'
import { Wrench, Hash, Tag as TagIcon, Boxes, ChevronRight } from 'lucide-react'
import type { EquipmentInfo } from '@/lib/odoo/tecnico'

/**
 * Cabeçalho do grupo de um equipamento — e o controle que abre e fecha o
 * grupo.
 *
 * É `<button aria-expanded>`, não `<details>`: o grupo precisa abrir por
 * decisão de fora (abrir uma coleta expande o grupo dela, e trocar de
 * segmento redefine o padrão), e `<details>` só abre por toque do usuário ou
 * por manipulação imperativa do DOM.
 *
 * O número é o progresso do equipamento inteiro ("3 de 8"), não a contagem do
 * segmento em exibição: dentro de "Pendentes" a contagem do segmento seria
 * sempre "quanto falta", que é justo o que o técnico já vê na lista aberta.
 *
 * O `sticky` vale em toda largura desde que o invólucro do app tenha altura
 * definida — até 2026-09-05 ele usava `min-h-screen`, crescia com o conteúdo
 * e deixava todo `sticky` de dentro do `<main>` inerte abaixo de 1024px.
 */
export function EquipmentHeader({
  label,
  eq,
  feitas,
  total,
  tone = 'cyan',
  aberto,
  onToggle,
  controlsId,
}: {
  label: string
  eq?: EquipmentInfo
  /** Coletas do equipamento já realizadas, na OS inteira. */
  feitas: number
  /** Coletas do equipamento na OS inteira. */
  total: number
  tone?: 'cyan' | 'emerald'
  aberto: boolean
  onToggle: () => void
  /** Id do container das coletas deste grupo, para o `aria-controls`. */
  controlsId: string
}) {
  const palette = tone === 'cyan'
    ? {
        bg: 'bg-cyan-500/15 dark:bg-cyan-500/10',
        border: 'border-cyan-600/40 dark:border-cyan-500/30',
        text: 'text-cyan-800 dark:text-cyan-300',
        muted: 'text-cyan-800/80 dark:text-cyan-300/70',
        chip: 'bg-cyan-600/20 text-cyan-900 dark:bg-cyan-500/20 dark:text-cyan-200',
      }
    : {
        bg: 'bg-emerald-500/15 dark:bg-emerald-500/10',
        border: 'border-emerald-600/40 dark:border-emerald-500/30',
        text: 'text-emerald-800 dark:text-emerald-300',
        muted: 'text-emerald-800/80 dark:text-emerald-300/70',
        chip: 'bg-emerald-600/20 text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-200',
      }

  const title = eq?.name || label
  const apelido = eq?.apelido
  const tag = eq?.tag
  const model = eq?.model
  const serial = eq?.serial_number
  const marca = eq?.marca_id ? eq.marca_id[1] : null

  return (
    <button
      type="button"
      aria-expanded={aberto}
      aria-controls={controlsId}
      onClick={onToggle}
      className={clsx(
        // Fundo opaco por baixo do tom: o tom é translúcido
        // (`bg-cyan-500/15`), e grudado no topo sobre a lista rolando ele
        // deixava os cartões atravessarem o nome do equipamento. Visto no
        // browser antes de virar `bg-background` + camada de tom por cima.
        'relative block w-full min-h-[44px] rounded-md border bg-background px-3 py-2 text-left',
        palette.border,
        // Só o grupo aberto gruda: fechado ele já ocupa uma linha e nada rola
        // por baixo dele. O deslocamento livra o filtro, que gruda acima e tem
        // 54px (44 de alvo + 4+4 de padding + o fio de 1px em cima e embaixo).
        // Medido no browser: com 52px o cabeçalho subia 2px por baixo dele.
        aberto && 'sticky top-[54px] z-[4]',
      )}
    >
      <span aria-hidden className={clsx('absolute inset-0 rounded-md', palette.bg)} />
      <div className="relative flex items-start gap-2">
        <ChevronRight
          className={clsx(
            'mt-0.5 h-4 w-4 shrink-0 transition-transform',
            palette.text,
            aberto && 'rotate-90',
          )}
          aria-hidden
        />
        <Wrench className={`mt-0.5 h-4 w-4 shrink-0 ${palette.text}`} aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <strong className={`truncate text-sm ${palette.text}`}>{title}</strong>
            {tag && (
              <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-mono ${palette.chip}`}>
                <TagIcon className="mr-0.5 inline h-2.5 w-2.5" aria-hidden />{tag}
              </span>
            )}
            <span className={`ml-auto shrink-0 tabular-nums text-xs ${palette.muted}`}>
              {feitas} de {total}
            </span>
          </div>
          {apelido && (
            <p className={`mt-0.5 truncate text-xs italic ${palette.muted}`}>
              &ldquo;{apelido}&rdquo;
            </p>
          )}
          {(marca || model || serial) && (
            <div className={`mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[11px] ${palette.muted}`}>
              {marca && <span>{marca}</span>}
              {model && (
                <span className="inline-flex items-center gap-1">
                  <Boxes className="h-3 w-3" aria-hidden />{model}
                </span>
              )}
              {serial && (
                <span className="inline-flex items-center gap-1">
                  <Hash className="h-3 w-3" aria-hidden />{serial}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </button>
  )
}
