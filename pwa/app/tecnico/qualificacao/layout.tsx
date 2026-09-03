'use client'
import { ReactNode, useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Wrench } from 'lucide-react'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'

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
    <div className="mx-auto flex min-h-screen max-w-[480px] flex-col bg-background">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-card px-4 py-3 shadow-md">
        <div className="flex items-center gap-2">
          <Wrench className="h-5 w-5 text-primary" />
          <span className="font-semibold">Qualificação · Técnico</span>
        </div>
      </header>
      <main className="flex-1 overflow-auto p-3">{children}</main>
      <BottomNav />
    </div>
  )
}

function BottomNav() {
  const pathname = usePathname()
  const isHist = pathname.startsWith(ROOT_PATH + '/historico')
  const isPerfil = pathname.startsWith(ROOT_PATH + '/perfil')
  const isHome = pathname === ROOT_PATH || (!isHist && !isPerfil && pathname.startsWith(ROOT_PATH))
  const link = (active: boolean) =>
    active
      ? 'font-semibold text-primary'
      : 'opacity-60 hover:opacity-100 transition'
  return (
    <nav className="sticky bottom-0 flex justify-around border-t border-border bg-card px-2 py-2 text-xs text-muted-foreground shadow-[0_-2px_8px_rgba(0,0,0,0.08)]">
      <Link href={ROOT_PATH} className={link(isHome)}>📋 OSs</Link>
      <Link href={`${ROOT_PATH}/historico`} className={link(isHist)}>📊 Histórico</Link>
      <Link href={`${ROOT_PATH}/perfil`} className={link(isPerfil)}>👤 Perfil</Link>
    </nav>
  )
}
