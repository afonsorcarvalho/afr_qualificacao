// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import TecnicoLayout from '../layout'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/tecnico/qualificacao',
}))

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ json: () => Promise.resolve({ uid: 7 }) })),
  )
})

/**
 * O invólucro do app do técnico precisa ter altura definida em TODA largura,
 * senão o `<main overflow-auto>` cresce com o conteúdo, quem rola é a janela,
 * o scrollport do `main` nunca rola e todo `sticky` lá dentro fica inerte —
 * medido a 375px em 2026-09-05: o filtro de coletas e o cabeçalho de grupo
 * saíam da tela junto com a lista.
 *
 * Asserção por classe porque o happy-dom não faz layout: não há altura real
 * pra medir. O que se pode travar aqui é a decisão — altura fixa e
 * `min-h-0` na coluna, não `min-h-screen`.
 */
describe('casca do app do técnico', () => {
  it('o invólucro tem altura definida em toda largura, não só em desktop', () => {
    const { container } = render(<TecnicoLayout><p>conteúdo</p></TecnicoLayout>)
    const raiz = container.querySelector('div.mx-auto') as HTMLElement
    expect(raiz.className).toContain('h-dvh')
    // `min-h-screen` deixa o invólucro crescer com o conteúdo: é justo o que
    // matava o sticky em tela estreita.
    expect(raiz.className).not.toContain('min-h-screen')
    expect(raiz.className).toContain('overflow-hidden')
    // Sem `lg:` no prefixo: valia só a partir de 1024px antes.
    expect(raiz.className).not.toContain('lg:h-dvh')
  })

  it('a coluna de conteúdo pode encolher, senão o main não rola', () => {
    const { container } = render(<TecnicoLayout><p>conteúdo</p></TecnicoLayout>)
    const main = container.querySelector('main') as HTMLElement
    expect(main.className).toContain('overflow-auto')
    expect(main.className).toContain('min-h-0')
    const coluna = main.parentElement as HTMLElement
    expect(coluna.className).toContain('min-h-0')
  })
})
