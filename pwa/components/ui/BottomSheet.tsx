'use client'
import { useEffect } from 'react'
import { X } from 'lucide-react'

/**
 * Folha vinda de baixo. O projeto não tem Modal genérico (só o
 * `PdfViewerModal`, que é específico); esta é a primeira.
 */
export function BottomSheet({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: React.ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <div
        className="absolute inset-0 bg-black/60"
        aria-hidden
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative w-full max-w-[560px] rounded-t-2xl border-t border-border bg-card p-4 shadow-[0_-8px_24px_rgba(0,0,0,0.45)]"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">{title}</h2>
          <button
            type="button"
            aria-label="Fechar"
            onClick={onClose}
            className="flex h-11 w-11 items-center justify-center rounded-md hover:bg-accent"
          >
            <X className="h-5 w-5" aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
