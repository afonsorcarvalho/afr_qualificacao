'use client'
import { clsx } from 'clsx'

const COLORS: Record<string, string> = {
  installation: 'bg-blue-500',     // QI
  operational: 'bg-purple-500',    // QO
  performance: 'bg-emerald-500',   // QD
  software: 'bg-gray-500',         // QS
  calibration: 'bg-amber-500',     // Calib
}
const LABELS: Record<string, string> = {
  installation: 'QI',
  operational: 'QO',
  performance: 'QD',
  software: 'QS',
  calibration: 'Cal',
}

export function KindPill({
  qualifType,
  subLabel,
  className,
}: {
  qualifType: string
  subLabel?: string
  className?: string
}) {
  const color = COLORS[qualifType] ?? 'bg-gray-500'
  const label = LABELS[qualifType] ?? qualifType
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold text-white',
        color,
        className,
      )}
    >
      {label}
      {subLabel ? <span className="ml-1 opacity-80">·{subLabel}</span> : null}
    </span>
  )
}
