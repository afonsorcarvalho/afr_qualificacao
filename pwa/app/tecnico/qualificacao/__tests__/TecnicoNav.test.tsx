// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TecnicoNav } from '../_components/TecnicoNav'

const push = vi.fn()
let pathname = '/tecnico/qualificacao'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, back: vi.fn() }),
  usePathname: () => pathname,
}))

describe('TecnicoNav', () => {
  beforeEach(() => {
    pathname = '/tecnico/qualificacao'
    push.mockClear()
  })

  it('renderiza os três destinos com href correto', () => {
    render(<TecnicoNav variant="bottom" />)
    expect(screen.getByRole('link', { name: /OSs/ })).toHaveAttribute(
      'href',
      '/tecnico/qualificacao',
    )
    expect(screen.getByRole('link', { name: /Histórico/ })).toHaveAttribute(
      'href',
      '/tecnico/qualificacao/historico',
    )
    expect(screen.getByRole('link', { name: /Perfil/ })).toHaveAttribute(
      'href',
      '/tecnico/qualificacao/perfil',
    )
  })

  it('marca aria-current no destino ativo', () => {
    pathname = '/tecnico/qualificacao/historico'
    render(<TecnicoNav variant="bottom" />)
    expect(screen.getByRole('link', { name: /Histórico/ })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('link', { name: /OSs/ })).not.toHaveAttribute('aria-current')
  })

  it('todo item tem alvo de toque de 44px em qualquer variante', () => {
    const { unmount } = render(<TecnicoNav variant="bottom" />)
    for (const link of screen.getAllByRole('link')) {
      expect(link.className).toContain('min-h-[44px]')
    }
    unmount()
    render(<TecnicoNav variant="side" />)
    for (const link of screen.getAllByRole('link')) {
      expect(link.className).toContain('min-h-[44px]')
    }
  })

  it('variante bottom é barra fixa embaixo e some em lg', () => {
    const { container } = render(<TecnicoNav variant="bottom" />)
    const nav = container.querySelector('nav') as HTMLElement
    expect(nav.className).toContain('sticky')
    expect(nav.className).toContain('bottom-0')
    expect(nav.className).toContain('lg:hidden')
  })

  it('variante side é coluna vertical, só visível em lg, sem sombra flutuante', () => {
    const { container } = render(<TecnicoNav variant="side" />)
    const nav = container.querySelector('nav') as HTMLElement
    expect(nav.className).toContain('hidden')
    expect(nav.className).toContain('lg:flex')
    expect(nav.className).toContain('flex-col')
    expect(nav.className).toContain('border-r')
    expect(nav.className).not.toContain('shadow-[0_-8px_24px')
  })
})
