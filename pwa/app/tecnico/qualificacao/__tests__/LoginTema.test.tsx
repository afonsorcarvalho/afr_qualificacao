// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import LoginPage from '../../../login/page'
import { odooClient } from '@/lib/odoo/client'

/**
 * É a tela mais quebrada do app: no tema claro `text-white/60` sobre
 * `bg-card` branco é branco sobre branco. O técnico vê um formulário sem
 * rótulo e sem o que digitou. Confirmado em captura de tela (2026-09-06).
 *
 * Esta suíte tem duas partes:
 *   1. Varredura de texto-fonte (a mesma proibição da catraca global,
 *      aplicada aqui como teste de aceitação da task).
 *   2. Teste de RENDER: prova que rótulo e valor carregam tokens
 *      DIFERENTES — uma varredura de classe proibida não pega um par
 *      colapsado na MESMA cor permitida (ex.: rótulo e valor os dois em
 *      `text-foreground`), que mata a hierarquia sem violar regex nenhuma.
 */

const SRC = readFileSync(join(__dirname, '..', '..', '..', '..', 'app/login/page.tsx'), 'utf8')

describe('login: legível nos dois temas (varredura de texto-fonte)', () => {
  it('nenhuma tinta branca absoluta', () => {
    // `text-white/60` sobre `bg-card` é branco sobre branco no tema claro:
    // o rótulo e o valor digitado somem da tela.
    expect(SRC).not.toMatch(/\b(?:text|bg|border|divide)-white(?:\/\d{1,3})?\b/)
  })

  it('as opções do seletor de banco não fixam fundo escuro', () => {
    // `bg-dark-800 text-white` num <option> entrega texto branco em lista
    // clara nos navegadores que respeitam o estilo da opção.
    expect(SRC).not.toMatch(/bg-dark-\d{3}/)
  })

  it('nenhuma shade crua de cor de estado', () => {
    expect(SRC).not.toMatch(/\b(?:text|bg|border)-(?:emerald|red|amber|cyan)-\d{2,3}\b/)
  })
})

// ─── Parte 2: render ─────────────────────────────────────────────────────

const replace = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace, back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(''),
  usePathname: () => '/login',
}))

vi.mock('@/lib/odoo/client', () => {
  const falso = {
    getDatabases: vi.fn().mockResolvedValue(['qualificacao-dev']),
    pingServer: vi.fn().mockResolvedValue(true),
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

const wrap = (ui: React.ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

/** Vai do passo "Servidor" até o formulário de credenciais (banco COM
 *  lista — cenário do <select>, para cobrir a opção de banco também). */
async function conecta() {
  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'http://localhost:8084' },
  })
  fireEvent.click(screen.getByRole('button', { name: /Conectar/i }))
  await waitFor(
    () => expect(document.querySelector('input[type="password"]')).not.toBeNull(),
    { timeout: 3000 },
  )
}

beforeEach(() => {
  replace.mockClear()
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ json: () => Promise.resolve({}), ok: true })),
  )
})

describe('login: passo 1 — rótulo e valor digitado usam tokens diferentes', () => {
  it('o rótulo "URL do servidor" e o valor digitado no campo não colapsam na mesma cor', async () => {
    wrap(<LoginPage />)

    const rotulo = screen.getByText('URL do servidor')
    const campo = screen.getByRole('textbox') as HTMLInputElement

    fireEvent.change(campo, { target: { value: 'http://localhost:8084' } })

    // Par primário/secundário: o valor que o técnico digitou é a
    // informação principal (text-foreground); o rótulo é metadado
    // (text-muted-foreground). Colapsar os dois na mesma classe é
    // exatamente o defeito de 2026-09-06 (perda de hierarquia).
    // `.split(' ')` em vez de `.toContain` na string inteira: o campo tem
    // `placeholder:text-muted-foreground` (cor do PLACEHOLDER, variante
    // diferente) — um `toContain` ingênuo acusaria falso positivo aqui.
    const classesCampo = campo.className.split(/\s+/)
    const classesRotulo = rotulo.className.split(/\s+/)
    expect(classesCampo).toContain('text-foreground')
    expect(classesRotulo).toContain('text-muted-foreground')
    expect(classesCampo).not.toContain('text-muted-foreground')
    expect(classesRotulo).not.toContain('text-foreground')

    // Placeholder e texto de apoio continuam presentes no DOM (o teste de
    // aceitação da task pede isso na tela — aqui é a garantia de que o
    // atributo/token não foi apagado junto com a cor antiga).
    expect(campo.placeholder).toBe('https://mb.fitadigital.com.br')
  })
})

describe('login: passo 2 — rótulos, banco no seletor e usuário digitado', () => {
  it('rótulos "Banco de dados"/"Usuário"/"Senha", o nome do banco e o valor digitado usam tokens visíveis e diferentes entre si', async () => {
    wrap(<LoginPage />)
    await conecta()

    const rotuloBanco = screen.getByText('Banco de dados')
    const rotuloUsuario = screen.getByText('Usuário')
    const rotuloSenha = screen.getByText('Senha')

    // Nome do banco dentro do <select>: cenário com lista (getDatabases
    // resolve para ['qualificacao-dev']).
    const select = document.querySelector('select') as HTMLSelectElement
    expect(select).not.toBeNull()
    const option = screen.getByRole('option', { name: 'qualificacao-dev' }) as HTMLOptionElement
    expect(option).toBeInTheDocument()
    // Nenhuma cor fixa no <option>: o color-scheme do <html> (Task 2) é o
    // que faz o navegador pintar a lista de forma legível — uma classe
    // aqui reintroduziria o defeito.
    expect(option.className).toBe('')

    const textos = screen.getAllByRole('textbox')
    const campoUsuario = textos[textos.length - 1] as HTMLInputElement
    fireEvent.change(campoUsuario, { target: { value: 'tecnico.a@teste.local' } })

    for (const rotulo of [rotuloBanco, rotuloUsuario, rotuloSenha]) {
      expect(rotulo.className.split(/\s+/)).toContain('text-muted-foreground')
    }
    const classesSelect = select.className.split(/\s+/)
    const classesUsuario = campoUsuario.className.split(/\s+/)
    expect(classesSelect).toContain('text-foreground')
    expect(classesUsuario).toContain('text-foreground')
    expect(classesSelect).not.toContain('text-muted-foreground')
    expect(classesUsuario).not.toContain('text-muted-foreground')
  })
})
