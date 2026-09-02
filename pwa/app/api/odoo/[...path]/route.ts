import { NextRequest, NextResponse } from 'next/server'

const DEFAULT_ODOO_URL = process.env.ODOO_URL || 'http://localhost:8069'

function normalizeTarget(raw: string | null | undefined): string {
  if (!raw) return DEFAULT_ODOO_URL
  let u = raw.trim().replace(/\/+$/, '')
  if (!/^https?:\/\//i.test(u)) u = 'https://' + u
  return u
}

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params

  // URL-alvo vem do header (enviado pelo cliente) ou do cookie (persistido)
  const headerTarget = request.headers.get('x-odoo-target')
  const cookieTarget = request.cookies.get('odoo-target')?.value
  const base = normalizeTarget(headerTarget ?? cookieTarget)

  const targetUrl = `${base}/${path.join('/')}${request.nextUrl.search}`

  const forwardHeaders = new Headers()
  const incomingCT = request.headers.get('content-type')
  forwardHeaders.set('Content-Type', incomingCT || 'application/json')

  const sessionCookie = request.cookies.get('session_id')
  if (sessionCookie) {
    forwardHeaders.set('Cookie', `session_id=${sessionCookie.value}`)
  }

  const body = request.method !== 'GET'
    ? (incomingCT?.includes('application/x-www-form-urlencoded') || incomingCT?.includes('multipart/form-data')
        ? await request.arrayBuffer()
        : await request.text())
    : undefined

  let odooResponse: Response
  try {
    odooResponse = await fetch(targetUrl, {
      method: request.method,
      headers: forwardHeaders,
      body: body as BodyInit | undefined,
      redirect: 'follow',
    })
  } catch (err) {
    return NextResponse.json(
      {
        jsonrpc: '2.0',
        id: null,
        error: {
          code: 502,
          message: 'Bad Gateway',
          data: { message: `Falha ao conectar em ${base}: ${err instanceof Error ? err.message : 'erro desconhecido'}` },
        },
      },
      { status: 502 }
    )
  }

  // Binário (PDF, imagens) precisa passar por arrayBuffer, não text()
  const upstreamCT = odooResponse.headers.get('content-type') || 'application/json'
  const isTextLike = /^(application\/(json|xml)|text\/)/i.test(upstreamCT)
  const responseBody: BodyInit = isTextLike
    ? await odooResponse.text()
    : await odooResponse.arrayBuffer()

  const outHeaders = new Headers()
  outHeaders.set('Content-Type', upstreamCT)
  const disposition = odooResponse.headers.get('content-disposition')
  if (disposition) outHeaders.set('Content-Disposition', disposition)

  const response = new NextResponse(responseBody, {
    status: odooResponse.status,
    headers: outHeaders,
  })

  // Logout: força expiração do session_id e odoo-target (Odoo renova a sessão
  // em /web/session/destroy em vez de expirar — por isso sobrescrevemos aqui).
  const isLogout = path.join('/').endsWith('web/session/destroy')

  if (isLogout) {
    response.headers.append('Set-Cookie', 'session_id=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax')
    response.headers.append('Set-Cookie', 'odoo-target=; Path=/; Max-Age=0; SameSite=Lax')
  } else {
    const setCookieHeader = odooResponse.headers.get('set-cookie')
    if (setCookieHeader) {
      response.headers.set('Set-Cookie', setCookieHeader)
    }

    // Persiste a URL-alvo em cookie para requisições subsequentes
    if (headerTarget) {
      response.headers.append('Set-Cookie', `odoo-target=${encodeURIComponent(base)}; Path=/; SameSite=Lax`)
    }
  }

  return response
}

export const GET = handler
export const POST = handler
