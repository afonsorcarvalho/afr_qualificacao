import { describe, it, expect, vi, beforeEach } from 'vitest'
import odooClient from '@/lib/odoo/client'
import {
  listOsMine,
  getOsDetail,
  startDailyRelatorio,
  finalizeRelatorio,
} from '@/lib/odoo/tecnico'

vi.mock('@/lib/odoo/client', () => ({
  default: {
    callKw: vi.fn(),
    searchRead: vi.fn(),
    searchCount: vi.fn(),
    write: vi.fn(),
  },
}))

const mocked = vi.mocked(odooClient)

describe('listOsMine', () => {
  beforeEach(() => vi.clearAllMocks())

  it('filtra por tecnico_default_user_id (sem travessia em hr.employee)', async () => {
    mocked.searchRead.mockResolvedValue([])
    await listOsMine(42, true)
    const [model, domain, fields] = mocked.searchRead.mock.calls[0]
    expect(model).toBe('afr.qualificacao.os')
    expect(domain).toContainEqual(['tecnico_default_user_id', '=', 42])
    expect(domain).not.toContainEqual(['tecnico_default_id.user_id', '=', 42])
    expect(fields).toContain('tecnico_default_user_id')
  })

  it('sem filterMine não manda cláusula de usuário', async () => {
    mocked.searchRead.mockResolvedValue([])
    await listOsMine(42, false)
    const [, domain] = mocked.searchRead.mock.calls[0]
    expect(JSON.stringify(domain)).not.toContain('tecnico_default_user_id')
  })
})

describe('getOsDetail', () => {
  beforeEach(() => vi.clearAllMocks())

  it('resolve o relatório aberto do dia via action_get_daily_relatorio (servidor decide a janela)', async () => {
    mocked.searchRead.mockImplementation(async (model: string) => {
      if (model === 'afr.qualificacao.os') {
        return [{ id: 10, name: 'OS0010' }] as any
      }
      // collect_item vazio => getOsDetail não chega a buscar equipment/instrument
      if (model === 'afr.qualificacao.collect.item') return [] as any
      return [] as any
    })
    mocked.callKw.mockResolvedValue(55)

    const detail = await getOsDetail(10, 42)

    expect(mocked.callKw).toHaveBeenCalledWith(
      'afr.qualificacao.os',
      'action_get_daily_relatorio',
      [[10]],
    )
    expect(detail.open_relatorio_id).toBe(55)
  })

  it('open_relatorio_id fica null quando o servidor devolve false', async () => {
    mocked.searchRead.mockImplementation(async (model: string) => {
      if (model === 'afr.qualificacao.os') {
        return [{ id: 10, name: 'OS0010' }] as any
      }
      if (model === 'afr.qualificacao.collect.item') return [] as any
      return [] as any
    })
    mocked.callKw.mockResolvedValue(false)

    const detail = await getOsDetail(10, 42)

    expect(detail.open_relatorio_id).toBeNull()
  })
})

describe('startDailyRelatorio', () => {
  beforeEach(() => vi.clearAllMocks())

  it('chama action_start_daily_relatorio sem day_start/day_end — quem decide a janela é o servidor', async () => {
    mocked.callKw.mockResolvedValue(77)
    const relId = await startDailyRelatorio(5)
    expect(relId).toBe(77)
    const call = mocked.callKw.mock.calls[0]
    const [model, method, args] = call
    expect(model).toBe('afr.qualificacao.os')
    expect(method).toBe('action_start_daily_relatorio')
    expect(args).toEqual([[5]])
    // Nenhum 4º argumento (kwargs) com day_start/day_end.
    expect(call.length).toBeLessThanOrEqual(3)
  })
})

describe('finalizeRelatorio', () => {
  beforeEach(() => vi.clearAllMocks())

  it('escreve os campos e só depois chama action_done', async () => {
    mocked.write.mockResolvedValue(true)
    mocked.callKw.mockResolvedValue(true)
    const order: string[] = []
    mocked.write.mockImplementation(async () => {
      order.push('write')
      return true
    })
    mocked.callKw.mockImplementation(async () => {
      order.push('callKw')
      return true
    })

    await finalizeRelatorio(9, { descricao: 'Turno OK', signature_b64: 'QUJD' })

    expect(order).toEqual(['write', 'callKw'])

    const [model, ids, vals] = mocked.write.mock.calls[0]
    expect(model).toBe('afr.qualificacao.os.relatorio')
    expect(ids).toEqual([9])
    expect(vals).toMatchObject({
      descricao: 'Turno OK',
      signature_technician: 'QUJD',
    })
    expect(vals).toHaveProperty('data_fim')
    expect(vals).toHaveProperty('signature_technician_date')
    // state NÃO vai no write — quem transiciona é action_done
    expect(vals).not.toHaveProperty('state')

    expect(mocked.callKw).toHaveBeenCalledWith(
      'afr.qualificacao.os.relatorio',
      'action_done',
      [[9]],
    )
  })

  it('não chama action_done se o write falhar', async () => {
    mocked.write.mockRejectedValue(new Error('odoo down'))
    await expect(
      finalizeRelatorio(9, { descricao: 'x', signature_b64: 'QUJD' }),
    ).rejects.toThrow('odoo down')
    expect(mocked.callKw).not.toHaveBeenCalled()
  })
})
