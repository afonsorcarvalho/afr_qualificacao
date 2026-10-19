'use client'
import { useEffect, useState } from 'react'
import { CloudOff } from 'lucide-react'
import { errorCount, pendingCount } from '@/lib/levantamento/repo'
import { onSyncTick } from '@/lib/levantamento/events'

const REFRESH_MS = 5_000

/** Alterações ainda na outbox. Relê a cada poucos segundos: o loop de sync
 *  esvazia a fila em segundo plano e não avisa a tela. */
export function PendenciasBanner() {
  const [n, setN] = useState(0)
  const [erros, setErros] = useState(0)
  useEffect(() => {
    let vivo = true
    const ler = () =>
      Promise.all([pendingCount(), errorCount()])
        .then(([p, e]) => {
          if (!vivo) return
          setN(p)
          setErros(e)
        })
        .catch(() => {})
    void ler()
    const id = setInterval(ler, REFRESH_MS)
    const off = onSyncTick(() => void ler())
    return () => {
      vivo = false
      clearInterval(id)
      off()
    }
  }, [])
  if (n <= 0 && erros <= 0) return null
  const partes = [
    n > 0 ? (n === 1 ? '1 alteração aguardando sinal' : `${n} alterações aguardando sinal`) : '',
    erros > 0 ? (erros === 1 ? '1 com erro' : `${erros} com erro`) : '',
  ].filter(Boolean)
  return (
    <div
      role="status"
      className="mb-3 flex items-center gap-2 rounded-md border border-warn/40 bg-warn-surface px-3 py-2 text-sm text-foreground"
    >
      <CloudOff className="h-4 w-4 shrink-0 text-warn" aria-hidden />
      {partes.join(' · ')}
    </div>
  )
}
