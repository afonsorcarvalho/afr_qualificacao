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

  it('navegação do app casa', () => {
    expect(matchPageNavigation({ request: nav, url: u('/cliente?id=1') })).toBe(true)
    expect(matchPageNavigation({ request: nav, url: u('/tecnico/qualificacao') })).toBe(true)
    expect(matchPageNavigation({ request: nav, url: u('/levantamento') })).toBe(true)
    expect(matchPageNavigation({ request: nav, url: u('/login') })).toBe(true)
  })
  it('navegação do Odoo não casa', () => {
    expect(matchPageNavigation({ request: nav, url: u('/web#action=1') })).toBe(false)
    expect(matchPageNavigation({ request: nav, url: u('/odoo/x') })).toBe(false)
    expect(matchPageNavigation({ request: nav, url: u('/clientes') })).toBe(false)
  })
  it('rsc', () => {
    expect(matchRscRequest({ request: rsc, url: u('/tecnico/qualificacao') })).toBe(true)
    expect(matchRscRequest({ request: rsc, url: u('/web/x') })).toBe(false)
    expect(matchRscRequest({ request: nav, url: u('/tecnico/x') })).toBe(false)
  })
  it('imagens', () => {
    expect(matchAppImage({ request: img, url: u('/web/image/x.png') })).toBe(false)
    expect(matchAppImage({ request: img, url: u('/_next/static/a.png') })).toBe(true)
    expect(matchAppImage({ request: img, url: new URL('https://o.test/_next/a.png') })).toBe(false)
  })
})
