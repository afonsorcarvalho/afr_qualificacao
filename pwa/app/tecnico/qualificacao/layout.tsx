'use client'
import { ReactNode, useEffect, useTransition } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { Wrench, ClipboardList, BarChart3, User, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import {
  NavProgressBar,
  NavProgressProvider,
  useNavProgress,
} from '@/components/providers/NavProgress'

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
      <div className="mx-auto flex min-h-screen max-w-[480px] flex-col bg-background">
        <header className="sticky top-0 z-10 border-b border-border bg-card shadow-md">
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
        <BottomNav />
      </div>
    </NavProgressProvider>
  )
}

function BottomNav() {
  const pathname = usePathname()
  const isHist = pathname.startsWith(ROOT_PATH + '/historico')
  const isPerfil = pathname.startsWith(ROOT_PATH + '/perfil')
  const isHome = pathname === ROOT_PATH || (!isHist && !isPerfil && pathname.startsWith(ROOT_PATH))
  // Alvo de 44px por item (PRODUCT.md: o técnico usa de luva) e ícone SVG —
  // emoji como ícone de interface está proibido no DESIGN.md.
  const link = (active: boolean) =>
    clsx(
      'flex min-h-[44px] flex-1 flex-col items-center justify-center gap-0.5 rounded-md transition-colors',
      active
        ? 'font-semibold text-foreground'
        : 'text-muted-foreground hover:text-foreground',
    )
  return (
    <nav className="sticky bottom-0 flex justify-around border-t border-border bg-card px-2 py-1 text-xs shadow-[0_-8px_24px_rgba(0,0,0,0.45)]">
      <NavItem href={ROOT_PATH} active={isHome} icon={<ClipboardList className="h-5 w-5" aria-hidden />} label="OSs" className={link(isHome)} />
      <NavItem href={`${ROOT_PATH}/historico`} active={isHist} icon={<BarChart3 className="h-5 w-5" aria-hidden />} label="Histórico" className={link(isHist)} />
      <NavItem href={`${ROOT_PATH}/perfil`} active={isPerfil} icon={<User className="h-5 w-5" aria-hidden />} label="Perfil" className={link(isPerfil)} />
    </nav>
  )
}

/**
 * Item da barra inferior. Troca o ícone por spinner enquanto a rota carrega —
 * o destino já está destacado antes mesmo de a tela trocar, então o técnico vê
 * que o toque pegou.
 */
function NavItem({
  href,
  active,
  icon,
  label,
  className,
}: {
  href: string
  active: boolean
  icon: React.ReactNode
  label: string
  className: string
}) {
  const router = useRouter()
  const { begin } = useNavProgress()
  const [isPending, startTransition] = useTransition()
  return (
    <a
      href={href}
      aria-current={active ? 'page' : undefined}
      aria-busy={isPending || undefined}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
        e.preventDefault()
        if (active || isPending) return
        begin()
        startTransition(() => router.push(href))
      }}
      className={className}
    >
      {isPending ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> : icon}
      {label}
    </a>
  )
}
