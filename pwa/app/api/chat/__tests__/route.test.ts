import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const originalFetch = globalThis.fetch
const originalKey = process.env.OPENROUTER_API_KEY
const originalModels = process.env.OPENROUTER_MODELS

function req(body: unknown, sessionId?: string) {
  const bodyStr = typeof body === 'string' ? body : JSON.stringify(body)
  const headers = new Headers({ 'Content-Type': 'application/json' })
  if (sessionId) {
    headers.append('Cookie', `session_id=${sessionId}`)
  }
  // Mock simples de NextRequest: estender com .cookies que as rotas usam
  const request = new Request('http://localhost/api/chat', {
    method: 'POST',
    headers,
    body: bodyStr,
  })

  // Mock de cookies.get() que o route.ts chama
  Object.defineProperty(request, 'cookies', {
    value: {
      get: (name: string) => {
        if (name === 'session_id' && sessionId) {
          return { value: sessionId }
        }
        return undefined
      },
    },
    configurable: true,
  })

  return request as never
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
  it('devolve 401 sem session_id', async () => {
    const { POST } = await import('../route')
    const res = await POST(req(corpoValido) as never)
    expect(res.status).toBe(401)
    expect(await res.json()).toEqual({ error: 'Sessão expirada' })
  })

  it('devolve 400 com JSON inválido', async () => {
    const { POST } = await import('../route')
    const res = await POST(req('{nao json', 'test') as never)
    expect(res.status).toBe(400)
  })

  it('devolve 400 quando messages não é lista', async () => {
    const { POST } = await import('../route')
    const res = await POST(req({ messages: 'oi' }, 'test') as never)
    expect(res.status).toBe(400)
  })

  it('devolve 400 quando messages vazia', async () => {
    const { POST } = await import('../route')
    const res = await POST(req({ messages: [] }, 'test') as never)
    expect(res.status).toBe(400)
  })

  it('devolve 400 quando excede 40 mensagens', async () => {
    const { POST } = await import('../route')
    const messages = Array(41).fill({ role: 'user', content: 'oi' })
    const res = await POST(req({ messages }, 'test') as never)
    expect(res.status).toBe(400)
  })

  it('devolve 400 quando content ultrapassa 8000 caracteres', async () => {
    const { POST } = await import('../route')
    const messages = [{ role: 'user', content: 'a'.repeat(8001) }]
    const res = await POST(req({ messages }, 'test') as never)
    expect(res.status).toBe(400)
  })

  it('devolve 400 quando role é inválido', async () => {
    const { POST } = await import('../route')
    const messages = [{ role: 'invalid_role', content: 'oi' }]
    const res = await POST(req({ messages }, 'test') as never)
    expect(res.status).toBe(400)
  })

  it('devolve 503 sem OPENROUTER_API_KEY', async () => {
    process.env.OPENROUTER_API_KEY = ''
    const { POST } = await import('../route')
    const res = await POST(req(corpoValido, 'test') as never)
    expect(res.status).toBe(503)
  })

  it('injeta tools, política de provedor e reasoning desligado no corpo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok({ content: 'oi', tool_calls: null }))
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { POST } = await import('../route')
    const res = await POST(req(corpoValido, 'test') as never)

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
    const res = await POST(req(corpoValido, 'test') as never)

    expect(res.status).toBe(200)
    expect(await res.json()).toMatchObject({ content: 'oi', model: 'modelo/b:free' })
    expect(JSON.parse(fetchMock.mock.calls[1][1].body as string).model).toBe('modelo/b:free')
    // Verificar que as mensagens foram passadas ao retry
    expect(JSON.parse(fetchMock.mock.calls[1][1].body as string).messages).toEqual(corpoValido.messages)
  })

  it('cadeia esgotada devolve o status do último erro', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { message: 'rate' } }), { status: 429 }),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { POST } = await import('../route')
    const res = await POST(req(corpoValido, 'test') as never)
    expect(res.status).toBe(429)
    expect((await res.json()).error).toMatch(/indisponível/i)
    // Verificar que ambos os modelos foram tentados
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('erro de argumento (400) NÃO tenta o próximo modelo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { message: 'bad request' } }), { status: 400 }),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const { POST } = await import('../route')
    const res = await POST(req(corpoValido, 'test') as never)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(res.status).toBe(400)
  })

  it('erro genérico (não-LlmError) devolve 502 com JSON', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Network error'))
    const { POST } = await import('../route')
    const res = await POST(req(corpoValido, 'test') as never)
    expect(res.status).toBe(502)
    expect(await res.json()).toEqual({ error: 'Falha na conexão com a IA' })
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

describe('fronteira de escrita — verificar import chain completa', () => {
  it('route.ts não importa lib/odoo nem chat/tools (direto)', () => {
    const fonte = fs.readFileSync(
      path.resolve(__dirname, '../route.ts'), 'utf-8',
    )
    // Procurar por imports reais, não comentários
    expect(fonte).not.toMatch(/from\s+['"]@?\/lib\/odoo/)
    expect(fonte).not.toMatch(/from\s+['"]@?\/lib\/chat\/tools/)
  })

  it('dependências (lib/llm/client e lib/chat/toolDefs) também não contêm imports de lib/odoo (transitive)', () => {
    // Verificar que os dois módulos que route.ts importa não contêm
    // lib/odoo, garantindo que nenhuma import transitiva quebra a barreira.
    // Procuramos por imports reais (from/import statements), não comentários.
    const toolDefs = fs.readFileSync(
      path.resolve(__dirname, '../../../../lib/chat/toolDefs.ts'), 'utf-8',
    )
    const llmClient = fs.readFileSync(
      path.resolve(__dirname, '../../../../lib/llm/client.ts'), 'utf-8',
    )
    // Nota: um grep de fonte é imperfeito — não vê imports dinâmicos ou
    // via eval — mas é suficiente para catch regressions manuais.
    expect(toolDefs).not.toMatch(/from\s+['"]@?\/lib\/odoo/)
    expect(llmClient).not.toMatch(/from\s+['"]@?\/lib\/odoo/)
  })
})
