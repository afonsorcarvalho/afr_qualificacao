import { describe, it, expect, vi, afterEach } from 'vitest'
import { llmChat, LlmError } from './client'

const originalFetch = globalThis.fetch

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('llmChat', () => {
  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('posta em <baseUrl>/chat/completions com Bearer e repassa tools e extraBody', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      respond({ choices: [{ message: { content: 'olá', tool_calls: null } }] }),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const tools = [
      {
        type: 'function' as const,
        function: { name: 'buscar_agenda', description: 'd', parameters: { type: 'object' } },
      },
    ]
    const turn = await llmChat([{ role: 'user', content: 'oi' }], {
      baseUrl: 'https://openrouter.ai/api/v1',
      apiKey: 'sk-test',
      model: 'google/gemma-4-31b-it:free',
      tools,
      extraBody: { provider: { ignore: ['nvidia'] }, reasoning: { enabled: false } },
    })

    expect(turn).toEqual({ content: 'olá', tool_calls: [] })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://openrouter.ai/api/v1/chat/completions')
    const headers = new Headers((init as RequestInit).headers)
    expect(headers.get('Authorization')).toBe('Bearer sk-test')
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body.model).toBe('google/gemma-4-31b-it:free')
    expect(body.tools).toEqual(tools)
    expect(body.provider).toEqual({ ignore: ['nvidia'] })
    expect(body.reasoning).toEqual({ enabled: false })
  })

  it('normaliza tool_calls ausente para lista vazia e content ausente para null', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      respond({ choices: [{ message: {} }] }),
    ) as unknown as typeof fetch

    const turn = await llmChat([{ role: 'user', content: 'oi' }], {
      baseUrl: 'https://x/v1', apiKey: 'k', model: 'm',
    })
    expect(turn).toEqual({ content: null, tool_calls: [] })
  })

  it('devolve tool_calls quando o modelo pede ferramenta', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      respond({
        choices: [{
          message: {
            content: null,
            tool_calls: [{
              id: 'call_1',
              type: 'function',
              function: { name: 'buscar_agenda', arguments: '{"date_from":"2026-10-12"}' },
            }],
          },
        }],
      }),
    ) as unknown as typeof fetch

    const turn = await llmChat([{ role: 'user', content: 'oi' }], {
      baseUrl: 'https://x/v1', apiKey: 'k', model: 'm',
    })
    expect(turn.tool_calls).toHaveLength(1)
    expect(turn.tool_calls[0].function.name).toBe('buscar_agenda')
  })

  it('lança LlmError com o status em resposta de erro', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      respond({ error: { message: 'rate limited' } }, 429),
    ) as unknown as typeof fetch

    await expect(
      llmChat([{ role: 'user', content: 'oi' }], { baseUrl: 'https://x/v1', apiKey: 'k', model: 'm' }),
    ).rejects.toMatchObject({ name: 'LlmError', status: 429 })
  })

  it('lança LlmError 503 quando a apiKey é vazia', async () => {
    await expect(
      llmChat([{ role: 'user', content: 'oi' }], { baseUrl: 'https://x/v1', apiKey: '', model: 'm' }),
    ).rejects.toMatchObject({ name: 'LlmError', status: 503 })
  })

  it('lança LlmError 504 no timeout', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(
      Object.assign(new Error('aborted'), { name: 'AbortError' }),
    ) as unknown as typeof fetch

    await expect(
      llmChat([{ role: 'user', content: 'oi' }], {
        baseUrl: 'https://x/v1', apiKey: 'k', model: 'm', timeoutMs: 5,
      }),
    ).rejects.toMatchObject({ name: 'LlmError', status: 504 })
  })

  it('LlmError é instanciável com mensagem e status', () => {
    const e = new LlmError('x', 500)
    expect(e.status).toBe(500)
  })
})
