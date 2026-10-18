'use client'
import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'

/** Selo vermelho de falha de envio; ao tocar mostra o motivo (`syncError`). */
export function SyncErrorBadge({ error }: { error?: string }) {
  const [aberto, setAberto] = useState(false)
  return (
    <div>
      <button
        type="button"
        aria-expanded={aberto}
        onClick={() => setAberto((v) => !v)}
        className="inline-flex min-h-[44px] items-center gap-1 rounded-full border border-danger/30 bg-danger-surface px-3 text-xs font-medium text-danger"
      >
        <AlertTriangle className="h-3 w-3" aria-hidden />
        erro de envio
      </button>
      {aberto && <p className="mt-1 text-xs text-danger">{error || 'Falha ao enviar. Tente novamente.'}</p>}
    </div>
  )
}
