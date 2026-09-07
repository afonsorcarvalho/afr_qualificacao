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
  const PADRAO = '/tecnico/qualificacao'

  it('usa destino padrão quando não há next', () => {
    expect(destinoSeguro(null)).toBe(PADRAO)
  })

  it('aceita caminho interno', () => {
    expect(destinoSeguro('/tecnico/qualificacao/4/coleta/213')).toBe(
      '/tecnico/qualificacao/4/coleta/213',
    )
  })

  it('preserva query string e fragmento do destino — o recurso que a task existe para entregar', () => {
    // Se a correção do bypass quebrar isto, ela quebrou o próprio objetivo
    // da task: devolver o técnico ao link exato que ele abriu.
    expect(destinoSeguro('/tecnico/qualificacao/4/coleta/213?x=1#top')).toBe(
      '/tecnico/qualificacao/4/coleta/213?x=1#top',
    )
  })

  it('recusa destino externo (open redirect)', () => {
    // `?next=https://evil.example` faria o login mandar o técnico para
    // fora. Só caminho absoluto interno vale.
    const req = new NextRequest('http://localhost:3010/login?next=https://evil.example')
    expect(destinoSeguro(req.nextUrl.searchParams.get('next'))).toBe(PADRAO)
  })

  it('recusa protocolo relativo (barra dupla) — URL absoluta para o navegador', () => {
    expect(destinoSeguro('//evil.example')).toBe(PADRAO)
  })

  it('recusa barra tripla e variantes barra/contrabarra que colapsam para host externo', () => {
    expect(destinoSeguro('///evil.example')).toBe(PADRAO)
    expect(destinoSeguro('/\\evil.example')).toBe(PADRAO)
    expect(destinoSeguro('\\/evil.example')).toBe(PADRAO)
  })

  it('recusa esquema absoluto, com ou sem barra dupla (https:/evil, http://evil)', () => {
    expect(destinoSeguro('https:/evil')).toBe(PADRAO)
    expect(destinoSeguro('http://evil')).toBe(PADRAO)
  })

  it('recusa esquema não-http (javascript:, data:) — origin opaco não bate com o interno', () => {
    expect(destinoSeguro('javascript:alert(1)')).toBe(PADRAO)
    expect(destinoSeguro('data:text/html,x')).toBe(PADRAO)
  })

  // Achado da revisão adversarial (fix round 1): a primeira versão desta
  // função checava a string CRUA (`startsWith`, `includes('\\')`), mas quem
  // consome o retorno (`router.replace` do Next) resolve com `new URL`, cujo
  // parser remove todo tab/LF/CR da string ANTES de resolver — colapsando
  // `/\t/evil.example` em `//evil.example` por baixo do bloqueio de `\`.
  // Exploração real: autentica com `?next=%2F%09%2Fevil.example` e o técnico
  // sai do host. Cobre literal e percent-encoded — o encoded não deve
  // decodificar para o caractere de controle nesta camada (permanece
  // caminho interno literal, inofensivo).
  it('recusa tab/LF/CR (literal) que o parser da URL colapsa para host externo', () => {
    expect(destinoSeguro('/\t/evil.example')).toBe(PADRAO)
    expect(destinoSeguro('/\n/evil.example')).toBe(PADRAO)
    expect(destinoSeguro('/\r/evil.example')).toBe(PADRAO)
  })

  it('percent-encoded (%09/%0A/%0D) não decodifica para controle nesta camada — path interno literal', () => {
    expect(destinoSeguro('/%09/evil.example')).toBe('/%09/evil.example')
    expect(destinoSeguro('/%0A/evil.example')).toBe('/%0A/evil.example')
    expect(destinoSeguro('/%0D/evil.example')).toBe('/%0D/evil.example')
  })

  it('normaliza travessia de diretório (..) em vez de devolver literal', () => {
    // Bônus da correção por `new URL`: o parser resolve `..` antes de
    // comparar origin, então não sobra `..` no destino final.
    expect(destinoSeguro('/tecnico/../../evil')).toBe('/evil')
  })

  it('destino malformado (URL lança) cai no padrão', () => {
    expect(destinoSeguro('http://')).toBe(PADRAO)
  })
})
