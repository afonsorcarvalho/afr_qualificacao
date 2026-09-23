// lib/llm/transcribe.ts
// Cliente de transcrição do OpenRouter. Ao contrário do endpoint de chat
// (que segue o wire OpenAI-compatível em `lib/llm/client.ts`), o endpoint
// de transcrição do OpenRouter é JSON com áudio em base64, não multipart
// — divergente do Groq (`lib/groq/client.ts`, `groqTranscribe`), que espera
// `FormData`. Mandar multipart aqui é o jeito de falhar em silêncio com 400.
// Reaproveita `LlmError`/`readError` de `./client`: não é uma hierarquia de
// erro nova.
import { LlmError, readError } from './client'

export interface TranscribeOpts {
  language?: string
  model?: string
}

export interface TranscribeUsage {
  seconds?: number
  cost?: number
}

export interface TranscribeResult {
  text: string
  /** Ausente quando o provedor não devolve `usage` na resposta. */
  usage?: TranscribeUsage
}

const BASE_URL = 'https://openrouter.ai/api/v1'
const MODELO_PADRAO = 'openai/whisper-large-v3-turbo'

function requireKey(): string {
  const key = process.env.OPENROUTER_API_KEY
  if (!key) {
    throw new LlmError('OPENROUTER_API_KEY não configurada', 503)
  }
  return key
}

function modeloConfigurado(): string {
  return process.env.OPENROUTER_STT_MODEL || MODELO_PADRAO
}

/**
 * O corpo do OpenRouter pede `input_audio.format` como extensão curta
 * (webm/mp4/wav), não o mime completo do `MediaRecorder` do navegador
 * (que vem como `audio/webm;codecs=opus`, por exemplo) — daí a derivação
 * em vez de repassar `blob.type` direto.
 */
function formatoDoMime(mime: string): 'webm' | 'mp4' | 'wav' {
  if (mime.includes('wav')) return 'wav'
  if (mime.includes('mp4') || mime.includes('m4a')) return 'mp4'
  return 'webm'
}

export async function openrouterTranscribe(
  audio: Blob,
  opts: TranscribeOpts = {},
): Promise<TranscribeResult> {
  const key = requireKey()
  const buffer = await audio.arrayBuffer()
  const data = Buffer.from(buffer).toString('base64')
  const format = formatoDoMime(audio.type || '')

  const controller = new AbortController()
  const t = setTimeout(() => controller.abort(), 60_000)
  try {
    const res = await fetch(`${BASE_URL}/audio/transcriptions`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${key}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: opts.model ?? modeloConfigurado(),
        input_audio: { data, format },
        ...(opts.language ? { language: opts.language } : {}),
      }),
    })
    if (!res.ok) {
      throw new LlmError(await readError(res), res.status)
    }
    const corpo = await res.json()
    if (typeof corpo?.text !== 'string') {
      throw new LlmError('Resposta OpenRouter sem text', 502)
    }
    const usageBruto = corpo?.usage
    const numeroOuUndefined = (v: unknown): number | undefined => (typeof v === 'number' ? v : undefined)
    const usage: TranscribeUsage | undefined = usageBruto && typeof usageBruto === 'object'
      ? { seconds: numeroOuUndefined(usageBruto.seconds), cost: numeroOuUndefined(usageBruto.cost) }
      : undefined
    return { text: corpo.text, ...(usage ? { usage } : {}) }
  } catch (e) {
    if ((e as { name?: string } | null)?.name === 'AbortError') {
      throw new LlmError('Timeout — IA demorou demais', 504)
    }
    throw e
  } finally {
    clearTimeout(t)
  }
}
