// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { NextRequest } from 'next/server'
import LoginPage from '../../../login/page'
import { destinoSeguro } from '@/lib/navegacao'
import { middleware } from '@/middleware'

const push = vi.fn()
const replace = vi.fn()

// `vi.hoisted`: a fábrica de `vi.mock` abaixo é hoisted acima destas
// declarações, então o estado mutável de `?next=` que ela lê precisa nascer
// dentro do próprio hoist para não virar `undefined` na primeira leitura.
const { getSearchParams, setNext, clearNext } = vi.hoisted(() => {
  let params = new URLSearchParams('')
  return {
    getSearchParams: () => params,
    setNext: (next: string) => {
      params = new URLSearchParams()
      params.set('next', next)
    },
    clearNext: () => {
      params = new URLSearchParams('')
    },
  }
})

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace, back: vi.fn() }),
  useSearchParams: () => getSearchParams(),
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
  clearNext()
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

  it('depois de autenticar vai para o destino guardado (?next=), sem deixar o login no histórico', async () => {
    // Deep link real: /tecnico/qualificacao/4/coleta/213. `replace`, não
    // `push` — o formulário de credenciais não pode sobreviver no histórico
    // (regra travada por navegacaoHistorico.test.ts).
    setNext('/tecnico/qualificacao/4/coleta/213')
    wrap(<LoginPage />)
    await conecta()

    const campos = screen.getAllByRole('textbox')
    fireEvent.change(campos[campos.length - 1], { target: { value: 'tecnico.a@teste.local' } })
    fireEvent.change(document.querySelector('input[type="password"]')!, {
      target: { value: 'Teste@2026' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith('/tecnico/qualificacao/4/coleta/213'),
    )
    expect(push).not.toHaveBeenCalled()
  })

  it('ignora ?next= externo e cai na lista padrão (open redirect)', async () => {
    setNext('https://evil.example')
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

describe('middleware: expulsão guarda o destino original', () => {
  it('guarda o destino original ao expulsar para o login', () => {
    const req = new NextRequest('http://localhost:3010/tecnico/qualificacao/4/coleta/213')
    const res = middleware(req)
    const destino = new URL(res.headers.get('location')!)
    expect(destino.pathname).toBe('/login')
    expect(destino.searchParams.get('next')).toBe('/tecnico/qualificacao/4/coleta/213')
  })

  it('preserva a query string do destino original em next', () => {
    const req = new NextRequest('http://localhost:3010/tecnico/qualificacao?filtro=pendentes')
    const res = middleware(req)
    const destino = new URL(res.headers.get('location')!)
    expect(destino.searchParams.get('next')).toBe('/tecnico/qualificacao?filtro=pendentes')
  })

  it('não expulsa /login, mesmo sem sessão', () => {
    const req = new NextRequest('http://localhost:3010/login')
    const res = middleware(req)
    expect(res.headers.get('location')).toBeNull()
  })
})

describe('destinoSeguro: só caminho interno vale', () => {
  it('usa destino padrão quando não há next', () => {
    expect(destinoSeguro(null)).toBe('/tecnico/qualificacao')
  })

  it('aceita caminho interno', () => {
    expect(destinoSeguro('/tecnico/qualificacao/4/coleta/213')).toBe(
      '/tecnico/qualificacao/4/coleta/213',
    )
  })

  it('recusa destino externo (open redirect)', () => {
    // `?next=https://evil.example` faria o login mandar o técnico para
    // fora. Só caminho absoluto interno vale.
    const req = new NextRequest('http://localhost:3010/login?next=https://evil.example')
    expect(destinoSeguro(req.nextUrl.searchParams.get('next'))).toBe('/tecnico/qualificacao')
  })

  it('recusa protocolo relativo (barra dupla) — URL absoluta para o navegador', () => {
    expect(destinoSeguro('//evil.example')).toBe('/tecnico/qualificacao')
  })

  it('recusa contrabarra, que alguns navegadores normalizam para barra', () => {
    expect(destinoSeguro('/\\evil.example')).toBe('/tecnico/qualificacao')
  })

  it('recusa esquema absoluto sem barra dupla (https:/evil)', () => {
    expect(destinoSeguro('https:/evil')).toBe('/tecnico/qualificacao')
  })
})
