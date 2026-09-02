'use client'
import { useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { SignaturePad } from '../../../../_components/SignatureCanvas'
import { MicButton } from '../../../../_components/MicButton'
import { SummaryButton } from '../../../../_components/SummaryButton'
import { ReviewPanel } from '../../../../_components/ReviewPanel'
import { useFinalizeRelatorio, useOsDetail } from '@/lib/hooks/useTecnicoQualif'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import { useGroqStatus } from '@/lib/hooks/useGroqStatus'
import { buildSummaryContext } from '@/lib/tecnico/buildSummaryContext'
import toast from 'react-hot-toast'

export default function FinalizarPage() {
  const { osId, relId } = useParams<{ osId: string; relId: string }>()
  const oid = parseInt(osId, 10)
  const rid = parseInt(relId, 10)
  const router = useRouter()
  const { lastUserId } = useTecnicoSettings()
  const userId = lastUserId ?? 0
  const { data } = useOsDetail(oid, userId)
  const [descricao, setDescricao] = useState('')
  const [signatureB64, setSignatureB64] = useState<string | null>(null)
  const mutation = useFinalizeRelatorio(oid)

  const { enabled: groqEnabled } = useGroqStatus()
  const autoTriggeredRef = useRef(false)
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    if (autoTriggeredRef.current) return
    if (!groqEnabled) return
    if (!data) return
    if (descricao !== '') return
    if (typeof navigator !== 'undefined' && navigator.onLine === false) return
    autoTriggeredRef.current = true
    setGenerating(true)
    fetch('/api/groq/summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildSummaryContext(data)),
    })
      .then(async (res) => {
        let json: any = null
        try { json = await res.json() } catch { /* response sem JSON */ }
        if (res.ok && typeof json?.summary === 'string') {
          setDescricao(json.summary)
        } else {
          toast.error(`IA: ${json?.error || `falha auto-resumo (HTTP ${res.status})`}`)
        }
      })
      .catch((e) => toast.error(`IA: ${e.message || 'offline'}`))
      .finally(() => setGenerating(false))
  }, [data, descricao, groqEnabled])

  const collected = (data?.collect_items ?? []).filter((i) => i.state === 'collected').length
  const pending = (data?.collect_items ?? []).filter((i) => i.state === 'pending').length

  const handleFinish = () => {
    if (!descricao.trim()) {
      toast.error('Descrição do turno é obrigatória')
      return
    }
    if (!signatureB64) {
      toast.error('Assinatura é obrigatória')
      return
    }
    mutation.mutate(
      {
        relId: rid,
        payload: { descricao, signature_b64: signatureB64 },
      },
      {
        onSuccess: () => {
          toast.success('Relatório finalizado')
          router.push(`/tecnico/qualificacao/${oid}`)
        },
        onError: (e: any) => toast.error(`Erro: ${e.message}`),
      },
    )
  }

  return (
    <div className="space-y-3">
      <Button variant="ghost" size="sm" onClick={() => router.back()}>
        ← Voltar
        <kbd className="ml-2 hidden rounded border border-border/60 bg-muted/30 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground/90 sm:inline">Esc</kbd>
      </Button>
      <h1 className="text-lg font-semibold">Finalizar relatório #{rid}</h1>

      <div className="border-l-4 border-l-emerald-500 rounded-lg bg-muted/30 border border-border/70 p-3">
        <div className="flex justify-between">
          <strong>Coletas realizadas</strong>
          <span className="font-semibold text-emerald-600">{collected}</span>
        </div>
      </div>

      <div className="border-l-4 border-l-amber-500 rounded-lg bg-muted/30 border border-border/70 p-3">
        <div className="flex justify-between">
          <strong>Pendentes restantes</strong>
          <span className="font-semibold text-amber-600">{pending}</span>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Voltam pra próxima sessão
        </p>
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <label htmlFor="desc" className="text-sm font-medium">Descrição do turno *</label>
          <div className="flex items-center gap-2">
            <MicButton
              onTranscribe={(t) =>
                setDescricao((prev) => (prev ? `${prev} ${t}`.trim() : t))
              }
            />
            {data && (
              <SummaryButton
                buildContext={() => buildSummaryContext(data)}
                onGenerate={(s) => setDescricao(s)}
                label={descricao ? '✨ Regenerar resumo' : '✨ Gerar resumo'}
                confirmOverwrite={!!descricao}
              />
            )}
          </div>
        </div>
        <textarea
          id="desc"
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          placeholder={generating ? 'Gerando resumo automático... (você pode editar aqui)' : 'Ex.: Ciclo vazio 08-12h, ciclo carga 13-17h. Sem anomalias.'}
          rows={6}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      {data && (
        <ReviewPanel
          buildContext={() => buildSummaryContext(data)}
          osId={oid}
          relId={rid}
          autoTrigger
        />
      )}

      <div>
        <label className="text-sm font-medium">Assinatura técnico *</label>
        <SignaturePad onChange={setSignatureB64} />
      </div>

      <div className="flex gap-2">
        <Button variant="outline" className="flex-1" onClick={() => router.back()}>
          Cancelar
        </Button>
        <Button
          className="flex-[2] bg-emerald-500 hover:bg-emerald-600"
          onClick={handleFinish}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Finalizando...' : 'Fechar relatório'}
        </Button>
      </div>
    </div>
  )
}
