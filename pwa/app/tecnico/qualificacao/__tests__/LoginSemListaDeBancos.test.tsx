// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import LoginPage from '../../../login/page'
import { odooClient } from '@/lib/odoo/client'

/**
 * Odoo de produção costuma rodar com `list_db = False`: ele se RECUSA a
 * listar os bancos. Foi o que aconteceu ao publicar no labquali em
 * 2026-09-06 — `/web/database/list` devolveu AccessDenied, e a tela de
 * conexão declarou "Não foi possível conectar. Verifique a URL e se o
 * servidor está acessível", mandando procurar problema onde não havia.
 *
 * Servidor que não lista bancos não é servidor inacessível: é a
 * configuração normal de produção, e o próprio Odoo simplesmente não mostra
 * seletor nesse caso.
 */

const replace = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace, back: vi.fn() }),
  useSearchParams: () => new URLSearchParams('db=odoo-labquali'),
  usePathname: () => '/login',
}))

vi.mock('@/lib/odoo/client', () => {
  const falso = {
    getDatabases: vi.fn(),
    pingServer: vi.fn(),
    authenticate: vi.fn().mockResolvedValue({ uid: 7, name: 'Téc', company_id: 1 }),
    reset: vi.fn(),
    read: vi.fn().mockResolvedValue([]),
    searchRead: vi.fn().mockResolvedValue([]),
    callKw: vi.fn().mockResolvedValue(null),
  }
  return { odooClient: falso, default: falso }
})

vi.mock('@/lib/odoo/schema', () => ({
  preloadSchemas: vi.fn().mockResolvedValue({ ok: 0, failed: 0 }),
}))
vi.mock('@/lib/odoo/publicCompany', () => ({ getCompanyLogoUrl: vi.fn(() => null) }))

const mock = vi.mocked(odooClient) as unknown as {
  getDatabases: ReturnType<typeof vi.fn>
  pingServer: ReturnType<typeof vi.fn>
  authenticate: ReturnType<typeof vi.fn>
}

const wrap = (ui: React.ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

const recusaDeListagem = () =>
  Object.assign(new Error('Odoo Server Error'), { name: 'AccessDenied' })

async function conecta() {
  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'https://labquali.afrsistemas.com.br' },
  })
  fireEvent.click(screen.getByRole('button', { name: /Conectar/i }))
}

beforeEach(() => {
  replace.mockClear()
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ json: () => Promise.resolve({}), ok: true })),
  )
})

describe('servidor que não lista bancos', () => {
  it('segue para as credenciais em vez de dizer que o servidor caiu', async () => {
    mock.getDatabases.mockRejectedValue(recusaDeListagem())
    mock.pingServer.mockResolvedValue(true)

    wrap(<LoginPage />)
    await conecta()

    await waitFor(
      () => expect(document.querySelector('input[type="password"]')).not.toBeNull(),
      { timeout: 3000 },
    )
    expect(screen.queryByText(/Não foi possível conectar/)).not.toBeInTheDocument()
  })

  it('oferece campo de banco preenchido pelo ?db= da URL', async () => {
    mock.getDatabases.mockRejectedValue(recusaDeListagem())
    mock.pingServer.mockResolvedValue(true)

    wrap(<LoginPage />)
    await conecta()

    await waitFor(
      () => expect(document.querySelector('input[type="password"]')).not.toBeNull(),
      { timeout: 3000 },
    )
    // Sem lista não há <select>; o banco vira campo digitável.
    expect(document.querySelector('select')).toBeNull()
    const campoDb = document.querySelector<HTMLInputElement>('input[name="db"]')
    expect(campoDb).not.toBeNull()
    expect(campoDb!.value).toBe('odoo-labquali')
  })

  it('autentica com o banco digitado', async () => {
    mock.getDatabases.mockRejectedValue(recusaDeListagem())
    mock.pingServer.mockResolvedValue(true)

    wrap(<LoginPage />)
    await conecta()
    await waitFor(
      () => expect(document.querySelector('input[type="password"]')).not.toBeNull(),
      { timeout: 3000 },
    )

    const textos = screen.getAllByRole('textbox')
    fireEvent.change(textos[textos.length - 1], { target: { value: 'tecnico@labquali' } })
    fireEvent.change(document.querySelector('input[type="password"]')!, {
      target: { value: 'segredo' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() => expect(mock.authenticate).toHaveBeenCalled())
    const [, db] = mock.authenticate.mock.calls[0]
    expect(db).toBe('odoo-labquali')
  })

  it('servidor realmente fora do ar continua dando erro', async () => {
    // O ramo que não pode sumir: se nem a listagem nem o ping respondem, aí
    // sim o servidor está inacessível.
    mock.getDatabases.mockRejectedValue(new Error('Network Error'))
    mock.pingServer.mockResolvedValue(false)

    wrap(<LoginPage />)
    await conecta()

    await waitFor(() =>
      expect(screen.getByText(/Não foi possível conectar/)).toBeInTheDocument(),
    )
    expect(document.querySelector('input[type="password"]')).toBeNull()
  })
})
