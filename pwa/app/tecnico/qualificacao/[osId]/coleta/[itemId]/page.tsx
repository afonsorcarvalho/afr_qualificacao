'use client'
import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { LoadingState } from '@/components/ui/LoadingState'
import { Lightbulb } from 'lucide-react'
import { CameraInput } from '../../../_components/CameraInput'
import { FileInput } from '../../../_components/FileInput'
import { MicButton } from '../../../_components/MicButton'
import { ColetaList } from '../../../_components/ColetaList'
import { SplitPane } from '../../../_components/SplitPane'
import { useCollectItem, useOsDetail } from '@/lib/hooks/useTecnicoQualif'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import odooClient from '@/lib/odoo/client'
import toast from 'react-hot-toast'
import type { ColetaItemDetail } from '@/lib/odoo/tecnico'

// Todo item coletado precisa de anexo, 'outro' incluído. O backend sempre
// exigiu isso (`_check_required_has_file`: qualquer item em `state=collected`
// precisa de `file`), mas o front tratava 'outro' como anexo opcional — salvar
// um item "Outro" sem foto estourava ValidationError na cara do técnico, em
// campo, depois de ele já ter preenchido a observação. Decisão de 2026-09-03:
// alinhar pelo backend — item coletado é item com evidência anexada.
const FILE_REQUIRED_KINDS = ['foto', 'excel', 'pdf', 'qualificador_data', 'outro']

export default function ColetaPage() {
  const { osId, itemId } = useParams<{ osId: string; itemId: string }>()
  const oid = parseInt(osId, 10)
  const iid = parseInt(itemId, 10)
  const router = useRouter()

  const { data: itemList } = useQuery({
    queryKey: ['coleta', iid],
    queryFn: () => odooClient.searchRead<ColetaItemDetail>(
      'afr.qualificacao.collect.item',
      [['id', '=', iid]],
      ['name', 'kind', 'required', 'state', 'description', 'instruction',
       'requires_instrument', 'docx_section', 'qualif_id', 'equipment_id'],
    ),
    enabled: iid > 0,
  })
  const item = itemList?.[0]

  const { lastUserId } = useTecnicoSettings()
  const userId = lastUserId ?? 0
  const osDetail = useOsDetail(oid, userId)
  const relatorioId = osDetail.data?.open_relatorio_id ?? null

  const [fileData, setFileData] = useState<{
    base64: string
    filename: string
    mimetype: string
  } | null>(null)
  const [description, setDescription] = useState('')
  const [acao, setAcao] = useState<'salvar' | 'pular' | null>(null)

  const mutation = useCollectItem(oid)

  if (!item) return <LoadingState label="Carregando coleta..." />

  const lista = osDetail.data ? (
    <ColetaList data={osDetail.data} osId={oid} selectedId={iid} />
  ) : null

  if (!relatorioId) {
    return (
      <SplitPane narrow="detail" list={lista}>
        <div className="space-y-3">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
          ← Voltar
          <kbd className="ml-2 hidden rounded border border-border/60 bg-muted/30 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground/90 sm:inline">Esc</kbd>
        </Button>
          <p className="rounded-lg bg-destructive/10 p-3 text-center text-sm text-destructive">
            Inicie um relatório do dia antes de coletar.
          </p>
        </div>
      </SplitPane>
    )
  }

  const fileRequired = FILE_REQUIRED_KINDS.includes(item.kind)

  const handleSave = (skip: boolean) => {
    if (!skip && fileRequired && !fileData) {
      toast.error('Anexe arquivo antes de salvar')
      return
    }
    setAcao(skip ? 'pular' : 'salvar')
    mutation.mutate(
      {
        itemId: iid,
        payload: {
          ...(fileData
            ? {
                file_b64: fileData.base64,
                filename: fileData.filename,
                mimetype: fileData.mimetype,
              }
            : {}),
          description,
          relatorio_id: relatorioId,
          state: skip ? 'skipped' : 'collected',
        },
      },
      {
        onSuccess: () => {
          toast.success(skip ? 'Item pulado' : 'Coleta salva')
          router.back()
        },
        onError: (e: any) => toast.error(e.message),
      },
    )
  }

  return (
    <SplitPane narrow="detail" list={lista}>
    <div className="space-y-3">
      <Button variant="ghost" size="sm" onClick={() => router.back()}>
        ← Voltar
        <kbd className="ml-2 hidden rounded border border-border/60 bg-muted/30 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground/90 sm:inline">Esc</kbd>
      </Button>

      {item.equipment_id && (
        <div className="flex items-center gap-2 rounded-md bg-cyan-500/10 px-3 py-2 border border-cyan-500/30">
          <span className="text-base">🔧</span>
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wider text-cyan-300/60">Equipamento</p>
            <p className="truncate text-sm font-semibold text-cyan-300">{item.equipment_id[1]}</p>
          </div>
        </div>
      )}

      <h1 className="text-lg font-semibold">{item.name}</h1>

      {item.instruction && (
        <div className="flex gap-2 rounded-lg bg-amber-50 p-3 text-sm dark:bg-amber-950">
          <Lightbulb className="h-4 w-4 shrink-0 text-amber-600" />
          <p>{item.instruction}</p>
        </div>
      )}

      {fileRequired && (
        <div>
          <label className="text-sm font-medium">
            Arquivo *
          </label>
          {item.kind === 'foto' ? (
            <CameraInput onCapture={setFileData} />
          ) : (
            <FileInput kind={item.kind} onCapture={setFileData} />
          )}
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-1">
          <label htmlFor="desc" className="text-sm font-medium">Observação</label>
          <MicButton
            onTranscribe={(t) =>
              setDescription((prev) => (prev ? `${prev} ${t}`.trim() : t))
            }
          />
        </div>
        <textarea
          id="desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Notas adicionais..."
          rows={3}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      <div className="flex gap-2">
        {/* Dois botões disparam a mesma mutation, então cada um guarda qual
            foi tocado: sem isso, pular acendia o spinner em "Salvar" e vice-
            versa, e o técnico não sabia qual ação estava rodando. */}
        <Button
          variant="outline"
          className="min-h-[48px] flex-1"
          onClick={() => handleSave(true)}
          loading={mutation.isPending && acao === 'pular'}
          loadingText="Pulando..."
          disabled={mutation.isPending}
        >
          Pular
        </Button>
        <Button
          className="min-h-[48px] flex-[2]"
          onClick={() => handleSave(false)}
          loading={mutation.isPending && acao === 'salvar'}
          loadingText="Salvando..."
          disabled={mutation.isPending}
        >
          ✓ Salvar coleta
        </Button>
      </div>
    </div>
    </SplitPane>
  )
}
