'use client'
import { useState } from 'react'
import { AlertTriangle, RotateCcw, Trash2 } from 'lucide-react'
import { discardRecord, retryRecord, type RecordKind } from '@/lib/levantamento/repo'
import { emitSyncTick, requestSync } from '@/lib/levantamento/events'

const NOME: Record<RecordKind, string> = {
  partner: 'este cliente e os equipamentos dele',
  equipment: 'este equipamento, seus ciclos e fotos',
  cycle: 'este ciclo e suas fotos',
  photo: 'esta foto',
}

/**
 * Selo vermelho de falha de envio; ao tocar mostra o motivo (`syncError`) e,
 * com `recordKey`, as ações "Reenviar" e "Descartar" do registro.
 */
export function SyncErrorBadge({
  error,
  recordKey,
  recordKind,
  label = 'erro de envio',
  onDiscarded,
}: {
  error?: string
  recordKey?: string
  recordKind?: RecordKind
  label?: string
  onDiscarded?: () => void
}) {
  const [aberto, setAberto] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [falha, setFalha] = useState('')

  async function agir(fn: () => Promise<unknown>) {
    setOcupado(true)
    setFalha('')
    try {
      await fn()
      emitSyncTick()
      return true
    } catch (e) {
      setFalha(e instanceof Error ? e.message : 'Falha')
      return false
    } finally {
      setOcupado(false)
    }
  }

  const reenviar = () =>
    agir(async () => {
      await retryRecord(recordKey!, recordKind)
      requestSync()
    })

  async function descartar() {
    const alvo = recordKind ? NOME[recordKind] : 'este registro'
    if (!window.confirm(`Descartar ${alvo}? As alterações não enviadas serão apagadas deste aparelho.`)) return
    if (await agir(() => discardRecord(recordKey!, recordKind))) onDiscarded?.()
  }

  return (
    <div>
      <button
        type="button"
        aria-expanded={aberto}
        onClick={() => setAberto((v) => !v)}
        className="inline-flex min-h-[44px] items-center gap-1 rounded-full border border-danger/30 bg-danger-surface px-3 text-xs font-medium text-danger"
      >
        <AlertTriangle className="h-3 w-3" aria-hidden />
        {label}
      </button>
      {aberto && (
        <div className="mt-1 space-y-2">
          <p className="text-xs text-danger">{error || 'Falha ao enviar. Tente novamente.'}</p>
          {recordKey && (
            <div className="flex gap-2">
              <button
                type="button"
                disabled={ocupado}
                onClick={() => void reenviar()}
                className="inline-flex min-h-[44px] items-center gap-1 rounded-md border border-border bg-card px-3 text-xs font-medium text-foreground hover:bg-accent disabled:opacity-50"
              >
                <RotateCcw className="h-3 w-3" aria-hidden />
                Reenviar
              </button>
              <button
                type="button"
                disabled={ocupado}
                onClick={() => void descartar()}
                className="inline-flex min-h-[44px] items-center gap-1 rounded-md border border-danger/30 bg-card px-3 text-xs font-medium text-danger hover:bg-accent disabled:opacity-50"
              >
                <Trash2 className="h-3 w-3" aria-hidden />
                Descartar
              </button>
            </div>
          )}
          {falha && <p role="alert" className="text-xs text-danger">{falha}</p>}
        </div>
      )}
    </div>
  )
}
