// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render } from '@testing-library/react'
import { ServiceWorkerRegister } from '@/components/providers/ServiceWorkerRegister'

/**
 * O PWA é servido no MESMO domínio do Odoo do cliente
 * (labquali.afrsistemas.com.br/tecnico), então o escopo do service worker
 * não é detalhe de configuração: registrado na raiz, ele passaria a
 * interceptar também as páginas do backend do Odoo e a servi-las do cache.
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
  it('registra o service worker com escopo restrito ao app do técnico', () => {
    render(<ServiceWorkerRegister />)
    expect(register).toHaveBeenCalledTimes(1)
    const [url, opts] = register.mock.calls[0]
    expect(url).toBe('/sw.js')
    expect(opts?.scope).toBe('/tecnico/')
  })

  it('não registra nada fora de produção', () => {
    // Em dev o `next-pwa` nem gera o sw.js; registrar só encheria o console
    // de 404.
    vi.stubEnv('NODE_ENV', 'development')
    render(<ServiceWorkerRegister />)
    expect(register).not.toHaveBeenCalled()
  })
})
