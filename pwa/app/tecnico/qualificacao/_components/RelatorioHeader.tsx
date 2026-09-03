'use client'
import { GlassCard } from '@/components/ui/GlassCard'
import { Button } from '@/components/ui/button'
import { Play, FileText, RefreshCw, RotateCcw } from 'lucide-react'

/**
 * Cabeçalho do turno na tela da OS: iniciar, acompanhar ou reabrir.
 *
 * Todas as três ações falam com o servidor, então todas mostram estado de
 * carregando (regra da casa: nenhum toque sem resposta). A faixa lateral
 * colorida, o gradiente e o `animate-pulse` com blur saíram junto com o tema
 * neon — ver DESIGN.md.
 */
export function RelatorioHeader({
  openRelId,
  onStart,
  onContinue,
  starting,
  refreshing = false,
  allDone = false,
}: {
  openRelId: number | null
  onStart: () => void
  onContinue: () => void
  starting: boolean
  refreshing?: boolean
  allDone?: boolean
}) {
  if (allDone && !openRelId) {
    return (
      <Button
        variant="outline"
        onClick={onStart}
        loading={starting}
        loadingText="Reabrindo coletas..."
        className="h-12 w-full border-dashed"
      >
        <RotateCcw className="mr-2 h-4 w-4" aria-hidden />
        Reabrir coletas (corrigir alguma)
      </Button>
    )
  }

  if (openRelId) {
    return (
      <GlassCard noPadding className="p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <FileText className="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
            <div className="min-w-0">
              <p className="text-xs uppercase text-muted-foreground">Relatório aberto</p>
              <p className="font-semibold tabular-nums">REL #{openRelId}</p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onContinue}
            loading={refreshing}
            loadingText="Atualizando..."
            className="min-h-[44px] shrink-0"
          >
            <RefreshCw className="mr-1 h-3.5 w-3.5" aria-hidden /> Atualizar
          </Button>
        </div>
      </GlassCard>
    )
  }

  return (
    <Button
      onClick={onStart}
      loading={starting}
      loadingText="Iniciando relatório..."
      className="h-14 w-full justify-start gap-3 text-base"
    >
      <Play className="h-5 w-5 shrink-0" aria-hidden />
      <span className="flex flex-col items-start leading-tight">
        <span className="text-[11px] font-medium uppercase tracking-wider opacity-70">
          Comece o turno
        </span>
        <span className="font-semibold">Iniciar relatório do dia</span>
      </span>
    </Button>
  )
}
