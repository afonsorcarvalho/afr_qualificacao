// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VisitaCard } from '../_components/VisitaCard'
import { agruparPorDia, deslocarJanela } from '../agenda/janela'
import type { VisitaAgenda } from '@/lib/odoo/agenda'
import { semRelogioDoAparelho } from '@/tests/relogio'

function visita(over: Partial<VisitaAgenda> = {}): VisitaAgenda {
  return {
    id: 1, date: '2026-09-17', time_start: 8, time_stop: 12, planned_hours: 4,
    os_id: 4, os_name: 'OS26-06-0002', os_state: 'scheduled',
    partner_name: 'Hospital São Lucas', city: 'São Luís',
    equipment_list: ['Autoclave 01'], instrument_list: [], instrument_ids: [],
    tecnico_id: 441, tecnico_name: 'Afonso', is_mine: true,
    state: 'planned', overflow: false,
    editable: true, lock_reason: false,
    conflict: false, conflict_msg: '', note: '',
    ...over,
  }
}

describe('VisitaCard', () => {
  it('editável é botão e chama onSelect', () => {
    const onSelect = vi.fn()
    render(<VisitaCard visita={visita()} onSelect={onSelect} />)
    const alvo = screen.getByRole('button', { name: /OS26-06-0002/ })
    alvo.click()
    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(alvo.className).toContain('min-h-[44px]')
  })

  it('travado mostra o motivo do servidor e não é clicável', () => {
    const onSelect = vi.fn()
    render(
      <VisitaCard
        visita={visita({ editable: false, lock_reason: 'Somente o Gestor edita a agenda.' })}
        onSelect={onSelect}
      />,
    )
    expect(screen.getByText(/Somente o Gestor edita a agenda\./)).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('mostra o instrumento junto do equipamento quando houver', () => {
    render(
      <VisitaCard
        visita={visita({ instrument_list: ['Termômetro TH-02'] })}
        onSelect={vi.fn()}
      />,
    )
    expect(screen.getByText(/Instr\.: Termômetro TH-02/)).toBeInTheDocument()
  })

  it('mostra a mensagem de conflito quando houver', () => {
    render(
      <VisitaCard
        visita={visita({ conflict: true, conflict_msg: 'Deslocamento São Luís → Imperatriz' })}
        onSelect={vi.fn()}
      />,
    )
    expect(screen.getByText(/Deslocamento São Luís/)).toBeInTheDocument()
  })
})

describe('agrupamento e janela', () => {
  it('agrupa por data preservando a ordem do servidor', () => {
    const grupos = agruparPorDia([
      visita({ id: 1, date: '2026-09-17' }),
      visita({ id: 2, date: '2026-09-17' }),
      visita({ id: 3, date: '2026-09-19' }),
    ])
    expect(grupos.map((g) => g.date)).toEqual(['2026-09-17', '2026-09-19'])
    expect(grupos[0].visitas.map((v) => v.id)).toEqual([1, 2])
  })

  it('desloca a janela sem consultar o relógio do aparelho', () => {
    // Qualquer leitura do relógio local aqui é defeito: a janela nasce do
    // `server_today` que veio no payload.
    semRelogioDoAparelho(() => {
      expect(deslocarJanela('2026-09-16', 14)).toEqual('2026-09-30')
      expect(deslocarJanela('2026-09-16', -14)).toEqual('2026-09-02')
    })
  })
})
