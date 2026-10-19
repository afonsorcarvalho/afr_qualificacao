'use client'
import { ReactNode } from 'react'
import { Building2, Eye } from 'lucide-react'
import { NavProgressBar, NavProgressProvider } from '@/components/providers/NavProgress'
import { TecnicoNav } from '@/app/tecnico/qualificacao/_components/TecnicoNav'
import { useCanEdit } from '@/lib/cliente/nav'

/**
 * Casca de `/cliente`. Sem o grupo do levantamento a tela abre em modo leitura
 * (a página esconde as ações); o loop de sync e o pedido de storage persistente
 * moram em `SurveySyncProvider` e só rodam com o grupo.
 */
export default function ClienteLayout({ children }: { children: ReactNode }) {
  const podeEditar = useCanEdit()

  return (
    <NavProgressProvider>
      <div className="mx-auto flex h-dvh min-h-0 w-full max-w-[480px] flex-col overflow-hidden bg-background sm:max-w-[720px] lg:max-w-none lg:flex-row">
        <TecnicoNav variant="side" />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-10 border-b border-border bg-card shadow-md lg:static lg:shadow-none">
            <div className="flex items-center gap-2 px-4 py-3">
              <Building2 className="h-5 w-5 text-foreground" aria-hidden />
              <span className="font-semibold">Clientes</span>
              {!podeEditar && (
                <span className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <Eye className="h-3 w-3" aria-hidden />
                  Somente leitura
                </span>
              )}
            </div>
            <NavProgressBar />
          </header>
          <main className="min-h-0 flex-1 overflow-auto">
            <div className="h-full p-3">{children}</div>
          </main>
          <TecnicoNav variant="bottom" />
        </div>
      </div>
    </NavProgressProvider>
  )
}
