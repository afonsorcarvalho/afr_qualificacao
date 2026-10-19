'use client'
import { useTransition } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { ClipboardList, CalendarDays, BarChart3, User, Loader2, Building2 } from 'lucide-react'
import { clsx } from 'clsx'
import { useNavProgress } from '@/components/providers/NavProgress'
import { goCliente } from '@/lib/cliente/nav'

const ROOT_PATH = '/tecnico/qualificacao'

export const NAV_ITEMS = [
  { href: ROOT_PATH, label: 'OSs', Icon: ClipboardList },
  { href: `${ROOT_PATH}/agenda`, label: 'Agenda', Icon: CalendarDays },
  { href: `${ROOT_PATH}/historico`, label: 'Histórico', Icon: BarChart3 },
  { href: `${ROOT_PATH}/perfil`, label: 'Perfil', Icon: User },
] as const

/** Fora do prefixo /tecnico/qualificacao: página única de clientes (todo usuário autenticado). */
export const CLIENTES_PATH = '/cliente'
const CLIENTES_ITEM = { href: CLIENTES_PATH, label: 'Clientes', Icon: Building2 } as const

function useActiveHref() {
  const pathname = usePathname()
  if (pathname === CLIENTES_PATH || pathname.startsWith(`${CLIENTES_PATH}/`)) {
    return CLIENTES_PATH
  }
  const isHist = pathname.startsWith(`${ROOT_PATH}/historico`)
  const isPerfil = pathname.startsWith(`${ROOT_PATH}/perfil`)
  if (isHist) return `${ROOT_PATH}/historico`
  if (isPerfil) return `${ROOT_PATH}/perfil`
  const isAgenda = pathname.startsWith(`${ROOT_PATH}/agenda`)
  if (isAgenda) return `${ROOT_PATH}/agenda`
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
export function TecnicoNav({
  variant,
  agendaDisponivel = true,
}: {
  variant: 'bottom' | 'side'
  /** Falso esconde a aba Agenda: o módulo de agendamento não está instalado. */
  agendaDisponivel?: boolean
}) {
  const activeHref = useActiveHref()
  const isSide = variant === 'side'
  const base = NAV_ITEMS.filter(
    (i) => agendaDisponivel || !i.href.endsWith('/agenda'),
  )
  // Antes de Perfil, que fica sempre por último.
  const itens = [...base.slice(0, -1), CLIENTES_ITEM, base[base.length - 1]]
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
      {itens.map(({ href, label, Icon }) => (
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
      // Agenda, Histórico, Perfil). Ver ColetaCard: lá a coleta selecionada usa
      // aria-current="true" porque marca seleção dentro de uma lista, não a
      // página atual — os dois valores divergem de propósito, não por acaso.
      aria-current={active ? 'page' : undefined}
      aria-busy={isPending || undefined}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
        e.preventDefault()
        // Dentro de /cliente?id=..: a aba ativa volta para a lista sem buscar RSC.
        if (active && href === CLIENTES_PATH && window.location.search) {
          goCliente({})
          return
        }
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
