'use client'
import { ReactNode } from 'react'
import { Ruler } from 'lucide-react'
import { NavProgressBar, NavProgressProvider } from '@/components/providers/NavProgress'
import { TecnicoNav } from '@/app/tecnico/qualificacao/_components/TecnicoNav'
import { SURVEY_GROUP } from '@/lib/levantamento/constants'
import { useHasGroup } from '@/lib/hooks/useHasGroup'

/**
 * Casca do levantamento de campo. O loop de sync e o pedido de storage
 * persistente moram em `SurveySyncProvider` (app inteiro), para a fila esvaziar
 * mesmo fora destas telas.
 */
export default function LevantamentoLayout({ children }: { children: ReactNode }) {
  const temGrupo = useHasGroup(SURVEY_GROUP)

  return (
    <NavProgressProvider>
      <div className="mx-auto flex h-dvh min-h-0 w-full max-w-[480px] flex-col overflow-hidden bg-background sm:max-w-[720px] lg:max-w-none lg:flex-row">
        <TecnicoNav variant="side" levantamento={temGrupo} />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-10 border-b border-border bg-card shadow-md lg:static lg:shadow-none">
            <div className="flex items-center gap-2 px-4 py-3">
              <Ruler className="h-5 w-5 text-foreground" aria-hidden />
              <span className="font-semibold">Levantamento de campo</span>
            </div>
            <NavProgressBar />
          </header>
          <main className="min-h-0 flex-1 overflow-auto">
            <div className="h-full p-3">{children}</div>
          </main>
          <TecnicoNav variant="bottom" levantamento={temGrupo} />
        </div>
      </div>
    </NavProgressProvider>
  )
}
