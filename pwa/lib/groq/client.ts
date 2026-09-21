// lib/groq/client.ts
import { llmChat, LlmError, readError, type LlmMessage } from '@/lib/llm/client'

export class GroqError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message)
    this.name = 'GroqError'
  }
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface ChatOpts {
  model: string
  temperature?: number
  max_tokens?: number
  response_format?: { type: 'json_object' }
}

export interface TranscribeOpts {
  language?: string
  model?: string
}

const BASE_URL = 'https://api.groq.com/openai/v1'

function requireKey(): string {
  const key = process.env.GROQ_API_KEY
  if (!key) {
    throw new GroqError('GROQ_API_KEY não configurada', 503)
  }
  return key
}

export async function groqChat(
  messages: ChatMessage[],
  opts: ChatOpts,
): Promise<{ content: string }> {
  try {
    const turn = await llmChat(messages as LlmMessage[], {
      baseUrl: BASE_URL,
      apiKey: requireKey(),
      model: opts.model,
      temperature: opts.temperature,
      max_tokens: opts.max_tokens,
      response_format: opts.response_format,
    })
    if (typeof turn.content !== 'string') {
      throw new GroqError('Resposta Groq sem content', 502)
    }
    return { content: turn.content }
  } catch (e) {
    // A superfície pública deste módulo é `GroqError`; os chamadores
    // (review, summary) ramificam nela. Converter aqui evita mexer neles.
    if (e instanceof LlmError) {
      throw new GroqError(
        e.status === 503 ? 'GROQ_API_KEY não configurada' : e.message,
        e.status,
      )
    }
    throw e
  }
}

export async function groqTranscribe(
  audio: Blob,
  opts: TranscribeOpts = {},
): Promise<{ text: string }> {
  const key = requireKey()
  const form = new FormData()
  const file = audio instanceof File
    ? audio
    : new File([audio], 'audio.webm', { type: audio.type || 'audio/webm' })
  form.append('file', file)
  form.append('model', opts.model ?? 'whisper-large-v3-turbo')
  if (opts.language) form.append('language', opts.language)

  const controller = new AbortController()
  const t = setTimeout(() => controller.abort(), 60_000)
  try {
    const res = await fetch(`${BASE_URL}/audio/transcriptions`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Authorization': `Bearer ${key}`,
      },
      body: form,
    })
    if (!res.ok) {
      throw new GroqError(await readError(res), res.status)
    }
    const data = await res.json()
    if (typeof data?.text !== 'string') {
      throw new GroqError('Resposta Whisper sem text', 502)
    }
    return { text: data.text }
  } catch (e) {
    if ((e as { name?: string } | null)?.name === 'AbortError') {
      throw new GroqError('Timeout — IA demorou demais', 504)
    }
    throw e
  } finally {
    clearTimeout(t)
  }
}
