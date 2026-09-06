// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { StatusBadge } from '@/components/ui/StatusBadge'

describe('StatusBadge: cor de estado por token', () => {
  it('estado concluído usa o token --ok em vez do par emerald-700/dark:emerald-400', () => {
    const { container } = render(<StatusBadge tone="done">Coletada</StatusBadge>)
    const cls = container.firstElementChild!.className
    expect(cls).toContain('text-ok')
    expect(cls).not.toMatch(/emerald-\d/)
    // O token já resolve o tema: o par `dark:` vira ruído e some.
    expect(cls).not.toContain('dark:')
  })

  it('em espera usa --warn, falha usa --danger', () => {
    const warn = render(<StatusBadge tone="waiting">Pendente</StatusBadge>)
    expect(warn.container.firstElementChild!.className).toContain('text-warn')
    const err = render(<StatusBadge tone="error">Falhou</StatusBadge>)
    expect(err.container.firstElementChild!.className).toContain('text-danger')
  })

  it('a informação sobrevive sem a cor (Regra do Par, DESIGN.md §2)', () => {
    const { container } = render(<StatusBadge tone="waiting">Pendente</StatusBadge>)
    expect(container.textContent).toBe('Pendente')
  })
})
