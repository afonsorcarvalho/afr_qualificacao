import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const originalFetch = globalThis.fetch
const originalKey = process.env.OPENROUTER_API_KEY
const originalModels = process.env.OPENROUTER_MODELS

function req(body: unknown) {
  return new Request('http://localhost/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  })
}
function ok(message: unknown) {
  return new Response(JSON.stringify({ choices: [{ message }] }), {
    status: 200, headers: { 'Content-Type': 'application/json' },
  })
}
const corpoValido = { messages: [{ role: 'user', content: 'oi' }] }

beforeEach(() => {
  process.env.OPENROUTER_API_KEY = 'sk-or-test'
  process.env.OPENROUTER_MODELS = 'modelo/a:free,modelo/b:free'
  vi.resetModules()
})
afterEach(() => {
  globalThis.fetch = originalFetch
  process.env.OPENROUTER_API_KEY = originalKey
  process.env.OPENROUTER_MODELS = originalModels
})

describe('POST /api/chat', () => {
  it('devolve 400 com JSON inválido', async () => {
    const { POST } = await import('../route')
    const res = await POST(req('{nao json') as never)
    expect(res.status).toBe(400)
  })

  it('devolve 400 quando messages não é lista', async () => {
    const { POST } = await import('../route')
    const res = await POST(req({ messages: 'oi' }) as never)
    expect(res.status).toBe(400)
  })

  it('devolve 503 sem OPENROUTER_API_KEY', async () => {
    process.env.OPENROUTER_API_KEY = ''
    const { POST } = await import('../route')
    const res = await POST(req(corpoValido) as never)
    expect(res.status).toBe(503)
  })

  it('injeta tools, política de provedor e reasoning desligado no corpo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok({ content: 'oi', tool_calls: null }))
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { POST } = await import('../route')
    const res = await POST(req(corpoValido) as never)

    expect(res.status).toBe(200)
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string)
    expect(body.model).toBe('modelo/a:free')
    expect(body.tools.map((t: any) => t.function.name)).toContain('buscar_agenda')
    expect(body.tools.map((t: any) => t.function.name)).not.toContain('excluir_visita')
    expect(body.provider).toEqual({
      ignore: ['nvidia', 'liquid', 'thinkingmachines'],
      require_parameters: true,
    })
    expect(body.reasoning).toEqual({ enabled: false })
  })

  it('cai para o próximo modelo da cadeia em 429 e informa qual respondeu', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { message: 'rate' } }), { status: 429 }))
      .mockResolvedValueOnce(ok({ content: 'oi', tool_calls: null }))
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { POST } = await import('../route')
    const res = await POST(req(corpoValido) as never)

    expect(res.status).toBe(200)
    expect(await res.json()).toMatchObject({ content: 'oi', model: 'modelo/b:free' })
    expect(JSON.parse(fetchMock.mock.calls[1][1].body as string).model).toBe('modelo/b:free')
  })

  it('cadeia esgotada devolve o status do último erro', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { message: 'rate' } }), { status: 429 }),
    ) as unknown as typeof fetch
    const { POST } = await import('../route')
    const res = await POST(req(corpoValido) as never)
    expect(res.status).toBe(429)
    expect((await res.json()).error).toMatch(/indisponível/i)
  })

  it('erro de argumento (400) NÃO tenta o próximo modelo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { message: 'bad request' } }), { status: 400 }),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { POST } = await import('../route')
    const res = await POST(req(corpoValido) as never)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(res.status).toBe(400)
  })
})

describe('GET /api/chat/status', () => {
  it('reflete a presença da chave', async () => {
    const { GET } = await import('../status/route')
    expect(await (await GET()).json()).toEqual({ enabled: true })
    process.env.OPENROUTER_API_KEY = ''
    vi.resetModules()
    const novo = await import('../status/route')
    expect(await (await novo.GET()).json()).toEqual({ enabled: false })
  })
})

describe('fronteira de escrita', () => {
  it('a rota não importa lib/odoo nem lib/chat/tools', () => {
    const fonte = fs.readFileSync(
      path.resolve(__dirname, '../route.ts'), 'utf-8',
    )
    expect(fonte).not.toMatch(/lib\/odoo/)
    expect(fonte).not.toMatch(/chat\/tools/)
  })
})
