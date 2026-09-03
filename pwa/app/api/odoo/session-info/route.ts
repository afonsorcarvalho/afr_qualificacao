import { NextRequest, NextResponse } from 'next/server'

const DEFAULT_ODOO_URL = process.env.ODOO_URL ?? 'http://localhost:8083'

function normalizeTarget(raw: string | null | undefined): string {
  if (!raw) return DEFAULT_ODOO_URL
  let u = raw.trim().replace(/\/+$/, '')
  if (!/^https?:\/\//i.test(u)) u = 'https://' + u
  return u
}

export async function GET(request: NextRequest) {
  const sessionId = request.cookies.get('session_id')?.value
  if (!sessionId) return NextResponse.json({ uid: null }, { status: 401 })

  const cookieTarget = request.cookies.get('odoo-target')?.value
  const base = normalizeTarget(cookieTarget)

  try {
    const res = await fetch(`${base}/web/session/get_session_info`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Cookie: `session_id=${sessionId}`,
      },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} }),
    })
    const data = await res.json()
    const r = data?.result ?? {}
    return NextResponse.json({
      uid: r.uid ?? null,
      name: typeof r.name === 'string' ? r.name : null,
      username: typeof r.username === 'string' ? r.username : null,
      partner_id: Array.isArray(r.partner_id) ? r.partner_id[0] : null,
      company_id: Array.isArray(r.user_companies?.current_company)
        ? r.user_companies.current_company[0]
        : r.company_id ?? null,
    })
  } catch {
    return NextResponse.json({ uid: null }, { status: 500 })
  }
}
