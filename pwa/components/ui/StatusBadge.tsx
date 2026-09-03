'use client'

import { clsx } from 'clsx'
import { ReactNode } from 'react'

/**
 * Chip de estado. Substitui o `NeonBadge` do tema antigo.
 *
 * O vocabulário de cor aqui é fechado e semântico (DESIGN.md, "A Regra do
 * Estado"): verde é concluído, âmbar é em espera, vermelho é falha, neutro é
 * o resto. O componente anterior expunha `blue`/`purple`/`pink` com brilho —
 * cor como decoração, que fazia "aprovado" (roxo) e "agendado" (azul) não
 * significarem nada por si.
 *
 * O texto do chip sempre nomeia o estado ("A Regra do Par"): apagando a cor,
 * a informação continua legível.
 */
export type StatusTone = 'done' | 'progress' | 'waiting' | 'error' | 'neutral'

const TONES: Record<StatusTone, string> = {
  done: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-600/30',
  progress: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-600/30',
  waiting: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-600/30',
  error: 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-600/30',
  neutral: 'bg-muted text-muted-foreground border-border',
}

const DOTS: Record<StatusTone, string> = {
  done: 'bg-emerald-600 dark:bg-emerald-400',
  progress: 'bg-emerald-600 dark:bg-emerald-400',
  waiting: 'bg-amber-600 dark:bg-amber-400',
  error: 'bg-red-600 dark:bg-red-400',
  neutral: 'bg-muted-foreground',
}

export function StatusBadge({
  children,
  tone = 'neutral',
  size = 'sm',
  dot = false,
  className,
}: {
  children: ReactNode
  tone?: StatusTone
  size?: 'sm' | 'md'
  dot?: boolean
  className?: string
}) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
        TONES[tone],
        className,
      )}
    >
      {dot && (
        <span
          className={clsx('h-1.5 w-1.5 shrink-0 rounded-full', DOTS[tone])}
          aria-hidden
        />
      )}
      {children}
    </span>
  )
}
