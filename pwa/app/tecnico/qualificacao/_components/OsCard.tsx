'use client'
import Link from 'next/link'
import { CheckCircle2, Clock, Wrench } from 'lucide-react'
import { GlassCard } from '@/components/ui/GlassCard'
import { NeonBadge } from '@/components/ui/NeonBadge'
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

type NeonColor = 'blue' | 'purple' | 'pink' | 'green' | 'orange' | 'gray'

const STATE_COLORS: Record<string, NeonColor> = {
  draft: 'gray',
  scheduled: 'blue',
  in_progress: 'green',
  in_approved: 'orange',
  approved: 'purple',
  done: 'gray',
  cancelled: 'gray',
}

export function OsCard({ os }: { os: OsTecnicoSummary }) {
  return (
    <Link href={`/tecnico/qualificacao/${os.id}`} className="block">
      <GlassCard
        variant="hover"
        noPadding
        className="cursor-pointer p-3"
      >
        <div className="flex items-center justify-between gap-2">
          <strong className="truncate text-foreground text-sm">{os.name}</strong>
          <NeonBadge color={STATE_COLORS[os.state] ?? 'gray'} size="sm">
            {STATE_LABELS[os.state] ?? os.state}
          </NeonBadge>
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
    </Link>
  )
}
