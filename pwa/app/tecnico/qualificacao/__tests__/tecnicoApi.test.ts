import { describe, it, expect, vi, beforeEach } from 'vitest'
import odooClient from '@/lib/odoo/client'
import {
  dayWindowOdoo,
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

describe('dayWindowOdoo', () => {
  it('devolve janela de 24h em formato datetime do Odoo', () => {
    const { from, to } = dayWindowOdoo(new Date('2026-07-02T15:30:00-03:00'))
    expect(from).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
    expect(to).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
    // datetime do Odoo usa espaço; ISO exige 'T' — sem o replace, o parse
    // depende do fallback leniente do V8 e a asserção pode flakear.
    const asIso = (s: string) => new Date(`${s.replace(' ', 'T')}Z`).getTime()
    expect(asIso(to) - asIso(from)).toBe(86400000)
  })

  it('fixa `from` na meia-noite local do dia de referência, não em qualquer horário', () => {
    // Referência fica no meio da tarde (15:30) de propósito: se `dayWindowOdoo`
    // não fizer `setHours(0,0,0,0)`, `from` sairia com 15:30 em vez de 00:00 e
    // este teste pega isso. A expectativa é construída a partir de
    // `new Date(ano, mês, dia, 0, 0, 0)` (local, mês 0-indexado) e passa pela
    // MESMA conversão pra string que a função usa — assim a asserção não
    // depende do fuso horário de quem roda o teste.
    const ref = new Date(2026, 6, 2, 15, 30, 0) // 2026-07-02 15:30 local
    const { from } = dayWindowOdoo(ref)
    const localMidnight = new Date(2026, 6, 2, 0, 0, 0) // 2026-07-02 00:00 local
    const expectedFrom = localMidnight.toISOString().slice(0, 19).replace('T', ' ')
    expect(from).toBe(expectedFrom)
  })
})

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

  it('busca o relatório aberto do dia escopado por create_uid (não por tecnico_ids)', async () => {
    mocked.searchRead.mockImplementation(async (model: string) => {
      if (model === 'afr.qualificacao.os') {
        return [{ id: 10, name: 'OS0010' }] as any
      }
      // collect_item vazio => getOsDetail não chega a buscar equipment/instrument
      if (model === 'afr.qualificacao.collect.item') return [] as any
      if (model === 'afr.qualificacao.os.relatorio') return [] as any
      return [] as any
    })

    await getOsDetail(10, 42)

    const relCall = mocked.searchRead.mock.calls.find(
      ([model]) => model === 'afr.qualificacao.os.relatorio',
    )
    expect(relCall).toBeDefined()
    const [, domain] = relCall!
    // Escopo por técnico: dois técnicos na mesma OS/dia não podem "roubar"
    // o relatório um do outro por engano — ver comentário em getOsDetail.
    expect(domain).toContainEqual(['create_uid', '=', 42])
    // Nunca travessia em hr.employee (mesmo motivo do tecnico_default_user_id).
    expect(JSON.stringify(domain)).not.toContain('tecnico_ids')
  })
})

describe('startDailyRelatorio', () => {
  beforeEach(() => vi.clearAllMocks())

  it('passa day_start/day_end como kwargs pro método da OS', async () => {
    mocked.callKw.mockResolvedValue(77)
    const relId = await startDailyRelatorio(5)
    expect(relId).toBe(77)
    const [model, method, args, kwargs] = mocked.callKw.mock.calls[0]
    expect(model).toBe('afr.qualificacao.os')
    expect(method).toBe('action_start_daily_relatorio')
    expect(args).toEqual([[5]])
    expect(kwargs).toMatchObject({
      day_start: expect.stringMatching(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/),
      day_end: expect.stringMatching(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/),
    })
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
