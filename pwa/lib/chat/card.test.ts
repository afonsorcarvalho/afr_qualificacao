import { describe, it, expect } from 'vitest'
import { montarCardProposta, formatarDataHumana } from './card'
import type { AgendaPayload } from '@/lib/odoo/agenda'
import type { Proposta } from './machine'

function proposta(over: Partial<Proposta> = {}): Proposta {
  return {
    toolCallId: 'c1', name: 'atualizar_visita', args: {}, resumo: 'r',
    ...over,
  }
}

// Duas visitas de propósito (mesmo padrão de ChatAgenda.test.tsx): com uma
// só, acertar por `find(id)` e uma regressão para `visitas[0]` ficam
// indistinguíveis.
const payload: AgendaPayload = {
  server_today: '2026-09-21',
  date_from: '2026-09-01',
  date_to: '2026-09-30',
  my_employee_id: 441,
  can_manage: true,
  visitas: [
    {
      id: 2126, date: '2026-09-24', time_start: 8, time_stop: 17, planned_hours: 9,
      os_id: 5, os_name: 'OS26-08-0005-2', os_state: 'draft',
      partner_name: 'UITest Hospital', city: '', equipment_list: [],
      instrument_ids: [2, 5], instrument_list: ['Paquímetro', 'Termômetro'],
      tecnico_id: 7, tecnico_name: 'Bruno Neves', is_mine: false, state: 'planned',
      overflow: false, editable: true, lock_reason: false, conflict: false,
      conflict_msg: '', note: '',
    },
    {
      id: 91, date: '2026-10-16', time_start: 9, time_stop: 16, planned_hours: 7,
      os_id: 9, os_name: 'OS26-06-0009', os_state: 'draft',
      partner_name: 'Clínica Oceano', city: 'Imperatriz', equipment_list: [],
      instrument_ids: [], instrument_list: [], tecnico_id: 3,
      tecnico_name: 'Maria Souza', is_mine: false, state: 'planned', overflow: false,
      editable: true, lock_reason: false, conflict: false, conflict_msg: '', note: '',
    },
  ],
}

describe('formatarDataHumana', () => {
  it('formata com dia da semana abreviado sem ponto, dd/mm/aaaa', () => {
    expect(formatarDataHumana('2026-09-24')).toBe('qui, 24/09/2026')
    expect(formatarDataHumana('2026-10-01')).toBe('qui, 01/10/2026')
  })

  it('cobre os sete dias da semana', () => {
    // 2026-09-20 é domingo (âncora conhecida do calendário deste ano fictício).
    expect(formatarDataHumana('2026-09-20')).toBe('dom, 20/09/2026')
    expect(formatarDataHumana('2026-09-21')).toBe('seg, 21/09/2026')
    expect(formatarDataHumana('2026-09-22')).toBe('ter, 22/09/2026')
    expect(formatarDataHumana('2026-09-23')).toBe('qua, 23/09/2026')
    expect(formatarDataHumana('2026-09-24')).toBe('qui, 24/09/2026')
    expect(formatarDataHumana('2026-09-25')).toBe('sex, 25/09/2026')
    expect(formatarDataHumana('2026-09-26')).toBe('sáb, 26/09/2026')
  })
})

describe('montarCardProposta — atualizar_visita', () => {
  it('remarcar (data muda): título pela OS, subtítulo técnico · cliente, linha Data de→para', () => {
    const p = proposta({ args: { visita_id: 2126, date: '2026-10-01' } })
    const card = montarCardProposta(payload, p)
    expect(card.titulo).toBe('Remarcar visita da OS26-08-0005-2')
    expect(card.titulo).not.toMatch(/2126/)
    expect(card.subtitulo).toBe('Bruno Neves · UITest Hospital')
    expect(card.aviso).toBeUndefined()
    expect(card.linhas).toEqual([
      { rotulo: 'Data', de: 'qui, 24/09/2026', para: 'qui, 01/10/2026' },
    ])
  })

  it('subtítulo inclui cidade quando presente', () => {
    const p = proposta({ args: { visita_id: 91, tecnico_id: 3 } })
    const card = montarCardProposta(payload, p)
    expect(card.subtitulo).toBe('Maria Souza · Clínica Oceano · Imperatriz')
  })

  it('subtítulo nunca tem separador solto quando cliente/cidade estão vazios (achado do bug original)', () => {
    const p = proposta({ args: { visita_id: 2126, tecnico_id: 3 } })
    const card = montarCardProposta(payload, p)
    // A visita 2126 tem city vazia — não pode sobrar " · · " nem "·" solto.
    expect(card.subtitulo).toBe('Bruno Neves · UITest Hospital')
    expect(card.subtitulo).not.toMatch(/·\s*·/)
    expect(card.subtitulo).not.toMatch(/·\s*$/)
  })

  it('só horário muda: Data aparece como linha de contexto SEM seta, Horário com seta', () => {
    const p = proposta({ args: { visita_id: 2126, time_start: 9, time_stop: 12 } })
    const card = montarCardProposta(payload, p)
    expect(card.titulo).toBe('Alterar visita da OS26-08-0005-2') // sem "Remarcar": data não mudou
    expect(card.linhas).toEqual([
      { rotulo: 'Data', para: 'qui, 24/09/2026' }, // sem `de`: é contexto, não mudança
      { rotulo: 'Horário', de: '08:00–17:00', para: '09:00–12:00' },
    ])
  })

  it('técnico muda: linha Técnico resolve o nome a partir do payload', () => {
    const p = proposta({ args: { visita_id: 2126, tecnico_id: 3 } })
    const card = montarCardProposta(payload, p)
    expect(card.linhas).toEqual([
      { rotulo: 'Técnico', de: 'Bruno Neves', para: 'Maria Souza' },
    ])
  })

  it('técnico novo sem nenhuma visita no payload: linha cai no fallback de id', () => {
    const p = proposta({ args: { visita_id: 2126, tecnico_id: 999 } })
    const card = montarCardProposta(payload, p)
    expect(card.linhas).toEqual([
      { rotulo: 'Técnico', de: 'Bruno Neves', para: 'técnico 999' },
    ])
  })

  it('instrumentos mudam: ids (não nomes — ver nota de alinhamento no relatório)', () => {
    const p = proposta({ args: { visita_id: 2126, instrument_ids: [2, 9, 11] } })
    const card = montarCardProposta(payload, p)
    expect(card.linhas).toEqual([
      { rotulo: 'Instrumentos', de: '2, 5', para: '2, 9, 11' },
    ])
  })

  it('observação muda: linha avisa a mudança sem vazar o texto', () => {
    const p = proposta({ args: { visita_id: 2126, note: 'texto novo qualquer' } })
    const card = montarCardProposta(payload, p)
    expect(card.linhas).toEqual([{ rotulo: 'Observação', para: 'alterada' }])
  })

  it('várias mudanças juntas: uma linha por campo, na ordem Data/Horário/Técnico/Instrumentos/Observação', () => {
    const p = proposta({
      args: {
        visita_id: 2126, date: '2026-10-01', tecnico_id: 3,
        instrument_ids: [9], note: 'x',
      },
    })
    const card = montarCardProposta(payload, p)
    expect(card.linhas.map((l) => l.rotulo)).toEqual(['Data', 'Técnico', 'Instrumentos', 'Observação'])
    expect(card.titulo).toBe('Remarcar visita da OS26-08-0005-2')
  })

  it('visita fora da janela carregada: aviso explícito com o id, sem fingir que informou', () => {
    const p = proposta({ args: { visita_id: 4242, date: '2026-10-01' } })
    const card = montarCardProposta(payload, p)
    expect(card.aviso).toBe('visita 4242 · fora do período aberto na agenda')
    expect(card.subtitulo).toBeUndefined()
    // Sem alvo carregado não há "de" conhecido — só o que o modelo propôs.
    expect(card.linhas).toEqual([{ rotulo: 'Data', para: 'qui, 01/10/2026' }])
  })

  it('visita_id como string coercionável (quirk do modelo) resolve o mesmo alvo', () => {
    const p = proposta({ args: { visita_id: '2126', date: '2026-10-01' } })
    const card = montarCardProposta(payload, p)
    expect(card.titulo).toBe('Remarcar visita da OS26-08-0005-2')
    expect(card.aviso).toBeUndefined()
  })
})

describe('montarCardProposta — criar_visita', () => {
  it('resolve nome da OS e do técnico a partir do payload, data formatada em pt-BR', () => {
    const p = proposta({
      name: 'criar_visita',
      args: { os_id: 9, tecnico_id: 7, date: '2026-09-24' },
    })
    const card = montarCardProposta(payload, p)
    expect(card.titulo).toBe('Criar visita para OS26-06-0009')
    expect(card.linhas).toEqual([
      { rotulo: 'Data', para: 'qui, 24/09/2026' },
      { rotulo: 'Técnico', para: 'Bruno Neves' },
    ])
  })

  it('OS sem nenhuma visita no payload: fallback pelo id, não trava', () => {
    const p = proposta({
      name: 'criar_visita',
      args: { os_id: 123, tecnico_id: 7, date: '2026-09-24' },
    })
    const card = montarCardProposta(payload, p)
    expect(card.titulo).toBe('Criar visita para OS 123')
  })
})

describe('montarCardProposta — fallback', () => {
  it('ferramenta desconhecida cai no resumo cru da proposta, sem quebrar', () => {
    const p = proposta({ name: 'ferramenta_nova_desconhecida' as never, resumo: 'texto cru do resumir()' })
    const card = montarCardProposta(payload, p)
    expect(card.titulo).toBe('texto cru do resumir()')
    expect(card.linhas).toEqual([])
  })
})
