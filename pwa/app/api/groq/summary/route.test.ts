import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { NextRequest } from 'next/server'

vi.mock('@/lib/groq/client', () => ({
  groqChat: vi.fn(),
  GroqError: class GroqError extends Error {
    status: number
    constructor(msg: string, status: number) {
      super(msg)
      this.status = status
      this.name = 'GroqError'
    }
  },
}))

import { groqChat, GroqError } from '@/lib/groq/client'
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
  process.env.GROQ_API_KEY = 'gsk_test'
  vi.mocked(groqChat).mockReset()
})

afterEach(() => {
  delete process.env.GROQ_API_KEY
})

describe('POST /api/groq/summary', () => {
  it('retorna 401 sem cookie session_id', async () => {
    const res = await POST(makeRequest(validBody, { withCookie: false }) as any)
    expect(res.status).toBe(401)
  })

  it('retorna 503 sem GROQ_API_KEY', async () => {
    delete process.env.GROQ_API_KEY
    const res = await POST(makeRequest(validBody) as any)
    expect(res.status).toBe(503)
  })

  it('retorna 400 com body inválido', async () => {
    const res = await POST(makeRequest({ foo: 'bar' }) as any)
    expect(res.status).toBe(400)
  })

  it('chama groqChat com system + user e retorna summary', async () => {
    vi.mocked(groqChat).mockResolvedValue({ content: 'Autoclave 100L (AUT-001): ciclo de carga ok, sem anomalias.' })
    const res = await POST(makeRequest(validBody) as any)
    expect(res.status).toBe(200)
    const json = await res.json()
    expect(json.summary).toContain('Autoclave 100L')

    const [messages, opts] = vi.mocked(groqChat).mock.calls[0]
    expect(messages[0].role).toBe('system')
    expect(messages[1].role).toBe('user')
    expect(messages[1].content).toContain('QOS00012')
    expect(opts.model).toBe('llama-3.3-70b-versatile')
    expect(opts.temperature).toBe(0.3)
  })

  it('propaga status code de GroqError', async () => {
    vi.mocked(groqChat).mockRejectedValue(new (GroqError as any)('rate limit', 429))
    const res = await POST(makeRequest(validBody) as any)
    expect(res.status).toBe(429)
  })
})
