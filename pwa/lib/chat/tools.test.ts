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
import { runTool, ToolNotFoundError, ToolArgumentError } from './tools'
import { coletarIds } from './machine'

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

  // Fix round 1: type coercion and validation
  it('atualizar_visita coerce strings para números em time_start e tecnico_id', async () => {
    vi.mocked(agenda.updateVisita).mockResolvedValue({ id: 87 } as never)
    await runTool('atualizar_visita', { visita_id: 87, time_start: '8.5', tecnico_id: '3' })
    expect(agenda.updateVisita).toHaveBeenCalledWith(87, { time_start: 8.5, tecnico_id: 3 })
  })

  it('criar_visita com os_id ausente lança ToolArgumentError e NÃO chama createVisita', async () => {
    await expect(
      runTool('criar_visita', { tecnico_id: 3, date: '2026-10-20' }),
    ).rejects.toBeInstanceOf(ToolArgumentError)
    expect(agenda.createVisita).not.toHaveBeenCalled()
  })

  it('atualizar_visita com visita_id inválido lança ToolArgumentError e NÃO chama updateVisita', async () => {
    await expect(
      runTool('atualizar_visita', { visita_id: 'abc', date: '2026-10-16' }),
    ).rejects.toBeInstanceOf(ToolArgumentError)
    expect(agenda.updateVisita).not.toHaveBeenCalled()
  })

  it('buscar_agenda sem date_from lança ToolArgumentError e NÃO chama fetchAgenda', async () => {
    await expect(runTool('buscar_agenda', { date_to: '2026-10-18' })).rejects.toBeInstanceOf(
      ToolArgumentError,
    )
    expect(agenda.fetchAgenda).not.toHaveBeenCalled()
  })

  it('atualizar_visita com apenas chaves não-whitelisted lança ToolArgumentError', async () => {
    await expect(
      runTool('atualizar_visita', { visita_id: 87, planned_hours: 9, state: 'done' }),
    ).rejects.toBeInstanceOf(ToolArgumentError)
    expect(agenda.updateVisita).not.toHaveBeenCalled()
  })

  it('atualizar_visita com instrument_ids como string lança ToolArgumentError', async () => {
    await expect(
      runTool('atualizar_visita', { visita_id: 87, instrument_ids: '123' }),
    ).rejects.toBeInstanceOf(ToolArgumentError)
    expect(agenda.updateVisita).not.toHaveBeenCalled()
  })

  it('atualizar_visita coerce instrument_ids array de strings para números', async () => {
    vi.mocked(agenda.updateVisita).mockResolvedValue({ id: 87 } as never)
    await runTool('atualizar_visita', { visita_id: 87, instrument_ids: ['1', '2', '3'] })
    expect(agenda.updateVisita).toHaveBeenCalledWith(87, { instrument_ids: [1, 2, 3] })
  })

  // Fix 4: a mensagem de erro de time_start/time_stop dizia "inteiro",
  // mas o campo é float (8.5 = 08:30). Um modelo lendo "inteiro" manda 8
  // em vez de 8.5 na próxima tentativa, e a visita grava num horário
  // errado sem barulho nenhum — o código já aceitava float certo, só o
  // texto empurrava o modelo pro valor errado.
  it('atualizar_visita com time_start inválido orienta usar fração, não "inteiro"', async () => {
    await expect(
      runTool('atualizar_visita', { visita_id: 87, time_start: 'meio-dia' }),
    ).rejects.toMatchObject({ message: expect.stringMatching(/fração/i) })
    await expect(
      runTool('atualizar_visita', { visita_id: 87, time_start: 'meio-dia' }),
    ).rejects.toMatchObject({ message: expect.not.stringMatching(/inteiro/i) })
  })

  it('atualizar_visita com time_stop inválido orienta usar fração, não "inteiro"', async () => {
    await expect(
      runTool('atualizar_visita', { visita_id: 87, time_stop: 'meia-noite' }),
    ).rejects.toMatchObject({ message: expect.stringMatching(/fração/i) })
  })

  it('atualizar_visita com tecnico_id inválido continua exigindo "inteiro" (não é campo de hora)', async () => {
    await expect(
      runTool('atualizar_visita', { visita_id: 87, tecnico_id: 'joão' }),
    ).rejects.toMatchObject({ message: expect.stringMatching(/inteiro/i) })
  })

  // Caso real que motivou a mudança: o modelo respondeu ao gestor citando id
  // interno ("cancelar a visita id 2140") porque não tinha outro jeito de
  // diferenciar duas visitas da MESMA OS no mesmo dia (Bruno tinha as duas).
  // buscar_agenda agora devolve um rótulo pronto — OS + data + técnico +
  // horário — que resolve exatamente esse caso sem o modelo precisar montar
  // a frase sozinho.
  describe('buscar_agenda — rótulo pronto pra prosa (OS + data, desambigua por horário/técnico)', () => {
    const visitaBase = {
      os_id: 4, os_state: 'confirmed', city: 'São Luís',
      equipment_list: [], instrument_list: [], instrument_ids: [],
      tecnico_id: 9, is_mine: false, state: 'planned', overflow: false,
      editable: true, lock_reason: false, conflict: true,
      conflict_msg: 'Bruno Neves já tem visita nesse horário', note: '',
    }

    it('cada visita ganha um campo "rotulo" com OS, data e horário', async () => {
      vi.mocked(agenda.fetchAgenda).mockResolvedValue({
        visitas: [{
          ...visitaBase, id: 2138, date: '2026-09-23', time_start: 8, time_stop: 12,
          os_name: 'OS26-08-0005', partner_name: 'Hospital Central', tecnico_name: 'Bruno Neves',
        }],
      } as never)

      const r = (await runTool('buscar_agenda', {
        date_from: '2026-09-21', date_to: '2026-09-25',
      })) as { visitas: Array<{ rotulo: string }> }

      expect(r.visitas[0].rotulo).toContain('OS26-08-0005')
      expect(r.visitas[0].rotulo).toContain('23/09/2026')
      expect(r.visitas[0].rotulo).toContain('Bruno Neves')
      expect(r.visitas[0].rotulo).toContain('08:00')
      expect(r.visitas[0].rotulo).toContain('12:00')
      // Campos que a máquina/ferramentas dependem continuam intactos.
      expect(r.visitas[0]).toMatchObject({ id: 2138, os_name: 'OS26-08-0005', date: '2026-09-23' })
    })

    it('visita sem OS vinculada (os_name vazio) não produz rótulo com separador solto no início', async () => {
      // `os_id` é tipado `number | false` em `VisitaAgenda` — uma visita
      // sem OS chega com `os_name` vazio. Sem o guard condicional (mesmo
      // padrão já usado para `tecnico_name`), o rótulo virava
      // `" · qua, 23/09/2026 · 08:00–12:00"`: separador solto no começo,
      // exatamente o defeito que `juntarSubtitulo` (card.ts) já evita do
      // outro lado da tela.
      vi.mocked(agenda.fetchAgenda).mockResolvedValue({
        visitas: [{
          ...visitaBase, id: 2139, date: '2026-09-23', time_start: 8, time_stop: 12,
          os_id: false, os_name: '', partner_name: 'Hospital Central', tecnico_name: 'Bruno Neves',
        }],
      } as never)

      const r = (await runTool('buscar_agenda', {
        date_from: '2026-09-21', date_to: '2026-09-25',
      })) as { visitas: Array<{ rotulo: string }> }

      const rotulo = r.visitas[0].rotulo
      expect(rotulo).not.toMatch(/^\s*·/)
      expect(rotulo.startsWith(' ·')).toBe(false)
      expect(rotulo).toContain('sem OS')
    })

    it('desambigua duas visitas da MESMA OS no MESMO dia (caso real: Bruno com id 2138 e 2140)', async () => {
      vi.mocked(agenda.fetchAgenda).mockResolvedValue({
        visitas: [
          {
            ...visitaBase, id: 2138, date: '2026-09-23', time_start: 8, time_stop: 12,
            os_name: 'OS26-08-0005', partner_name: 'Hospital Central', tecnico_name: 'Bruno Neves',
          },
          {
            ...visitaBase, id: 2140, date: '2026-09-23', time_start: 11, time_stop: 15,
            os_name: 'OS26-08-0005', partner_name: 'Hospital Central', tecnico_name: 'Bruno Neves',
          },
        ],
      } as never)

      const r = (await runTool('buscar_agenda', {
        date_from: '2026-09-21', date_to: '2026-09-25',
      })) as { visitas: Array<{ rotulo: string }> }

      const [rotuloA, rotuloB] = r.visitas.map((v) => v.rotulo)
      expect(rotuloA).not.toEqual(rotuloB)
      expect(rotuloA).toContain('08:00')
      expect(rotuloB).toContain('11:00')
    })

    // O campo novo é um plano à parte (prosa); a trava de id em `machine.ts`
    // (`coletarIds`) é outro plano e não pode ser afetada por ele. Prova
    // direta: a mesma função que a máquina usa pra "id já apareceu nesta
    // conversa" continua coletando os ids normalmente a partir do payload
    // já com `rotulo` — nada foi substituído, só acrescentado.
    it('não muda o que coletarIds (guard de ids da máquina) enxerga no payload', async () => {
      vi.mocked(agenda.fetchAgenda).mockResolvedValue({
        visitas: [
          {
            ...visitaBase, id: 2138, date: '2026-09-23', time_start: 8, time_stop: 12,
            os_name: 'OS26-08-0005', partner_name: 'Hospital Central', tecnico_name: 'Bruno Neves',
          },
          {
            ...visitaBase, id: 2140, date: '2026-09-23', time_start: 11, time_stop: 15,
            os_name: 'OS26-08-0005', partner_name: 'Hospital Central', tecnico_name: 'Bruno Neves',
          },
        ],
      } as never)

      const r = await runTool('buscar_agenda', { date_from: '2026-09-21', date_to: '2026-09-25' })

      const vistos = new Set<number>()
      coletarIds(r, vistos)
      expect(Array.from(vistos)).toEqual(expect.arrayContaining([2138, 2140, 4, 9]))
    })
  })
})
