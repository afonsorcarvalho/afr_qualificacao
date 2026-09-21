import { describe, it, expect } from 'vitest'
import { buildSystemPrompt, resumirVisitas } from './prompt'

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
    // Extrai a cláusula AMBIGUIDADE para evitar false positives da REGRA DE IDENTIFICADORES
    const ambiguidadeMatch = p.match(/AMBIGUIDADE:.*?\.\n/)
    expect(ambiguidadeMatch).toBeTruthy()
    const ambiguidadeClause = ambiguidadeMatch![0]

    expect(ambiguidadeClause).toMatch(/pergunte/i)
    // Deve cobrir todos os quatro tipos de entidade dentro da cláusula AMBIGUIDADE
    expect(ambiguidadeClause).toMatch(/visita[\s\S]*técnico[\s\S]*os[\s\S]*instrumento/i)
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

  it('formata horas fracionárias em HH:MM no prompt (leitura do gestor)', () => {
    const ctxComFracionaria = {
      serverToday: '2026-10-14',
      tecnicos: [{ id: 1, name: 'Ana' }],
      visitas: [{
        id: 99, date: '2026-10-16', os_name: 'OS26-06-0099',
        tecnico_name: 'Ana', partner_name: 'Clínica', time_start: 8.5, time_stop: 16.75,
      }],
    }
    const p = buildSystemPrompt(ctxComFracionaria)
    expect(p).toContain('08:30')
    expect(p).toContain('16:45')
  })
})

describe('buildSystemPrompt — identificação na prosa (OS + data, nunca id)', () => {
  // Extrai só a cláusula nova, mesma técnica do teste de AMBIGUIDADE acima —
  // sem isso, um assert genérico por "visita"/"técnico"/"OS" passaria por
  // causa da cláusula de AMBIGUIDADE, que já usa essas palavras, sem que a
  // regra nova precisasse existir.
  function clausulaIdentificacao(p: string): string {
    const m = p.match(/IDENTIFICAÇÃO NA PROSA:.*?\.\n/)
    expect(m).toBeTruthy()
    return m![0]
  }

  it('manda identificar a visita por OS e data, não por id, ao falar com o gestor', () => {
    const clausula = clausulaIdentificacao(buildSystemPrompt(ctx))
    expect(clausula).toMatch(/OS/)
    expect(clausula).toMatch(/data/i)
    expect(clausula).toMatch(/nunca.*id interno/i)
  })

  it('manda desambiguar com técnico ou horário quando a OS repete no mesmo dia', () => {
    const clausula = clausulaIdentificacao(buildSystemPrompt(ctx))
    expect(clausula).toMatch(/mesma OS.*mesmo dia/i)
    expect(clausula).toMatch(/técnico|horário/i)
  })

  it('aponta o campo "rotulo" de buscar_agenda como o texto pronto a usar', () => {
    const clausula = clausulaIdentificacao(buildSystemPrompt(ctx))
    expect(clausula).toContain('rotulo')
    expect(clausula).toMatch(/buscar_agenda/)
  })

  it('reafirma que o id continua obrigatório nos argumentos de ferramenta', () => {
    const clausula = clausulaIdentificacao(buildSystemPrompt(ctx))
    expect(clausula).toMatch(/visita_id/)
    expect(clausula).toMatch(/tecnico_id/)
    expect(clausula).toMatch(/os_id/)
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
