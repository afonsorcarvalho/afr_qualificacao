import { describe, it, expect, vi, beforeEach } from 'vitest'

const post = vi.fn()
vi.mock('axios', () => ({
  default: {
    create: () => ({ post: (...a: unknown[]) => post(...a), interceptors: { response: { use: vi.fn() } } }),
  },
}))

import { odooClient, OdooError, OdooSessionError } from '../client'

const rpcError = (code: number, name: string) => ({
  data: { jsonrpc: '2.0', id: 1, error: { code, message: 'x', data: { name, debug: '', message: 'm', arguments: [], exception_type: '' } } },
})

beforeEach(() => post.mockReset())

describe('odooClient.getSession', () => {
  it('devolve o resultado em caso normal', async () => {
    post.mockResolvedValue({ data: { jsonrpc: '2.0', id: 1, result: { uid: 7, name: 'A' } } })
    await expect(odooClient.getSession()).resolves.toEqual({ uid: 7, name: 'A' })
  })

  it('lança OdooSessionError quando o JSON-RPC traz sessão expirada (code 100)', async () => {
    post.mockResolvedValue(rpcError(100, 'odoo.http.SessionExpiredException'))
    await expect(odooClient.getSession()).rejects.toBeInstanceOf(OdooSessionError)
  })

  it('lança OdooSessionError quando só o data.name indica SessionExpired', async () => {
    post.mockResolvedValue(rpcError(200, 'odoo.http.SessionExpiredException'))
    await expect(odooClient.getSession()).rejects.toBeInstanceOf(OdooSessionError)
  })

  it('lança OdooError (não de sessão) para outro erro JSON-RPC', async () => {
    post.mockResolvedValue(rpcError(200, 'odoo.exceptions.UserError'))
    const e = await odooClient.getSession().catch((x) => x)
    expect(e).toBeInstanceOf(OdooError)
    expect(e).not.toBeInstanceOf(OdooSessionError)
  })
})
