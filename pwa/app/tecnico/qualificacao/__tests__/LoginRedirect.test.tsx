// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import LoginPage from '../../../login/page'

const push = vi.fn()
const replace = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace, back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(''),
  usePathname: () => '/login',
}))

vi.mock('@/lib/odoo/client', () => {
  const falso = {
    getDatabases: vi.fn().mockResolvedValue(['qualificacao-dev']),
    authenticate: vi.fn().mockResolvedValue({ uid: 7, name: 'Técnico A', company_id: 1 }),
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

// Retorno SÍNCRONO: a página usa o valor direto em `setCompanyLogoUrl`.
vi.mock('@/lib/odoo/publicCompany', () => ({
  getCompanyLogoUrl: vi.fn(() => null),
}))

const wrap = (ui: React.ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

/** Vai do passo "Servidor" até o formulário de credenciais.
 *  O marco é o campo de senha aparecer — o botão "Entrar" nasce desabilitado
 *  até haver usuário e senha, então esperar por ele habilitado travaria. */
async function conecta() {
  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'http://localhost:8084' },
  })
  fireEvent.click(screen.getByRole('button', { name: /Conectar/i }))
  // 3s, não o 1s padrão: a troca de passo é agendada com `setTimeout(400)` e
  // ainda espera a animação de saída do framer-motion.
  await waitFor(
    () => expect(document.querySelector('input[type="password"]')).not.toBeNull(),
    { timeout: 3000 },
  )
}

beforeEach(() => {
  push.mockClear()
  replace.mockClear()
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ json: () => Promise.resolve({}), ok: true })),
  )
})

describe('entrar', () => {
  it('SUBSTITUI a entrada no histórico ao entrar, em vez de empilhar', async () => {
    // Com `push`, o botão voltar levava o técnico já autenticado de volta à
    // tela de credenciais. Mesmo defeito do fechamento de relatório e do
    // logout, achado na mesma varredura em 2026-09-05.
    wrap(<LoginPage />)
    await conecta()

    const campos = screen.getAllByRole('textbox')
    fireEvent.change(campos[campos.length - 1], { target: { value: 'tecnico.a@teste.local' } })
    fireEvent.change(document.querySelector('input[type="password"]')!, {
      target: { value: 'Teste@2026' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/tecnico/qualificacao'))
    expect(push).not.toHaveBeenCalled()
  })
})
