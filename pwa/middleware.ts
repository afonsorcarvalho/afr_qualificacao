import { NextRequest, NextResponse } from 'next/server'

const PUBLIC_PATHS = ['/login']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Ignora arquivos estáticos e API
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/api') ||
    pathname.startsWith('/favicon') ||
    pathname === '/pdf.worker.min.mjs' ||
    /\.(mjs|js|css|svg|png|jpg|jpeg|ico|woff2?)$/i.test(pathname)
  ) {
    return NextResponse.next()
  }

  // Verifica cookie de sessão do Odoo
  const sessionId = request.cookies.get('session_id')
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p))

  if (!sessionId && !isPublic) {
    const loginUrl = new URL('/login', request.url)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
