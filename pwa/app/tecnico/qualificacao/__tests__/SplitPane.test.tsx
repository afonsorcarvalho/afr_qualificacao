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

  it('a coluna da lista rola sozinha em lg', () => {
    const { container } = setup('list')
    const lista = container.querySelector('[data-pane="list"]') as HTMLElement
    expect(lista.className).toContain('lg:sticky')
    expect(lista.className).toContain('lg:overflow-y-auto')
  })
})
