'use client'

import { Loader2 } from 'lucide-react'
import { clsx } from 'clsx'

/**
 * Estado de carregamento de tela ou de bloco.
 *
 * Existe pra que "esperando" tenha sempre a mesma cara e nunca seja silêncio:
 * spinner + frase do que está sendo buscado, anunciado com `role="status"`.
 * Regra da casa (PRODUCT.md): nenhuma espera sem resposta.
 */
export function LoadingState({
  label = 'Carregando...',
  className,
}: {
  label?: string
  className?: string
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={clsx(
        'flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground',
        className,
      )}
    >
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </div>
  )
}

/** Linha de esqueleto — usada onde já sabemos o formato do que vem. */
export function SkeletonRow({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={clsx('h-16 animate-pulse rounded-lg border border-border bg-muted', className)}
    />
  )
}
