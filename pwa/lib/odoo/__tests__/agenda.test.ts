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

  it('createVisita manda os/tecnico/data posicionais', async () => {
    callKw.mockResolvedValue({ id: 8 })
    await createVisita(3, 44, '2026-09-20')
    expect(callKw).toHaveBeenCalledWith(MODEL, 'pwa_visita_create', [3, 44, '2026-09-20'])
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
})
