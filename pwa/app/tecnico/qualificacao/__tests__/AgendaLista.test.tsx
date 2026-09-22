// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VisitaCard } from '../_components/VisitaCard'
import { agruparPorDia, deslocarJanela } from '../agenda/janela'
import { corDoTecnico, corDoInstrumento } from '../agenda/mes'
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
        visita={visita({ instrument_ids: [77] })}
        onSelect={vi.fn()}
        instrumentoNomePorId={new Map([[77, 'Termômetro TH-02']])}
      />,
    )
    const nome = screen.getByText(/Termômetro TH-02/)
    expect(nome).toBeInTheDocument()
    // `nome` é o `<span className="truncate">` — o ícone é irmão dele, dentro
    // do `<span>` pai que agrupa ícone+nome por instrumento.
    const svg = nome.parentElement?.querySelector('svg')
    expect(svg?.style.color).toBe(corDoInstrumento(77, undefined))
  })

  it('sem instrumentoNomePorId (catálogo com falha), o bloco de instrumento some — nunca fabrica Instrumento #<id>', () => {
    // `undefined` (não um Map vazio) é o sinal de catálogo indisponível —
    // ver `instrumentosComFalha` em `page.tsx`. Sem catálogo bom não há nome
    // de verdade, e mostrar `Instrumento #77` seria apresentar um
    // identificador fabricado como se fosse fato (mesma regra que
    // `ModoMes.test.tsx` já cobre pra grade/legenda do Mês).
    render(
      <VisitaCard visita={visita({ instrument_ids: [77] })} onSelect={vi.fn()} />,
    )
    expect(screen.queryByText(/Instrumento #/)).toBeNull()
  })

  it('resolve nome e cor por id, não por posição, quando instrument_ids e o catálogo desalinham', () => {
    // Regressão: `instrument_list` do servidor pode vir menor/desalinhada de
    // `instrument_ids` (filtra instrumento sem nome cadastrado — ver
    // `instrumentosPorDia` em `mes.ts`). O card não usa mais `instrument_list`
    // pra nome/cor — só `instrument_ids`, casado por id contra os Maps do
    // catálogo. Aqui só o id 88 está no catálogo; 77 cai no fallback.
    render(
      <VisitaCard
        visita={visita({ instrument_ids: [77, 88] })}
        onSelect={vi.fn()}
        instrumentoColorPorId={new Map([[88, 3]])}
        instrumentoNomePorId={new Map([[88, 'Balança BL-09']])}
      />,
    )
    const semNome = screen.getByText('Instrumento #77')
    const comNome = screen.getByText('Balança BL-09')
    expect(semNome).toBeInTheDocument()
    expect(comNome).toBeInTheDocument()

    const svgSemNome = semNome.parentElement?.querySelector('svg')
    const svgComNome = comNome.parentElement?.querySelector('svg')
    expect(svgSemNome?.style.color).toBe(corDoInstrumento(77, undefined))
    expect(svgComNome?.style.color).toBe(corDoInstrumento(88, 3))
    // Cores diferentes confirmam que cada ícone pegou a cor do PRÓPRIO id,
    // não a do vizinho por posição no array.
    expect(svgSemNome?.style.color).not.toBe(svgComNome?.style.color)
  })

  it('mostra o ícone do técnico quando a visita não é minha', () => {
    render(
      <VisitaCard
        visita={visita({ is_mine: false, tecnico_name: 'Ariel Neves' })}
        onSelect={vi.fn()}
      />,
    )
    const nome = screen.getByText(/Ariel Neves/)
    expect(nome).toBeInTheDocument()
    const svg = nome.closest('p')?.querySelector('svg')
    expect(svg?.style.color).toBe(corDoTecnico(441, undefined))
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
