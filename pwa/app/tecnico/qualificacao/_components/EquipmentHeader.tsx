'use client'
import { Wrench, Hash, Tag as TagIcon, Boxes } from 'lucide-react'
import type { EquipmentInfo } from '@/lib/odoo/tecnico'

export function EquipmentHeader({
  label,
  eq,
  count,
  tone = 'cyan',
}: {
  label: string
  eq?: EquipmentInfo
  count: number
  tone?: 'cyan' | 'emerald'
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
    <div className={`rounded-md ${palette.bg} px-3 py-2 border ${palette.border}`}>
      <div className="flex items-start gap-2">
        <Wrench className={`mt-0.5 h-4 w-4 shrink-0 ${palette.text}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <strong className={`truncate text-sm ${palette.text}`}>{title}</strong>
            {tag && (
              <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-mono ${palette.chip}`}>
                <TagIcon className="mr-0.5 inline h-2.5 w-2.5" />{tag}
              </span>
            )}
            <span className={`ml-auto shrink-0 text-xs ${palette.muted}`}>
              {count}
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
                  <Boxes className="h-3 w-3" />{model}
                </span>
              )}
              {serial && (
                <span className="inline-flex items-center gap-1">
                  <Hash className="h-3 w-3" />{serial}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
