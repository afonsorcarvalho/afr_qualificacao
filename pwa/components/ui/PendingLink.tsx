'use client'

import { useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { useNavProgress } from '@/components/providers/NavProgress'

/**
 * Link de navegação que responde ao toque.
 *
 * O `<Link>` do Next não dá sinal nenhum enquanto busca a rota nova: em 4G de
 * hospital isso são segundos de tela parada, e o técnico toca de novo. Aqui a
 * navegação passa por `useTransition`, então dá pra:
 *
 *  - escurecer a linha tocada e mostrar um spinner nela (`isPending`);
 *  - acender a barra de progresso no topo (`NavProgress`);
 *  - ignorar toques repetidos enquanto a primeira navegação não termina.
 *
 * Regra da casa (PRODUCT.md): nenhum toque fica sem resposta.
 */
export function PendingLink({
  href,
  children,
  className,
  spinnerClassName,
  'aria-label': ariaLabel,
}: {
  href: string
  children: React.ReactNode
  className?: string
  spinnerClassName?: string
  'aria-label'?: string
}) {
  const router = useRouter()
  const { begin } = useNavProgress()
  const [isPending, startTransition] = useTransition()

  return (
    <a
      href={href}
      aria-label={ariaLabel}
      aria-busy={isPending || undefined}
      onClick={(e) => {
        // Deixa passar o comportamento nativo em nova aba / botão do meio.
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
        e.preventDefault()
        if (isPending) return
        begin()
        startTransition(() => router.push(href))
      }}
      className={clsx(
        'relative block transition-opacity',
        isPending && 'pointer-events-none opacity-60',
        className,
      )}
    >
      {children}
      {isPending && (
        <span
          className={clsx(
            'pointer-events-none absolute right-3 top-1/2 -translate-y-1/2',
            spinnerClassName,
          )}
        >
          <Loader2 className="h-4 w-4 animate-spin text-foreground" aria-hidden />
          <span className="sr-only">Abrindo…</span>
        </span>
      )}
    </a>
  )
}
