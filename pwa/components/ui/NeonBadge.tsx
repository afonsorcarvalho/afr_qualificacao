'use client'

import { clsx } from 'clsx'
import { ReactNode } from 'react'

type NeonColor = 'blue' | 'purple' | 'pink' | 'green' | 'orange' | 'gray'

interface NeonBadgeProps {
  children: ReactNode
  color?: NeonColor
  size?: 'sm' | 'md'
  dot?: boolean
  className?: string
}

const colorMap: Record<NeonColor, string> = {
  blue:   'bg-neon-blue/10 text-neon-blue border-neon-blue/30',
  purple: 'bg-neon-purple/10 text-neon-purple border-neon-purple/30',
  pink:   'bg-neon-pink/10 text-neon-pink border-neon-pink/30',
  green:  'bg-neon-green/10 text-neon-green border-neon-green/30',
  orange: 'bg-neon-orange/10 text-neon-orange border-neon-orange/30',
  gray:   'bg-white/5 text-white/50 border-white/15',
}

const dotMap: Record<NeonColor, string> = {
  blue:   'bg-neon-blue shadow-[0_0_6px_rgba(0,212,255,0.8)]',
  purple: 'bg-neon-purple shadow-[0_0_6px_rgba(168,85,247,0.8)]',
  pink:   'bg-neon-pink shadow-[0_0_6px_rgba(236,72,153,0.8)]',
  green:  'bg-neon-green shadow-[0_0_6px_rgba(16,185,129,0.8)]',
  orange: 'bg-neon-orange shadow-[0_0_6px_rgba(245,158,11,0.8)]',
  gray:   'bg-white/40',
}

export function NeonBadge({
  children,
  color = 'blue',
  size = 'sm',
  dot = false,
  className,
}: NeonBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
        colorMap[color],
        className
      )}
    >
      {dot && <span className={clsx('w-1.5 h-1.5 rounded-full', dotMap[color])} />}
      {children}
    </span>
  )
}
