// lib/chat/machine.ts
// O loop do agente, sem React, para poder ser testado sozinho.
//
// Duas travas moram aqui, e são elas que tornam aceitável usar um modelo
// gratuito: data só entra em formato absoluto, e id de escrita só passa se
// tiver aparecido em algum resultado de ferramenta desta conversa. Quando
// uma delas barra, o erro volta ao modelo como resultado de ferramenta e
// ele se corrige na volta seguinte.
import type { LlmMessage, LlmTurn, LlmToolCall, LlmUsage } from '@/lib/llm/client'
import { isWriteTool } from './toolDefs'

export const MAX_TOOL_ROUNDS = 4

/**
 * Um item do painel de debug: uma ferramenta chamada nesta volta (com
 * argumentos crus e resultado RESUMIDO) ou o marcador `'texto'` quando a
 * volta terminou em resposta de texto, sem ferramenta nenhuma.
 */
export interface TracoChamada {
  nome: string
  /** JSON cru, exatamente como o modelo mandou. Ausente quando `nome === 'texto'`. */
  argumentos?: string
  /** Resumo — nunca o payload cru (ver `resumirResultadoLeitura`). Ausente quando `nome === 'texto'`. */
  resultado?: string
}

/** Uma volta = uma chamada ao modelo, mais o que aconteceu com o(s) tool_call(s) dela. */
export interface TracoVolta {
  modelo?: string
  usage?: LlmUsage
  duracaoMs: number
  chamadas: TracoChamada[]
}

export interface Proposta {
  toolCallId: string
  name: string
  args: Record<string, unknown>
  resumo: string
  /**
   * `call.function.arguments` cru, exatamente como o modelo mandou —
   * NUNCA `JSON.stringify(args)`. `confirmarEscrita` usa isto pro traço da
   * escrita confirmada; reserializar perderia espaçamento/ordem de chave
   * originais bem no ponto que o gestor mais vai querer auditar ("o que
   * exatamente foi gravado?"). Ver `TracoChamada.argumentos`.
   */
  argumentosBrutos: string
  /** Mesmos tracos do `PassoResultado` que gerou esta proposta — o card de
   * confirmação precisa deles porque uma proposta não gera bolha de texto. */
  tracos?: TracoVolta[]
}

export type PassoResultado =
  | { kind: 'text'; messages: LlmMessage[]; text: string; tracos?: TracoVolta[] }
  | { kind: 'proposal'; messages: LlmMessage[]; proposta: Proposta; tracos?: TracoVolta[] }
  | { kind: 'error'; messages: LlmMessage[]; erro: string; tracos?: TracoVolta[] }

export interface MachineDeps {
  callModel: (messages: LlmMessage[]) => Promise<LlmTurn>
  runTool: (name: string, args: Record<string, unknown>) => Promise<unknown>
  /** Mutável de propósito: acumula ao longo da conversa inteira. */
  idsVistos: Set<number>
}

const CHAVES_DE_ID = new Set([
  'id', 'visita_id', 'tecnico_id', 'os_id', 'instrument_id',
])

// Assimetria deliberada com `validar` abaixo: aqui só aceitamos `number`,
// sem coagir string. Nossas próprias RPCs (`fetchAgenda`, `createVisita`,
// `updateVisita`) sempre devolvem id como number — não há JSON de ida e
// volta por um modelo de linguagem neste lado —, então não há caso real de
// id-como-string para coletar. `validar` precisa coagir porque quem manda
// o id ali é o modelo, que alterna formato; aqui não é o mesmo problema.
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
    // Coagir, não rejeitar: um modelo do tier gratuito manda id inteiro
    // como string ("999") com frequência, e a cota é de 50 requisições/dia
    // — rejeitar por formato custaria uma volta cara por uma frescura de
    // tipo. `typeof v === 'number'` sozinho deixava "999" passar direto
    // pela trava (nunca era `typeof === 'number'`) até virar `Number(v)`
    // em `tools.ts`, já despachado contra o id errado.
    if (typeof v !== 'number' && typeof v !== 'string') continue
    const n = Number(v)
    if (!Number.isInteger(n)) {
      // Não é "id nunca visto" — é lixo de formato ("abc", 1.5, etc.).
      // Erro diferente para o modelo não tentar "buscar de novo" à toa.
      return `O campo "${campo}" veio como ${JSON.stringify(v)}, que não é um id inteiro válido.`
    }
    if (!idsVistos.has(n)) {
      return `O id ${n} em "${campo}" não apareceu em nenhuma consulta desta conversa. Chame a ferramenta de consulta adequada primeiro e use o id que ela devolver.`
    }
  }
  const instrumentos = args.instrument_ids
  if (Array.isArray(instrumentos)) {
    for (const item of instrumentos) {
      if (typeof item !== 'number' && typeof item !== 'string') continue
      const n = Number(item)
      if (!Number.isInteger(n)) {
        return `O instrumento "${JSON.stringify(item)}" não é um id inteiro válido. Chame listar_instrumentos primeiro.`
      }
      if (!idsVistos.has(n)) {
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

// `runTool` roda no navegador direto contra o Odoo — nada limita o
// tamanho da resposta neste lado. `buscar_agenda` com janela larga pode
// devolver até 500 visitas (teto do fetch server-side) a ~690 caracteres
// cada quando serializada, ou seja, até ~345000 caracteres. O teto da rota
// (`MAX_CHARS_CONTEUDO_MAQUINA` em `app/api/chat/route.ts`) é 120000 por
// mensagem "tool"; sem cortar aqui, `route.ts` devolve 400, e como
// `historico.current` é append-only (ver `useChatAgenda.aplicar`), TODA
// mensagem seguinte reenvia o mesmo payload gigante e falha do mesmo
// jeito — a conversa trava de vez a partir de um "como está o mês?" bem
// plausível. 100000 deixa folga sob o teto de 120000 para a marca de corte
// abaixo e para o resto da conversa (system prompt, histórico anterior).
const LIMITE_RESULTADO_FERRAMENTA = 100_000
const MARCA_TRUNCAMENTO = '\n… [resultado truncado; refine a janela de datas]'

/**
 * Serializa o resultado de uma ferramenta de LEITURA para a transcript,
 * cortando se passar do limite. O corte carrega uma marca explícita em
 * pt-BR em vez de só truncar o JSON em silêncio — o modelo lê a marca e
 * pode se corrigir pedindo uma janela menor, o mesmo padrão das outras
 * travas deste arquivo (erro volta como resultado de ferramenta, o loop
 * continua).
 */
function serializarResultadoFerramenta(resultado: unknown): string {
  const bruto = JSON.stringify(resultado)
  if (bruto.length <= LIMITE_RESULTADO_FERRAMENTA) return bruto
  return bruto.slice(0, LIMITE_RESULTADO_FERRAMENTA) + MARCA_TRUNCAMENTO
}

const RESULTADO_ROTULO: Record<string, string> = {
  buscar_agenda: 'visitas',
  listar_tecnicos: 'técnicos',
  listar_instrumentos: 'instrumentos',
  listar_os: 'OS',
}

function idDoItem(item: unknown): number | null {
  if (!item || typeof item !== 'object') return null
  const id = (item as Record<string, unknown>).id
  return typeof id === 'number' ? id : null
}

/**
 * Resumo de um resultado de LEITURA pro painel de debug — nunca o payload
 * cru (pode chegar a ~345000 caracteres numa janela larga de
 * `buscar_agenda`, ver `serializarResultadoFerramenta` acima). Conta os
 * itens e amostra até 3 ids; formato inesperado (escrita, erro do próprio
 * Odoo devolvido como objeto solto, etc.) cai em `'ok'` sem quebrar — este
 * helper é só cosmético, nunca deve ser o motivo de um traço faltar.
 */
export function resumirResultadoLeitura(name: string, resultado: unknown): string {
  let arr: unknown[] | null = null
  if (name === 'buscar_agenda' && resultado && typeof resultado === 'object') {
    const v = (resultado as Record<string, unknown>).visitas
    if (Array.isArray(v)) arr = v
  } else if (Array.isArray(resultado)) {
    arr = resultado
  }
  if (!arr) return 'ok'

  const rotulo = RESULTADO_ROTULO[name] ?? 'itens'
  const ids = arr.map(idDoItem).filter((n): n is number => n !== null)
  const amostra = ids.slice(0, 3).join(', ')
  const reticencias = ids.length > 3 ? '…' : ''
  return amostra ? `${arr.length} ${rotulo} (${amostra}${reticencias})` : `${arr.length} ${rotulo}`
}

const AGUARDANDO_CONFIRMACAO = 'aguardando confirmação do gestor'
const NAO_EXECUTADA_TRACO = 'não executada (proposta anterior pendente nesta volta)'

/**
 * Roda o loop até o modelo responder em texto, propor uma escrita, ou
 * esbarrar no teto. Nunca lança: erro vira resultado.
 */
export async function runTurn(
  messages: LlmMessage[],
  deps: MachineDeps,
): Promise<PassoResultado> {
  let atual = [...messages]
  // Um traço por volta (chamada ao modelo), acumulado pro turno inteiro —
  // é o que alimenta o painel de debug (▸ detalhes) da MUDANÇA B. Nunca
  // guarda payload cru de ferramenta, só resumo (ver `resumirResultadoLeitura`).
  const tracos: TracoVolta[] = []

  for (let volta = 0; volta < MAX_TOOL_ROUNDS; volta++) {
    const inicioVolta = Date.now()
    let turn: LlmTurn
    try {
      turn = await deps.callModel(atual)
    } catch (e) {
      // Esta volta não produziu traço (o modelo nem respondeu) — as
      // anteriores continuam valendo pro painel de debug.
      return { kind: 'error', messages: atual, erro: mensagemDeErro(e), tracos }
    }
    const duracaoMs = Date.now() - inicioVolta

    if (!turn.tool_calls.length) {
      atual = [...atual, msgAssistente(turn)]
      tracos.push({
        modelo: turn.model, usage: turn.usage, duracaoMs,
        chamadas: [{ nome: 'texto' }],
      })
      return { kind: 'text', messages: atual, text: turn.content ?? '', tracos }
    }

    atual = [...atual, msgAssistente(turn)]
    let propostaPendente: Proposta | null = null
    const chamadasDaVolta: TracoChamada[] = []

    for (let i = 0; i < turn.tool_calls.length; i++) {
      const call = turn.tool_calls[i]
      const args = parseArgs(call)
      if (!args) {
        const erroArgs = 'Não consegui ler os argumentos: não são um objeto JSON válido. Repita a chamada com JSON bem formado.'
        atual = [...atual, msgFerramenta(call.id, erroArgs)]
        chamadasDaVolta.push({ nome: call.function.name, argumentos: call.function.arguments, resultado: erroArgs })
        continue
      }
      const erro = validar(call.function.name, args, deps.idsVistos)
      if (erro) {
        atual = [...atual, msgFerramenta(call.id, erro)]
        chamadasDaVolta.push({ nome: call.function.name, argumentos: call.function.arguments, resultado: erro })
        continue
      }
      if (isWriteTool(call.function.name)) {
        // O loop para aqui: escrita não executa sem o gestor confirmar.
        propostaPendente = {
          toolCallId: call.id,
          name: call.function.name,
          args,
          resumo: resumir(call.function.name, args),
          argumentosBrutos: call.function.arguments,
        }
        chamadasDaVolta.push({
          nome: call.function.name, argumentos: call.function.arguments,
          resultado: AGUARDANDO_CONFIRMACAO,
        })
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
          chamadasDaVolta.push({ nome: restante.function.name, argumentos: restante.function.arguments, resultado: NAO_EXECUTADA_TRACO })
        }
        break
      }
      try {
        const resultado = await deps.runTool(call.function.name, args)
        // Coletar ids ANTES de truncar, sobre o resultado inteiro: um id
        // legítimo que o modelo já viu não pode desaparecer da trava só
        // porque caiu na parte cortada da serialização abaixo.
        coletarIds(resultado, deps.idsVistos)
        atual = [...atual, msgFerramenta(call.id, serializarResultadoFerramenta(resultado))]
        chamadasDaVolta.push({
          nome: call.function.name, argumentos: call.function.arguments,
          resultado: resumirResultadoLeitura(call.function.name, resultado),
        })
      } catch (e) {
        const msgErro = mensagemDeErro(e)
        atual = [...atual, msgFerramenta(call.id, msgErro)]
        chamadasDaVolta.push({ nome: call.function.name, argumentos: call.function.arguments, resultado: msgErro })
      }
    }

    tracos.push({ modelo: turn.model, usage: turn.usage, duracaoMs, chamadas: chamadasDaVolta })

    if (propostaPendente) {
      // Cópia própria (não a mesma referência de array) pra proposta poder
      // ser lida independente de `tracos` continuar mutando (não deveria,
      // já que a função retorna aqui, mas evita acoplar por referência).
      return {
        kind: 'proposal', messages: atual,
        proposta: { ...propostaPendente, tracos: [...tracos] },
        tracos,
      }
    }
  }
  return {
    kind: 'error',
    messages: atual,
    erro: `A IA excedeu ${MAX_TOOL_ROUNDS} voltas de consulta sem concluir. Tente reformular o pedido.`,
    tracos,
  }
}

/** Executa a escrita que o gestor confirmou e devolve o loop ao modelo. */
export async function confirmarEscrita(
  messages: LlmMessage[],
  proposta: Proposta,
  deps: MachineDeps,
): Promise<PassoResultado> {
  let atual = [...messages]
  const inicio = Date.now()
  let resultadoTraco: string
  try {
    const resultado = await deps.runTool(proposta.name, proposta.args)
    coletarIds(resultado, deps.idsVistos)
    atual = [...atual, msgFerramenta(proposta.toolCallId, JSON.stringify(resultado))]
    resultadoTraco = 'ok'
  } catch (e) {
    const msgErro = mensagemDeErro(e)
    atual = [...atual, msgFerramenta(proposta.toolCallId, msgErro)]
    resultadoTraco = msgErro
  }
  const tracoEscrita: TracoVolta = {
    duracaoMs: Date.now() - inicio,
    chamadas: [{ nome: proposta.name, argumentos: proposta.argumentosBrutos, resultado: resultadoTraco }],
  }
  const proximo = await runTurn(atual, deps)
  return { ...proximo, tracos: [tracoEscrita, ...(proximo.tracos ?? [])] }
}
