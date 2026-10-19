import { beforeAll, describe, expect, it } from 'vitest'
import * as routes from './swRoutes.mjs'

// Funções JS puras (serializadas no sw.js): tipadas como any no teste.
const { matchPageNavigation, matchRscRequest, matchAppImage } = routes as any

const nav = { mode: 'navigate', headers: new Headers() }
const rsc = { mode: 'cors', headers: new Headers({ RSC: '1' }) }
const img = { mode: 'no-cors', headers: new Headers() }
const u = (p: string) => new URL(p, 'https://x.test')

describe('swRoutes', () => {
  beforeAll(() => {
    ;(globalThis as any).self = { location: { origin: 'https://x.test' } }
  })

  it('navegação do app casa (prefixo /app/)', () => {
    expect(matchPageNavigation({ request: nav, url: u('/app/cliente?id=1') })).toBe(true)
    expect(matchPageNavigation({ request: nav, url: u('/app/tecnico/qualificacao') })).toBe(true)
    expect(matchPageNavigation({ request: nav, url: u('/app/levantamento') })).toBe(true)
    expect(matchPageNavigation({ request: nav, url: u('/app/login') })).toBe(true)
    expect(matchPageNavigation({ request: nav, url: u('/app/rota-nova') })).toBe(true)
  })
  it('navegação do Odoo / API / fora do prefixo não casa', () => {
    expect(matchPageNavigation({ request: nav, url: u('/web#action=1') })).toBe(false)
    expect(matchPageNavigation({ request: nav, url: u('/web') })).toBe(false)
    expect(matchPageNavigation({ request: nav, url: u('/cliente') })).toBe(false)
    expect(matchPageNavigation({ request: nav, url: u('/application') })).toBe(false)
    expect(matchPageNavigation({ request: nav, url: u('/app/api/odoo/x') })).toBe(false)
  })
  it('rsc', () => {
    expect(matchRscRequest({ request: rsc, url: u('/app/tecnico/qualificacao') })).toBe(true)
    expect(matchRscRequest({ request: rsc, url: u('/web/x') })).toBe(false)
    expect(matchRscRequest({ request: rsc, url: u('/app/api/odoo/x') })).toBe(false)
    expect(matchRscRequest({ request: nav, url: u('/app/tecnico/x') })).toBe(false)
  })
  it('imagens', () => {
    expect(matchAppImage({ request: img, url: u('/web/image/1') })).toBe(false)
    expect(matchAppImage({ request: img, url: u('/web/image/x.png') })).toBe(false)
    expect(matchAppImage({ request: img, url: u('/app/_next/a.png') })).toBe(true)
    expect(matchAppImage({ request: img, url: u('/app/icons/icon-192.png') })).toBe(true)
    expect(matchAppImage({ request: img, url: u('/_next/static/a.png') })).toBe(false)
    expect(matchAppImage({ request: img, url: new URL('https://o.test/app/_next/a.png') })).toBe(false)
  })
})
