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
    // `.json`/`.webmanifest` entram aqui por causa do `/manifest.json`: o
    // browser busca o manifesto antes de qualquer sessão, e sem esta exceção
    // ele levava 307 pro /login — sem manifesto não há prompt de instalação
    // nem ícone de app. O manifesto só tem nome/cores/ícones, nada sensível.
    /\.(mjs|js|css|json|webmanifest|svg|png|jpg|jpeg|ico|woff2?)$/i.test(pathname)
  ) {
    return NextResponse.next()
  }

  // Verifica cookie de sessão do Odoo
  const sessionId = request.cookies.get('session_id')
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p))

  if (!sessionId && !isPublic) {
    const loginUrl = new URL('/login', request.url)
    // Guarda o destino original para o login devolver o técnico direto à
    // coleta pedida em vez de cair na home — o valor sai do próprio
    // `nextUrl` da requisição (interno por construção), então não passa por
    // `destinoSeguro` aqui. A validação entra do lado que LÊ `next`
    // (`app/login/page.tsx`), que é o ponto de risco de open redirect.
    loginUrl.searchParams.set('next', pathname + request.nextUrl.search)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
