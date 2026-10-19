import { describe, it, expect } from 'vitest'
import { NextRequest } from 'next/server'
import { middleware } from './middleware'

const req = (url: string, cookie?: string) =>
  new NextRequest(url, {
    headers: cookie ? { cookie } : {},
    nextConfig: { basePath: '/app' },
  })

describe('middleware sob basePath /app', () => {
  it('sem sessão redireciona para /app/login?next=<rota sem basePath>', () => {
    const res = middleware(req('https://x.test/app/cliente?id=1'))
    const loc = new URL(res.headers.get('location')!)
    expect(loc.pathname).toBe('/app/login')
    // `next` é consumido por router.replace (que prefixa sozinho): sem /app.
    expect(loc.searchParams.get('next')).toBe('/cliente?id=1')
  })
  it('com sessão deixa passar', () => {
    const res = middleware(req('https://x.test/app/cliente', 'session_id=abc'))
    expect(res.headers.get('location')).toBeNull()
  })
  it('/app/login é público', () => {
    const res = middleware(req('https://x.test/app/login'))
    expect(res.headers.get('location')).toBeNull()
  })
})
