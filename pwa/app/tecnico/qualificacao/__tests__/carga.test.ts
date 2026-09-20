import { describe, it, expect } from 'vitest'
import {
  cargaPorDia, cargaPorTecnico, usoPorInstrumento, diasDaSemana,
  rosterTecnicos, picoDaSemana, horasDaVisita,
} from '../agenda/carga'
import type { VisitaAgenda } from '@/lib/odoo/agenda'
import { semRelogioDoAparelho } from '@/tests/relogio'

function v(over: Partial<VisitaAgenda> = {}): VisitaAgenda {
  return {
    id: 1, date: '2026-09-17', time_start: 8, time_stop: 12, planned_hours: 4,
    os_id: 4, os_name: 'OS26-02', os_state: 'scheduled',
    partner_name: 'Hospital', city: 'São Luís',
    equipment_list: [], instrument_list: [], instrument_ids: [],
    tecnico_id: 441, tecnico_name: 'Afonso', is_mine: true,
    state: 'planned', overflow: false, editable: true, lock_reason: false,
    conflict: false, conflict_msg: '', note: '',
    ...over,
  }
}

describe('diasDaSemana', () => {
  it('devolve 7 dias ISO a partir do início, sem ler o relógio do aparelho', () => {
    semRelogioDoAparelho(() => {
      expect(diasDaSemana('2026-09-14')).toEqual([
        '2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17',
        '2026-09-18', '2026-09-19', '2026-09-20',
      ])
    })
  })

  it('atravessa virada de ano sem tropeçar no transbordo de mês/dia', () => {
    expect(diasDaSemana('2026-12-29')).toEqual([
      '2026-12-29', '2026-12-30', '2026-12-31', '2027-01-01',
      '2027-01-02', '2027-01-03', '2027-01-04',
    ])
  })
})

describe('horasDaVisita', () => {
  it('rende a duração da janela mesmo com planned_hours zerado — é o bug do usuário: card 08:00–12:00 com o painel acusando "livre"', () => {
    expect(horasDaVisita(v({ time_start: 8, time_stop: 12, planned_hours: 0 }))).toBe(4)
  })

  it('ignora planned_hours quando diverge da janela — a janela manda', () => {
    expect(horasDaVisita(v({ time_start: 8, time_stop: 12, planned_hours: 6 }))).toBe(4)
  })

  it('virada de dia com overflow e time_stop > 24 (onchange clássico time_start + planned_hours, sem cap): conta o valor cheio, sem truncar — a continuação ainda não existe como visita separada', () => {
    expect(horasDaVisita(v({ time_start: 20, time_stop: 26, overflow: true }))).toBe(6)
  })

  it('virada de dia com overflow e time_stop <= time_start (par digitado "ao contrário", sem como saber quanto passa da meia-noite): conta o que cabe até o fim do dia (24 - time_start), nunca negativo', () => {
    // time_stop (2h, já do dia seguinte) é menor que time_start (22h). O
    // backend marca `overflow_next_day = true` até a divisão acontecer.
    expect(horasDaVisita(v({ time_start: 22, time_stop: 2, overflow: true }))).toBe(2)
  })

  it('janela não-crescente sem overflow sinalizado: dado inconsistente vira 0h, nunca negativo', () => {
    expect(horasDaVisita(v({ time_start: 22, time_stop: 2, overflow: false }))).toBe(0)
  })

  it('janela igual (time_stop === time_start) sem overflow: 0h', () => {
    expect(horasDaVisita(v({ time_start: 8, time_stop: 8, overflow: false }))).toBe(0)
  })
})

describe('cargaPorDia', () => {
  const dias = ['2026-09-17', '2026-09-18', '2026-09-19']

  it('soma as horas previstas de cada dia, pela JANELA — não pelo campo planned_hours (divergente de propósito, para provar isso)', () => {
    const r = cargaPorDia(
      [v({ id: 1, date: '2026-09-17', time_start: 8, time_stop: 12, planned_hours: 0 }),
       v({ id: 2, date: '2026-09-17', time_start: 13, time_stop: 15.5, planned_hours: 0 }),
       v({ id: 3, date: '2026-09-19', time_start: 8, time_stop: 16, planned_hours: 0 })],
      dias,
    )
    expect(r.map((d) => d.horas)).toEqual([6.5, 0, 8])
  })

  it('devolve todos os dias da janela, inclusive os vazios', () => {
    expect(cargaPorDia([], dias).map((d) => d.date)).toEqual(dias)
  })

  it('marca o dia que tem alguma visita em conflito', () => {
    const r = cargaPorDia(
      [v({ id: 1, date: '2026-09-18', conflict: true })], dias,
    )
    expect(r.map((d) => d.conflito)).toEqual([false, true, false])
  })
})

describe('cargaPorTecnico', () => {
  const tecnicos = [
    { id: 441, name: 'Afonso' },
    { id: 9, name: 'Bruno' },
  ]

  it('inclui técnico do roster sem visita nenhuma, com zero hora', () => {
    const r = cargaPorTecnico(
      [v({ tecnico_id: 441, date: '2026-09-17', planned_hours: 4 })],
      '2026-09-17', tecnicos,
    )
    expect(r).toEqual([
      { id: 441, name: 'Afonso', horas: 4 },
      { id: 9, name: 'Bruno', horas: 0 },
    ])
  })

  it('ignora visita de outro dia', () => {
    const r = cargaPorTecnico(
      [v({ tecnico_id: 441, date: '2026-09-18', planned_hours: 4 })],
      '2026-09-17', tecnicos,
    )
    expect(r[0].horas).toBe(0)
  })

  it('soma pela janela, não pelo campo — planned_hours divergente (6) não muda o resultado da janela 08:00–12:00 (4h)', () => {
    const r = cargaPorTecnico(
      [v({ tecnico_id: 441, date: '2026-09-17', time_start: 8, time_stop: 12, planned_hours: 6 })],
      '2026-09-17', tecnicos,
    )
    expect(r[0].horas).toBe(4)
  })
})

describe('rosterTecnicos', () => {
  const oficiais = [
    { id: 441, name: 'Afonso' },
    { id: 9, name: 'Bruno' },
  ]

  it('inclui técnico oficial sem visita nenhuma', () => {
    const r = rosterTecnicos(oficiais, [])
    expect(r.map((t) => t.id).sort((a, b) => a - b)).toEqual([9, 441])
  })

  it('acrescenta técnico da visita que NÃO está no roster oficial, com o nome da visita', () => {
    const r = rosterTecnicos(
      oficiais,
      [v({ tecnico_id: 55, tecnico_name: 'Carlos (sem flag)', planned_hours: 4 })],
    )
    expect(r.map((t) => t.name)).toContain('Carlos (sem flag)')
    const carlos = r.find((t) => t.id === 55)
    expect(carlos).toEqual({ id: 55, name: 'Carlos (sem flag)' })
  })

  it('não duplica quando o técnico da visita já está no roster oficial', () => {
    const r = rosterTecnicos(
      oficiais,
      [v({ tecnico_id: 441, tecnico_name: 'Afonso' })],
    )
    expect(r.filter((t) => t.id === 441)).toHaveLength(1)
  })

  it('ordena por nome, não por id ou ordem de chegada', () => {
    const r = rosterTecnicos(
      [{ id: 2, name: 'Zeca' }],
      [v({ tecnico_id: 1, tecnico_name: 'Ana' })],
    )
    expect(r.map((t) => t.name)).toEqual(['Ana', 'Zeca'])
  })

  it('ignora visita sem técnico (tecnico_id false)', () => {
    const r = rosterTecnicos(oficiais, [v({ tecnico_id: false })])
    expect(r).toHaveLength(2)
  })

  // Propagação da cor configurada (Task 2, plano cor-por-recurso): a união
  // preserva o `color` de quem veio do roster oficial — é o campo que
  // `tecnicosPorDia`/a legenda em `page.tsx` usam para vencer a cor
  // automática.
  it('preserva o color do roster oficial na união', () => {
    const r = rosterTecnicos(
      [{ id: 441, name: 'Afonso', color: 6 }, { id: 9, name: 'Bruno' }],
      [],
    )
    expect(r.find((t) => t.id === 441)).toEqual({ id: 441, name: 'Afonso', color: 6 })
    expect(r.find((t) => t.id === 9)).toEqual({ id: 9, name: 'Bruno' })
  })

  it('técnico vindo só das visitas (sem índice) não ganha color nenhum — cai na cor automática', () => {
    const r = rosterTecnicos(
      oficiais,
      [v({ tecnico_id: 55, tecnico_name: 'Carlos (sem flag)' })],
    )
    const carlos = r.find((t) => t.id === 55)
    expect(carlos).toEqual({ id: 55, name: 'Carlos (sem flag)' })
    expect(carlos?.color).toBeUndefined()
  })
})

describe('picoDaSemana', () => {
  const tecnicos = [{ id: 441, name: 'Afonso' }]
  const dias = ['2026-09-17', '2026-09-18']

  it('é o maior técnico-dia de TODOS os dias da semana, não só de um', () => {
    const r = picoDaSemana(
      // A carga vem da janela, não de `planned_hours` (Task fix): o dia 18
      // precisa de uma janela de 12h de verdade (08:00–20:00) para valer
      // como pico — antes do fix, `planned_hours: 12` bastava sozinho.
      [v({ id: 1, date: '2026-09-17', tecnico_id: 441, time_start: 8, time_stop: 12, planned_hours: 4 }),
       v({ id: 2, date: '2026-09-18', tecnico_id: 441, time_start: 8, time_stop: 20, planned_hours: 12 })],
      dias, tecnicos,
    )
    expect(r).toBe(12)
  })

  it('sem visita nenhuma, o piso é 1 (nunca 0, para não dividir por zero)', () => {
    expect(picoDaSemana([], dias, tecnicos)).toBe(1)
  })
})

describe('usoPorInstrumento', () => {
  const instrumentos = [
    { id: 1, name: 'Q001', validade: '2027-01-01' as string | false },
    { id: 2, name: 'Q002', validade: '2026-01-01' as string | false },
    { id: 3, name: 'Q003', validade: false as string | false },
  ]

  it('lista onde cada instrumento está, com a faixa de horário', () => {
    const r = usoPorInstrumento(
      [v({ id: 7, date: '2026-09-17', instrument_ids: [1],
           time_start: 8, time_stop: 12, os_name: 'OS26-02',
           tecnico_name: 'Afonso' })],
      '2026-09-17', instrumentos,
    )
    expect(r[0].usos).toEqual([
      { visitaId: 7, osName: 'OS26-02', tecnicoName: 'Afonso', faixa: '08:00–12:00' },
    ])
    expect(r[1].usos).toEqual([])
  })

  it('um instrumento em duas visitas no mesmo dia aparece com os dois usos', () => {
    const r = usoPorInstrumento(
      [v({ id: 7, date: '2026-09-17', instrument_ids: [1], time_start: 8, time_stop: 12 }),
       v({ id: 8, date: '2026-09-17', instrument_ids: [1], time_start: 13, time_stop: 17 })],
      '2026-09-17', instrumentos,
    )
    expect(r[0].usos.map((u) => u.visitaId)).toEqual([7, 8])
  })

  it('marca vencido quando a validade não alcança o dia, e não marca quando alcança', () => {
    const r = usoPorInstrumento([], '2026-09-17', instrumentos)
    expect(r.map((i) => i.vencido)).toEqual([false, true, true])
  })

  it('validade exatamente igual ao dia ainda vale', () => {
    const r = usoPorInstrumento(
      [], '2026-09-17', [{ id: 1, name: 'Q001', validade: '2026-09-17' }],
    )
    expect(r[0].vencido).toBe(false)
  })

  it('ordena os usos por horário, não pela ordem de chegada da API', () => {
    const r = usoPorInstrumento(
      // A visita das 13h chega primeiro no array — se a função apenas
      // repassar a ordem de entrada, o teste falha.
      [v({ id: 8, date: '2026-09-17', instrument_ids: [1], time_start: 13, time_stop: 17 }),
       v({ id: 7, date: '2026-09-17', instrument_ids: [1], time_start: 8, time_stop: 12 })],
      '2026-09-17', instrumentos,
    )
    expect(r[0].usos.map((u) => u.visitaId)).toEqual([7, 8])
  })
})
