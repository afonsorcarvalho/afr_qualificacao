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

export interface LlmTurn {
  content: string | null
  tool_calls: LlmToolCall[]
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
    return {
      content: typeof msg.content === 'string' ? msg.content : null,
      tool_calls: Array.isArray(msg.tool_calls) ? msg.tool_calls : [],
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
