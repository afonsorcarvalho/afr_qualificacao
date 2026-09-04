// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SplitPane } from '../_components/SplitPane'

const setup = (narrow: 'list' | 'detail') =>
  render(
    <SplitPane narrow={narrow} list={<p>lado lista</p>}>
      <p>lado detalhe</p>
    </SplitPane>,
  )

describe('SplitPane', () => {
  it('renderiza os dois lados no DOM, em qualquer modo', () => {
    setup('list')
    expect(screen.getByText('lado lista')).toBeInTheDocument()
    expect(screen.getByText('lado detalhe')).toBeInTheDocument()
  })

  it('narrow=list esconde o detalhe abaixo de lg', () => {
    const { container } = setup('list')
    const [lista, detalhe] = Array.from(
      container.querySelectorAll('[data-pane]'),
    ) as HTMLElement[]
    expect(lista.className).not.toContain('hidden')
    expect(detalhe.className).toContain('hidden')
    expect(detalhe.className).toContain('lg:block')
  })

  it('narrow=detail esconde a lista abaixo de lg', () => {
    const { container } = setup('detail')
    const [lista, detalhe] = Array.from(
      container.querySelectorAll('[data-pane]'),
    ) as HTMLElement[]
    expect(lista.className).toContain('hidden')
    expect(lista.className).toContain('lg:block')
    expect(detalhe.className).not.toContain('hidden')
  })

  it('vira grid de duas colunas em lg, com teto de largura', () => {
    const { container } = setup('list')
    const root = container.firstElementChild as HTMLElement
    expect(root.className).toContain('lg:grid')
    expect(root.className).toContain('lg:grid-cols-[minmax(320px,380px)_1fr]')
    expect(root.className).toContain('lg:max-w-[1440px]')
  })

  // Regressão 2026-09-04: a versão anterior confiava em `lg:sticky` +
  // `lg:max-h-full`, que nunca chega a rolar sozinho — `max-height:100%`
  // não resolve contra uma track de grid `auto` (sem altura definida), então
  // quem rolava era o `<main>` inteiro, arrastando lista E detalhe juntos.
  // Só um teste de classe não prova rolagem de verdade (jsdom não faz
  // layout), mas prova que a receita certa está presente: o container tem
  // altura definida (`lg:h-full` + `lg:grid-rows-1`, o "blowout fix" padrão
  // de grid — track vira `minmax(0,1fr)` em vez de `auto`) e as DUAS colunas
  // têm `lg:min-h-0 lg:overflow-y-auto` pra virarem seus próprios
  // containers de rolagem. A verificação de rolagem de verdade é visual,
  // num browser (Task 5 do plano de layout desktop).
  it('o grid tem altura definida e track que não estoura (blowout fix)', () => {
    const { container } = setup('list')
    const root = container.firstElementChild as HTMLElement
    expect(root.className).toContain('lg:h-full')
    expect(root.className).toContain('lg:grid-rows-1')
    // `lg:items-start` (o valor antigo) deixa cada coluna crescer pro seu
    // próprio content-height, estourando a track de 1fr sem rolar — a mesma
    // falha de antes com outra roupa. Precisa ser `stretch` (o default do
    // grid, mas explícito aqui documenta a decisão) pra as colunas
    // ocuparem exatamente a altura da row e `overflow-y-auto` ter o que
    // fazer.
    expect(root.className).toContain('lg:items-stretch')
    expect(root.className).not.toContain('lg:items-start')
  })

  // Achado 4 da revisão de branch (2026-09-04): sem isto, um usuário de
  // teclado precisava passar por ~24 links da lista antes de chegar no
  // formulário. O link só some visualmente (sr-only), aparece no foco.
  it('achado 4: tem um link de pular pra #detalhe antes da lista, e o pane de detalhe tem esse id', () => {
    const { container } = setup('list')
    const skipLink = screen.getByRole('link', { name: 'Ir para o formulário' })
    expect(skipLink).toHaveAttribute('href', '#detalhe')
    expect(skipLink.className).toContain('sr-only')
    expect(skipLink.className).toContain('focus:not-sr-only')

    const detalhe = container.querySelector('[data-pane="detail"]') as HTMLElement
    expect(detalhe).toHaveAttribute('id', 'detalhe')
  })

  it('as duas colunas rolam sozinhas em lg (min-h-0 + overflow-y-auto cada uma)', () => {
    const { container } = setup('list')
    const [lista, detalhe] = Array.from(
      container.querySelectorAll('[data-pane]'),
    ) as HTMLElement[]
    expect(lista.className).toContain('lg:min-h-0')
    expect(lista.className).toContain('lg:overflow-y-auto')
    expect(detalhe.className).toContain('lg:min-h-0')
    expect(detalhe.className).toContain('lg:overflow-y-auto')
  })
})
