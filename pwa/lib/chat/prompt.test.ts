import { describe, it, expect } from 'vitest'
import { buildSystemPrompt, resumirVisitas, hora } from './prompt'

const ctx = {
  serverToday: '2026-10-14',
  tecnicos: [{ id: 3, name: 'João Silva' }, { id: 7, name: 'Ana Souza' }],
  visitas: [{
    id: 87, date: '2026-10-15', os_name: 'OS26-06-0002',
    tecnico_name: 'João Silva', partner_name: 'Hospital Central',
    time_start: 8, time_stop: 17,
  }],
}

describe('buildSystemPrompt', () => {
  it('injeta server_today e proíbe deduzir a data de hoje', () => {
    const p = buildSystemPrompt(ctx)
    expect(p).toContain('2026-10-14')
    expect(p).toMatch(/nunca.*deduz/i)
  })

  it('manda responder em português do Brasil, explicitamente', () => {
    expect(buildSystemPrompt(ctx)).toContain('português do Brasil')
  })

  it('declara a regra de ids: só os que vieram de ferramenta', () => {
    const p = buildSystemPrompt(ctx)
    expect(p).toMatch(/id/i)
    expect(p).toMatch(/nunca invente|não invente/i)
  })

  it('manda perguntar quando houver ambiguidade, em vez de escolher', () => {
    const p = buildSystemPrompt(ctx)
    expect(p).toMatch(/pergunte/i)
    // Deve cobrir todos os quatro tipos de entidade: visita, técnico, OS, instrumento
    expect(p).toMatch(/visita.*técnico.*os.*instrumento/is)
  })

  it('lista os técnicos com id e nome', () => {
    const p = buildSystemPrompt(ctx)
    expect(p).toContain('João Silva')
    expect(p).toContain('3')
    expect(p).toContain('Ana Souza')
  })

  it('lista as visitas visíveis com id, data e cliente', () => {
    const p = buildSystemPrompt(ctx)
    expect(p).toContain('87')
    expect(p).toContain('2026-10-15')
    expect(p).toContain('Hospital Central')
  })

  it('funciona com janela vazia', () => {
    const p = buildSystemPrompt({ ...ctx, visitas: [] })
    expect(p).toContain('2026-10-14')
    expect(p).toMatch(/nenhuma visita/i)
  })
})

describe('resumirVisitas', () => {
  it('reduz a visita do payload ao que o prompt precisa', () => {
    const r = resumirVisitas([{
      id: 87, date: '2026-10-15', time_start: 8, time_stop: 17,
      planned_hours: 9, os_id: 4, os_name: 'OS26-06-0002', os_state: 'draft',
      partner_name: 'Hospital Central', city: 'São Luís', equipment_list: [],
      instrument_ids: [], instrument_list: [], tecnico_id: 3,
      tecnico_name: 'João Silva', is_mine: false, state: 'draft',
      overflow: false, editable: true, lock_reason: false,
      conflict: false, conflict_msg: '', note: '',
    } as never])
    expect(r).toEqual([{
      id: 87, date: '2026-10-15', os_name: 'OS26-06-0002',
      tecnico_name: 'João Silva', partner_name: 'Hospital Central',
      time_start: 8, time_stop: 17,
    }])
  })
})

describe('hora', () => {
  it('formata horas fracionárias em HH:MM', () => {
    expect(hora(8.5)).toBe('08:30')
  })
})
