import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { NextRequest } from 'next/server'

vi.mock('@/lib/llm/client', () => ({
  llmChat: vi.fn(),
  LlmError: class LlmError extends Error {
    status: number
    constructor(msg: string, status: number) {
      super(msg)
      this.status = status
      this.name = 'LlmError'
    }
  },
}))

import { llmChat, LlmError } from '@/lib/llm/client'
import { POST } from './route'

function makeRequest(body: unknown, opts: { withCookie?: boolean } = { withCookie: true }) {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  if (opts.withCookie) headers.set('cookie', 'session_id=fake')
  return new NextRequest('http://localhost/api/groq/summary', {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
}

const validBody = {
  os_name: 'QOS00012',
  equipments: [
    {
      tag: 'AUT-001',
      name: 'Autoclave 100L',
      items: [
        { name: 'Ciclo carga', status: 'collected', obs: 'OK', at: '2026-05-18 09:15' },
      ],
    },
  ],
}

beforeEach(() => {
  process.env.OPENROUTER_API_KEY = 'sk-or-test'
  vi.mocked(llmChat).mockReset()
})

afterEach(() => {
  delete process.env.OPENROUTER_API_KEY
})

describe('POST /api/groq/summary', () => {
  it('retorna 401 sem cookie session_id', async () => {
    const res = await POST(makeRequest(validBody, { withCookie: false }) as any)
    expect(res.status).toBe(401)
  })

  it('retorna 503 sem OPENROUTER_API_KEY', async () => {
    delete process.env.OPENROUTER_API_KEY
    const res = await POST(makeRequest(validBody) as any)
    expect(res.status).toBe(503)
  })

  it('retorna 400 com body inválido', async () => {
    const res = await POST(makeRequest({ foo: 'bar' }) as any)
    expect(res.status).toBe(400)
  })

  it('chama llmChat com system + user e retorna summary', async () => {
    vi.mocked(llmChat).mockResolvedValue({
      content: 'Autoclave 100L (AUT-001): ciclo de carga ok, sem anomalias.',
      tool_calls: [],
    })
    const res = await POST(makeRequest(validBody) as any)
    expect(res.status).toBe(200)
    const json = await res.json()
    expect(json.summary).toContain('Autoclave 100L')

    const [messages, opts] = vi.mocked(llmChat).mock.calls[0]
    expect(messages[0].role).toBe('system')
    expect(messages[1].role).toBe('user')
    expect(messages[1].content).toContain('QOS00012')
    expect(opts.baseUrl).toBe('https://openrouter.ai/api/v1')
    expect(opts.apiKey).toBe('sk-or-test')
    expect(opts.model).toBe('meta-llama/llama-3.3-70b-instruct')
    expect(opts.temperature).toBe(0.3)
  })

  it('retorna 502 se llmChat devolve content nulo', async () => {
    vi.mocked(llmChat).mockResolvedValue({ content: null, tool_calls: [] })
    const res = await POST(makeRequest(validBody) as any)
    expect(res.status).toBe(502)
  })

  it('propaga status code de LlmError', async () => {
    vi.mocked(llmChat).mockRejectedValue(new (LlmError as any)('rate limit', 429))
    const res = await POST(makeRequest(validBody) as any)
    expect(res.status).toBe(429)
  })
})
