import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { groqChat, groqTranscribe, GroqError } from './client'

const originalFetch = globalThis.fetch
const originalKey = process.env.GROQ_API_KEY

describe('groqChat', () => {
  beforeEach(() => {
    process.env.GROQ_API_KEY = 'gsk_test'
  })
  afterEach(() => {
    globalThis.fetch = originalFetch
    process.env.GROQ_API_KEY = originalKey
  })

  it('envia POST para /openai/v1/chat/completions com Bearer auth', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ choices: [{ message: { content: 'olá' } }] }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const result = await groqChat([{ role: 'user', content: 'oi' }], {
      model: 'llama-3.3-70b-versatile',
      temperature: 0.3,
    })

    expect(result).toEqual({ content: 'olá' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://api.groq.com/openai/v1/chat/completions')
    expect((init as RequestInit).method).toBe('POST')
    const headers = new Headers((init as RequestInit).headers)
    expect(headers.get('Authorization')).toBe('Bearer gsk_test')
    expect(headers.get('Content-Type')).toBe('application/json')
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body.model).toBe('llama-3.3-70b-versatile')
    expect(body.temperature).toBe(0.3)
    expect(body.messages).toEqual([{ role: 'user', content: 'oi' }])
  })

  it('lança GroqError com status em resposta 4xx', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { message: 'bad' } }), { status: 429 }),
    ) as unknown as typeof fetch

    await expect(
      groqChat([{ role: 'user', content: 'oi' }], { model: 'x' }),
    ).rejects.toMatchObject({ name: 'GroqError', status: 429 })
  })

  it('lança GroqError se GROQ_API_KEY estiver vazio', async () => {
    process.env.GROQ_API_KEY = ''
    await expect(
      groqChat([{ role: 'user', content: 'oi' }], { model: 'x' }),
    ).rejects.toMatchObject({ name: 'GroqError', status: 503 })
  })
})

describe('groqTranscribe', () => {
  beforeEach(() => {
    process.env.GROQ_API_KEY = 'gsk_test'
  })
  afterEach(() => {
    globalThis.fetch = originalFetch
    process.env.GROQ_API_KEY = originalKey
  })

  it('envia multipart/form-data com file, model e language', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'transcrito' }), { status: 200 }),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const audio = new Blob(['fake-audio'], { type: 'audio/webm' })
    const result = await groqTranscribe(audio, { language: 'pt' })

    expect(result).toEqual({ text: 'transcrito' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://api.groq.com/openai/v1/audio/transcriptions')
    expect((init as RequestInit).method).toBe('POST')
    const body = (init as RequestInit).body as FormData
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('model')).toBe('whisper-large-v3-turbo')
    expect(body.get('language')).toBe('pt')
    expect(body.get('file')).toBeInstanceOf(File)
  })
})
