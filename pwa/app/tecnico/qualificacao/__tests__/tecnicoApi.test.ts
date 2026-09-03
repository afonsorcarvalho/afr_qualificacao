import { describe, it, expect, vi, beforeEach } from 'vitest'
import odooClient from '@/lib/odoo/client'
import {
  listOsMine,
  getOsDetail,
  startDailyRelatorio,
  finalizeRelatorio,
  getHistoricoSummary,
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

  it('faz uma única chamada a action_finish_daily_relatorio, sem write nem carimbo de tempo do dispositivo', async () => {
    mocked.callKw.mockResolvedValue(true)

    await finalizeRelatorio(9, { descricao: 'Turno OK', signature_b64: 'QUJD' })

    // Não há mais 1º RPC de write — quem carimba data_fim/signature_technician_date
    // é o servidor, dentro de action_finish_daily_relatorio.
    expect(mocked.write).not.toHaveBeenCalled()
    expect(mocked.callKw).toHaveBeenCalledTimes(1)

    const [model, method, args, kwargs] = mocked.callKw.mock.calls[0]
    expect(model).toBe('afr.qualificacao.os.relatorio')
    expect(method).toBe('action_finish_daily_relatorio')
    expect(args).toEqual([[9]])
    expect(kwargs).toMatchObject({
      descricao: 'Turno OK',
      signature_b64: 'QUJD',
    })
    // Relógio do dispositivo não entra: nem data_fim nem
    // signature_technician_date são mandados pelo front.
    expect(kwargs).not.toHaveProperty('data_fim')
    expect(kwargs).not.toHaveProperty('signature_technician_date')
  })

  it('propaga erro do RPC sem engolir', async () => {
    mocked.callKw.mockRejectedValue(new Error('odoo down'))
    await expect(
      finalizeRelatorio(9, { descricao: 'x', signature_b64: 'QUJD' }),
    ).rejects.toThrow('odoo down')
  })
})

describe('getHistoricoSummary', () => {
  beforeEach(() => vi.clearAllMocks())

  it('pede os contadores prontos ao servidor, sem montar janela no cliente', async () => {
    mocked.callKw.mockResolvedValue({
      hoje_coletas: 3,
      hoje_oss: 2,
      hoje_relatorios_fechados: 1,
    })

    const resumo = await getHistoricoSummary(42)

    expect(resumo).toEqual({
      hoje_coletas: 3,
      hoje_oss: 2,
      hoje_relatorios_fechados: 1,
    })
    const [model, method, args] = mocked.callKw.mock.calls[0]
    expect(model).toBe('afr.qualificacao.os.relatorio')
    expect(method).toBe('action_historico_hoje')
    // Método @api.model: sem ids, sem janela, sem uid — o servidor resolve
    // "hoje" no fuso do usuário logado.
    expect(args).toEqual([])
  })

  it('não consulta collect.item nem conta relatórios no cliente', async () => {
    mocked.callKw.mockResolvedValue({
      hoje_coletas: 0,
      hoje_oss: 0,
      hoje_relatorios_fechados: 0,
    })

    await getHistoricoSummary(42)

    // O caminho antigo lia collect.item por captured_at e fazia searchCount
    // com a janela do relógio do aparelho — nada disso pode voltar.
    expect(mocked.searchRead).not.toHaveBeenCalled()
    expect(mocked.searchCount).not.toHaveBeenCalled()
  })
})
