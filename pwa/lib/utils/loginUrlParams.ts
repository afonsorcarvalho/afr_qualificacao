/**
 * Helpers para pré-preencher o login via query params da URL.
 *
 * Uso: /login?server=https://odoo.exemplo.com&db=meu-banco
 *
 * Nunca aceitar user/password por URL (vaza em histórico/logs).
 */

export interface LoginPrefillParams {
  server: string | null
  db: string | null
}

export function parseLoginParams(sp: URLSearchParams): LoginPrefillParams {
  return {
    server: sp.get('server')?.trim() || null,
    db: sp.get('db')?.trim() || null,
  }
}

export function normalizeServerUrl(raw: string): string {
  let u = raw.trim().replace(/\/+$/, '')
  if (u && !/^https?:\/\//i.test(u)) u = 'https://' + u
  return u
}

export function buildPostLogoutLoginPath(
  serverUrl: string | null | undefined,
  dbName: string | null | undefined
): string {
  const params = new URLSearchParams()
  if (serverUrl) params.set('server', serverUrl)
  if (dbName) params.set('db', dbName)
  const qs = params.toString()
  return qs ? `/login?${qs}` : '/login'
}
