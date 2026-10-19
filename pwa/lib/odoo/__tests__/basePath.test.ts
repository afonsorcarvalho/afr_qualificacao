// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'

const create = vi.fn()
let onError: ((e: unknown) => unknown) | null = null
vi.mock('axios', () => ({
  default: {
    create: (cfg: unknown) => {
      create(cfg)
      return {
        post: vi.fn().mockResolvedValue({ data: { jsonrpc: '2.0', id: 1, result: { uid: 1 } } }),
        interceptors: { response: { use: (_ok: unknown, err: (e: unknown) => unknown) => { onError = err } } },
      }
    },
  },
}))

import { odooClient } from '../client'

describe('odooClient sob basePath', () => {
  it('axios usa baseURL /app/api/odoo', async () => {
    await odooClient.getSession()
    expect(create).toHaveBeenCalledWith(expect.objectContaining({ baseURL: '/app/api/odoo' }))
  })
  it('401 manda para /app/login', () => {
    expect(onError).not.toBeNull()
    try { onError!({ response: { status: 401 } }) } catch { /* OdooSessionError */ }
    expect(window.location.pathname).toBe('/app/login')
  })
})
