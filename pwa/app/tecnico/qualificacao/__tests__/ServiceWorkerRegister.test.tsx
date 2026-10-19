// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render } from '@testing-library/react'
import { ServiceWorkerRegister } from '@/components/providers/ServiceWorkerRegister'

/**
 * Escopo padrão `/app/` (basePath): todo o PWA vive sob o prefixo.
 * precisa funcionar offline. `NEXT_PUBLIC_SW_SCOPE` restringe, se preciso.
 */

const register = vi.fn().mockResolvedValue({})

beforeEach(() => {
  register.mockClear()
  vi.stubGlobal('navigator', { ...globalThis.navigator, serviceWorker: { register } })
  vi.stubEnv('NODE_ENV', 'production')
  Object.defineProperty(document, 'readyState', {
    value: 'complete',
    configurable: true,
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe('ServiceWorkerRegister', () => {
  it('registra /app/sw.js com escopo /app/ por padrão', () => {
    render(<ServiceWorkerRegister />)
    expect(register).toHaveBeenCalledTimes(1)
    const [url, opts] = register.mock.calls[0]
    expect(url).toBe('/app/sw.js')
    expect(opts?.scope).toBe('/app/')
  })

  it('NEXT_PUBLIC_SW_SCOPE sobrescreve o escopo', () => {
    vi.stubEnv('NEXT_PUBLIC_SW_SCOPE', '/app/tecnico/')
    render(<ServiceWorkerRegister />)
    expect(register.mock.calls[0][1]?.scope).toBe('/app/tecnico/')
  })

  it('não registra nada fora de produção', () => {
    // Em dev o `next-pwa` nem gera o sw.js; registrar só encheria o console
    // de 404.
    vi.stubEnv('NODE_ENV', 'development')
    render(<ServiceWorkerRegister />)
    expect(register).not.toHaveBeenCalled()
  })
})
