'use client'
import { PendingLink } from '@/components/ui/PendingLink'
import { CheckCircle2, Clock, Wrench } from 'lucide-react'
import { GlassCard } from '@/components/ui/GlassCard'
import { StatusBadge, type StatusTone } from '@/components/ui/StatusBadge'
import type { OsTecnicoSummary } from '@/lib/odoo/tecnico'

const STATE_LABELS: Record<string, string> = {
  draft: 'Rascunho',
  scheduled: 'Agendada',
  in_progress: 'Em andamento',
  in_approved: 'Aguard. aprovação',
  approved: 'Aprovada',
  done: 'Concluída',
  cancelled: 'Cancelada',
}


// Tom semântico, não paleta decorativa: o que está andando ou pronto é
// verde, o que espera alguém é âmbar, o que morreu é vermelho, o resto é
// neutro. Antes "aprovado" era roxo e "agendado" azul — cores que não
// diziam nada sozinhas.
const STATE_TONES: Record<string, StatusTone> = {
  draft: 'neutral',
  scheduled: 'neutral',
  in_progress: 'progress',
  in_approved: 'waiting',
  approved: 'done',
  done: 'done',
  cancelled: 'error',
}

export function OsCard({ os }: { os: OsTecnicoSummary }) {
  return (
    <PendingLink href={`/tecnico/qualificacao/${os.id}`} spinnerClassName="right-4 top-6">
      <GlassCard
        variant="hover"
        noPadding
        className="cursor-pointer p-3"
      >
        <div className="flex items-center justify-between gap-2">
          <strong className="truncate text-foreground text-sm">{os.name}</strong>
          <StatusBadge tone={STATE_TONES[os.state] ?? 'neutral'} size="sm">
            {STATE_LABELS[os.state] ?? os.state}
          </StatusBadge>
        </div>
        <p className="mt-1 truncate text-sm text-muted-foreground/90">
          {os.partner_id?.[1] ?? '—'}
        </p>

        {typeof os.equipment_count === 'number' && os.equipment_count > 0 && (
          <p className="mt-1 inline-flex items-center gap-1 text-xs text-cyan-700 dark:text-cyan-300">
            <Wrench className="h-3 w-3" />
            <strong>{os.equipment_count}</strong> equipamento{os.equipment_count !== 1 ? 's' : ''} a qualificar
          </p>
        )}

        {os.collect_total_count > 0 && (
          <div className="mt-2 space-y-1">
            <div className="flex items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 text-emerald-300">
                  <CheckCircle2 className="h-3 w-3" />
                  <strong>{os.collect_collected_count}</strong> coletadas
                </span>
                <span className="text-muted-foreground/60">·</span>
                <span className="inline-flex items-center gap-1 text-amber-300">
                  <Clock className="h-3 w-3" />
                  <strong>{os.collect_pending_count}</strong> pendentes
                </span>
              </div>
              <span className="font-mono text-muted-foreground/80">
                {os.collect_collected_count}/{os.collect_total_count}
              </span>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-muted/40">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all"
                style={{ width: `${(os.collect_collected_count / os.collect_total_count) * 100}%` }}
              />
            </div>
          </div>
        )}

        {os.date_planned_start && (
          <div className="mt-1 text-xs text-muted-foreground/80">
            {new Date(os.date_planned_start).toLocaleString('pt-BR')}
          </div>
        )}
      </GlassCard>
    </PendingLink>
  )
}
