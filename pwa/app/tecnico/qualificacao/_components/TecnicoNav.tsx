'use client'
import { useTransition } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { ClipboardList, BarChart3, User, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { useNavProgress } from '@/components/providers/NavProgress'

const ROOT_PATH = '/tecnico/qualificacao'

export const NAV_ITEMS = [
  { href: ROOT_PATH, label: 'OSs', Icon: ClipboardList },
  { href: `${ROOT_PATH}/historico`, label: 'Histórico', Icon: BarChart3 },
  { href: `${ROOT_PATH}/perfil`, label: 'Perfil', Icon: User },
] as const

function useActiveHref() {
  const pathname = usePathname()
  const isHist = pathname.startsWith(`${ROOT_PATH}/historico`)
  const isPerfil = pathname.startsWith(`${ROOT_PATH}/perfil`)
  if (isHist) return `${ROOT_PATH}/historico`
  if (isPerfil) return `${ROOT_PATH}/perfil`
  return pathname.startsWith(ROOT_PATH) ? ROOT_PATH : ''
}

/**
 * Navegação principal do app, em duas variantes.
 *
 * `bottom` é o padrão de polegar: barra fixa no rodapé, do celular ao tablet.
 * `side` é o padrão de mouse: coluna à esquerda a partir de 1024px, onde um
 * rodapé fixo ficaria longe do olho e do cursor. A sombra "Sobreposto" do
 * DESIGN.md §4 só vale pra elemento que flutua sobre conteúdo rolável — a
 * coluna lateral não flutua, então separa por fio de 1px.
 *
 * As duas variantes são renderizadas sempre; quem escolhe é o CSS
 * (`lg:hidden` / `hidden lg:flex`). Detectar viewport em JS quebraria a
 * hidratação e é proibido pelo plano.
 */
export function TecnicoNav({ variant }: { variant: 'bottom' | 'side' }) {
  const activeHref = useActiveHref()
  const isSide = variant === 'side'
  return (
    <nav
      aria-label={isSide ? 'Navegação principal (lateral)' : 'Navegação principal (barra inferior)'}
      className={clsx(
        'bg-card',
        isSide
          ? 'hidden w-[200px] shrink-0 flex-col gap-1 border-r border-border p-3 lg:flex'
          : 'sticky bottom-0 flex justify-around border-t border-border px-2 py-1 text-xs shadow-[0_-8px_24px_rgba(0,0,0,0.45)] lg:hidden',
      )}
    >
      {NAV_ITEMS.map(({ href, label, Icon }) => (
        <NavItem
          key={href}
          href={href}
          active={activeHref === href}
          label={label}
          icon={<Icon className="h-5 w-5" aria-hidden />}
          isSide={isSide}
        />
      ))}
    </nav>
  )
}

function NavItem({
  href,
  active,
  icon,
  label,
  isSide,
}: {
  href: string
  active: boolean
  icon: React.ReactNode
  label: string
  isSide: boolean
}) {
  const router = useRouter()
  const { begin } = useNavProgress()
  const [isPending, startTransition] = useTransition()
  return (
    <a
      href={href}
      // "page": este link leva a uma rota-destino de nível de app (OSs,
      // Histórico, Perfil). Ver ColetaCard: lá a coleta selecionada usa
      // aria-current="true" porque marca seleção dentro de uma lista, não a
      // página atual — os dois valores divergem de propósito, não por acaso.
      aria-current={active ? 'page' : undefined}
      aria-busy={isPending || undefined}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
        e.preventDefault()
        if (active || isPending) return
        begin()
        startTransition(() => router.push(href))
      }}
      className={clsx(
        'flex min-h-[44px] items-center rounded-md transition-colors',
        isSide
          ? 'gap-3 px-3 text-sm'
          : 'flex-1 flex-col justify-center gap-0.5',
        active
          ? 'font-semibold text-foreground'
          : 'text-muted-foreground hover:text-foreground',
        isSide && active && 'bg-accent',
      )}
    >
      {isPending ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> : icon}
      {label}
    </a>
  )
}
