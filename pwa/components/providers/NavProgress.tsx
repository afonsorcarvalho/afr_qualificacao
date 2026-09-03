'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { usePathname } from 'next/navigation'

/**
 * Estado global de "navegação em andamento".
 *
 * Navegar no App Router não é instantâneo: a rota nova busca RSC e, depois,
 * os dados do Odoo. Sem sinal nenhum, o técnico toca numa OS, não acontece
 * nada visível por um segundo e ele toca de novo achando que travou.
 *
 * Quem inicia a navegação chama `begin()`; o estado se apaga sozinho quando o
 * `pathname` muda (chegou) — ou depois de um teto de segurança, pra barra
 * nunca ficar acesa pra sempre se a navegação for cancelada.
 */
const NavProgressContext = createContext<{
  pending: boolean
  begin: () => void
}>({ pending: false, begin: () => {} })

const TETO_MS = 10_000

export function NavProgressProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const [pending, setPending] = useState(false)

  const begin = useCallback(() => setPending(true), [])

  // Chegou na rota nova: apaga.
  useEffect(() => {
    setPending(false)
  }, [pathname])

  useEffect(() => {
    if (!pending) return
    const t = setTimeout(() => setPending(false), TETO_MS)
    return () => clearTimeout(t)
  }, [pending])

  const value = useMemo(() => ({ pending, begin }), [pending, begin])

  return (
    <NavProgressContext.Provider value={value}>
      {children}
    </NavProgressContext.Provider>
  )
}

export function useNavProgress() {
  return useContext(NavProgressContext)
}

/** Barra fina no topo, visível enquanto uma navegação está em curso. */
export function NavProgressBar() {
  const { pending } = useNavProgress()
  return (
    <div
      className="h-0.5 w-full overflow-hidden bg-transparent"
      role="status"
      aria-live="polite"
      aria-label={pending ? 'Carregando' : undefined}
    >
      {pending && (
        <div className="h-full w-1/3 animate-nav-progress rounded-full bg-foreground/70" />
      )}
    </div>
  )
}
