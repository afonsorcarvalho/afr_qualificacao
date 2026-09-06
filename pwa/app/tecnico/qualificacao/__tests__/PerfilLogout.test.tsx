// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PerfilPage from '../perfil/page'
import { useAuthStore } from '@/lib/store/authStore'

const push = vi.fn()
const replace = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace, back: vi.fn() }),
  usePathname: () => '/tecnico/qualificacao/perfil',
}))

vi.mock('next-themes', () => ({ useTheme: () => ({ theme: 'dark', setTheme: vi.fn() }) }))

// O dublê precisa cobrir tudo que a página toca: além do `logout`, o
// `resetSessionCache` e o carregamento de empresas passam pelo mesmo cliente.
// Construído dentro da fábrica porque `vi.mock` sobe para o topo do arquivo e
// não enxerga variável declarada depois.
vi.mock('@/lib/odoo/client', () => {
  const falso = {
    logout: vi.fn().mockResolvedValue(undefined),
    reset: vi.fn(),
    searchRead: vi.fn().mockResolvedValue([]),
    read: vi.fn().mockResolvedValue([]),
    callKw: vi.fn().mockResolvedValue(null),
    searchCount: vi.fn().mockResolvedValue(0),
    write: vi.fn().mockResolvedValue(true),
  }
  return { odooClient: falso, default: falso }
})

vi.mock('@/lib/odoo/companies', () => ({
  fetchAvailableCompanies: vi.fn().mockResolvedValue([]),
}))

const wrap = (ui: React.ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  push.mockClear()
  replace.mockClear()
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ json: () => Promise.resolve({}) })),
  )
  useAuthStore.setState({
    userName: 'Técnico A',
    userId: 7,
    companyName: 'Hospital X',
    serverUrl: 'http://localhost:8084',
    dbName: 'qualificacao-dev',
  } as never)
})

describe('sair da conta', () => {
  it('SUBSTITUI a entrada no histórico ao sair, em vez de empilhar', async () => {
    // Com `push`, voltar trazia de volta a tela autenticada já sem sessão: o
    // AuthGuard só então expulsava — piscada, e um POST de logout extra que
    // chegava a aparecer como 502 no log. Achado junto com o mesmo defeito no
    // fechamento de relatório, em 2026-09-05.
    wrap(<PerfilPage />)
    fireEvent.click(screen.getByRole('button', { name: /Sair/i }))

    await waitFor(() => expect(replace).toHaveBeenCalled())
    expect(replace.mock.calls[0][0]).toMatch(/^\/login/)
    expect(push).not.toHaveBeenCalled()
  })

  it('a sessão é limpa antes de navegar', async () => {
    // Navegar com o store ainda populado deixaria a tela de login exibindo o
    // usuário anterior por um quadro.
    wrap(<PerfilPage />)
    fireEvent.click(screen.getByRole('button', { name: /Sair/i }))

    await waitFor(() => expect(replace).toHaveBeenCalled())
    expect(useAuthStore.getState().userId).toBeFalsy()
  })
})
