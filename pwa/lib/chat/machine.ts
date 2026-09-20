// lib/chat/machine.ts
// O loop do agente, sem React, para poder ser testado sozinho.
//
// Duas travas moram aqui, e são elas que tornam aceitável usar um modelo
// gratuito: data só entra em formato absoluto, e id de escrita só passa se
// tiver aparecido em algum resultado de ferramenta desta conversa. Quando
// uma delas barra, o erro volta ao modelo como resultado de ferramenta e
// ele se corrige na volta seguinte.
import type { LlmMessage, LlmTurn, LlmToolCall } from '@/lib/llm/client'
import { isWriteTool } from './toolDefs'

export const MAX_TOOL_ROUNDS = 4

export interface Proposta {
  toolCallId: string
  name: string
  args: Record<string, unknown>
  resumo: string
}

export type PassoResultado =
  | { kind: 'text'; messages: LlmMessage[]; text: string }
  | { kind: 'proposal'; messages: LlmMessage[]; proposta: Proposta }
  | { kind: 'error'; messages: LlmMessage[]; erro: string }

export interface MachineDeps {
  callModel: (messages: LlmMessage[]) => Promise<LlmTurn>
  runTool: (name: string, args: Record<string, unknown>) => Promise<unknown>
  /** Mutável de propósito: acumula ao longo da conversa inteira. */
  idsVistos: Set<number>
}

const CHAVES_DE_ID = new Set([
  'id', 'visita_id', 'tecnico_id', 'os_id', 'instrument_id',
])

export function coletarIds(valor: unknown, destino: Set<number>): void {
  if (Array.isArray(valor)) {
    for (const v of valor) coletarIds(v, destino)
    return
  }
  if (!valor || typeof valor !== 'object') return
  for (const [chave, v] of Object.entries(valor as Record<string, unknown>)) {
    if (chave === 'instrument_ids' && Array.isArray(v)) {
      for (const n of v) if (typeof n === 'number') destino.add(n)
      continue
    }
    if (CHAVES_DE_ID.has(chave) && typeof v === 'number') destino.add(v)
    else coletarIds(v, destino)
  }
}

const RE_ISO = /^\d{4}-\d{2}-\d{2}$/

export function isDataIso(v: unknown): boolean {
  if (typeof v !== 'string' || !RE_ISO.test(v)) return false
  const d = new Date(`${v}T00:00:00Z`)
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === v
}

const CAMPOS_DE_DATA = ['date', 'date_from', 'date_to']
const CAMPOS_DE_ID = ['visita_id', 'tecnico_id', 'os_id']

/** Erro legível para o modelo, ou null se os argumentos passam. */
function validar(
  name: string,
  args: Record<string, unknown>,
  idsVistos: Set<number>,
): string | null {
  for (const campo of CAMPOS_DE_DATA) {
    if (args[campo] !== undefined && !isDataIso(args[campo])) {
      return `O campo "${campo}" veio como ${JSON.stringify(args[campo])}. Use data absoluta no formato AAAA-MM-DD, calculada a partir da data de hoje informada no contexto.`
    }
  }
  if (!isWriteTool(name)) return null
  for (const campo of CAMPOS_DE_ID) {
    const v = args[campo]
    if (typeof v === 'number' && !idsVistos.has(v)) {
      return `O id ${v} em "${campo}" não apareceu em nenhuma consulta desta conversa. Chame a ferramenta de consulta adequada primeiro e use o id que ela devolver.`
    }
  }
  const instrumentos = args.instrument_ids
  if (Array.isArray(instrumentos)) {
    for (const n of instrumentos) {
      if (typeof n === 'number' && !idsVistos.has(n)) {
        return `O instrumento de id ${n} não apareceu em nenhuma consulta desta conversa. Chame listar_instrumentos primeiro.`
      }
    }
  }
  return null
}

/** Mostra o valor, ou um aviso em pt-BR em vez do literal "undefined". */
function ouFalta(v: unknown, campo: string): unknown {
  return v !== undefined ? v : `(${campo} não informado)`
}

// O card montado a partir deste texto é a última coisa que o gestor vê
// antes de confirmar uma escrita: nunca deixar "undefined" vazar para lá,
// mesmo quando o modelo omite um argumento obrigatório — a validação de
// obrigatoriedade só acontece depois, em runTool, que não roda para
// escritas dentro de runTurn.
function resumir(name: string, args: Record<string, unknown>): string {
  if (name === 'criar_visita') {
    const os = ouFalta(args.os_id, 'id da OS')
    const data = ouFalta(args.date, 'data')
    const tecnico = ouFalta(args.tecnico_id, 'técnico')
    return `Criar visita para a OS ${os} em ${data}, técnico ${tecnico}.`
  }
  const visita = ouFalta(args.visita_id, 'id da visita')
  const partes: string[] = []
  if (args.date !== undefined) partes.push(`data → ${args.date}`)
  if (args.time_start !== undefined) partes.push(`início → ${args.time_start}`)
  if (args.time_stop !== undefined) partes.push(`fim → ${args.time_stop}`)
  if (args.tecnico_id !== undefined) partes.push(`técnico → ${args.tecnico_id}`)
  if (args.instrument_ids !== undefined) {
    partes.push(`instrumentos → ${JSON.stringify(args.instrument_ids)}`)
  }
  if (args.note !== undefined) partes.push('observação alterada')
  return `Alterar a visita ${visita}: ${partes.join(', ') || 'sem mudança'}.`
}

function parseArgs(call: LlmToolCall): Record<string, unknown> | null {
  try {
    const v = JSON.parse(call.function.arguments || '{}')
    return v && typeof v === 'object' && !Array.isArray(v) ? v : null
  } catch {
    return null
  }
}

function msgAssistente(turn: LlmTurn): LlmMessage {
  return { role: 'assistant', content: turn.content, tool_calls: turn.tool_calls }
}

function msgFerramenta(id: string, conteudo: string): LlmMessage {
  return { role: 'tool', content: conteudo, tool_call_id: id }
}

function mensagemDeErro(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

/**
 * Roda o loop até o modelo responder em texto, propor uma escrita, ou
 * esbarrar no teto. Nunca lança: erro vira resultado.
 */
export async function runTurn(
  messages: LlmMessage[],
  deps: MachineDeps,
): Promise<PassoResultado> {
  let atual = [...messages]
  for (let volta = 0; volta < MAX_TOOL_ROUNDS; volta++) {
    let turn: LlmTurn
    try {
      turn = await deps.callModel(atual)
    } catch (e) {
      return { kind: 'error', messages: atual, erro: mensagemDeErro(e) }
    }

    if (!turn.tool_calls.length) {
      atual = [...atual, msgAssistente(turn)]
      return { kind: 'text', messages: atual, text: turn.content ?? '' }
    }

    atual = [...atual, msgAssistente(turn)]
    let propostaPendente: Proposta | null = null

    for (let i = 0; i < turn.tool_calls.length; i++) {
      const call = turn.tool_calls[i]
      const args = parseArgs(call)
      if (!args) {
        atual = [...atual, msgFerramenta(
          call.id,
          'Não consegui ler os argumentos: não são um objeto JSON válido. Repita a chamada com JSON bem formado.',
        )]
        continue
      }
      const erro = validar(call.function.name, args, deps.idsVistos)
      if (erro) {
        atual = [...atual, msgFerramenta(call.id, erro)]
        continue
      }
      if (isWriteTool(call.function.name)) {
        // O loop para aqui: escrita não executa sem o gestor confirmar.
        propostaPendente = {
          toolCallId: call.id,
          name: call.function.name,
          args,
          resumo: resumir(call.function.name, args),
        }
        // O modelo pode ter pedido várias ferramentas nesta mesma volta
        // (gemma-4-31b-it suporta tool calls paralelas). A API exige uma
        // resposta "tool" para cada tool_call_id da mensagem assistant
        // anterior, senão a próxima chamada ao modelo é rejeitada — então
        // as chamadas depois da escrita, que não vão rodar agora, recebem
        // uma resposta explicando por quê, em vez de ficar sem resposta.
        for (let j = i + 1; j < turn.tool_calls.length; j++) {
          const restante = turn.tool_calls[j]
          atual = [...atual, msgFerramenta(
            restante.id,
            'Não executada: a alteração anterior está aguardando confirmação do gestor; refaça esta chamada depois se ainda for necessária.',
          )]
        }
        break
      }
      try {
        const resultado = await deps.runTool(call.function.name, args)
        coletarIds(resultado, deps.idsVistos)
        atual = [...atual, msgFerramenta(call.id, JSON.stringify(resultado))]
      } catch (e) {
        atual = [...atual, msgFerramenta(call.id, mensagemDeErro(e))]
      }
    }

    if (propostaPendente) {
      return { kind: 'proposal', messages: atual, proposta: propostaPendente }
    }
  }
  return {
    kind: 'error',
    messages: atual,
    erro: `A IA excedeu ${MAX_TOOL_ROUNDS} voltas de consulta sem concluir. Tente reformular o pedido.`,
  }
}

/** Executa a escrita que o gestor confirmou e devolve o loop ao modelo. */
export async function confirmarEscrita(
  messages: LlmMessage[],
  proposta: Proposta,
  deps: MachineDeps,
): Promise<PassoResultado> {
  let atual = [...messages]
  try {
    const resultado = await deps.runTool(proposta.name, proposta.args)
    coletarIds(resultado, deps.idsVistos)
    atual = [...atual, msgFerramenta(proposta.toolCallId, JSON.stringify(resultado))]
  } catch (e) {
    atual = [...atual, msgFerramenta(proposta.toolCallId, mensagemDeErro(e))]
  }
  return runTurn(atual, deps)
}
