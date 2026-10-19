'use client'
import { useCallback, useSyncExternalStore } from 'react'
import { SURVEY_GROUP } from '@/lib/levantamento/constants'
import { useHasGroup } from '@/lib/hooks/useHasGroup'
import { withBase } from '@/lib/basePath'

/**
 * Navegação da página única `/cliente`. O estado mora na query
 * (`?id=<cliente>&eq=<equip|novo>`) e muda só por `history.pushState` /
 * `replaceState`: nunca `router.push`, que buscaria RSC (quebra offline).
 */
export const CLIENTE_PATH = '/cliente'
const EVENTO = 'cliente-nav'

export interface ClienteNavState {
  id?: string | null
  eq?: string | null
}

/** Rota de `/cliente` SEM basePath — para o router (`router.replace`), que prefixa sozinho. */
function clienteRoute({ id, eq }: ClienteNavState = {}): string {
  const p = new URLSearchParams()
  if (id) {
    p.set('id', id)
    if (eq) p.set('eq', eq)
  }
  const q = p.toString()
  return q ? `${CLIENTE_PATH}?${q}` : CLIENTE_PATH
}

/** URL de navegador (com basePath): `history.pushState` e `<a href>` cru. */
export function clienteUrl(state: ClienteNavState = {}): string {
  return withBase(clienteRoute(state))
}

/** Navega dentro de `/cliente` sem round-trip ao servidor. */
export function goCliente(state: ClienteNavState, opts: { replace?: boolean } = {}): void {
  if (typeof window === 'undefined') return
  const url = clienteUrl(state)
  if (opts.replace) window.history.replaceState(window.history.state, '', url)
  else window.history.pushState(window.history.state, '', url)
  // Next 14.2 sincroniza o useSearchParams sozinho; o evento garante o mesmo
  // para quem lê por aqui (e para os testes, sem o router do Next).
  window.dispatchEvent(new Event(EVENTO))
}

function subscribe(cb: () => void) {
  window.addEventListener('popstate', cb)
  window.addEventListener(EVENTO, cb)
  return () => {
    window.removeEventListener('popstate', cb)
    window.removeEventListener(EVENTO, cb)
  }
}
const snapshot = () => window.location.search
const serverSnapshot = () => ''

export function useClienteNav(): {
  id: string | null
  eq: string | null
  go: (state: ClienteNavState, opts?: { replace?: boolean }) => void
} {
  const search = useSyncExternalStore(subscribe, snapshot, serverSnapshot)
  const p = new URLSearchParams(search)
  const id = p.get('id') || null
  const eq = id ? p.get('eq') || null : null
  const go = useCallback((s: ClienteNavState, o?: { replace?: boolean }) => goCliente(s, o), [])
  return { id, eq, go }
}

/** Pode criar/editar no levantamento (grupo `group_survey_user`); sem ele, modo leitura. */
export function useCanEdit(): boolean {
  return useHasGroup(SURVEY_GROUP)
}

/** `/levantamento[/<c>[/<e>]]` (rotas antigas) -> URL equivalente em `/cliente`. */
export function levantamentoRedirect(segments: string[] = []): string {
  const [c, e] = segments.map((s) => decodeURIComponent(s))
  return clienteRoute({ id: c ?? null, eq: e ?? null })
}
