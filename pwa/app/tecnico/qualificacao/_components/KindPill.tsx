'use client'
import { clsx } from 'clsx'

/**
 * Etiqueta do tipo de qualificação de uma coleta (QI/QO/QD/QS/Calibração).
 *
 * Neutra de propósito: no resto do app cor responde "em que pé está isto?"
 * (verde coletado, âmbar pendente, vermelho erro). Aqui o que se comunica é
 * *categoria*, não estado — se esta etiqueta fosse verde para QD, verde
 * passaria a significar duas coisas na mesma tela. Ver "A Regra do Estado"
 * no DESIGN.md.
 *
 * Antes o componente pintava uma cor por tipo e o chamador mandava
 * `qualifType="installation"` fixo: toda etiqueta saía azul e escrita "QI",
 * mesmo em item de QO.
 */
const LABELS: Record<string, string> = {
  installation: 'QI',
  operational: 'QO',
  performance: 'QD',
  software: 'QS',
  calibration: 'Cal',
}

const TITULOS: Record<string, string> = {
  installation: 'Qualificação de instalação',
  operational: 'Qualificação de operação',
  performance: 'Qualificação de desempenho',
  software: 'Qualificação de software',
  calibration: 'Calibração',
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
  const label = LABELS[qualifType] ?? qualifType
  const titulo = TITULOS[qualifType] ?? label
  return (
    <span
      title={titulo}
      className={clsx(
        'inline-flex shrink-0 items-center rounded-full border border-border',
        'bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground',
        className,
      )}
    >
      <span className="sr-only">{titulo}: </span>
      {label}
      {subLabel ? <span className="ml-1 opacity-70">·{subLabel}</span> : null}
    </span>
  )
}
