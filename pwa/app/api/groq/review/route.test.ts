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
  return new NextRequest('http://localhost/api/groq/review', {
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
        { id: 42, name: 'Foto display', status: 'collected', obs: 'tela rachada', at: '2026-05-18 09:15' },
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

describe('POST /api/groq/review', () => {
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

  it('parseia JSON do LLM e retorna issues válidas', async () => {
    vi.mocked(groqChat).mockResolvedValue({
      content: JSON.stringify({
        verdict: 'warnings',
        issues: [
          {
            severity: 'warning',
            item_id: 42,
            type: 'contradiction',
            message: 'Foto display AUT-001: coletada mas obs menciona "tela rachada"',
            suggestion: 'Reabrir item e tirar nova foto ou marcar como pulada',
          },
        ],
      }),
    })
    const res = await POST(makeRequest(validBody) as any)
    expect(res.status).toBe(200)
    const json = await res.json()
    expect(json.verdict).toBe('warnings')
    expect(json.issues).toHaveLength(1)
    expect(json.issues[0].type).toBe('contradiction')
    expect(json.issues[0].item_id).toBe(42)
  })

  it('passa response_format json_object e temperature baixa pro groqChat', async () => {
    vi.mocked(groqChat).mockResolvedValue({
      content: JSON.stringify({ verdict: 'ok', issues: [] }),
    })
    await POST(makeRequest(validBody) as any)
    const [, opts] = vi.mocked(groqChat).mock.calls[0]
    expect(opts.response_format).toEqual({ type: 'json_object' })
    expect(opts.temperature).toBe(0.1)
    expect(opts.model).toBe('llama-3.3-70b-versatile')
  })

  it('descarta issues com type inválido e limita em 8', async () => {
    const eight = Array.from({ length: 12 }, (_, i) => ({
      severity: 'warning',
      item_id: i,
      type: 'contradiction',
      message: `msg ${i}`,
      suggestion: 's',
    }))
    eight.push({ severity: 'warning', item_id: 99, type: 'nao_existe' as any, message: 'x', suggestion: 'y' })
    vi.mocked(groqChat).mockResolvedValue({
      content: JSON.stringify({ verdict: 'warnings', issues: eight }),
    })
    const res = await POST(makeRequest(validBody) as any)
    const json = await res.json()
    expect(json.issues).toHaveLength(8)
    expect(json.issues.every((i: any) => i.type === 'contradiction')).toBe(true)
  })

  it('retorna verdict ok se LLM devolve JSON quebrado', async () => {
    vi.mocked(groqChat).mockResolvedValue({ content: 'not json' })
    const res = await POST(makeRequest(validBody) as any)
    const json = await res.json()
    expect(json.verdict).toBe('ok')
    expect(json.issues).toEqual([])
  })

  it('propaga status code de GroqError', async () => {
    vi.mocked(groqChat).mockRejectedValue(new (GroqError as any)('rate limit', 429))
    const res = await POST(makeRequest(validBody) as any)
    expect(res.status).toBe(429)
  })
})
