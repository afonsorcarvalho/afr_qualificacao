'use client'
import { GlassCard } from '@/components/ui/GlassCard'
import { Button } from '@/components/ui/button'
import { Play, FileText, RefreshCw, RotateCcw } from 'lucide-react'

export function RelatorioHeader({
  openRelId,
  onStart,
  onContinue,
  starting,
  allDone = false,
}: {
  openRelId: number | null
  onStart: () => void
  onContinue: () => void
  starting: boolean
  allDone?: boolean
}) {
  if (allDone && !openRelId) {
    return (
      <button
        type="button"
        onClick={onStart}
        disabled={starting}
        className="group flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-amber-400/40 bg-amber-500/5 px-4 py-3 text-sm font-semibold text-amber-200 transition hover:border-amber-400/80 hover:bg-amber-500/10 disabled:cursor-wait disabled:opacity-60"
      >
        <RotateCcw className="h-4 w-4" />
        {starting ? 'Reabrindo...' : 'Reabrir coletas (corrigir alguma)'}
      </button>
    )
  }
  if (openRelId) {
    return (
      <GlassCard noPadding className="border-l-4 border-l-emerald-500 p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-emerald-400" />
            <div>
              <p className="text-xs uppercase text-muted-foreground/90">Relatório aberto</p>
              <p className="font-semibold text-foreground">REL #{openRelId}</p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={onContinue}>
            <RefreshCw className="mr-1 h-3.5 w-3.5" /> Atualizar
          </Button>
        </div>
      </GlassCard>
    )
  }
  return (
    <button
      type="button"
      onClick={onStart}
      disabled={starting}
      className="group relative w-full overflow-hidden rounded-xl bg-gradient-to-br from-emerald-500 via-emerald-600 to-teal-600 px-6 py-5 text-left shadow-lg shadow-emerald-500/40 ring-1 ring-emerald-300/40 transition hover:shadow-emerald-500/60 hover:brightness-110 disabled:cursor-wait disabled:opacity-60"
    >
      <span className="pointer-events-none absolute inset-0 opacity-0 transition group-hover:opacity-100 bg-[radial-gradient(circle_at_20%_-20%,rgba(255,255,255,0.4),transparent_60%)]" />
      <span className="pointer-events-none absolute -inset-1 -z-10 animate-pulse rounded-xl bg-emerald-400/30 blur-xl" />
      <div className="relative flex items-center gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-foreground/10 ring-2 ring-foreground/20">
          <Play className="h-6 w-6 fill-white text-foreground" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-foreground/90">
            Comece o turno
          </p>
          <p className="text-lg font-bold leading-tight text-foreground">
            {starting ? 'Iniciando...' : 'Iniciar relatório do dia'}
          </p>
        </div>
        <span className="text-2xl text-foreground/90">›</span>
      </div>
    </button>
  )
}
