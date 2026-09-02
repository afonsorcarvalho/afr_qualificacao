'use client'
import Link from 'next/link'
import { Camera, FileSpreadsheet, FileText, Database, File } from 'lucide-react'
import { GlassCard } from '@/components/ui/GlassCard'
import { KindPill } from './KindPill'
import { InstrumentBadges } from './InstrumentBadges'
import type { ColetaItemDetail, InstrumentInfo } from '@/lib/odoo/tecnico'

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  foto: Camera,
  excel: FileSpreadsheet,
  pdf: FileText,
  qualificador_data: Database,
  outro: File,
}

export function ColetaCard({
  osId,
  item,
  instruments = {},
}: {
  osId: number
  item: ColetaItemDetail
  instruments?: Record<number, InstrumentInfo>
}) {
  const Icon = ICONS[item.kind] ?? File
  return (
    <Link
      href={`/tecnico/qualificacao/${osId}/coleta/${item.id}`}
      className="block"
    >
      <GlassCard
        variant="hover"
        noPadding
        className="cursor-pointer p-3"
      >
        <div className="flex items-center gap-3">
          <Icon className="h-5 w-5 shrink-0 text-muted-foreground/80" />
          <div className="flex-1 overflow-hidden">
            <div className="flex items-center justify-between gap-2">
              <strong className="truncate text-sm text-foreground">{item.name}</strong>
              {item.docx_section && (
                <KindPill
                  qualifType="installation"
                  subLabel={item.docx_section.split('_')[0]?.toUpperCase()}
                />
              )}
            </div>
            {item.instruction && (
              <p className="mt-1 line-clamp-1 text-xs text-muted-foreground/80">
                {item.instruction}
              </p>
            )}
            <InstrumentBadges item={item} instruments={instruments} />
          </div>
          <span className="text-muted-foreground/60">→</span>
        </div>
      </GlassCard>
    </Link>
  )
}
