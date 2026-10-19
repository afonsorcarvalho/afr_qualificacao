/**
 * Prefixo único do PWA (`basePath` do next.config.mjs, exposto ao cliente via
 * `env.NEXT_PUBLIC_BASE_PATH`). O Next prefixa sozinho `Link`, `router.*`,
 * `redirect()` e o middleware; TODO o resto — fetch/axios, `window.location`,
 * `history.pushState`, `<a href>` cru, `serviceWorker.register`, metadata
 * `manifest`, `workerSrc` do pdf.js — passa por `withBase`.
 *
 * Nunca usar `withBase` em caminho entregue ao router (`router.push`,
 * `<Link>`, `redirect`): sairia `/app/app/...`.
 */
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? ''

export function withBase(path: string): string {
  return `${BASE_PATH}${path}`
}
