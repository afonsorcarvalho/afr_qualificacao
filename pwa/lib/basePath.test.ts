import { describe, expect, it } from 'vitest'
import { BASE_PATH, withBase } from './basePath'

describe('basePath', () => {
  it('lê NEXT_PUBLIC_BASE_PATH (setup dos testes = /app)', () => {
    expect(BASE_PATH).toBe('/app')
  })
  it('prefixa caminhos absolutos', () => {
    expect(withBase('/api/odoo')).toBe('/app/api/odoo')
    expect(withBase('/login?next=%2Fx')).toBe('/app/login?next=%2Fx')
    expect(withBase('/')).toBe('/app/')
  })
})
