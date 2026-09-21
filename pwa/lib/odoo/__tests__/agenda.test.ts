import { describe, it, expect, vi, beforeEach } from 'vitest'

const callKw = vi.fn()
const searchCount = vi.fn()

vi.mock('../client', () => ({
  default: { callKw: (...a: unknown[]) => callKw(...a), searchCount: (...a: unknown[]) => searchCount(...a) },
}))

import {
  fetchAgenda,
  agendaDisponivel,
  updateVisita,
  createVisita,
  deleteVisita,
  listTecnicoOptions,
  listInstrumentoOptions,
  listOsOptions,
  fetchOsOptions,
} from '../agenda'

const MODEL = 'afr.qualificacao.os.visita'

describe('agenda RPC', () => {
  beforeEach(() => {
    callKw.mockReset()
    searchCount.mockReset()
  })

  it('fetchAgenda passa as datas como kwargs nomeados', async () => {
    callKw.mockResolvedValue({ visitas: [] })
    await fetchAgenda('2026-09-16', '2026-09-29', true)
    expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_agenda_fetch', [], {
      date_from: '2026-09-16',
      date_to: '2026-09-29',
      only_mine: true,
    })
  })

  it('fetchAgenda sem datas deixa o servidor decidir a janela', async () => {
    callKw.mockResolvedValue({ visitas: [] })
    await fetchAgenda(null, null, false)
    expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_agenda_fetch', [], {
      date_from: null,
      date_to: null,
      only_mine: false,
    })
  })

  it('agendaDisponivel é falso quando o modelo não existe', async () => {
    searchCount.mockResolvedValue(0)
    expect(await agendaDisponivel()).toBe(false)
    expect(searchCount).toHaveBeenCalledWith('ir.model', [['model', '=', MODEL]])
  })

  it('agendaDisponivel é verdadeiro quando o modelo existe', async () => {
    searchCount.mockResolvedValue(1)
    expect(await agendaDisponivel()).toBe(true)
  })

  it('updateVisita manda id e vals posicionais', async () => {
    callKw.mockResolvedValue({ id: 7 })
    await updateVisita(7, { note: 'x' })
    expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_visita_update', [7, { note: 'x' }])
  })

  it('createVisita manda os/tecnico/data posicionais, sem equipamento/instrumento', async () => {
    callKw.mockResolvedValue({ id: 8 })
    await createVisita(3, 44, '2026-09-20')
    expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_visita_create', [3, 44, '2026-09-20'], {
      equipment_ids: undefined,
      instrument_ids: undefined,
    })
  })

  it('createVisita manda equipment_ids/instrument_ids como kwargs quando informados', async () => {
    callKw.mockResolvedValue({ id: 8 })
    await createVisita(3, 44, '2026-09-20', [10, 11], [20])
    expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_visita_create', [3, 44, '2026-09-20'], {
      equipment_ids: [10, 11],
      instrument_ids: [20],
    })
  })

  it('deleteVisita manda o id posicional', async () => {
    callKw.mockResolvedValue(true)
    await deleteVisita(9)
    expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_visita_delete', [9])
  })

  it('listTecnicoOptions chama pwa_tecnico_options, não board_technician_options', async () => {
    callKw.mockResolvedValue([{ id: 441, name: 'Afonso' }])
    await listTecnicoOptions()
    expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_tecnico_options', [])
  })

  it('listInstrumentoOptions chama o método com sudo do backend', async () => {
    callKw.mockResolvedValue([])
    await listInstrumentoOptions()
    expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_instrumento_options', [])
  })

  it('updateVisita aceita instrument_ids como lista de ids', async () => {
    callKw.mockResolvedValue({ id: 7 })
    await updateVisita(7, { instrument_ids: [1, 2] })
    expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_visita_update', [
      7, { instrument_ids: [1, 2] },
    ])
  })

  describe('fetchOsOptions / listOsOptions — pwa_os_options substitui board_os_options', () => {
    it('fetchOsOptions chama pwa_os_options e devolve o payload rico', async () => {
      const payload = [{
        id: 9, name: 'QOS00009', partner_name: 'Cliente X', city: 'São Luís',
        state: 'draft', equipment_list: [{ id: 1, name: 'Autoclave' }],
        instrument_suggestions: [],
      }]
      callKw.mockResolvedValue(payload)
      const r = await fetchOsOptions()
      expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_os_options', [])
      expect(r).toEqual(payload)
    })

    it('listOsOptions reconstrói "OS - cliente" a partir do payload rico', async () => {
      callKw.mockResolvedValue([
        { id: 9, name: 'QOS00009', partner_name: 'Cliente X', city: '', state: 'draft', equipment_list: [], instrument_suggestions: [] },
      ])
      const r = await listOsOptions()
      expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_os_options', [])
      expect(r).toEqual([{ id: 9, name: 'QOS00009 - Cliente X' }])
    })

    it('listOsOptions sem cliente devolve só o nome da OS (sem separador solto)', async () => {
      callKw.mockResolvedValue([
        { id: 9, name: 'QOS00009', partner_name: '', city: '', state: 'draft', equipment_list: [], instrument_suggestions: [] },
      ])
      const r = await listOsOptions()
      expect(r).toEqual([{ id: 9, name: 'QOS00009' }])
    })
  })
})
