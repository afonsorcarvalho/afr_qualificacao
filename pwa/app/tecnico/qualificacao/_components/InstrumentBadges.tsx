'use client'
import { ShieldCheck, ShieldAlert, RotateCw, Activity } from 'lucide-react'
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
      {/* Ciclo e malha são categoria do item, não estado — chip neutro. Violeta
          e laranja saíram: no DESIGN.md cor só comunica estado. */}
      {item.cycle_id && (
        <div className="inline-flex items-center gap-1 rounded border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
          <RotateCw className="h-3 w-3 shrink-0" aria-hidden /> Ciclo: {item.cycle_id[1]}
        </div>
      )}
      {item.malha_id && (
        <div className="inline-flex items-center gap-1 rounded border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
          <Activity className="h-3 w-3 shrink-0" aria-hidden /> Malha: {item.malha_id[1]}
        </div>
      )}

      {/* Sem instrumento cadastrado: uma linha de aviso, não um cartão dentro
          do cartão da coleta (cartão aninhado é proibido no DESIGN.md). */}
      {(item.requires_instrument || item.kind === 'qualificador_data') && linked.length === 0 && (
        <p className="flex items-center gap-1.5 text-[11px] text-amber-600 dark:text-amber-400">
          <ShieldAlert className="h-3.5 w-3.5 shrink-0" aria-hidden />
          Sem qualificador/padrão cadastrado
        </p>
      )}

      {linked.length > 0 && (
        <ul className="space-y-0.5">
          {linked.map((inst) => (
            <li key={inst.id} className="flex items-start gap-1.5 text-[11px] text-foreground">
              {inst.has_valid_certificate
                ? <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
                : <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden />
              }
              <span className="min-w-0">
                <span className="sr-only">
                  {inst.has_valid_certificate ? 'Certificado válido: ' : 'Sem certificado válido: '}
                </span>
                <strong className="font-semibold">{inst.name}</strong>
                {inst.tag && <span className="ml-1 font-mono text-muted-foreground">[{inst.tag}]</span>}
                {inst.id_number && <span className="ml-1 text-muted-foreground">#{inst.id_number}</span>}
                {(inst.marca || inst.modelo) && (
                  <span className="block text-[10px] text-muted-foreground">
                    {[inst.marca, inst.modelo].filter(Boolean).join(' · ')}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
