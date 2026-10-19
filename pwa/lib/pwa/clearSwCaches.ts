/**
 * Apaga os caches do service worker que guardam HTML/RSC de páginas
 * autenticadas. Chamado no logout e na troca de usuário: o próximo usuário do
 * aparelho não pode receber páginas do anterior via cache offline.
 * `static-assets` (imagens/fontes) não carrega dados de sessão e fica.
 */
export const SW_PAGE_CACHES = ['pages', 'rsc', 'start-url'] as const

export function clearSwCaches(): Promise<void> {
  if (typeof caches === 'undefined') return Promise.resolve()
  return Promise.all(SW_PAGE_CACHES.map((n) => caches.delete(n).catch(() => false))).then(
    () => undefined,
    () => undefined,
  )
}
