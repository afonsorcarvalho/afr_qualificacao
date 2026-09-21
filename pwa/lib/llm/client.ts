// lib/llm/client.ts
// Cliente HTTP para qualquer endpoint com wire OpenAI-compatível (Groq,
// OpenRouter). Genérico de propósito: baseUrl, chave e modelo vêm por
// parâmetro, para não haver um segundo cliente quase igual no projeto.
export class LlmError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message)
    this.name = 'LlmError'
  }
}

export interface LlmToolCall {
  id: string
  type: 'function'
  function: { name: string; arguments: string }
}

export interface LlmMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string | null
  tool_calls?: LlmToolCall[]
  tool_call_id?: string
}

export interface LlmToolDef {
  type: 'function'
  function: {
    name: string
    description: string
    parameters: Record<string, unknown>
  }
}

export interface LlmOpts {
  baseUrl: string
  apiKey: string
  model: string
  tools?: LlmToolDef[]
  temperature?: number
  max_tokens?: number
  response_format?: { type: 'json_object' }
  /** Campos extras do corpo — no OpenRouter, `provider` e `reasoning`. */
  extraBody?: Record<string, unknown>
  timeoutMs?: number
}

export interface LlmUsage {
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  /**
   * USD. Só vem quando o corpo pede `usage: { include: true }` (ver
   * `extraBody` em `app/api/chat/route.ts`) — verificado empiricamente
   * contra a API real do OpenRouter, não documentação. Nem todo provedor
   * manda; ausente quando não vier, nunca calculado no cliente.
   */
  cost?: number
}

export interface LlmTurn {
  content: string | null
  tool_calls: LlmToolCall[]
  /** Ausente quando o provedor não devolve `usage` na resposta. */
  usage?: LlmUsage
  /** Não vem de `llmChat` — a rota (`app/api/chat/route.ts`) acrescenta
   * `{ ...turn, model }` antes de responder ao cliente. Mora aqui só pra
   * o tipo cobrir o formato real que trafega na rede. */
  model?: string
}

export async function readError(res: Response): Promise<string> {
  try {
    const j = await res.json()
    return j?.error?.message || res.statusText
  } catch {
    return res.statusText
  }
}

export async function llmChat(
  messages: LlmMessage[],
  opts: LlmOpts,
): Promise<LlmTurn> {
  if (!opts.apiKey) {
    throw new LlmError('Chave de API não configurada', 503)
  }
  const controller = new AbortController()
  const t = setTimeout(() => controller.abort(), opts.timeoutMs ?? 30_000)
  try {
    const res = await fetch(`${opts.baseUrl}/chat/completions`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${opts.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: opts.model,
        messages,
        temperature: opts.temperature ?? 0.3,
        max_tokens: opts.max_tokens ?? 1500,
        ...(opts.tools ? { tools: opts.tools } : {}),
        ...(opts.response_format ? { response_format: opts.response_format } : {}),
        ...(opts.extraBody ?? {}),
      }),
    })
    if (!res.ok) {
      throw new LlmError(await readError(res), res.status)
    }
    const data = await res.json()
    const msg = data?.choices?.[0]?.message
    if (!msg || typeof msg !== 'object') {
      throw new LlmError('Resposta sem message', 502)
    }
    const usageBruto = data?.usage
    const numeroOuUndefined = (v: unknown): number | undefined => (typeof v === 'number' ? v : undefined)
    const usage: LlmUsage | undefined = usageBruto && typeof usageBruto === 'object'
      ? {
          prompt_tokens: numeroOuUndefined(usageBruto.prompt_tokens),
          completion_tokens: numeroOuUndefined(usageBruto.completion_tokens),
          total_tokens: numeroOuUndefined(usageBruto.total_tokens),
          cost: numeroOuUndefined(usageBruto.cost),
        }
      : undefined

    return {
      content: typeof msg.content === 'string' ? msg.content : null,
      tool_calls: Array.isArray(msg.tool_calls) ? msg.tool_calls : [],
      ...(usage ? { usage } : {}),
    }
  } catch (e) {
    if ((e as { name?: string } | null)?.name === 'AbortError') {
      throw new LlmError('Timeout — IA demorou demais', 504)
    }
    throw e
  } finally {
    clearTimeout(t)
  }
}
