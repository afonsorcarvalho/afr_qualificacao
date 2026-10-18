'use client'
import { useEffect, useState } from 'react'
import { CloudOff } from 'lucide-react'
import { pendingCount } from '@/lib/levantamento/repo'

const REFRESH_MS = 5_000

/** Alterações ainda na outbox. Relê a cada poucos segundos: o loop de sync
 *  esvazia a fila em segundo plano e não avisa a tela. */
export function PendenciasBanner() {
  const [n, setN] = useState(0)
  useEffect(() => {
    let vivo = true
    const ler = () =>
      pendingCount()
        .then((v) => vivo && setN(v))
        .catch(() => {})
    void ler()
    const id = setInterval(ler, REFRESH_MS)
    return () => {
      vivo = false
      clearInterval(id)
    }
  }, [])
  if (n <= 0) return null
  return (
    <div
      role="status"
      className="mb-3 flex items-center gap-2 rounded-md border border-warn/40 bg-warn-surface px-3 py-2 text-sm text-foreground"
    >
      <CloudOff className="h-4 w-4 shrink-0 text-warn" aria-hidden />
      {n === 1 ? '1 alteração aguardando sinal' : `${n} alterações aguardando sinal`}
    </div>
  )
}
