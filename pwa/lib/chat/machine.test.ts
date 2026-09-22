import { describe, it, expect, vi } from 'vitest'
import {
  runTurn, confirmarEscrita, coletarIds, isDataIso, MAX_TOOL_ROUNDS,
  resumirResultadoLeitura,
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
function chamadas(...specs: Array<{ id: string; name: string; args: unknown }>): LlmTurn {
  return {
    content: null,
    tool_calls: specs.map((s) => ({
      id: s.id,
      type: 'function' as const,
      function: { name: s.name, arguments: JSON.stringify(s.args) },
    })),
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

  // Concern real: `listar_os` devolve equipment_ids/instrument_ids
  // ANINHADOS, um nível mais fundo do que o payload plano de antes
  // (`equipment_list: [{id, name}]`, `instrument_suggestions: [{id, name}]`,
  // dentro de uma lista de OS). Se a trava de id (`validar`, mais abaixo)
  // não reconhecesse esses ids como "vistos", TODO `criar_visita` real
  // quebraria — e nenhum teste de `tools.test.ts` acusaria, porque lá
  // `fetchOsOptions` é mockado. Prova direta de que a recursão genérica de
  // `coletarIds` (chave "id" bate em qualquer profundidade) cobre o
  // payload novo sem precisar de caso especial.
  it('coleta ids aninhados em equipment_list/instrument_suggestions (payload de listar_os)', () => {
    const s = new Set<number>()
    coletarIds([
      {
        id: 9, name: 'QOS00009',
        equipment_list: [{ id: 771, name: 'Autoclave' }, { id: 772, name: 'Estufa' }],
        instrument_suggestions: [{ id: 882, name: 'Q001' }],
      },
    ], s)
    expect(Array.from(s).sort((a, b) => a - b)).toEqual([9, 771, 772, 882])
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

  it('turno [leitura, escrita, leitura]: a leitura anterior executa, a escrita para o loop, e a leitura seguinte ainda recebe resposta tool', async () => {
    const runTool = vi.fn().mockResolvedValue({ ok: true })
    const d = deps([
      chamadas(
        { id: 'c1', name: 'buscar_agenda', args: { date_from: '2026-10-12', date_to: '2026-10-18' } },
        { id: 'c2', name: 'atualizar_visita', args: { visita_id: 87, date: '2026-10-16' } },
        { id: 'c3', name: 'listar_tecnicos', args: {} },
      ),
    ], runTool)
    d.idsVistos.add(87)
    const r = await runTurn(inicio, d)
    // A leitura antes da escrita realmente rodou; a leitura depois, não.
    expect(runTool).toHaveBeenCalledTimes(1)
    expect(runTool).toHaveBeenCalledWith('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' })
    expect(r.kind).toBe('proposal')
    const respostaC3 = r.messages.find((m) => m.role === 'tool' && m.tool_call_id === 'c3')
    expect(respostaC3).toBeTruthy()
    expect(respostaC3?.content).toMatch(/aguardando confirmação/i)
  })

  it('turno [escrita, escrita]: a primeira vira proposta, a segunda recebe placeholder, runTool nunca chamado', async () => {
    const runTool = vi.fn()
    const d = deps([
      chamadas(
        { id: 'c1', name: 'atualizar_visita', args: { visita_id: 87, date: '2026-10-16' } },
        { id: 'c2', name: 'criar_visita', args: { os_id: 5, tecnico_id: 3, date: '2026-10-17' } },
      ),
    ], runTool)
    d.idsVistos.add(87)
    d.idsVistos.add(5)
    d.idsVistos.add(3)
    const r = await runTurn(inicio, d)
    expect(runTool).not.toHaveBeenCalled()
    expect(r.kind).toBe('proposal')
    if (r.kind === 'proposal') expect(r.proposta.toolCallId).toBe('c1')
    const respostaC2 = r.messages.find((m) => m.role === 'tool' && m.tool_call_id === 'c2')
    expect(respostaC2).toBeTruthy()

    // Invariante: toda tool_call_id da mensagem assistant, exceto a que
    // virou proposta (ainda pendente do gestor), tem exatamente uma
    // resposta "tool" — senão a próxima chamada ao modelo é rejeitada
    // pela API.
    const assistente = r.messages.find((m) => m.role === 'assistant' && m.tool_calls)
    const idsRespondidos = r.messages.filter((m) => m.role === 'tool').map((m) => m.tool_call_id)
    for (const call of assistente!.tool_calls!) {
      if (r.kind === 'proposal' && call.id === r.proposta.toolCallId) continue
      expect(idsRespondidos.filter((id) => id === call.id).length).toBe(1)
    }
  })

  it('resumo da proposta não imprime "undefined" quando falta um argumento obrigatório', async () => {
    const d = deps([chamada('criar_visita', { date: '2026-10-16', tecnico_id: 3 })])
    d.idsVistos.add(3)
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('proposal')
    if (r.kind === 'proposal') {
      expect(r.proposta.resumo).not.toMatch(/undefined/)
      expect(r.proposta.resumo).toMatch(/não informad/i)
    }
  })

  // Concern real: o resumo de `criar_visita` (texto que VOLTA PRO MODELO,
  // distinto do card — ver nota em card.ts) não citava equipment_ids/
  // instrument_ids. Como os dois são obrigatórios desde esta task, omiti-
  // los do resumo escondia do próprio modelo o que ele estava propondo.
  it('resumo de criar_visita cita equipamentos e instrumentos quando informados', async () => {
    const d = deps([chamada('criar_visita', {
      os_id: 9, tecnico_id: 3, date: '2026-10-20',
      equipment_ids: [771, 772], instrument_ids: [882],
    })])
    d.idsVistos.add(9)
    d.idsVistos.add(3)
    d.idsVistos.add(771)
    d.idsVistos.add(772)
    d.idsVistos.add(882)
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('proposal')
    if (r.kind === 'proposal') {
      expect(r.proposta.resumo).toContain('771')
      expect(r.proposta.resumo).toContain('772')
      expect(r.proposta.resumo).toContain('882')
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

  it('escrita com visita_id como string alucinado (nunca visto) não vira proposta', async () => {
    // "999" (string), não 999 (number) — a quirk exata do achado 1: um
    // modelo de tier gratuito que devolve id inteiro como string.
    const d = deps([
      chamada('atualizar_visita', { visita_id: '999', date: '2026-10-16' }),
      texto('desculpe, vou buscar primeiro'),
    ])
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('text')
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toContain('999')
    expect(tool?.content).toMatch(/não apareceu/i)
  })

  it('escrita com visita_id como string cujo equivalente numérico já foi visto vira proposta', async () => {
    const d = deps([chamada('atualizar_visita', { visita_id: '87', date: '2026-10-16' })])
    d.idsVistos.add(87)
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('proposal')
    if (r.kind === 'proposal') {
      // O guard coage para validar, mas não reescreve os args da proposta
      // — quem coage para despacho é `tools.ts`. Fixar isto aqui evita que
      // alguém "normalize" args dentro de `machine.ts` mais tarde e mova a
      // responsabilidade de coerção para o lugar errado.
      expect(r.proposta.args.visita_id).toBe('87')
    }
  })

  it('visita_id não numérico (lixo de formato, não id alucinado) recebe erro específico, distinto de "não apareceu"', async () => {
    const d = deps([
      chamada('atualizar_visita', { visita_id: 'abc', date: '2026-10-16' }),
      texto('corrigindo'),
    ])
    const r = await runTurn(inicio, d)
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toMatch(/não é um id inteiro válido/i)
    expect(tool?.content).not.toMatch(/não apareceu/i)
  })

  it('instrument_ids com string alucinada (nunca vista) não vira proposta', async () => {
    const d = deps([
      chamada('atualizar_visita', { visita_id: 87, instrument_ids: ['11', '999'] }),
      texto('vou conferir os instrumentos'),
    ])
    d.idsVistos.add(87)
    d.idsVistos.add(11)
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('text')
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toContain('999')
    expect(tool?.content).toMatch(/não apareceu/i)
  })

  it('instrument_ids com strings cujos equivalentes numéricos já foram vistos vira proposta', async () => {
    const d = deps([chamada('atualizar_visita', { visita_id: 87, instrument_ids: ['11', '12'] })])
    d.idsVistos.add(87)
    d.idsVistos.add(11)
    d.idsVistos.add(12)
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('proposal')
  })

  // Concern real: `equipment_ids` é campo novo em `criar_visita` (obrigatório
  // desde esta task) e não tinha NENHUMA trava de id aqui — só
  // `instrument_ids` era checado contra `idsVistos`. Um equipamento
  // alucinado (nunca visto em listar_os) passava direto pra proposta;
  // hoje espelha exatamente o comportamento de `instrument_ids`.
  it('equipment_ids com id alucinado (nunca visto) não vira proposta', async () => {
    const d = deps([
      chamada('criar_visita', {
        os_id: 9, tecnico_id: 3, date: '2026-10-20',
        equipment_ids: [771, 99999], instrument_ids: [882],
      }),
      texto('vou conferir os equipamentos'),
    ])
    d.idsVistos.add(9)
    d.idsVistos.add(3)
    d.idsVistos.add(771)
    d.idsVistos.add(882)
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('text')
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toContain('99999')
    expect(tool?.content).toMatch(/não apareceu/i)
  })

  it('equipment_ids com todos os ids já vistos vira proposta', async () => {
    const d = deps([chamada('criar_visita', {
      os_id: 9, tecnico_id: 3, date: '2026-10-20',
      equipment_ids: [771, 772], instrument_ids: [882],
    })])
    d.idsVistos.add(9)
    d.idsVistos.add(3)
    d.idsVistos.add(771)
    d.idsVistos.add(772)
    d.idsVistos.add(882)
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('proposal')
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

  it('resultado de leitura gigante (janela larga de buscar_agenda) é truncado com marca em pt-BR, e a mensagem fica sob o teto de 120000 da rota', async () => {
    // Simula o cenário real: 500 "visitas" (teto do fetch server-side),
    // bem acima do que cabe em `MAX_CHARS_CONTEUDO_MAQUINA` (120000, em
    // app/api/chat/route.ts) depois de serializado.
    const visitaGrande = {
      id: 1, os_name: 'OS26-06-0002', partner_name: 'Hospital Central',
      city: 'São Luís', note: 'x'.repeat(600),
    }
    const resultadoGigante = { visitas: Array.from({ length: 500 }, () => visitaGrande) }
    const tamanhoBruto = JSON.stringify(resultadoGigante).length
    expect(tamanhoBruto).toBeGreaterThan(120_000) // prova que o cenário é realista

    const runTool = vi.fn().mockResolvedValue(resultadoGigante)
    const d = deps([
      chamada('buscar_agenda', { date_from: '2026-10-01', date_to: '2026-10-31' }),
      texto('muita coisa'),
    ], runTool)
    const r = await runTurn(inicio, d)
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toBeTruthy()
    expect(tool!.content!.length).toBeLessThan(120_000)
    expect(tool?.content).toMatch(/truncado/i)
    expect(tool?.content).toMatch(/refine a janela/i)
  })

  it('resultado de leitura pequeno não é truncado nem ganha marca', async () => {
    const runTool = vi.fn().mockResolvedValue({ visitas: [{ id: 87 }] })
    const d = deps([
      chamada('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' }),
      texto('achei'),
    ], runTool)
    const r = await runTurn(inicio, d)
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toBe(JSON.stringify({ visitas: [{ id: 87 }] }))
    expect(tool?.content).not.toMatch(/truncado/i)
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
    // Literal, não `MAX_TOOL_ROUNDS`: comparar o símbolo consigo mesmo não
    // pegaria uma regressão do valor. 4 é uma decisão de capacidade
    // deliberada — o tier gratuito dá 50 requisições/dia e cada volta gasta
    // uma, então subir para 8 cortaria pela metade as mensagens diárias do
    // gestor.
    expect(MAX_TOOL_ROUNDS).toBe(4)
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
      argumentosBrutos: '{"visita_id":87,"date":"2026-10-16"}',
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
    const proposta = { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'r', argumentosBrutos: '{"visita_id":87}' }
    const r = await confirmarEscrita([...inicio], proposta, d)
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toContain('Visita já realizada')
    expect(r.kind).toBe('text')
  })
})

describe('resumirResultadoLeitura', () => {
  it('buscar_agenda: conta e amostra até 3 ids, com reticências quando há mais', () => {
    const resultado = { visitas: Array.from({ length: 7 }, (_, i) => ({ id: 100 + i })) }
    expect(resumirResultadoLeitura('buscar_agenda', resultado)).toBe('7 visitas (100, 101, 102…)')
  })

  it('buscar_agenda: sem reticências quando cabe tudo em 3', () => {
    const resultado = { visitas: [{ id: 1 }, { id: 2 }] }
    expect(resumirResultadoLeitura('buscar_agenda', resultado)).toBe('2 visitas (1, 2)')
  })

  it('listar_tecnicos: array direto, rótulo próprio', () => {
    const resultado = [{ id: 3, name: 'Bruno' }, { id: 7, name: 'Maria' }]
    expect(resumirResultadoLeitura('listar_tecnicos', resultado)).toBe('2 técnicos (3, 7)')
  })

  it('listar_instrumentos e listar_os têm rótulos próprios', () => {
    expect(resumirResultadoLeitura('listar_instrumentos', [{ id: 1 }])).toBe('1 instrumentos (1)')
    expect(resumirResultadoLeitura('listar_os', [{ id: 9 }])).toBe('1 OS (9)')
  })

  it('lista vazia: sem parênteses vazios', () => {
    expect(resumirResultadoLeitura('buscar_agenda', { visitas: [] })).toBe('0 visitas')
  })

  it('formato inesperado (nem array nem {visitas}) cai em "ok" sem quebrar', () => {
    expect(resumirResultadoLeitura('buscar_agenda', { ok: true })).toBe('ok')
    expect(resumirResultadoLeitura('buscar_agenda', null)).toBe('ok')
  })
})

describe('runTurn — tracos (painel de debug)', () => {
  it('uma volta de leitura + uma volta final de texto: dois tracos, resumo nunca cru', async () => {
    const runTool = vi.fn().mockResolvedValue({ visitas: [{ id: 87 }, { id: 88 }] })
    const d = deps([
      { ...chamada('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' }), model: 'modelo/a', usage: { prompt_tokens: 100, completion_tokens: 10, total_tokens: 110 } },
      { ...texto('achei'), model: 'modelo/a', usage: { prompt_tokens: 50, completion_tokens: 5, total_tokens: 55 } },
    ], runTool)
    const r = await runTurn(inicio, d)
    expect(r.tracos).toHaveLength(2)

    const volta1 = r.tracos![0]
    expect(volta1.modelo).toBe('modelo/a')
    expect(volta1.usage).toEqual({ prompt_tokens: 100, completion_tokens: 10, total_tokens: 110 })
    expect(volta1.duracaoMs).toBeGreaterThanOrEqual(0)
    expect(volta1.chamadas).toEqual([{
      nome: 'buscar_agenda',
      argumentos: JSON.stringify({ date_from: '2026-10-12', date_to: '2026-10-18' }),
      resultado: '2 visitas (87, 88)',
    }])
    // Nunca o payload cru na trace — só o resumo.
    expect(JSON.stringify(volta1)).not.toMatch(/"id":87/)

    const volta2 = r.tracos![1]
    expect(volta2.modelo).toBe('modelo/a')
    expect(volta2.chamadas).toEqual([{ nome: 'texto' }])
  })

  it('escrita vira proposta: a chamada correspondente registra "aguardando confirmação", e a Proposta carrega os mesmos tracos', async () => {
    const d = deps([chamada('atualizar_visita', { visita_id: 87, date: '2026-10-16' })])
    d.idsVistos.add(87)
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('proposal')
    expect(r.tracos).toHaveLength(1)
    expect(r.tracos![0].chamadas).toEqual([{
      nome: 'atualizar_visita',
      argumentos: JSON.stringify({ visita_id: 87, date: '2026-10-16' }),
      resultado: 'aguardando confirmação do gestor',
    }])
    if (r.kind === 'proposal') {
      expect(r.proposta.tracos).toEqual(r.tracos)
    }
  })

  it('turno [leitura, escrita, leitura]: a leitura pulada também vira um item no traço, marcada como não executada', async () => {
    const runTool = vi.fn().mockResolvedValue({ ok: true })
    const d = deps([
      chamadas(
        { id: 'c1', name: 'buscar_agenda', args: { date_from: '2026-10-12', date_to: '2026-10-18' } },
        { id: 'c2', name: 'atualizar_visita', args: { visita_id: 87, date: '2026-10-16' } },
        { id: 'c3', name: 'listar_tecnicos', args: {} },
      ),
    ], runTool)
    d.idsVistos.add(87)
    const r = await runTurn(inicio, d)
    expect(r.tracos).toHaveLength(1)
    expect(r.tracos![0].chamadas.map((c) => c.nome)).toEqual(['buscar_agenda', 'atualizar_visita', 'listar_tecnicos'])
    const c3 = r.tracos![0].chamadas[2]
    expect(c3.resultado).toMatch(/não executada/i)
  })

  it('JSON inválido: o traço guarda o argumento cru (mesmo sem parse) e o erro como resultado', async () => {
    const callModel = vi.fn()
      .mockResolvedValueOnce({
        content: null,
        tool_calls: [{ id: 'c1', type: 'function', function: { name: 'buscar_agenda', arguments: '{nao é json' } }],
      })
      .mockResolvedValueOnce(texto('ok'))
    const d = { callModel, runTool: vi.fn(), idsVistos: new Set<number>() }
    const r = await runTurn(inicio, d)
    expect(r.tracos![0].chamadas[0]).toEqual({
      nome: 'buscar_agenda',
      argumentos: '{nao é json',
      resultado: expect.stringMatching(/argumentos/i),
    })
  })

  it('validação (data não-ISO): traço registra a mesma mensagem de erro devolvida ao modelo', async () => {
    const d = deps([
      chamada('buscar_agenda', { date_from: 'quinta', date_to: '2026-10-18' }),
      texto('corrigindo'),
    ])
    const r = await runTurn(inicio, d)
    expect(r.tracos![0].chamadas[0].resultado).toMatch(/AAAA-MM-DD/)
  })

  it('erro de ferramenta (throw): traço registra a mensagem de erro, não trava', async () => {
    const runTool = vi.fn().mockRejectedValue(new Error('OS em execução (approved).'))
    const d = deps([
      chamada('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' }),
      texto('a OS está travada'),
    ], runTool)
    const r = await runTurn(inicio, d)
    expect(r.tracos![0].chamadas[0].resultado).toContain('OS em execução')
  })

  it('teto de voltas: o erro final ainda carrega os tracos acumulados nas voltas anteriores', async () => {
    const callModel = vi.fn().mockResolvedValue(
      chamada('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' }),
    )
    const d = { callModel, runTool: vi.fn().mockResolvedValue({}), idsVistos: new Set<number>() }
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('error')
    expect(r.tracos).toHaveLength(MAX_TOOL_ROUNDS)
  })

  it('erro do modelo (callModel rejeita na segunda volta): o resultado de erro preserva o traço da primeira volta', async () => {
    const callModel = vi.fn()
      .mockResolvedValueOnce({
        content: null,
        tool_calls: [{ id: 'c1', type: 'function' as const, function: { name: 'buscar_agenda', arguments: '{}' } }],
      })
      .mockRejectedValueOnce(new Error('IA indisponível'))
    const runTool = vi.fn().mockResolvedValue({ visitas: [] })
    const d = { callModel, runTool, idsVistos: new Set<number>() }
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('error')
    // A primeira volta (buscar_agenda, executada) já tinha traço; a segunda
    // (que rejeitou) não some com ele.
    expect(r.tracos).toHaveLength(1)
    expect(r.tracos![0].chamadas[0].nome).toBe('buscar_agenda')
  })
})

describe('confirmarEscrita — tracos', () => {
  it('a escrita confirmada vira o primeiro traço com os argumentos CRUS (não reserializados), seguido dos tracos do runTurn seguinte', async () => {
    const runTool = vi.fn().mockResolvedValue({ id: 87, date: '2026-10-16' })
    const d = deps([texto('pronto, remarcada')], runTool)
    // Espaçamento deliberadamente diferente do que `JSON.stringify(args)`
    // produziria (`{"visita_id":87,...}`, sem espaço) — é o que distingue
    // "argumento cru preservado" de "argumento reserializado a partir de
    // `args`". Achado da rodada de revisão: em todo teste anterior,
    // `JSON.stringify(proposta.args)` canônico coincidia por acaso com o
    // cru, escondendo a reserialização que havia em `confirmarEscrita`.
    const argumentosBrutos = '{"visita_id": 87, "date": "2026-10-16"}'
    const proposta = {
      toolCallId: 'c1', name: 'atualizar_visita',
      args: { visita_id: 87, date: '2026-10-16' }, resumo: 'r',
      argumentosBrutos,
    }
    const msgs: LlmMessage[] = [...inicio, {
      role: 'assistant', content: null,
      tool_calls: [{ id: 'c1', type: 'function', function: { name: 'atualizar_visita', arguments: '{}' } }],
    }]
    const r = await confirmarEscrita(msgs, proposta, d)
    expect(r.tracos).toHaveLength(2)
    // Byte a byte contra o cru — não contra `JSON.stringify(proposta.args)`.
    expect(r.tracos![0].chamadas).toEqual([{
      nome: 'atualizar_visita',
      argumentos: argumentosBrutos,
      resultado: 'ok',
    }])
    expect(r.tracos![0].chamadas[0].argumentos).not.toBe(JSON.stringify(proposta.args))
    expect(r.tracos![1].chamadas).toEqual([{ nome: 'texto' }])
  })

  it('escrita que falha: traço registra a mensagem de erro no lugar de "ok"', async () => {
    const runTool = vi.fn().mockRejectedValue(new Error('Visita já realizada.'))
    const d = deps([texto('não deu')], runTool)
    const proposta = { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'r', argumentosBrutos: '{"visita_id":87}' }
    const r = await confirmarEscrita([...inicio], proposta, d)
    expect(r.tracos![0].chamadas[0].resultado).toBe('Visita já realizada.')
  })
})
