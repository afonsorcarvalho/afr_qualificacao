'use client'

import React from 'react'
import { motion, HTMLMotionProps } from 'framer-motion'
import { clsx } from 'clsx'

interface GlassCardProps extends Omit<HTMLMotionProps<'div'>, 'children'> {
  variant?: 'default' | 'hover' | 'selected' | 'elevated'
  glow?: 'blue' | 'purple' | 'pink' | 'none'
  alert?: boolean
  noPadding?: boolean
  children?: React.ReactNode
}

const glowStyles = {
  blue:   'shadow-glow-blue border-neon-blue/20',
  purple: 'shadow-glow-purple border-neon-purple/20',
  pink:   'shadow-glow-pink border-neon-pink/20',
  none:   'shadow-glass border-border dark:border-white/10',
}

export function GlassCard({
  children,
  variant = 'default',
  glow = 'none',
  alert = false,
  noPadding = false,
  className,
  ...props
}: GlassCardProps) {
  return (
    <motion.div
      className={clsx(
        'relative overflow-hidden rounded-2xl border backdrop-blur-xl',
        'bg-card/95 dark:bg-white/[0.04] transition-colors duration-300',
        alert ? 'card-alert-glow' : glowStyles[glow],
        !noPadding && 'p-6',
        variant === 'selected' && 'border-neon-blue/40 bg-neon-blue/5 shadow-glow-blue',
        variant === 'elevated' && 'shadow-glass-lg bg-card dark:bg-white/[0.06]',
        className
      )}
      whileHover={
        variant === 'hover'
          ? {
              scale: 1.02,
              boxShadow:
                '0 0 30px rgba(0, 212, 255, 0.2), 0 25px 50px rgba(0,0,0,0.5)',
            }
          : undefined
      }
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
      {...props}
    >
      <div className={clsx(
        'absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent to-transparent',
        alert ? 'via-red-500/50' : 'via-white/20',
      )} />
      {children}
    </motion.div>
  )
}
