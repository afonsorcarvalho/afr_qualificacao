/**
 * Endpoints públicos do Odoo usados antes do login.
 *
 * Odoo 16 expõe `/web/binary/company_logo?dbname=<db>` sem autenticação
 * — retorna PNG da empresa principal ou um placeholder padrão.
 */

export function getCompanyLogoUrl(serverUrl: string, db: string): string | null {
  if (!serverUrl || !db) return null
  const base = serverUrl.replace(/\/+$/, '')
  // `unique` força cache-bust por DB quando o user troca de banco
  const unique = encodeURIComponent(db)
  return `${base}/web/binary/company_logo?dbname=${encodeURIComponent(db)}&unique=${unique}`
}
