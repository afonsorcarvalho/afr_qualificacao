'use client'
import { useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { GlassCard } from '@/components/ui/GlassCard'

/** Seção colapsável da ficha. O `aria-label` dá o nome de região (usado por leitores de tela e testes). */
export function FichaSecao({
  titulo,
  children,
  defaultOpen = true,
}: {
  titulo: string
  children: ReactNode
  defaultOpen?: boolean
}) {
  const [aberta, setAberta] = useState(defaultOpen)
  return (
    <section aria-label={titulo}>
      <GlassCard noPadding className="overflow-hidden">
        <button
          type="button"
          aria-expanded={aberta}
          onClick={() => setAberta((v) => !v)}
          className="flex min-h-[44px] w-full items-center justify-between px-3 text-left text-sm font-semibold"
        >
          {titulo}
          <ChevronDown className={aberta ? 'h-4 w-4 rotate-180' : 'h-4 w-4'} aria-hidden />
        </button>
        {aberta && <div className="space-y-3 border-t border-border p-3">{children}</div>}
      </GlassCard>
    </section>
  )
}
