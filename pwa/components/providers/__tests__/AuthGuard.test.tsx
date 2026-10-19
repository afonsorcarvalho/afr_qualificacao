// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, waitFor, act } from '@testing-library/react'

const getSession = vi.fn()
const logoutApi = vi.fn()
vi.mock('@/lib/odoo/client', async () => {
  class OdooError extends Error {
    constructor(m: string, public readonly code: number) { super(m); this.name = 'OdooError' }
  }
  class OdooSessionError extends OdooError {
    constructor() { super('sessao', 401); this.name = 'OdooSessionError' }
  }
  return {
    OdooError,
    OdooSessionError,
    odooClient: { getSession: () => getSession(), logout: () => logoutApi() },
  }
})
vi.mock('@/lib/odoo/schema', () => ({ preloadSchemas: vi.fn().mockResolvedValue(undefined) }))
let pathname = '/a'
const replace = vi.fn()
const router = { replace } // referência estável, como no Next
vi.mock('next/navigation', () => ({
  usePathname: () => pathname,
  useRouter: () => router,
}))

import { OdooError, OdooSessionError } from '@/lib/odoo/client'
import { useAuthStore } from '@/lib/store/authStore'
import { AuthGuard } from '../AuthGuard'

const ui = () => (
  <AuthGuard>
    <div data-testid="kids">conteudo</div>
  </AuthGuard>
)

beforeEach(() => {
  vi.clearAllMocks()
  pathname = '/a'
  logoutApi.mockResolvedValue(undefined)
  useAuthStore.setState({ isAuthenticated: true, serverUrl: 'https://s', dbName: 'd', userId: 1 })
})

describe('AuthGuard', () => {
  it('rede fora (OdooError code 0) com store autenticado: mantém sessão e renderiza', async () => {
    getSession.mockRejectedValue(new OdooError('offline', 0))
    const { findByTestId } = render(ui())
    await findByTestId('kids')
    expect(logoutApi).not.toHaveBeenCalled()
    expect(replace).not.toHaveBeenCalled()
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })

  it('502 do proxy: mantém sessão e renderiza', async () => {
    getSession.mockRejectedValue(new OdooError('bad gateway', 502))
    const { findByTestId } = render(ui())
    await findByTestId('kids')
    expect(logoutApi).not.toHaveBeenCalled()
    expect(replace).not.toHaveBeenCalled()
  })

  it('OdooSessionError: logout e redireciona', async () => {
    getSession.mockRejectedValue(new OdooSessionError())
    const { queryByTestId } = render(ui())
    await waitFor(() => expect(replace).toHaveBeenCalledTimes(1))
    expect(replace.mock.calls[0][0]).toContain('/login')
    expect(logoutApi).toHaveBeenCalled()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(queryByTestId('kids')).toBeNull()
  })

  it('uid false: logout e redireciona', async () => {
    getSession.mockResolvedValue({ uid: false, name: '' })
    render(ui())
    await waitFor(() => expect(replace).toHaveBeenCalledTimes(1))
    expect(logoutApi).toHaveBeenCalled()
  })

  it('uid válido: renderiza', async () => {
    getSession.mockResolvedValue({ uid: 7, name: 'A' })
    const { findByTestId } = render(ui())
    await findByTestId('kids')
    expect(logoutApi).not.toHaveBeenCalled()
    expect(replace).not.toHaveBeenCalled()
  })

  it('erro de rede sem store autenticado: redireciona ao login', async () => {
    useAuthStore.setState({ isAuthenticated: false })
    getSession.mockRejectedValue(new OdooError('offline', 0))
    render(ui())
    await waitFor(() => expect(replace).toHaveBeenCalledTimes(1))
  })

  it('troca de rota offline continua sem logout', async () => {
    getSession.mockRejectedValue(new OdooError('offline', 0))
    const { findByTestId, rerender } = render(ui())
    await findByTestId('kids')
    pathname = '/b'
    await act(async () => { rerender(ui()) })
    await waitFor(() => expect(getSession).toHaveBeenCalledTimes(2))
    await findByTestId('kids')
    expect(logoutApi).not.toHaveBeenCalled()
    expect(replace).not.toHaveBeenCalled()
  })
})
