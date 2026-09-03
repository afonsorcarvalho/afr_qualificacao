'use client'
import { useTransition } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { LoadingState } from '@/components/ui/LoadingState'
import { useNavProgress } from '@/components/providers/NavProgress'
import { ColetaCard } from '../_components/ColetaCard'
import { CollectedCard } from '../_components/CollectedCard'
import { EquipmentHeader } from '../_components/EquipmentHeader'
import { RelatorioHeader } from '../_components/RelatorioHeader'
import { ReviewPanel } from '../_components/ReviewPanel'
import {
  useOsDetail,
  useStartDailyRelatorio,
} from '@/lib/hooks/useTecnicoQualif'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import { buildSummaryContext } from '@/lib/tecnico/buildSummaryContext'
import toast from 'react-hot-toast'

export default function OsDetailPage() {
  const { osId } = useParams<{ osId: string }>()
  const id = parseInt(osId, 10)
  const router = useRouter()
  const { lastUserId } = useTecnicoSettings()
  const userId = lastUserId ?? 0
  const { data, isLoading, isFetching, error, refetch } = useOsDetail(id, userId)
  const startMutation = useStartDailyRelatorio()
  const { begin } = useNavProgress()
  // A ida pra tela de fechar turno também busca dados: sem `useTransition` o
  // botão ficava mudo entre o toque e a troca de tela.
  const [finalizando, startFinalize] = useTransition()

  if (isLoading) return <LoadingState label="Carregando OS..." />
  if (error || !data) return <p className="text-center text-red-400">Erro ao carregar OS</p>

  const { os, collect_items, open_relatorio_id, equipments, instruments } = data
  const pending_items = collect_items.filter((i) => i.state === 'pending')
  const done_items = collect_items.filter((i) => i.state === 'collected' || i.state === 'skipped')

  function groupByEquipment(items: typeof collect_items) {
    const groups = new Map<string, { label: string; eqId: number | null; items: typeof collect_items }>()
    for (const it of items) {
      const eqId = it.equipment_id ? it.equipment_id[0] : null
      const key = eqId !== null ? `eq-${eqId}` : 'sem-equip'
      const label = it.equipment_id ? it.equipment_id[1] : 'Sem equipamento'
      if (!groups.has(key)) groups.set(key, { label, eqId, items: [] })
      groups.get(key)!.items.push(it)
    }
    return Array.from(groups.values()).sort((a, b) => a.label.localeCompare(b.label))
  }
  const groupList = groupByEquipment(pending_items)
  const doneGroupList = groupByEquipment(done_items)

  const handleStart = () => {
    startMutation.mutate(id, {
      onError: (e: any) => toast.error(e.message),
    })
  }
  const handleContinue = () => {
    refetch()
  }
  const handleFinalize = () => {
    if (!open_relatorio_id || finalizando) return
    begin()
    startFinalize(() =>
      router.push(`/tecnico/qualificacao/${id}/relatorio/${open_relatorio_id}/finalizar`),
    )
  }

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => router.back()}>
        ← Voltar
        <kbd className="ml-2 hidden rounded border border-border/60 bg-muted/30 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground/90 sm:inline">Esc</kbd>
      </Button>

      <div className="rounded-lg bg-muted/30 p-3 shadow-sm border border-border/70">
        <h1 className="text-lg font-semibold text-foreground">{os.name}</h1>
        <p className="text-sm text-muted-foreground/90">{os.partner_id?.[1]}</p>
      </div>

      <RelatorioHeader
        openRelId={open_relatorio_id}
        onStart={handleStart}
        onContinue={handleContinue}
        starting={startMutation.isPending}
        refreshing={isFetching && !isLoading}
        allDone={pending_items.length === 0 && done_items.length > 0}
      />

      {open_relatorio_id && done_items.length > 0 && (
        <ReviewPanel
          buildContext={() => buildSummaryContext(data)}
          osId={id}
          relId={open_relatorio_id}
          collapsedByDefault
        />
      )}

      {pending_items.length === 0 && done_items.length > 0 && (
        <div className="relative overflow-hidden rounded-2xl border-2 border-emerald-400/60 bg-gradient-to-br from-emerald-500/30 via-teal-500/20 to-cyan-500/20 p-5 text-center shadow-xl shadow-emerald-500/30">
          <div className="pointer-events-none absolute -top-10 -left-10 h-40 w-40 animate-pulse rounded-full bg-emerald-400/30 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-10 -right-10 h-40 w-40 animate-pulse rounded-full bg-cyan-400/30 blur-3xl" />
          <div className="relative">
            <div className="mb-2 flex justify-center gap-2 text-4xl">
              <span className="animate-bounce" style={{ animationDelay: '0ms' }}>🎉</span>
              <span className="animate-bounce" style={{ animationDelay: '120ms' }}>🏆</span>
              <span className="animate-bounce" style={{ animationDelay: '240ms' }}>🎊</span>
            </div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-200">Parabéns, técnico!</p>
            <h3 className="mt-1 text-2xl font-extrabold text-foreground drop-shadow">
              Todas as coletas concluídas
            </h3>
            <p className="mt-2 text-sm text-emerald-100/90">
              {done_items.length} de {done_items.length} item{done_items.length > 1 ? 's coletados' : ' coletado'} nesta OS.
            </p>
            {open_relatorio_id ? (
              <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-muted/70 px-3 py-1 text-xs font-semibold text-foreground ring-1 ring-foreground/20">
                ✓ Pronto pra finalizar o relatório
              </p>
            ) : (
              <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-muted/70 px-3 py-1 text-xs font-semibold text-foreground ring-1 ring-foreground/20">
                ✓ Ordem de Serviço concluída
              </p>
            )}
          </div>
        </div>
      )}

      {(pending_items.length > 0 || done_items.length === 0) && (
      <div className="space-y-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80">
          {open_relatorio_id ? `Coletas pendentes (${pending_items.length})` : `Prévia das coletas (${pending_items.length})`}
        </h2>
        {pending_items.length === 0 ? (
          <p className="rounded-lg bg-muted/30 border border-border/70 p-3 text-center text-sm text-muted-foreground/90">
            Nenhuma coleta cadastrada.
          </p>
        ) : (
          groupList.map((g) => (
            <div key={g.label} className="space-y-2">
              <EquipmentHeader
                label={g.label}
                eq={g.eqId ? equipments[g.eqId] : undefined}
                count={g.items.length}
                tone="cyan"
              />
              <div className="space-y-2 pl-2">
                {g.items.map((item) => (
                  open_relatorio_id ? (
                    <ColetaCard key={item.id} osId={id} item={item} instruments={instruments} />
                  ) : (
                    <div key={item.id} className="rounded-lg bg-muted/20 border border-border/40 p-3 opacity-60">
                      <p className="truncate text-sm text-foreground/90">{item.name}</p>
                      {item.instruction && (
                        <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground/80">{item.instruction}</p>
                      )}
                    </div>
                  )
                ))}
              </div>
            </div>
          ))
        )}
        {!open_relatorio_id && pending_items.length > 0 && (
          <p className="rounded-md border border-amber-500/20 bg-amber-500/5 p-2 text-center text-xs text-amber-300/80">
            Inicie o relatório do dia pra coletar.
          </p>
        )}
      </div>
      )}

      {done_items.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80">
            Já coletadas ({done_items.length})
          </h2>
          {doneGroupList.map((g) => (
            <div key={`done-${g.label}`} className="space-y-2">
              <EquipmentHeader
                label={g.label}
                eq={g.eqId ? equipments[g.eqId] : undefined}
                count={g.items.length}
                tone="emerald"
              />
              <div className="space-y-2 pl-2">
                {g.items.map((item) => (
                  <CollectedCard key={item.id} osId={id} item={item} canEdit={!!open_relatorio_id} instruments={instruments} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {open_relatorio_id && (
        <Button
          onClick={handleFinalize}
          className="h-12 w-full"
          loading={finalizando}
          loadingText="Abrindo fechamento..."
        >
          Finalizar relatório do dia
        </Button>
      )}
    </div>
  )
}
