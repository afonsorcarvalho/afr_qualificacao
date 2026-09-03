'use client'
import { Gauge, ShieldCheck, ShieldAlert, RotateCw, Activity } from 'lucide-react'
import type { ColetaItemDetail, InstrumentInfo } from '@/lib/odoo/tecnico'

export function InstrumentBadges({
  item,
  instruments,
}: {
  item: ColetaItemDetail
  instruments: Record<number, InstrumentInfo>
}) {
  const linked = (item.standard_instrument_ids ?? [])
    .map((id) => instruments[id])
    .filter(Boolean)

  const showSection = item.cycle_id || item.malha_id || linked.length > 0 || item.requires_instrument

  if (!showSection) return null

  return (
    <div className="mt-1.5 space-y-1.5">
      {item.cycle_id && (
        <div className="inline-flex items-center gap-1 rounded border border-violet-600/40 bg-violet-500/20 px-2 py-0.5 text-[11px] text-violet-900 dark:border-violet-500/30 dark:bg-violet-500/15 dark:text-violet-200">
          <RotateCw className="h-3 w-3" /> Ciclo: {item.cycle_id[1]}
        </div>
      )}
      {item.malha_id && (
        <div className="inline-flex items-center gap-1 rounded border border-orange-600/40 bg-orange-500/20 px-2 py-0.5 text-[11px] text-orange-900 dark:border-orange-500/30 dark:bg-orange-500/15 dark:text-orange-200">
          <Activity className="h-3 w-3" /> Malha: {item.malha_id[1]}
        </div>
      )}
      {(item.requires_instrument || item.kind === 'qualificador_data' || linked.length > 0) && (
        <div className="rounded border border-border/70 bg-muted/20 p-2">
          <p className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground/90">
            <Gauge className="h-3 w-3" />
            Qualificador / Padrão{linked.length > 1 ? 'es' : ''} cadastrado{linked.length > 1 ? 's' : ''}
          </p>
          {linked.length === 0 ? (
            <p className="text-[11px] italic text-amber-300/80">Nenhum cadastrado</p>
          ) : (
            <ul className="space-y-0.5">
              {linked.map((inst) => (
                <li key={inst.id} className="flex items-start gap-1.5 text-[11px] text-foreground/90">
                  {inst.has_valid_certificate
                    ? <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" />
                    : <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0 text-amber-400" />
                  }
                  <span className="min-w-0">
                    <strong className="text-foreground">{inst.name}</strong>
                    {inst.tag && <span className="ml-1 font-mono text-cyan-700 dark:text-cyan-300/80">[{inst.tag}]</span>}
                    {inst.id_number && <span className="ml-1 text-muted-foreground/90">#{inst.id_number}</span>}
                    {(inst.marca || inst.modelo) && (
                      <span className="block text-[10px] text-muted-foreground/80">
                        {[inst.marca, inst.modelo].filter(Boolean).join(' · ')}
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
