'use client'
import { ReactNode, useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { Wrench } from 'lucide-react'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import {
  NavProgressBar,
  NavProgressProvider,
} from '@/components/providers/NavProgress'
import { TecnicoNav } from './_components/TecnicoNav'

const ROOT_PATH = '/tecnico/qualificacao'

export default function TecnicoLayout({ children }: { children: ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const setLastUserId = useTecnicoSettings((s) => s.setLastUserId)

  // Refresca `lastUserId` uma vez por montagem do layout (todo entra em
  // /tecnico/qualificacao/*, este layout persiste por baixo). Sem isso, só a
  // home e o histórico buscavam session-info — abrir direto uma rota como
  // /[osId] (deep link, PWA reaberto) via localStorage estale ou vazio deixava
  // `lastUserId` desatualizado/null, e `useOsDetail` (que agora escopa por
  // `create_uid`) ou nunca disparava, ou pior, escopava pelo usuário ERRADO
  // se outro técnico tivesse usado o mesmo aparelho antes.
  useEffect(() => {
    fetch('/api/odoo/session-info')
      .then((r) => r.json())
      .then((d) => d?.uid && setLastUserId(d.uid))
      .catch(() => {})
  }, [setLastUserId])

  useEffect(() => {
    if (pathname === ROOT_PATH) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      const target = e.target as HTMLElement | null
      const tag = target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || target?.isContentEditable) return
      e.preventDefault()
      router.back()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pathname, router])

  return (
    <NavProgressProvider>
      <div className="mx-auto flex min-h-screen w-full max-w-[480px] flex-col bg-background sm:max-w-[720px] lg:h-dvh lg:min-h-0 lg:max-w-none lg:flex-row lg:overflow-hidden">
        <TecnicoNav variant="side" />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-10 border-b border-border bg-card shadow-md lg:static lg:shadow-none">
            <div className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-2">
                <Wrench className="h-5 w-5 text-foreground" />
                <span className="font-semibold">Qualificação · Técnico</span>
              </div>
            </div>
            {/* Toda navegação acende esta barra até a rota nova aparecer. */}
            <NavProgressBar />
          </header>
          <main className="flex-1 overflow-auto p-3">{children}</main>
          <TecnicoNav variant="bottom" />
        </div>
      </div>
    </NavProgressProvider>
  )
}
