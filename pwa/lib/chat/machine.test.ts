import { describe, it, expect, vi } from 'vitest'
import {
  runTurn, confirmarEscrita, coletarIds, isDataIso, MAX_TOOL_ROUNDS,
} from './machine'
import type { LlmTurn, LlmMessage } from '@/lib/llm/client'

function texto(t: string): LlmTurn {
  return { content: t, tool_calls: [] }
}
function chamada(name: string, args: unknown, id = 'c1'): LlmTurn {
  return {
    content: null,
    tool_calls: [{ id, type: 'function', function: { name, arguments: JSON.stringify(args) } }],
  }
}
function deps(turns: LlmTurn[], runTool = vi.fn().mockResolvedValue({ ok: true })) {
  const callModel = vi.fn()
  turns.forEach((t) => callModel.mockResolvedValueOnce(t))
  return { callModel, runTool, idsVistos: new Set<number>() }
}
const inicio: LlmMessage[] = [
  { role: 'system', content: 's' },
  { role: 'user', content: 'oi' },
]

describe('isDataIso', () => {
  it('aceita data absoluta válida', () => {
    expect(isDataIso('2026-10-16')).toBe(true)
  })
  it('rejeita texto relativo, formato errado e data impossível', () => {
    expect(isDataIso('quinta')).toBe(false)
    expect(isDataIso('16/10/2026')).toBe(false)
    expect(isDataIso('2026-13-01')).toBe(false)
    expect(isDataIso('2026-02-30')).toBe(false)
    expect(isDataIso(20261016)).toBe(false)
  })
})

describe('coletarIds', () => {
  it('coleta id de objeto, de lista aninhada e de instrument_ids', () => {
    const s = new Set<number>()
    coletarIds({ visitas: [{ id: 87, tecnico_id: 3, instrument_ids: [11, 12] }] }, s)
    expect(Array.from(s).sort((a, b) => a - b)).toEqual([3, 11, 12, 87])
  })
  it('ignora valores não numéricos', () => {
    const s = new Set<number>()
    coletarIds({ id: 'abc', os_id: null }, s)
    expect(s.size).toBe(0)
  })
})

describe('runTurn', () => {
  it('turno sem ferramenta devolve texto', async () => {
    const d = deps([texto('tudo certo')])
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('text')
    if (r.kind === 'text') expect(r.text).toBe('tudo certo')
  })

  it('leitura executa, realimenta e segue o loop', async () => {
    const runTool = vi.fn().mockResolvedValue({ visitas: [{ id: 87 }] })
    const d = deps([chamada('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' }), texto('achei')], runTool)
    const r = await runTurn(inicio, d)
    expect(runTool).toHaveBeenCalledWith('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' })
    expect(r.kind).toBe('text')
    expect(d.idsVistos.has(87)).toBe(true)
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool).toBeTruthy()
  })

  it('escrita PARA o loop e vira proposta, sem chamar runTool', async () => {
    const runTool = vi.fn()
    const d = deps([chamada('atualizar_visita', { visita_id: 87, date: '2026-10-16' })], runTool)
    d.idsVistos.add(87)
    const r = await runTurn(inicio, d)
    expect(runTool).not.toHaveBeenCalled()
    expect(r.kind).toBe('proposal')
    if (r.kind === 'proposal') {
      expect(r.proposta.name).toBe('atualizar_visita')
      expect(r.proposta.args).toEqual({ visita_id: 87, date: '2026-10-16' })
      expect(r.proposta.resumo).toContain('87')
    }
  })

  it('escrita com id nunca visto não vira proposta; o erro volta ao modelo', async () => {
    const d = deps([
      chamada('atualizar_visita', { visita_id: 999, date: '2026-10-16' }),
      texto('desculpe, vou buscar primeiro'),
    ])
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('text')
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toContain('999')
    expect(tool?.content).toMatch(/não apareceu/i)
  })

  it('data não-ISO é rejeitada antes de qualquer execução', async () => {
    const runTool = vi.fn()
    const d = deps([
      chamada('buscar_agenda', { date_from: 'quinta', date_to: '2026-10-18' }),
      texto('corrigindo'),
    ], runTool)
    const r = await runTurn(inicio, d)
    expect(runTool).not.toHaveBeenCalled()
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toMatch(/AAAA-MM-DD/)
    expect(r.kind).toBe('text')
  })

  it('erro de ferramenta vira role tool e o loop continua', async () => {
    const runTool = vi.fn().mockRejectedValue(new Error('OS em execução (approved).'))
    const d = deps([
      chamada('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' }),
      texto('a OS está travada'),
    ], runTool)
    const r = await runTurn(inicio, d)
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toContain('OS em execução')
    expect(r.kind).toBe('text')
  })

  it('argumentos com JSON inválido não derrubam o loop', async () => {
    const callModel = vi.fn()
      .mockResolvedValueOnce({
        content: null,
        tool_calls: [{ id: 'c1', type: 'function', function: { name: 'buscar_agenda', arguments: '{nao é json' } }],
      })
      .mockResolvedValueOnce(texto('ok'))
    const d = { callModel, runTool: vi.fn(), idsVistos: new Set<number>() }
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('text')
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toMatch(/argumentos/i)
  })

  it('respeita o teto de voltas', async () => {
    const callModel = vi.fn().mockResolvedValue(
      chamada('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' }),
    )
    const d = { callModel, runTool: vi.fn().mockResolvedValue({}), idsVistos: new Set<number>() }
    const r = await runTurn(inicio, d)
    expect(callModel).toHaveBeenCalledTimes(MAX_TOOL_ROUNDS)
    expect(r.kind).toBe('error')
    if (r.kind === 'error') expect(r.erro).toMatch(/voltas/i)
  })

  it('erro do modelo vira resultado de erro, não exceção', async () => {
    const callModel = vi.fn().mockRejectedValue(new Error('IA indisponível'))
    const d = { callModel, runTool: vi.fn(), idsVistos: new Set<number>() }
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('error')
    if (r.kind === 'error') expect(r.erro).toContain('IA indisponível')
  })
})

describe('confirmarEscrita', () => {
  it('executa a ferramenta, realimenta o resultado e segue o loop', async () => {
    const runTool = vi.fn().mockResolvedValue({ id: 87, date: '2026-10-16' })
    const d = deps([texto('pronto, remarcada')], runTool)
    const proposta = {
      toolCallId: 'c1', name: 'atualizar_visita',
      args: { visita_id: 87, date: '2026-10-16' }, resumo: 'r',
    }
    const msgs: LlmMessage[] = [...inicio, {
      role: 'assistant', content: null,
      tool_calls: [{ id: 'c1', type: 'function', function: { name: 'atualizar_visita', arguments: '{}' } }],
    }]
    const r = await confirmarEscrita(msgs, proposta, d)
    expect(runTool).toHaveBeenCalledWith('atualizar_visita', { visita_id: 87, date: '2026-10-16' })
    expect(r.kind).toBe('text')
    if (r.kind === 'text') expect(r.text).toContain('remarcada')
  })

  it('UserError do Odoo volta ao modelo em vez de estourar', async () => {
    const runTool = vi.fn().mockRejectedValue(new Error('Visita já realizada.'))
    const d = deps([texto('não deu: a visita já foi realizada')], runTool)
    const proposta = { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'r' }
    const r = await confirmarEscrita([...inicio], proposta, d)
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toContain('Visita já realizada')
    expect(r.kind).toBe('text')
  })
})
