import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { openrouterTranscribe } from './transcribe'

const originalFetch = globalThis.fetch
const originalKey = process.env.OPENROUTER_API_KEY
const originalModel = process.env.OPENROUTER_STT_MODEL

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('openrouterTranscribe', () => {
  beforeEach(() => {
    process.env.OPENROUTER_API_KEY = 'sk-or-test'
    delete process.env.OPENROUTER_STT_MODEL
  })
  afterEach(() => {
    globalThis.fetch = originalFetch
    process.env.OPENROUTER_API_KEY = originalKey
    process.env.OPENROUTER_STT_MODEL = originalModel
  })

  it('envia JSON (não multipart) com input_audio.data em base64 — multipart falha em silêncio com 400 no OpenRouter', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond({ text: 'transcrito' }))
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const audio = new Blob(['fake-audio'], { type: 'audio/webm' })
    await openrouterTranscribe(audio)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://openrouter.ai/api/v1/audio/transcriptions')
    expect((init as RequestInit).method).toBe('POST')
    const headers = new Headers((init as RequestInit).headers)
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Authorization')).toBe('Bearer sk-or-test')
    expect(typeof (init as RequestInit).body).toBe('string')
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body.input_audio.data).toBe(Buffer.from('fake-audio').toString('base64'))
  })

  it.each([
    ['audio/webm;codecs=opus', 'webm'],
    ['audio/webm', 'webm'],
    ['audio/mp4', 'mp4'],
    ['audio/wav', 'wav'],
  ])('mime %s do blob vira input_audio.format %s', async (mime, formatoEsperado) => {
    const fetchMock = vi.fn().mockResolvedValue(respond({ text: 'ok' }))
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const audio = new Blob(['x'], { type: mime })
    await openrouterTranscribe(audio)

    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body.input_audio.format).toBe(formatoEsperado)
  })

  it('inclui language no corpo quando informado', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond({ text: 'ok' }))
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const audio = new Blob(['x'], { type: 'audio/webm' })
    await openrouterTranscribe(audio, { language: 'pt' })

    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body.language).toBe('pt')
  })

  it('omite language do corpo quando não informado', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond({ text: 'ok' }))
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const audio = new Blob(['x'], { type: 'audio/webm' })
    await openrouterTranscribe(audio)

    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse((init as RequestInit).body as string)
    expect('language' in body).toBe(false)
  })

  it('usa o modelo default openai/whisper-large-v3-turbo quando OPENROUTER_STT_MODEL não está configurado', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond({ text: 'ok' }))
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const audio = new Blob(['x'], { type: 'audio/webm' })
    await openrouterTranscribe(audio)

    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body.model).toBe('openai/whisper-large-v3-turbo')
  })

  it('usa OPENROUTER_STT_MODEL quando configurado, sobrescrevendo o default', async () => {
    process.env.OPENROUTER_STT_MODEL = 'openai/whisper-large-v3'
    const fetchMock = vi.fn().mockResolvedValue(respond({ text: 'ok' }))
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const audio = new Blob(['x'], { type: 'audio/webm' })
    await openrouterTranscribe(audio)

    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body.model).toBe('openai/whisper-large-v3')
  })

  it('devolve text e usage no formato real medido contra a API (200 com seconds/cost)', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      respond({ text: ' E aí', usage: { seconds: 1, cost: 0.00000333 } }),
    ) as unknown as typeof fetch

    const audio = new Blob(['x'], { type: 'audio/webm' })
    const result = await openrouterTranscribe(audio)

    expect(result).toEqual({ text: ' E aí', usage: { seconds: 1, cost: 0.00000333 } })
  })

  it('resposta 200 sem text string vira LlmError, não undefined vazando pro chamador', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(respond({ usage: { seconds: 1 } })) as unknown as typeof fetch

    const audio = new Blob(['x'], { type: 'audio/webm' })
    await expect(openrouterTranscribe(audio)).rejects.toMatchObject({ name: 'LlmError' })
  })

  it('resposta não-ok vira LlmError com a mensagem do corpo', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      respond({ error: { message: 'áudio inválido' } }, 400),
    ) as unknown as typeof fetch

    const audio = new Blob(['x'], { type: 'audio/webm' })
    await expect(openrouterTranscribe(audio)).rejects.toMatchObject({
      name: 'LlmError',
      status: 400,
      message: 'áudio inválido',
    })
  })

  it('lança LlmError 503 quando OPENROUTER_API_KEY não está configurada', async () => {
    process.env.OPENROUTER_API_KEY = ''
    const audio = new Blob(['x'], { type: 'audio/webm' })
    await expect(openrouterTranscribe(audio)).rejects.toMatchObject({ name: 'LlmError', status: 503 })
  })

  it('preserva o timeout de 60s: aborta e vira LlmError 504, sem travar o chamador indefinidamente', async () => {
    vi.useFakeTimers()
    try {
      globalThis.fetch = vi.fn((_url: string, init?: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            reject(Object.assign(new Error('aborted'), { name: 'AbortError' }))
          })
        })
      }) as unknown as typeof fetch

      const audio = new Blob(['x'], { type: 'audio/webm' })
      const promise = openrouterTranscribe(audio)
      const expectation = expect(promise).rejects.toMatchObject({ name: 'LlmError', status: 504 })
      await vi.advanceTimersByTimeAsync(60_000)
      await expectation
    } finally {
      vi.useRealTimers()
    }
  })
})
