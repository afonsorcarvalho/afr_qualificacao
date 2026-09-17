// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { GradeMes } from '../agenda/_GradeMes'
import { gradeDoMes } from '../agenda/mes'
import type { PontosDia, PontoTecnico } from '../agenda/mes'

const ANCORA = '2026-09-01'
const GRADE = gradeDoMes(ANCORA) // 42 dias: 2026-08-30 .. 2026-10-10

function ponto(over: Partial<PontoTecnico> = {}): PontoTecnico {
  return { id: 1, name: 'Ana Silva', cor: '#0ea5e9', visitas: 1, ...over }
}

function pontosDiaVazio(date: string): PontosDia {
  return { date, pontos: [], total: 0, conflito: false }
}

/** Grade de 42 `PontosDia` vazios, com overrides por data ISO. */
function montarDias(overrides: Record<string, Partial<PontosDia>> = {}): PontosDia[] {
  return GRADE.map((date) => ({ ...pontosDiaVazio(date), ...(overrides[date] ?? {}) }))
}

describe('GradeMes', () => {
  it('renderiza 42 células, uma por dia da grade', () => {
    render(
      <GradeMes
        dias={montarDias()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(screen.getAllByRole('button')).toHaveLength(42)
  })

  it('célula fora do mês leva o prefixo no aria-label e continua clicável', () => {
    const onSelecionar = vi.fn()
    render(
      <GradeMes
        dias={montarDias()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={onSelecionar}
      />,
    )
    // 2026-08-30 é o primeiro dia da grade, fora do mês de setembro.
    const cel = screen.getByRole('button', { name: /^fora do mês, 30 de agosto, sem visitas$/ })
    fireEvent.click(cel)
    expect(onSelecionar).toHaveBeenCalledWith('2026-08-30')
  })

  it('aria-pressed é true só na célula selecionada', () => {
    render(
      <GradeMes
        dias={montarDias()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-05"
        onSelecionar={vi.fn()}
      />,
    )
    const pressionados = screen.getAllByRole('button', { pressed: true })
    expect(pressionados).toHaveLength(1)
    expect(pressionados[0]).toHaveAccessibleName(/5 de setembro/)
  })

  it('dia com 6 técnicos distintos mostra 3 pontos e o rótulo +3', () => {
    const dias = montarDias({
      '2026-09-17': {
        total: 6,
        pontos: [
          ponto({ id: 1, name: 'Ana Silva' }),
          ponto({ id: 2, name: 'Bruno' }),
          ponto({ id: 3, name: 'Carla' }),
          ponto({ id: 4, name: 'Dario' }),
          ponto({ id: 5, name: 'Elis' }),
          ponto({ id: 6, name: 'Fabio' }),
        ],
      },
    })
    render(
      <GradeMes
        dias={dias}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const cel = screen.getByRole('button', { name: /^17 de setembro,/ })
    expect(within(cel).getAllByTestId('ponto')).toHaveLength(3)
    expect(within(cel).getByTestId('mais')).toHaveTextContent('+3')
  })

  it('dia vazio tem aria-label "sem visitas"', () => {
    render(
      <GradeMes
        dias={montarDias()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', { name: '1 de setembro, sem visitas' }),
    ).toBeInTheDocument()
  })

  it('dia com conflito tem o sufixo ", com conflito" no aria-label', () => {
    const dias = montarDias({
      '2026-09-10': {
        total: 1,
        conflito: true,
        pontos: [ponto({ id: 1, name: 'Ana Silva' })],
      },
    })
    render(
      <GradeMes
        dias={dias}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', {
        name: '10 de setembro, 1 visita: Ana Silva, com conflito',
      }),
    ).toBeInTheDocument()
  })

  it('visita sem técnico aparece como "Sem técnico" no aria-label', () => {
    const dias = montarDias({
      '2026-09-12': {
        total: 1,
        pontos: [ponto({ id: false, name: 'Sem técnico', cor: '#6b7280' })],
      },
    })
    render(
      <GradeMes
        dias={dias}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', { name: '12 de setembro, 1 visita: Sem técnico' }),
    ).toBeInTheDocument()
  })

  it('hoje === null não marca nenhuma célula como hoje', () => {
    render(
      <GradeMes
        dias={montarDias()}
        ancora={ANCORA}
        hoje={null}
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const todas = screen.getAllByRole('button')
    expect(todas.every((b) => !b.className.includes('ring-primary'))).toBe(true)
  })

  it('hoje marca só a célula correspondente, distinta da seleção', () => {
    render(
      <GradeMes
        dias={montarDias()}
        ancora={ANCORA}
        hoje="2026-09-20"
        selecionado="2026-09-01"
        onSelecionar={vi.fn()}
      />,
    )
    const marcadas = screen
      .getAllByRole('button')
      .filter((b) => b.className.includes('ring-primary'))
    expect(marcadas).toHaveLength(1)
    expect(marcadas[0]).toHaveAccessibleName(/20 de setembro/)
  })
})
