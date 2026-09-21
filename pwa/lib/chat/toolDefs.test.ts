import { describe, it, expect } from 'vitest'
import { TOOL_DEFS, TOOL_KINDS, WRITE_TOOLS, isWriteTool } from './toolDefs'

const nomes = TOOL_DEFS.map((t) => t.function.name)

describe('TOOL_DEFS', () => {
  it('expõe exatamente as seis ferramentas previstas', () => {
    expect(nomes.sort()).toEqual([
      'atualizar_visita',
      'buscar_agenda',
      'criar_visita',
      'listar_instrumentos',
      'listar_os',
      'listar_tecnicos',
    ])
  })

  it('NÃO expõe excluir_visita', () => {
    expect(nomes).not.toContain('excluir_visita')
    expect(JSON.stringify(TOOL_DEFS)).not.toContain('delete')
  })

  it('marca leitura e escrita corretamente', () => {
    expect(TOOL_KINDS.buscar_agenda).toBe('read')
    expect(TOOL_KINDS.listar_tecnicos).toBe('read')
    expect(TOOL_KINDS.listar_instrumentos).toBe('read')
    expect(TOOL_KINDS.listar_os).toBe('read')
    expect(TOOL_KINDS.criar_visita).toBe('write')
    expect(TOOL_KINDS.atualizar_visita).toBe('write')
    expect([...WRITE_TOOLS].sort()).toEqual(['atualizar_visita', 'criar_visita'])
    expect(isWriteTool('criar_visita')).toBe(true)
    expect(isWriteTool('buscar_agenda')).toBe(false)
    expect(isWriteTool('inexistente')).toBe(false)
  })

  it('toda definição tem type function, descrição em pt-BR e parameters objeto', () => {
    for (const def of TOOL_DEFS) {
      expect(def.type).toBe('function')
      expect(def.function.description.length).toBeGreaterThan(20)
      expect(def.function.parameters.type).toBe('object')
    }
  })

  it('atualizar_visita aceita só os campos graváveis do PWA', () => {
    const def = TOOL_DEFS.find((t) => t.function.name === 'atualizar_visita')!
    const props = (def.function.parameters as Record<string, any>).properties
    expect(Object.keys(props).sort()).toEqual([
      'date', 'instrument_ids', 'note', 'tecnico_id', 'time_start', 'time_stop', 'visita_id',
    ])
    expect((def.function.parameters as Record<string, any>).required).toEqual(['visita_id'])
  })

  it('campos de data documentam o formato ISO absoluto', () => {
    const buscar = TOOL_DEFS.find((t) => t.function.name === 'buscar_agenda')!
    const p = (buscar.function.parameters as Record<string, any>).properties
    expect(p.date_from.description).toContain('AAAA-MM-DD')
    expect(p.date_to.description).toContain('AAAA-MM-DD')
  })

  it('criar_visita exige equipment_ids e instrument_ids no schema', () => {
    const def = TOOL_DEFS.find((t) => t.function.name === 'criar_visita')!
    const params = def.function.parameters as Record<string, any>
    expect(params.required).toEqual(
      expect.arrayContaining(['os_id', 'tecnico_id', 'date', 'equipment_ids', 'instrument_ids']),
    )
    expect(params.properties.equipment_ids.type).toBe('array')
    expect(params.properties.instrument_ids.type).toBe('array')
  })
})
