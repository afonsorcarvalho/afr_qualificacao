import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/odoo/agenda', () => ({
  fetchAgenda: vi.fn(),
  updateVisita: vi.fn(),
  createVisita: vi.fn(),
  listTecnicoOptions: vi.fn(),
  listOsOptions: vi.fn(),
  listInstrumentoOptions: vi.fn(),
}))

import * as agenda from '@/lib/odoo/agenda'
import { runTool, ToolNotFoundError } from './tools'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('runTool', () => {
  it('buscar_agenda repassa a janela e força only_mine=false', async () => {
    vi.mocked(agenda.fetchAgenda).mockResolvedValue({ visitas: [] } as never)
    await runTool('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' })
    expect(agenda.fetchAgenda).toHaveBeenCalledWith('2026-10-12', '2026-10-18', false)
  })

  it('atualizar_visita separa visita_id dos vals', async () => {
    vi.mocked(agenda.updateVisita).mockResolvedValue({ id: 87 } as never)
    await runTool('atualizar_visita', { visita_id: 87, date: '2026-10-16', tecnico_id: 3 })
    expect(agenda.updateVisita).toHaveBeenCalledWith(87, { date: '2026-10-16', tecnico_id: 3 })
  })

  it('atualizar_visita ignora chaves fora da whitelist do PWA', async () => {
    vi.mocked(agenda.updateVisita).mockResolvedValue({ id: 87 } as never)
    await runTool('atualizar_visita', { visita_id: 87, planned_hours: 9, state: 'done', note: 'x' })
    expect(agenda.updateVisita).toHaveBeenCalledWith(87, { note: 'x' })
  })

  it('criar_visita repassa os três argumentos posicionais', async () => {
    vi.mocked(agenda.createVisita).mockResolvedValue({ id: 99 } as never)
    await runTool('criar_visita', { os_id: 4, tecnico_id: 3, date: '2026-10-20' })
    expect(agenda.createVisita).toHaveBeenCalledWith(4, 3, '2026-10-20')
  })

  it('listar_* chamam as funções sem argumento', async () => {
    vi.mocked(agenda.listTecnicoOptions).mockResolvedValue([] as never)
    vi.mocked(agenda.listOsOptions).mockResolvedValue([] as never)
    vi.mocked(agenda.listInstrumentoOptions).mockResolvedValue([] as never)
    await runTool('listar_tecnicos', {})
    await runTool('listar_os', {})
    await runTool('listar_instrumentos', {})
    expect(agenda.listTecnicoOptions).toHaveBeenCalledWith()
    expect(agenda.listOsOptions).toHaveBeenCalledWith()
    expect(agenda.listInstrumentoOptions).toHaveBeenCalledWith()
  })

  it('ferramenta desconhecida lança ToolNotFoundError', async () => {
    await expect(runTool('excluir_visita', { visita_id: 1 })).rejects.toBeInstanceOf(
      ToolNotFoundError,
    )
  })

  it('não existe caminho para deleteVisita', async () => {
    const mod = await import('./tools')
    expect(JSON.stringify(Object.keys(mod))).not.toContain('delete')
  })
})
