// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ConfirmarMudancaData } from '../agenda/_ConfirmarMudancaData'

/**
 * Pedido do usuário: o diálogo de confirmação de mudança de data deve
 * aparecer CENTRALIZADO na tela, não subindo de baixo como a `VisitaSheet`
 * (que usa o mesmo `BottomSheet`, mas continua com a folha de baixo). O que
 * importa verificar aqui é só isso — que este componente pede a variante
 * `'centro'` ao `BottomSheet` compartilhado; a mecânica de foco/trap/Escape
 * já tem cobertura própria em `BottomSheet.test.tsx` para as duas variantes.
 */
describe('ConfirmarMudancaData: posição', () => {
  it('usa a variante centro do BottomSheet — arredonda os quatro cantos, não sobe de baixo', () => {
    render(
      <ConfirmarMudancaData
        open
        osName="OS26-06-0002"
        dataAtual="2026-09-17"
        dataNova="2026-09-18"
        onConfirmar={vi.fn()}
        onCancelar={vi.fn()}
      />,
    )
    const dialogo = screen.getByRole('dialog', { name: 'Mudar data da visita' })
    const moldura = dialogo.parentElement as HTMLElement

    expect(moldura.className).toContain('items-center')
    expect(dialogo.className).toMatch(/(?:^|\s)rounded-2xl(?:\s|$)/)
    expect(dialogo.className).not.toContain('rounded-t-2xl')
  })
})
