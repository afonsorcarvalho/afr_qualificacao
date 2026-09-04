'use client'
import { PendingLink } from '@/components/ui/PendingLink'
import { Camera, FileSpreadsheet, FileText, Database, File, ChevronRight } from 'lucide-react'
import { GlassCard } from '@/components/ui/GlassCard'
import { KindPill } from './KindPill'
import { InstrumentBadges } from './InstrumentBadges'
import type { ColetaItemDetail, InstrumentInfo, QualifInfo } from '@/lib/odoo/tecnico'

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  foto: Camera,
  excel: FileSpreadsheet,
  pdf: FileText,
  qualificador_data: Database,
  outro: File,
}

// O tipo precisa de nome, não só de ícone: a mesma coleta costuma existir em
// duas versões (a foto e a planilha do mesmo ciclo), com nome idêntico. Só o
// ícone deixava as duas linhas indistinguíveis na lista.
const KIND_LABELS: Record<string, string> = {
  foto: 'Foto',
  excel: 'Planilha',
  pdf: 'PDF',
  qualificador_data: 'Dados do qualificador',
  outro: 'Arquivo',
}

export function ColetaCard({
  osId,
  item,
  instruments = {},
  qualifs = {},
  mostrarTipo = false,
}: {
  osId: number
  item: ColetaItemDetail
  instruments?: Record<number, InstrumentInfo>
  qualifs?: Record<number, QualifInfo>
  /** Só marca o tipo quando a lista mistura QI/QO/QD — numa OS de um tipo só,
   *  a etiqueta seria a mesma em todas as linhas e viraria ruído. */
  mostrarTipo?: boolean
}) {
  const Icon = ICONS[item.kind] ?? File
  // Tipo real do item. Antes ia `"installation"` fixo, então a etiqueta dizia
  // "QI" até em coleta de QO.
  const qualifType = item.qualif_id
    ? qualifs[item.qualif_id[0]]?.qualification_type
    : undefined
  return (
    <PendingLink href={`/tecnico/qualificacao/${osId}/coleta/${item.id}`}>
      <GlassCard
        variant="hover"
        noPadding
        className="cursor-pointer p-3"
      >
        <div className="flex min-h-[56px] items-center gap-3">
          <Icon className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
          <div className="flex-1 overflow-hidden">
            <div className="flex items-center justify-between gap-2">
              <strong className="truncate text-sm text-foreground">{item.name}</strong>
              {mostrarTipo && qualifType && <KindPill qualifType={qualifType} />}
            </div>
            <p className="text-xs text-muted-foreground">
              {KIND_LABELS[item.kind] ?? item.kind}
            </p>
            {item.instruction && (
              <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                {item.instruction}
              </p>
            )}
            <InstrumentBadges item={item} instruments={instruments} />
          </div>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        </div>
      </GlassCard>
    </PendingLink>
  )
}
