'use client'

import React from 'react'
import { clsx } from 'clsx'

/**
 * Superfície padrão do app.
 *
 * Manteve o nome porque é usada em várias telas, mas de vidro não tem mais
 * nada: o `backdrop-blur` decorativo, o glow neon e o hover que dava zoom
 * (`scale: 1.02`) saíram com o tema antigo. Profundidade agora é tonal —
 * fundo da superfície + fio de 1px (DESIGN.md, "A Regra do Fio").
 *
 * `alert` é o único caso em que a borda muda de cor: sinaliza pendência que
 * precisa de ação, e vem sempre acompanhada de texto no conteúdo.
 */
interface SurfaceCardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'hover' | 'selected' | 'elevated'
  alert?: boolean
  noPadding?: boolean
  children?: React.ReactNode
}

export function GlassCard({
  children,
  variant = 'default',
  alert = false,
  noPadding = false,
  className,
  ...props
}: SurfaceCardProps) {
  return (
    <div
      className={clsx(
        'relative overflow-hidden rounded-lg border bg-card transition-colors',
        alert ? 'border-amber-600/50' : 'border-border',
        !noPadding && 'p-4',
        variant === 'hover' && 'hover:bg-accent',
        variant === 'selected' && 'border-foreground/30 bg-accent',
        variant === 'elevated' && 'bg-accent',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
