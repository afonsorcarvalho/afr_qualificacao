import { NextRequest, NextResponse } from 'next/server'
import { origemCanonica, resolverAlvoOdoo } from '@/lib/server/odooTarget'

/** Erro JSON-RPC — é o formato que o `odooClient` já sabe ler. */
function erro(mensagem: string, status: number) {
  return NextResponse.json(
    {
      jsonrpc: '2.0',
      id: null,
      error: { code: status, message: 'Bad Gateway', data: { message: mensagem } },
    },
    { status },
  )
}

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params

  // URL-alvo vem do header (login) ou do cookie (persistido) — e passa pela
  // allowlist antes de virar destino de `fetch`. Sem isso, qualquer um que
  // alcance esta porta faz o servidor buscar host interno e lê a resposta.
  const headerTarget = request.headers.get('x-odoo-target')
  const cookieTarget = request.cookies.get('odoo-target')?.value
  const alvo = resolverAlvoOdoo({
    header: headerTarget,
    cookie: cookieTarget,
    env: process.env as Record<string, string | undefined>,
  })
  if (!alvo.ok) {
    return erro(alvo.motivo, 403)
  }
  const base = alvo.base
  const headerTargetAceito = alvo.veioDoHeader

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
    return erro(
      `Falha ao conectar em ${base}: ${err instanceof Error ? err.message : 'erro desconhecido'}`,
      502,
    )
  }

  // `redirect: 'follow'` acima poderia levar a resposta pra fora da allowlist
  // (um 302 do Odoo apontando pra outro host). A allowlist vale pro destino
  // final, não só pro primeiro salto.
  if (odooResponse.url && origemCanonica(odooResponse.url) !== base) {
    return erro(
      `O servidor redirecionou para fora das origens autorizadas (${origemCanonica(odooResponse.url) ?? 'destino ilegível'}).`,
      502,
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
    response.headers.append('Set-Cookie', 'odoo-target=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax')
  } else {
    const setCookieHeader = odooResponse.headers.get('set-cookie')
    if (setCookieHeader) {
      response.headers.set('Set-Cookie', setCookieHeader)
    }

    // Persiste a URL-alvo em cookie para requisições subsequentes. `HttpOnly`
    // porque só o servidor lê este cookie — o front guarda a URL escolhida no
    // próprio authStore. Sem isso, script na página reescreve o alvo do proxy.
    if (headerTargetAceito) {
      response.headers.append(
        'Set-Cookie',
        `odoo-target=${encodeURIComponent(base)}; Path=/; HttpOnly; SameSite=Lax`,
      )
    }
  }

  return response
}

export const GET = handler
export const POST = handler
