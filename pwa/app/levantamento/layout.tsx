'use client'
import { ReactNode } from 'react'
import Link from 'next/link'
import { Ruler, ShieldAlert } from 'lucide-react'
import { NavProgressBar, NavProgressProvider } from '@/components/providers/NavProgress'
import { TecnicoNav } from '@/app/tecnico/qualificacao/_components/TecnicoNav'
import { SURVEY_GROUP } from '@/lib/levantamento/constants'
import { useHasGroup } from '@/lib/hooks/useHasGroup'
import { useAuthStore } from '@/lib/store/authStore'
import { LoadingState } from '@/components/ui/LoadingState'
import { buttonVariants } from '@/components/ui/button'

/**
 * Casca do levantamento de campo. O loop de sync e o pedido de storage
 * persistente moram em `SurveySyncProvider` (app inteiro), para a fila esvaziar
 * mesmo fora destas telas.
 */
export default function LevantamentoLayout({ children }: { children: ReactNode }) {
  const temGrupo = useHasGroup(SURVEY_GROUP)
  // `useHasGroup` devolve false tanto para "não tem" quanto para "ainda não sei";
  // o store só ganha a chave depois da 1ª resposta (ou do cache persistido).
  const conhecido = useAuthStore((s) => SURVEY_GROUP in s.groups)

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
            <div className="h-full p-3">
              {!conhecido ? (
                <LoadingState label="Verificando permissão..." />
              ) : temGrupo ? (
                children
              ) : (
                <SemAcesso />
              )}
            </div>
          </main>
          <TecnicoNav variant="bottom" levantamento={temGrupo} />
        </div>
      </div>
    </NavProgressProvider>
  )
}

/** Sem o grupo o sync nunca roda: bloquear a tela evita dado local que não sobe. */
function SemAcesso() {
  return (
    <div role="alert" className="mx-auto flex max-w-sm flex-col items-center gap-3 py-10 text-center">
      <ShieldAlert className="h-8 w-8 text-muted-foreground" aria-hidden />
      <h1 className="text-lg font-semibold">Sem acesso ao Levantamento de campo</h1>
      <p className="text-sm text-muted-foreground">
        Seu usuário não tem permissão para o levantamento. Peça ao administrador para incluir você no grupo
        “Levantamento de campo”.
      </p>
      <Link href="/tecnico/qualificacao" className={buttonVariants({ variant: 'outline' })}>
        Voltar para Qualificação
      </Link>
    </div>
  )
}
