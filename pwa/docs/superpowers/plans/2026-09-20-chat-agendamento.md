# Chat de Agendamento no PWA — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao Gestor um chat em linguagem natural na tela da agenda que consulta, cria e remarca visitas de campo, sempre com confirmação humana antes de gravar.

**Architecture:** O loop do agente é partido em dois. Uma rota Next.js stateless (`/api/chat`) faz UM turno do modelo no OpenRouter e nunca fala com o Odoo. O cliente executa as ferramentas: as de leitura rodam soltas dentro do loop, as de escrita param o loop e viram um card de proposta que o Gestor confirma. Toda escrita passa pelas RPCs `pwa_*` que já existem, com sua ACL, whitelist de campos e trava de estado da OS.

**Tech Stack:** Next.js 14 (App Router), TypeScript, React Query v5, Radix (via `BottomSheet`), Vitest + happy-dom, OpenRouter (wire OpenAI-compatível).

**Spec:** `pwa/docs/superpowers/specs/2026-09-20-chat-agendamento-design.md`

## Global Constraints

- **Nenhuma RPC de escrita nova no Odoo.** Nenhum arquivo fora de `addons/afr_qualificacao/pwa/` é tocado. Nenhum arquivo de `addons/afr_qualificacao_agendamento/` é tocado.
- **`pwa_visita_delete` NÃO é exposto ao modelo.** Não existe ferramenta `excluir_visita`.
- **`app/api/chat/route.ts` não pode importar nada de `lib/odoo`.** Essa fronteira é testada.
- **Datas sempre ISO absolutas** (`YYYY-MM-DD`). O modelo nunca deduz "hoje": recebe `server_today` de `pwa_agenda_fetch`.
- **Teto de 4 voltas de ferramenta por pedido** (`MAX_TOOL_ROUNDS = 4`).
- **Chave só no servidor.** `OPENROUTER_API_KEY` nunca em `NEXT_PUBLIC_*`.
- **Cadeia de modelos:** `google/gemma-4-31b-it:free,google/gemma-4-26b-a4b-it:free,qwen/qwen3.8-27b:free`.
- **Bloco de provedor injetado no servidor:** `{"ignore": ["nvidia","liquid","thinkingmachines"], "require_parameters": true}`. Nunca `zdr: true` nem `data_collection: "deny"`.
- **Thinking desligado:** `reasoning: {enabled: false}` no corpo.
- **Mudança só de front:** NÃO bumpar `__manifest__.py`. A versão do PWA vive em `package.json`.
- **Idioma:** código e identificadores em inglês quando o arquivo já é assim; nomes de ferramenta e textos de UI em pt-BR, seguindo o padrão do módulo. Comentários em pt-BR, como o resto do `pwa/`.
- **Rodar testes** com `npx vitest run <caminho>` a partir de `addons/afr_qualificacao/pwa`.
- **Commits** a partir de `/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao` (o submodule), com paths relativos a ele (`pwa/...`). Sem push e sem bump de pointer.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `lib/llm/client.ts` | Cliente HTTP OpenAI-compatível com suporte a `tools`. Genérico: baseUrl, key e model vêm por parâmetro. |
| `lib/groq/client.ts` | (modificar) Passa a delegar para `lib/llm/client.ts`, preservando `GroqError` e a assinatura pública. |
| `lib/chat/toolDefs.ts` | Só os JSON Schemas das ferramentas e a marca `read`/`write`. **Puro** — nenhum import de `lib/odoo`, para a rota poder importá-lo. |
| `lib/chat/tools.ts` | Dispatch: nome de ferramenta → função de `lib/odoo/agenda.ts`. Importa `toolDefs`. |
| `lib/chat/prompt.ts` | Monta o system prompt a partir de `server_today`, roster de técnicos e janela visível. |
| `lib/chat/machine.ts` | O loop: executa leituras, para nas escritas, valida datas e ids, aplica o teto de voltas. |
| `app/api/chat/route.ts` | Um turno do modelo. Injeta política de provedor e cadeia de fallback. |
| `app/api/chat/status/route.ts` | `{enabled}` conforme a chave. |
| `lib/hooks/useChatStatus.ts` | Espelha `useGroqStatus` para `/api/chat/status`. |
| `lib/hooks/useChatAgenda.ts` | Cola React: estado do transcript, chamada da máquina, invalidação do React Query. |
| `app/tecnico/qualificacao/agenda/_ChatAgenda.tsx` | UI do chat: bolhas, card de proposta, entrada de texto e voz. |
| `app/tecnico/qualificacao/agenda/page.tsx` | (modificar) Monta o botão e o chat quando `can_manage`. |

---

### Task 1: Cliente LLM genérico com suporte a ferramentas

**Files:**
- Create: `lib/llm/client.ts`
- Create: `lib/llm/client.test.ts`
- Modify: `lib/groq/client.ts` (fazer `groqChat` delegar)

**Interfaces:**
- Consumes: nada.
- Produces: `LlmError`, `LlmMessage`, `LlmToolCall`, `LlmToolDef`, `LlmTurn`, `LlmOpts`, `llmChat(messages, opts): Promise<LlmTurn>`.

- [ ] **Step 1: Write the failing test**

Criar `lib/llm/client.test.ts`:

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run lib/llm/client.test.ts`
Expected: FAIL — `Failed to resolve import "./client"`.

- [ ] **Step 3: Write minimal implementation**

Criar `lib/llm/client.ts`:

```ts
// lib/llm/client.ts
// Cliente HTTP para qualquer endpoint com wire OpenAI-compatível (Groq,
// OpenRouter). Genérico de propósito: baseUrl, chave e modelo vêm por
// parâmetro, para não haver um segundo cliente quase igual no projeto.
export class LlmError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message)
    this.name = 'LlmError'
  }
}

export interface LlmToolCall {
  id: string
  type: 'function'
  function: { name: string; arguments: string }
}

export interface LlmMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string | null
  tool_calls?: LlmToolCall[]
  tool_call_id?: string
}

export interface LlmToolDef {
  type: 'function'
  function: {
    name: string
    description: string
    parameters: Record<string, unknown>
  }
}

export interface LlmOpts {
  baseUrl: string
  apiKey: string
  model: string
  tools?: LlmToolDef[]
  temperature?: number
  max_tokens?: number
  response_format?: { type: 'json_object' }
  /** Campos extras do corpo — no OpenRouter, `provider` e `reasoning`. */
  extraBody?: Record<string, unknown>
  timeoutMs?: number
}

export interface LlmTurn {
  content: string | null
  tool_calls: LlmToolCall[]
}

async function readError(res: Response): Promise<string> {
  try {
    const j = await res.json()
    return j?.error?.message || res.statusText
  } catch {
    return res.statusText
  }
}

export async function llmChat(
  messages: LlmMessage[],
  opts: LlmOpts,
): Promise<LlmTurn> {
  if (!opts.apiKey) {
    throw new LlmError('Chave de API não configurada', 503)
  }
  const controller = new AbortController()
  const t = setTimeout(() => controller.abort(), opts.timeoutMs ?? 30_000)
  try {
    const res = await fetch(`${opts.baseUrl}/chat/completions`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${opts.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: opts.model,
        messages,
        temperature: opts.temperature ?? 0.3,
        max_tokens: opts.max_tokens ?? 1500,
        ...(opts.tools ? { tools: opts.tools } : {}),
        ...(opts.response_format ? { response_format: opts.response_format } : {}),
        ...(opts.extraBody ?? {}),
      }),
    })
    if (!res.ok) {
      throw new LlmError(await readError(res), res.status)
    }
    const data = await res.json()
    const msg = data?.choices?.[0]?.message
    if (!msg || typeof msg !== 'object') {
      throw new LlmError('Resposta sem message', 502)
    }
    return {
      content: typeof msg.content === 'string' ? msg.content : null,
      tool_calls: Array.isArray(msg.tool_calls) ? msg.tool_calls : [],
    }
  } catch (e) {
    if ((e as { name?: string } | null)?.name === 'AbortError') {
      throw new LlmError('Timeout — IA demorou demais', 504)
    }
    throw e
  } finally {
    clearTimeout(t)
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run lib/llm/client.test.ts`
Expected: PASS — 7 testes.

- [ ] **Step 5: Fazer `groqChat` delegar, sem mudar a assinatura**

Em `lib/groq/client.ts`, substituir o corpo de `groqChat` (mantendo `GroqError`, `ChatMessage`, `ChatOpts`, `groqTranscribe` e `BASE_URL` exatamente como estão):

```ts
export async function groqChat(
  messages: ChatMessage[],
  opts: ChatOpts,
): Promise<{ content: string }> {
  try {
    const turn = await llmChat(messages as LlmMessage[], {
      baseUrl: BASE_URL,
      apiKey: process.env.GROQ_API_KEY ?? '',
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
```

E acrescentar no topo do arquivo:

```ts
import { llmChat, LlmError, type LlmMessage } from '@/lib/llm/client'
```

- [ ] **Step 6: Rodar os testes do Groq para provar que nada quebrou**

Run: `npx vitest run lib/groq/client.test.ts lib/llm/client.test.ts`
Expected: PASS em ambos. Os testes existentes de `groqChat` (Bearer, 429, chave vazia) continuam verdes sem edição.

- [ ] **Step 7: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/lib/llm/client.ts pwa/lib/llm/client.test.ts pwa/lib/groq/client.ts
git commit -m "feat(pwa): generic OpenAI-compatible LLM client with tool support

Adds lib/llm/client.ts so OpenRouter and Groq share one HTTP client
instead of two near-identical ones. groqChat now delegates to it and
keeps GroqError as its public surface, so review/summary are untouched.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Definições puras das ferramentas

**Files:**
- Create: `lib/chat/toolDefs.ts`
- Create: `lib/chat/toolDefs.test.ts`

**Interfaces:**
- Consumes: `LlmToolDef` de `lib/llm/client.ts`.
- Produces: `TOOL_DEFS: LlmToolDef[]`, `TOOL_KINDS: Record<string, 'read' | 'write'>`, `WRITE_TOOLS: readonly string[]`, `isWriteTool(name: string): boolean`.

Este arquivo existe separado de `tools.ts` por um motivo estrutural: `app/api/chat/route.ts` precisa das definições, mas **não pode** importar `lib/odoo`. Manter os schemas puros preserva essa fronteira.

- [ ] **Step 1: Write the failing test**

Criar `lib/chat/toolDefs.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { TOOL_DEFS, TOOL_KINDS, WRITE_TOOLS, isWriteTool } from './toolDefs'

const nomes = TOOL_DEFS.map((t) => t.function.name)

describe('TOOL_DEFS', () => {
  it('expõe exatamente as seis ferramentas previstas', () => {
    expect(nomes.sort()).toEqual([
      'atualizar_visita',
      'buscar_agenda',
      'criar_visita',
      'listar_instrumentos',
      'listar_os',
      'listar_tecnicos',
    ])
  })

  it('NÃO expõe excluir_visita', () => {
    expect(nomes).not.toContain('excluir_visita')
    expect(JSON.stringify(TOOL_DEFS)).not.toContain('delete')
  })

  it('marca leitura e escrita corretamente', () => {
    expect(TOOL_KINDS.buscar_agenda).toBe('read')
    expect(TOOL_KINDS.listar_tecnicos).toBe('read')
    expect(TOOL_KINDS.listar_instrumentos).toBe('read')
    expect(TOOL_KINDS.listar_os).toBe('read')
    expect(TOOL_KINDS.criar_visita).toBe('write')
    expect(TOOL_KINDS.atualizar_visita).toBe('write')
    expect([...WRITE_TOOLS].sort()).toEqual(['atualizar_visita', 'criar_visita'])
    expect(isWriteTool('criar_visita')).toBe(true)
    expect(isWriteTool('buscar_agenda')).toBe(false)
    expect(isWriteTool('inexistente')).toBe(false)
  })

  it('toda definição tem type function, descrição em pt-BR e parameters objeto', () => {
    for (const def of TOOL_DEFS) {
      expect(def.type).toBe('function')
      expect(def.function.description.length).toBeGreaterThan(20)
      expect(def.function.parameters.type).toBe('object')
    }
  })

  it('atualizar_visita aceita só os campos graváveis do PWA', () => {
    const def = TOOL_DEFS.find((t) => t.function.name === 'atualizar_visita')!
    const props = (def.function.parameters as Record<string, any>).properties
    expect(Object.keys(props).sort()).toEqual([
      'date', 'instrument_ids', 'note', 'tecnico_id', 'time_start', 'time_stop', 'visita_id',
    ])
    expect((def.function.parameters as Record<string, any>).required).toEqual(['visita_id'])
  })

  it('campos de data documentam o formato ISO absoluto', () => {
    const buscar = TOOL_DEFS.find((t) => t.function.name === 'buscar_agenda')!
    const p = (buscar.function.parameters as Record<string, any>).properties
    expect(p.date_from.description).toContain('AAAA-MM-DD')
    expect(p.date_to.description).toContain('AAAA-MM-DD')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run lib/chat/toolDefs.test.ts`
Expected: FAIL — `Failed to resolve import "./toolDefs"`.

- [ ] **Step 3: Write minimal implementation**

Criar `lib/chat/toolDefs.ts`:

```ts
// lib/chat/toolDefs.ts
// Só os schemas. Nenhum import de `lib/odoo` pode entrar aqui: a rota
// `/api/chat` importa este arquivo, e a fronteira "o servidor não fala com
// o Odoo" é testada. O dispatch mora em `lib/chat/tools.ts`.
import type { LlmToolDef } from '@/lib/llm/client'

const DATA = 'Data absoluta no formato AAAA-MM-DD. Nunca use datas relativas.'

export const TOOL_DEFS: LlmToolDef[] = [
  {
    type: 'function',
    function: {
      name: 'buscar_agenda',
      description:
        'Lista as visitas de campo agendadas numa janela de datas. Use antes de propor qualquer alteração, para descobrir o id da visita.',
      parameters: {
        type: 'object',
        properties: {
          date_from: { type: 'string', description: `Início da janela. ${DATA}` },
          date_to: { type: 'string', description: `Fim da janela. ${DATA}` },
        },
        required: ['date_from', 'date_to'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'listar_tecnicos',
      description:
        'Lista os técnicos disponíveis, com id e nome. Use para converter um nome dito pelo gestor no id correspondente.',
      parameters: { type: 'object', properties: {} },
    },
  },
  {
    type: 'function',
    function: {
      name: 'listar_instrumentos',
      description:
        'Lista os instrumentos de medição disponíveis, com id, tag e validade de calibração.',
      parameters: { type: 'object', properties: {} },
    },
  },
  {
    type: 'function',
    function: {
      name: 'listar_os',
      description:
        'Lista as ordens de serviço de qualificação que aceitam visita nova, com id e nome.',
      parameters: { type: 'object', properties: {} },
    },
  },
  {
    type: 'function',
    function: {
      name: 'criar_visita',
      description:
        'Cria uma visita nova para uma OS, com técnico e data. Esta ação grava: será mostrada ao gestor para confirmação antes de executar.',
      parameters: {
        type: 'object',
        properties: {
          os_id: { type: 'integer', description: 'Id da OS, vindo de listar_os.' },
          tecnico_id: { type: 'integer', description: 'Id do técnico, vindo de listar_tecnicos.' },
          date: { type: 'string', description: `Data da visita. ${DATA}` },
        },
        required: ['os_id', 'tecnico_id', 'date'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'atualizar_visita',
      description:
        'Altera uma visita existente: data, horário, técnico, instrumentos ou observação. Informe apenas os campos que mudam. Esta ação grava: será mostrada ao gestor para confirmação antes de executar.',
      parameters: {
        type: 'object',
        properties: {
          visita_id: { type: 'integer', description: 'Id da visita, vindo de buscar_agenda.' },
          date: { type: 'string', description: `Nova data. ${DATA}` },
          time_start: { type: 'number', description: 'Hora de início como float, ex.: 8.5 para 08:30.' },
          time_stop: { type: 'number', description: 'Hora de fim como float, ex.: 17.0 para 17:00.' },
          tecnico_id: { type: 'integer', description: 'Id do novo técnico, vindo de listar_tecnicos.' },
          note: { type: 'string', description: 'Observação da visita.' },
          instrument_ids: {
            type: 'array',
            items: { type: 'integer' },
            description: 'Lista completa de ids de instrumentos da visita; substitui a anterior.',
          },
        },
        required: ['visita_id'],
      },
    },
  },
]

export const TOOL_KINDS: Record<string, 'read' | 'write'> = {
  buscar_agenda: 'read',
  listar_tecnicos: 'read',
  listar_instrumentos: 'read',
  listar_os: 'read',
  criar_visita: 'write',
  atualizar_visita: 'write',
}

export const WRITE_TOOLS = ['criar_visita', 'atualizar_visita'] as const

export function isWriteTool(name: string): boolean {
  return TOOL_KINDS[name] === 'write'
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run lib/chat/toolDefs.test.ts`
Expected: PASS — 6 testes.

- [ ] **Step 5: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/lib/chat/toolDefs.ts pwa/lib/chat/toolDefs.test.ts
git commit -m "feat(pwa): tool schemas for the scheduling chat

Six tools mapping to the existing pwa_* RPCs. Kept free of lib/odoo
imports so the chat route can import them without gaining a write path
to Odoo. No delete tool is defined, and a test asserts that.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Dispatch das ferramentas para o Odoo

**Files:**
- Create: `lib/chat/tools.ts`
- Create: `lib/chat/tools.test.ts`

**Interfaces:**
- Consumes: `TOOL_DEFS`, `TOOL_KINDS` de `lib/chat/toolDefs.ts`; `fetchAgenda`, `updateVisita`, `createVisita`, `listTecnicoOptions`, `listOsOptions`, `listInstrumentoOptions` de `lib/odoo/agenda.ts`.
- Produces: `runTool(name: string, args: Record<string, unknown>): Promise<unknown>`, `ToolNotFoundError`.

- [ ] **Step 1: Write the failing test**

Criar `lib/chat/tools.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/odoo/agenda', () => ({
  fetchAgenda: vi.fn(),
  updateVisita: vi.fn(),
  createVisita: vi.fn(),
  listTecnicoOptions: vi.fn(),
  listOsOptions: vi.fn(),
  listInstrumentoOptions: vi.fn(),
}))

import * as agenda from '@/lib/odoo/agenda'
import { runTool, ToolNotFoundError } from './tools'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('runTool', () => {
  it('buscar_agenda repassa a janela e força only_mine=false', async () => {
    vi.mocked(agenda.fetchAgenda).mockResolvedValue({ visitas: [] } as never)
    await runTool('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' })
    expect(agenda.fetchAgenda).toHaveBeenCalledWith('2026-10-12', '2026-10-18', false)
  })

  it('atualizar_visita separa visita_id dos vals', async () => {
    vi.mocked(agenda.updateVisita).mockResolvedValue({ id: 87 } as never)
    await runTool('atualizar_visita', { visita_id: 87, date: '2026-10-16', tecnico_id: 3 })
    expect(agenda.updateVisita).toHaveBeenCalledWith(87, { date: '2026-10-16', tecnico_id: 3 })
  })

  it('atualizar_visita ignora chaves fora da whitelist do PWA', async () => {
    vi.mocked(agenda.updateVisita).mockResolvedValue({ id: 87 } as never)
    await runTool('atualizar_visita', { visita_id: 87, planned_hours: 9, state: 'done', note: 'x' })
    expect(agenda.updateVisita).toHaveBeenCalledWith(87, { note: 'x' })
  })

  it('criar_visita repassa os três argumentos posicionais', async () => {
    vi.mocked(agenda.createVisita).mockResolvedValue({ id: 99 } as never)
    await runTool('criar_visita', { os_id: 4, tecnico_id: 3, date: '2026-10-20' })
    expect(agenda.createVisita).toHaveBeenCalledWith(4, 3, '2026-10-20')
  })

  it('listar_* chamam as funções sem argumento', async () => {
    vi.mocked(agenda.listTecnicoOptions).mockResolvedValue([] as never)
    vi.mocked(agenda.listOsOptions).mockResolvedValue([] as never)
    vi.mocked(agenda.listInstrumentoOptions).mockResolvedValue([] as never)
    await runTool('listar_tecnicos', {})
    await runTool('listar_os', {})
    await runTool('listar_instrumentos', {})
    expect(agenda.listTecnicoOptions).toHaveBeenCalledWith()
    expect(agenda.listOsOptions).toHaveBeenCalledWith()
    expect(agenda.listInstrumentoOptions).toHaveBeenCalledWith()
  })

  it('ferramenta desconhecida lança ToolNotFoundError', async () => {
    await expect(runTool('excluir_visita', { visita_id: 1 })).rejects.toBeInstanceOf(
      ToolNotFoundError,
    )
  })

  it('não existe caminho para deleteVisita', async () => {
    const mod = await import('./tools')
    expect(JSON.stringify(Object.keys(mod))).not.toContain('delete')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run lib/chat/tools.test.ts`
Expected: FAIL — `Failed to resolve import "./tools"`.

- [ ] **Step 3: Write minimal implementation**

Criar `lib/chat/tools.ts`:

```ts
// lib/chat/tools.ts
// Dispatch das ferramentas do chat. Cada uma cai numa função que já existe
// em `lib/odoo/agenda.ts`, portanto numa RPC `pwa_*` com ACL, whitelist de
// campos e trava de estado da OS. Nenhum caminho de escrita novo.
import {
  fetchAgenda,
  updateVisita,
  createVisita,
  listTecnicoOptions,
  listOsOptions,
  listInstrumentoOptions,
  type VisitaVals,
} from '@/lib/odoo/agenda'

export class ToolNotFoundError extends Error {
  constructor(name: string) {
    super(`Ferramenta desconhecida: ${name}`)
    this.name = 'ToolNotFoundError'
  }
}

/** Espelha `_PWA_WRITABLE_FIELDS` do servidor. Chave fora disto é descartada. */
const CAMPOS_GRAVAVEIS = [
  'date', 'time_start', 'time_stop', 'tecnico_id', 'note', 'instrument_ids',
] as const

function montarVals(args: Record<string, unknown>): VisitaVals {
  const vals: Record<string, unknown> = {}
  for (const campo of CAMPOS_GRAVAVEIS) {
    if (args[campo] !== undefined) vals[campo] = args[campo]
  }
  return vals as VisitaVals
}

export async function runTool(
  name: string,
  args: Record<string, unknown>,
): Promise<unknown> {
  switch (name) {
    case 'buscar_agenda':
      // `only_mine` é sempre false: o chat é do Gestor, que enxerga a
      // equipe inteira. A ACL do servidor continua decidindo o que volta.
      return fetchAgenda(
        String(args.date_from ?? ''),
        String(args.date_to ?? ''),
        false,
      )
    case 'listar_tecnicos':
      return listTecnicoOptions()
    case 'listar_os':
      return listOsOptions()
    case 'listar_instrumentos':
      return listInstrumentoOptions()
    case 'criar_visita':
      return createVisita(
        Number(args.os_id),
        Number(args.tecnico_id),
        String(args.date),
      )
    case 'atualizar_visita':
      return updateVisita(Number(args.visita_id), montarVals(args))
    default:
      throw new ToolNotFoundError(name)
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run lib/chat/tools.test.ts`
Expected: PASS — 7 testes.

- [ ] **Step 5: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/lib/chat/tools.ts pwa/lib/chat/tools.test.ts
git commit -m "feat(pwa): dispatch chat tools onto the existing agenda RPCs

Every tool lands on a function already in lib/odoo/agenda.ts, so the
chat inherits the server ACL, the writable-field whitelist and the OS
state lock. atualizar_visita drops any key outside that whitelist before
the call rather than relying on the server to reject it.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: System prompt

**Files:**
- Create: `lib/chat/prompt.ts`
- Create: `lib/chat/prompt.test.ts`

**Interfaces:**
- Consumes: `VisitaAgenda`, `Opcao` de `lib/odoo/agenda.ts` (só como tipo).
- Produces: `buildSystemPrompt(ctx: PromptContext): string`, `interface PromptContext { serverToday: string; tecnicos: { id: number; name: string }[]; visitas: VisitaResumo[] }`, `interface VisitaResumo { id: number; date: string; os_name: string; tecnico_name: string; partner_name: string; time_start: number; time_stop: number }`, `resumirVisitas(visitas: VisitaAgenda[]): VisitaResumo[]`.

- [ ] **Step 1: Write the failing test**

Criar `lib/chat/prompt.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { buildSystemPrompt, resumirVisitas } from './prompt'

const ctx = {
  serverToday: '2026-10-14',
  tecnicos: [{ id: 3, name: 'João Silva' }, { id: 7, name: 'Ana Souza' }],
  visitas: [{
    id: 87, date: '2026-10-15', os_name: 'OS26-06-0002',
    tecnico_name: 'João Silva', partner_name: 'Hospital Central',
    time_start: 8, time_stop: 17,
  }],
}

describe('buildSystemPrompt', () => {
  it('injeta server_today e proíbe deduzir a data de hoje', () => {
    const p = buildSystemPrompt(ctx)
    expect(p).toContain('2026-10-14')
    expect(p).toMatch(/nunca.*deduz/i)
  })

  it('manda responder em português do Brasil, explicitamente', () => {
    expect(buildSystemPrompt(ctx)).toContain('português do Brasil')
  })

  it('declara a regra de ids: só os que vieram de ferramenta', () => {
    const p = buildSystemPrompt(ctx)
    expect(p).toMatch(/id/i)
    expect(p).toMatch(/nunca invente|não invente/i)
  })

  it('manda perguntar quando houver ambiguidade, em vez de escolher', () => {
    expect(buildSystemPrompt(ctx)).toMatch(/pergunte/i)
  })

  it('lista os técnicos com id e nome', () => {
    const p = buildSystemPrompt(ctx)
    expect(p).toContain('João Silva')
    expect(p).toContain('3')
    expect(p).toContain('Ana Souza')
  })

  it('lista as visitas visíveis com id, data e cliente', () => {
    const p = buildSystemPrompt(ctx)
    expect(p).toContain('87')
    expect(p).toContain('2026-10-15')
    expect(p).toContain('Hospital Central')
  })

  it('funciona com janela vazia', () => {
    const p = buildSystemPrompt({ ...ctx, visitas: [] })
    expect(p).toContain('2026-10-14')
    expect(p).toMatch(/nenhuma visita/i)
  })
})

describe('resumirVisitas', () => {
  it('reduz a visita do payload ao que o prompt precisa', () => {
    const r = resumirVisitas([{
      id: 87, date: '2026-10-15', time_start: 8, time_stop: 17,
      planned_hours: 9, os_id: 4, os_name: 'OS26-06-0002', os_state: 'draft',
      partner_name: 'Hospital Central', city: 'São Luís', equipment_list: [],
      instrument_ids: [], instrument_list: [], tecnico_id: 3,
      tecnico_name: 'João Silva', is_mine: false, state: 'draft',
      overflow: false, editable: true, lock_reason: false,
      conflict: false, conflict_msg: '', note: '',
    } as never])
    expect(r).toEqual([{
      id: 87, date: '2026-10-15', os_name: 'OS26-06-0002',
      tecnico_name: 'João Silva', partner_name: 'Hospital Central',
      time_start: 8, time_stop: 17,
    }])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run lib/chat/prompt.test.ts`
Expected: FAIL — `Failed to resolve import "./prompt"`.

- [ ] **Step 3: Write minimal implementation**

Criar `lib/chat/prompt.ts`:

```ts
// lib/chat/prompt.ts
// O system prompt vive em arquivo próprio porque carrega as regras que
// seguram a feature: idioma, data absoluta, proibição de inventar id e o
// dever de perguntar em caso de ambiguidade. Precisa ser versionado e
// testável, não escondido dentro de um componente.
import type { VisitaAgenda } from '@/lib/odoo/agenda'

export interface VisitaResumo {
  id: number
  date: string
  os_name: string
  tecnico_name: string
  partner_name: string
  time_start: number
  time_stop: number
}

export interface PromptContext {
  serverToday: string
  tecnicos: { id: number; name: string }[]
  visitas: VisitaResumo[]
}

export function resumirVisitas(visitas: VisitaAgenda[]): VisitaResumo[] {
  return visitas.map((v) => ({
    id: v.id,
    date: v.date,
    os_name: v.os_name,
    tecnico_name: v.tecnico_name,
    partner_name: v.partner_name,
    time_start: v.time_start,
    time_stop: v.time_stop,
  }))
}

function hora(f: number): string {
  const h = Math.floor(f)
  const m = Math.round((f - h) * 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

export function buildSystemPrompt(ctx: PromptContext): string {
  const tecnicos = ctx.tecnicos.length
    ? ctx.tecnicos.map((t) => `- id ${t.id}: ${t.name}`).join('\n')
    : '- (nenhum técnico carregado ainda; use listar_tecnicos)'

  const visitas = ctx.visitas.length
    ? ctx.visitas
        .map(
          (v) =>
            `- id ${v.id} | ${v.date} ${hora(v.time_start)}–${hora(v.time_stop)} | ${v.os_name} | ${v.partner_name} | técnico: ${v.tecnico_name}`,
        )
        .join('\n')
    : '- nenhuma visita na janela aberta na tela'

  return `Você é o assistente de agendamento de visitas de campo de uma empresa de qualificação de equipamentos hospitalares. Conversa com o GESTOR da equipe.

Responda sempre em português do Brasil, de forma curta e direta.

DATA DE HOJE: ${ctx.serverToday}
Esta data vem do servidor. Nunca deduza a data de hoje por conta própria e nunca confie em relógio de aparelho. Toda data que você passar a uma ferramenta é absoluta, no formato AAAA-MM-DD. Converta "quinta", "amanhã", "semana que vem" a partir de ${ctx.serverToday}.

REGRA DE IDENTIFICADORES: nunca invente um id. Só use os ids de visita, técnico, OS ou instrumento que apareceram no contexto abaixo ou no resultado de uma ferramenta que você já chamou nesta conversa. Se precisar de um id que não tem, chame a ferramenta de consulta primeiro.

AMBIGUIDADE: se o pedido casar com mais de uma visita, pergunte qual, citando data, OS e cliente. Nunca escolha por conta própria.

CONFLITOS: buscar_agenda devolve campos de conflito (técnico ocupado, deslocamento, instrumento, calibração vencida). Ao sugerir data ou horário, prefira o que não gera conflito. Se o gestor pedir um horário conflitante, proponha assim mesmo e avise do conflito na sua resposta.

ESCRITA: criar_visita e atualizar_visita não executam na hora — viram um pedido de confirmação para o gestor. Chame a ferramenta normalmente quando tiver certeza dos argumentos, e não pergunte "posso gravar?" antes: a confirmação já é mostrada na tela.

TÉCNICOS CONHECIDOS:
${tecnicos}

VISITAS NA JANELA ABERTA NA TELA:
${visitas}`
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run lib/chat/prompt.test.ts`
Expected: PASS — 8 testes.

- [ ] **Step 5: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/lib/chat/prompt.ts pwa/lib/chat/prompt.test.ts
git commit -m "feat(pwa): system prompt for the scheduling chat

Lives in its own file because it carries the load-bearing rules: answer
in pt-BR explicitly (the model is otherwise neutral between Portuguese
varieties), resolve dates from the injected server_today, never invent
an id, and ask instead of guessing when a request is ambiguous.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: A máquina do loop

**Files:**
- Create: `lib/chat/machine.ts`
- Create: `lib/chat/machine.test.ts`

**Interfaces:**
- Consumes: `LlmMessage`, `LlmTurn`, `LlmToolCall` de `lib/llm/client.ts`; `isWriteTool` de `lib/chat/toolDefs.ts`.
- Produces:
  - `MAX_TOOL_ROUNDS = 4`
  - `interface Proposta { toolCallId: string; name: string; args: Record<string, unknown>; resumo: string }`
  - `type PassoResultado = { kind: 'text'; messages: LlmMessage[]; text: string } | { kind: 'proposal'; messages: LlmMessage[]; proposta: Proposta } | { kind: 'error'; messages: LlmMessage[]; erro: string }`
  - `interface MachineDeps { callModel: (messages: LlmMessage[]) => Promise<LlmTurn>; runTool: (name: string, args: Record<string, unknown>) => Promise<unknown>; idsVistos: Set<number> }`
  - `coletarIds(valor: unknown, destino: Set<number>): void`
  - `isDataIso(v: unknown): boolean`
  - `runTurn(messages: LlmMessage[], deps: MachineDeps): Promise<PassoResultado>`
  - `confirmarEscrita(messages: LlmMessage[], proposta: Proposta, deps: MachineDeps): Promise<PassoResultado>`

- [ ] **Step 1: Write the failing test**

Criar `lib/chat/machine.test.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import {
  runTurn, confirmarEscrita, coletarIds, isDataIso, MAX_TOOL_ROUNDS,
} from './machine'
import type { LlmTurn, LlmMessage } from '@/lib/llm/client'

function texto(t: string): LlmTurn {
  return { content: t, tool_calls: [] }
}
function chamada(name: string, args: unknown, id = 'c1'): LlmTurn {
  return {
    content: null,
    tool_calls: [{ id, type: 'function', function: { name, arguments: JSON.stringify(args) } }],
  }
}
function deps(turns: LlmTurn[], runTool = vi.fn().mockResolvedValue({ ok: true })) {
  const callModel = vi.fn()
  turns.forEach((t) => callModel.mockResolvedValueOnce(t))
  return { callModel, runTool, idsVistos: new Set<number>() }
}
const inicio: LlmMessage[] = [
  { role: 'system', content: 's' },
  { role: 'user', content: 'oi' },
]

describe('isDataIso', () => {
  it('aceita data absoluta válida', () => {
    expect(isDataIso('2026-10-16')).toBe(true)
  })
  it('rejeita texto relativo, formato errado e data impossível', () => {
    expect(isDataIso('quinta')).toBe(false)
    expect(isDataIso('16/10/2026')).toBe(false)
    expect(isDataIso('2026-13-01')).toBe(false)
    expect(isDataIso('2026-02-30')).toBe(false)
    expect(isDataIso(20261016)).toBe(false)
  })
})

describe('coletarIds', () => {
  it('coleta id de objeto, de lista aninhada e de instrument_ids', () => {
    const s = new Set<number>()
    coletarIds({ visitas: [{ id: 87, tecnico_id: 3, instrument_ids: [11, 12] }] }, s)
    expect([...s].sort((a, b) => a - b)).toEqual([3, 11, 12, 87])
  })
  it('ignora valores não numéricos', () => {
    const s = new Set<number>()
    coletarIds({ id: 'abc', os_id: null }, s)
    expect(s.size).toBe(0)
  })
})

describe('runTurn', () => {
  it('turno sem ferramenta devolve texto', async () => {
    const d = deps([texto('tudo certo')])
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('text')
    if (r.kind === 'text') expect(r.text).toBe('tudo certo')
  })

  it('leitura executa, realimenta e segue o loop', async () => {
    const runTool = vi.fn().mockResolvedValue({ visitas: [{ id: 87 }] })
    const d = deps([chamada('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' }), texto('achei')], runTool)
    const r = await runTurn(inicio, d)
    expect(runTool).toHaveBeenCalledWith('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' })
    expect(r.kind).toBe('text')
    expect(d.idsVistos.has(87)).toBe(true)
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool).toBeTruthy()
  })

  it('escrita PARA o loop e vira proposta, sem chamar runTool', async () => {
    const runTool = vi.fn()
    const d = deps([chamada('atualizar_visita', { visita_id: 87, date: '2026-10-16' })], runTool)
    d.idsVistos.add(87)
    const r = await runTurn(inicio, d)
    expect(runTool).not.toHaveBeenCalled()
    expect(r.kind).toBe('proposal')
    if (r.kind === 'proposal') {
      expect(r.proposta.name).toBe('atualizar_visita')
      expect(r.proposta.args).toEqual({ visita_id: 87, date: '2026-10-16' })
      expect(r.proposta.resumo).toContain('87')
    }
  })

  it('escrita com id nunca visto não vira proposta; o erro volta ao modelo', async () => {
    const d = deps([
      chamada('atualizar_visita', { visita_id: 999, date: '2026-10-16' }),
      texto('desculpe, vou buscar primeiro'),
    ])
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('text')
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toContain('999')
    expect(tool?.content).toMatch(/não apareceu/i)
  })

  it('data não-ISO é rejeitada antes de qualquer execução', async () => {
    const runTool = vi.fn()
    const d = deps([
      chamada('buscar_agenda', { date_from: 'quinta', date_to: '2026-10-18' }),
      texto('corrigindo'),
    ], runTool)
    const r = await runTurn(inicio, d)
    expect(runTool).not.toHaveBeenCalled()
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toMatch(/AAAA-MM-DD/)
    expect(r.kind).toBe('text')
  })

  it('erro de ferramenta vira role tool e o loop continua', async () => {
    const runTool = vi.fn().mockRejectedValue(new Error('OS em execução (approved).'))
    const d = deps([
      chamada('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' }),
      texto('a OS está travada'),
    ], runTool)
    const r = await runTurn(inicio, d)
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toContain('OS em execução')
    expect(r.kind).toBe('text')
  })

  it('argumentos com JSON inválido não derrubam o loop', async () => {
    const callModel = vi.fn()
      .mockResolvedValueOnce({
        content: null,
        tool_calls: [{ id: 'c1', type: 'function', function: { name: 'buscar_agenda', arguments: '{nao é json' } }],
      })
      .mockResolvedValueOnce(texto('ok'))
    const d = { callModel, runTool: vi.fn(), idsVistos: new Set<number>() }
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('text')
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toMatch(/argumentos/i)
  })

  it('respeita o teto de voltas', async () => {
    const callModel = vi.fn().mockResolvedValue(
      chamada('buscar_agenda', { date_from: '2026-10-12', date_to: '2026-10-18' }),
    )
    const d = { callModel, runTool: vi.fn().mockResolvedValue({}), idsVistos: new Set<number>() }
    const r = await runTurn(inicio, d)
    expect(callModel).toHaveBeenCalledTimes(MAX_TOOL_ROUNDS)
    expect(r.kind).toBe('error')
    if (r.kind === 'error') expect(r.erro).toMatch(/voltas/i)
  })

  it('erro do modelo vira resultado de erro, não exceção', async () => {
    const callModel = vi.fn().mockRejectedValue(new Error('IA indisponível'))
    const d = { callModel, runTool: vi.fn(), idsVistos: new Set<number>() }
    const r = await runTurn(inicio, d)
    expect(r.kind).toBe('error')
    if (r.kind === 'error') expect(r.erro).toContain('IA indisponível')
  })
})

describe('confirmarEscrita', () => {
  it('executa a ferramenta, realimenta o resultado e segue o loop', async () => {
    const runTool = vi.fn().mockResolvedValue({ id: 87, date: '2026-10-16' })
    const d = deps([texto('pronto, remarcada')], runTool)
    const proposta = {
      toolCallId: 'c1', name: 'atualizar_visita',
      args: { visita_id: 87, date: '2026-10-16' }, resumo: 'r',
    }
    const msgs: LlmMessage[] = [...inicio, {
      role: 'assistant', content: null,
      tool_calls: [{ id: 'c1', type: 'function', function: { name: 'atualizar_visita', arguments: '{}' } }],
    }]
    const r = await confirmarEscrita(msgs, proposta, d)
    expect(runTool).toHaveBeenCalledWith('atualizar_visita', { visita_id: 87, date: '2026-10-16' })
    expect(r.kind).toBe('text')
    if (r.kind === 'text') expect(r.text).toContain('remarcada')
  })

  it('UserError do Odoo volta ao modelo em vez de estourar', async () => {
    const runTool = vi.fn().mockRejectedValue(new Error('Visita já realizada.'))
    const d = deps([texto('não deu: a visita já foi realizada')], runTool)
    const proposta = { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'r' }
    const r = await confirmarEscrita([...inicio], proposta, d)
    const tool = r.messages.find((m) => m.role === 'tool')
    expect(tool?.content).toContain('Visita já realizada')
    expect(r.kind).toBe('text')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run lib/chat/machine.test.ts`
Expected: FAIL — `Failed to resolve import "./machine"`.

- [ ] **Step 3: Write minimal implementation**

Criar `lib/chat/machine.ts`:

```ts
// lib/chat/machine.ts
// O loop do agente, sem React, para poder ser testado sozinho.
//
// Duas travas moram aqui, e são elas que tornam aceitável usar um modelo
// gratuito: data só entra em formato absoluto, e id de escrita só passa se
// tiver aparecido em algum resultado de ferramenta desta conversa. Quando
// uma delas barra, o erro volta ao modelo como resultado de ferramenta e
// ele se corrige na volta seguinte.
import type { LlmMessage, LlmTurn, LlmToolCall } from '@/lib/llm/client'
import { isWriteTool } from './toolDefs'

export const MAX_TOOL_ROUNDS = 4

export interface Proposta {
  toolCallId: string
  name: string
  args: Record<string, unknown>
  resumo: string
}

export type PassoResultado =
  | { kind: 'text'; messages: LlmMessage[]; text: string }
  | { kind: 'proposal'; messages: LlmMessage[]; proposta: Proposta }
  | { kind: 'error'; messages: LlmMessage[]; erro: string }

export interface MachineDeps {
  callModel: (messages: LlmMessage[]) => Promise<LlmTurn>
  runTool: (name: string, args: Record<string, unknown>) => Promise<unknown>
  /** Mutável de propósito: acumula ao longo da conversa inteira. */
  idsVistos: Set<number>
}

const CHAVES_DE_ID = new Set([
  'id', 'visita_id', 'tecnico_id', 'os_id', 'instrument_id',
])

export function coletarIds(valor: unknown, destino: Set<number>): void {
  if (Array.isArray(valor)) {
    for (const v of valor) coletarIds(v, destino)
    return
  }
  if (!valor || typeof valor !== 'object') return
  for (const [chave, v] of Object.entries(valor as Record<string, unknown>)) {
    if (chave === 'instrument_ids' && Array.isArray(v)) {
      for (const n of v) if (typeof n === 'number') destino.add(n)
      continue
    }
    if (CHAVES_DE_ID.has(chave) && typeof v === 'number') destino.add(v)
    else coletarIds(v, destino)
  }
}

const RE_ISO = /^\d{4}-\d{2}-\d{2}$/

export function isDataIso(v: unknown): boolean {
  if (typeof v !== 'string' || !RE_ISO.test(v)) return false
  const d = new Date(`${v}T00:00:00Z`)
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === v
}

const CAMPOS_DE_DATA = ['date', 'date_from', 'date_to']
const CAMPOS_DE_ID = ['visita_id', 'tecnico_id', 'os_id']

/** Erro legível para o modelo, ou null se os argumentos passam. */
function validar(
  name: string,
  args: Record<string, unknown>,
  idsVistos: Set<number>,
): string | null {
  for (const campo of CAMPOS_DE_DATA) {
    if (args[campo] !== undefined && !isDataIso(args[campo])) {
      return `O campo "${campo}" veio como ${JSON.stringify(args[campo])}. Use data absoluta no formato AAAA-MM-DD, calculada a partir da data de hoje informada no contexto.`
    }
  }
  if (!isWriteTool(name)) return null
  for (const campo of CAMPOS_DE_ID) {
    const v = args[campo]
    if (typeof v === 'number' && !idsVistos.has(v)) {
      return `O id ${v} em "${campo}" não apareceu em nenhuma consulta desta conversa. Chame a ferramenta de consulta adequada primeiro e use o id que ela devolver.`
    }
  }
  const instrumentos = args.instrument_ids
  if (Array.isArray(instrumentos)) {
    for (const n of instrumentos) {
      if (typeof n === 'number' && !idsVistos.has(n)) {
        return `O instrumento de id ${n} não apareceu em nenhuma consulta desta conversa. Chame listar_instrumentos primeiro.`
      }
    }
  }
  return null
}

function resumir(name: string, args: Record<string, unknown>): string {
  if (name === 'criar_visita') {
    return `Criar visita para a OS ${args.os_id} em ${args.date}, técnico ${args.tecnico_id}.`
  }
  const partes: string[] = []
  if (args.date !== undefined) partes.push(`data → ${args.date}`)
  if (args.time_start !== undefined) partes.push(`início → ${args.time_start}`)
  if (args.time_stop !== undefined) partes.push(`fim → ${args.time_stop}`)
  if (args.tecnico_id !== undefined) partes.push(`técnico → ${args.tecnico_id}`)
  if (args.instrument_ids !== undefined) {
    partes.push(`instrumentos → ${JSON.stringify(args.instrument_ids)}`)
  }
  if (args.note !== undefined) partes.push('observação alterada')
  return `Alterar a visita ${args.visita_id}: ${partes.join(', ') || 'sem mudança'}.`
}

function parseArgs(call: LlmToolCall): Record<string, unknown> | null {
  try {
    const v = JSON.parse(call.function.arguments || '{}')
    return v && typeof v === 'object' && !Array.isArray(v) ? v : null
  } catch {
    return null
  }
}

function msgAssistente(turn: LlmTurn): LlmMessage {
  return { role: 'assistant', content: turn.content, tool_calls: turn.tool_calls }
}

function msgFerramenta(id: string, conteudo: string): LlmMessage {
  return { role: 'tool', content: conteudo, tool_call_id: id }
}

function mensagemDeErro(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

/**
 * Roda o loop até o modelo responder em texto, propor uma escrita, ou
 * esbarrar no teto. Nunca lança: erro vira resultado.
 */
export async function runTurn(
  messages: LlmMessage[],
  deps: MachineDeps,
): Promise<PassoResultado> {
  let atual = [...messages]
  for (let volta = 0; volta < MAX_TOOL_ROUNDS; volta++) {
    let turn: LlmTurn
    try {
      turn = await deps.callModel(atual)
    } catch (e) {
      return { kind: 'error', messages: atual, erro: mensagemDeErro(e) }
    }

    if (!turn.tool_calls.length) {
      atual = [...atual, msgAssistente(turn)]
      return { kind: 'text', messages: atual, text: turn.content ?? '' }
    }

    atual = [...atual, msgAssistente(turn)]
    let propostaPendente: Proposta | null = null

    for (const call of turn.tool_calls) {
      const args = parseArgs(call)
      if (!args) {
        atual = [...atual, msgFerramenta(
          call.id,
          'Não consegui ler os argumentos: não são um objeto JSON válido. Repita a chamada com JSON bem formado.',
        )]
        continue
      }
      const erro = validar(call.function.name, args, deps.idsVistos)
      if (erro) {
        atual = [...atual, msgFerramenta(call.id, erro)]
        continue
      }
      if (isWriteTool(call.function.name)) {
        // O loop para aqui: escrita não executa sem o gestor confirmar.
        propostaPendente = {
          toolCallId: call.id,
          name: call.function.name,
          args,
          resumo: resumir(call.function.name, args),
        }
        break
      }
      try {
        const resultado = await deps.runTool(call.function.name, args)
        coletarIds(resultado, deps.idsVistos)
        atual = [...atual, msgFerramenta(call.id, JSON.stringify(resultado))]
      } catch (e) {
        atual = [...atual, msgFerramenta(call.id, mensagemDeErro(e))]
      }
    }

    if (propostaPendente) {
      return { kind: 'proposal', messages: atual, proposta: propostaPendente }
    }
  }
  return {
    kind: 'error',
    messages: atual,
    erro: `A IA excedeu ${MAX_TOOL_ROUNDS} voltas de consulta sem concluir. Tente reformular o pedido.`,
  }
}

/** Executa a escrita que o gestor confirmou e devolve o loop ao modelo. */
export async function confirmarEscrita(
  messages: LlmMessage[],
  proposta: Proposta,
  deps: MachineDeps,
): Promise<PassoResultado> {
  let atual = [...messages]
  try {
    const resultado = await deps.runTool(proposta.name, proposta.args)
    coletarIds(resultado, deps.idsVistos)
    atual = [...atual, msgFerramenta(proposta.toolCallId, JSON.stringify(resultado))]
  } catch (e) {
    atual = [...atual, msgFerramenta(proposta.toolCallId, mensagemDeErro(e))]
  }
  return runTurn(atual, deps)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run lib/chat/machine.test.ts`
Expected: PASS — 14 testes.

- [ ] **Step 5: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/lib/chat/machine.ts pwa/lib/chat/machine.test.ts
git commit -m "feat(pwa): agent loop with write proposals and id guard

Read tools run inside the loop; write tools stop it and become a
proposal the gestor confirms. Two guards make a free model tolerable: a
date must be absolute ISO, and a write id must have appeared in some
tool result this conversation. Either way the error goes back to the
model as a tool result so it self-corrects instead of failing.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Rotas do servidor

**Files:**
- Create: `app/api/chat/route.ts`
- Create: `app/api/chat/status/route.ts`
- Create: `app/api/chat/__tests__/route.test.ts`
- Create: `.env.local.example`

**Interfaces:**
- Consumes: `llmChat`, `LlmError`, `LlmMessage` de `lib/llm/client.ts`; `TOOL_DEFS` de `lib/chat/toolDefs.ts`.
- Produces: `POST` handler em `/api/chat` que recebe `{ messages: LlmMessage[] }` e devolve `{ content: string | null, tool_calls: LlmToolCall[], model: string }`; `GET` em `/api/chat/status` que devolve `{ enabled: boolean }`; `OPENROUTER_BASE_URL`, `PROVIDER_POLICY`, `modelosConfigurados()` exportados para teste.

- [ ] **Step 1: Write the failing test**

Criar `app/api/chat/__tests__/route.test.ts`:

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run app/api/chat/__tests__/route.test.ts`
Expected: FAIL — `Failed to resolve import "../route"`.

- [ ] **Step 3: Write minimal implementation**

Criar `app/api/chat/route.ts`:

```ts
// app/api/chat/route.ts
// UM turno do modelo, sem estado. Esta rota NÃO importa `lib/odoo` nem o
// dispatch das ferramentas: o servidor não tem como gravar no Odoo nem se
// o prompt for subvertido. As ferramentas executam no cliente.
import { NextResponse } from 'next/server'
import { llmChat, LlmError, type LlmMessage } from '@/lib/llm/client'
import { TOOL_DEFS } from '@/lib/chat/toolDefs'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

export const OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'

/**
 * Política, não preferência: os provedores listados treinam nos prompts
 * enviados, e aqui trafega dado de cliente hospitalar. `require_parameters`
 * resolve outro problema — nem todo endpoint desses modelos declara
 * `tools`, e sem o flag o roteamento pode cair num que ignora as
 * ferramentas, fazendo o modelo parecer incapaz.
 *
 * Deliberadamente NÃO usamos `zdr: true` nem `data_collection: "deny"`:
 * esses filtram retenção, não treino, e excluiriam o próprio primário.
 */
export const PROVIDER_POLICY = {
  ignore: ['nvidia', 'liquid', 'thinkingmachines'],
  require_parameters: true,
} as const

const MODELOS_PADRAO = [
  'google/gemma-4-31b-it:free',
  'google/gemma-4-26b-a4b-it:free',
  'qwen/qwen3.8-27b:free',
]

export function modelosConfigurados(): string[] {
  const bruto = process.env.OPENROUTER_MODELS
  if (!bruto) return MODELOS_PADRAO
  const lista = bruto.split(',').map((m) => m.trim()).filter(Boolean)
  return lista.length ? lista : MODELOS_PADRAO
}

/** 429 e 5xx são do provedor: vale tentar o próximo. 4xx é nosso: não vale. */
function vaiTentarOutro(status: number): boolean {
  return status === 429 || status >= 500
}

function corpoValido(b: unknown): b is { messages: LlmMessage[] } {
  if (!b || typeof b !== 'object') return false
  const m = (b as Record<string, unknown>).messages
  return Array.isArray(m) && m.every((x) => x && typeof x === 'object')
}

export async function POST(request: Request) {
  if (!process.env.OPENROUTER_API_KEY) {
    return NextResponse.json({ error: 'IA não configurada' }, { status: 503 })
  }
  let body: unknown
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: 'JSON inválido' }, { status: 400 })
  }
  if (!corpoValido(body)) {
    return NextResponse.json({ error: 'Schema inválido' }, { status: 400 })
  }

  let ultimo: LlmError | null = null
  for (const model of modelosConfigurados()) {
    try {
      const turn = await llmChat(body.messages, {
        baseUrl: OPENROUTER_BASE_URL,
        apiKey: process.env.OPENROUTER_API_KEY,
        model,
        tools: TOOL_DEFS,
        extraBody: {
          provider: PROVIDER_POLICY,
          // Gemma 4 tem thinking opt-in; deixar explícito evita pagar
          // ~4,6x em latência caso um provedor mude o default.
          reasoning: { enabled: false },
        },
      })
      return NextResponse.json({ ...turn, model })
    } catch (e) {
      if (!(e instanceof LlmError)) throw e
      ultimo = e
      if (!vaiTentarOutro(e.status)) break
    }
  }
  return NextResponse.json(
    {
      error: vaiTentarOutro(ultimo?.status ?? 500)
        ? 'IA indisponível no momento — use a agenda manual.'
        : (ultimo?.message ?? 'Falha na IA'),
    },
    { status: ultimo?.status ?? 502 },
  )
}
```

Criar `app/api/chat/status/route.ts`:

```ts
// app/api/chat/status/route.ts
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
  return NextResponse.json({ enabled: !!process.env.OPENROUTER_API_KEY })
}
```

Criar `.env.local.example`:

```bash
# Groq — resumo, revisão e transcrição de áudio (features já existentes).
GROQ_API_KEY=

# OpenRouter — chat de agendamento. Sem esta chave o botão do chat não
# aparece e a agenda segue manual.
#
# ATENÇÃO à cota: o tier gratuito dá 20 req/min e 50 requisições/DIA por
# conta enquanto houver menos de US$ 10 de crédito comprado. Cada mensagem
# do gestor gasta de 2 a 5 requisições, então são ~10 a 25 mensagens por
# dia. Serve para demonstração, não para uso diário.
OPENROUTER_API_KEY=

# Cadeia de fallback, em ordem. Vazio usa o padrão do código.
OPENROUTER_MODELS=google/gemma-4-31b-it:free,google/gemma-4-26b-a4b-it:free,qwen/qwen3.8-27b:free
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run app/api/chat/__tests__/route.test.ts`
Expected: PASS — 9 testes.

- [ ] **Step 5: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/app/api/chat pwa/.env.local.example
git commit -m "feat(pwa): stateless chat route with model fallback chain

One model turn per call. The route injects the tool schemas, the
provider policy and reasoning:false server-side so the client cannot
override them, and walks the model chain on 429/5xx only.

It imports neither lib/odoo nor the tool dispatch, so the server has no
write path to Odoo at all; a test asserts that boundary.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Hooks e UI do chat

**Files:**
- Create: `lib/hooks/useChatStatus.ts`
- Create: `lib/hooks/useChatAgenda.ts`
- Create: `app/tecnico/qualificacao/agenda/_ChatAgenda.tsx`
- Create: `app/tecnico/qualificacao/__tests__/ChatAgenda.test.tsx`
- Modify: `app/tecnico/qualificacao/agenda/page.tsx` (montar o chat perto do bloco `data?.can_manage &&`, por volta da linha 951)

**Interfaces:**
- Consumes: `runTurn`, `confirmarEscrita`, `type Proposta`, `type PassoResultado` de `lib/chat/machine.ts`; `runTool` de `lib/chat/tools.ts`; `buildSystemPrompt`, `resumirVisitas` de `lib/chat/prompt.ts`; `BottomSheet` de `components/ui/BottomSheet`; `AgendaPayload` de `lib/odoo/agenda.ts`.
- Produces: `useChatStatus(): { enabled: boolean; isLoading: boolean }`; `useChatAgenda(payload: AgendaPayload | undefined): ChatState`; componente `<ChatAgenda open onClose payload />`.

- [ ] **Step 1: Write the failing test**

Criar `app/tecnico/qualificacao/__tests__/ChatAgenda.test.tsx`:

```tsx
// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

const runTurnMock = vi.fn()
const confirmarEscritaMock = vi.fn()
const runToolMock = vi.fn()

vi.mock('@/lib/chat/machine', async () => {
  const real = await vi.importActual<typeof import('@/lib/chat/machine')>('@/lib/chat/machine')
  return { ...real, runTurn: runTurnMock, confirmarEscrita: confirmarEscritaMock }
})
vi.mock('@/lib/chat/tools', () => ({ runTool: runToolMock }))

import { ChatAgenda } from '../agenda/_ChatAgenda'

const payload = {
  server_today: '2026-10-14',
  date_from: '2026-10-01',
  date_to: '2026-10-31',
  my_employee_id: 441 as number | false,
  can_manage: true,
  visitas: [{
    id: 87, date: '2026-10-15', time_start: 8, time_stop: 17, planned_hours: 9,
    os_id: 4, os_name: 'OS26-06-0002', os_state: 'draft',
    partner_name: 'Hospital Central', city: 'São Luís', equipment_list: [],
    instrument_ids: [], instrument_list: [], tecnico_id: 3,
    tecnico_name: 'João Silva', is_mine: false, state: 'draft', overflow: false,
    editable: true, lock_reason: false as const, conflict: false,
    conflict_msg: '', note: '',
  }],
}

function montar(props: Partial<React.ComponentProps<typeof ChatAgenda>> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ChatAgenda open onClose={() => {}} payload={payload as never} {...props} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  globalThis.sessionStorage?.clear()
})

describe('ChatAgenda', () => {
  it('não renderiza quando o payload diz que o usuário não gerencia', () => {
    montar({ payload: { ...payload, can_manage: false } as never })
    expect(screen.queryByPlaceholderText(/escreva/i)).toBeNull()
  })

  it('mostra a resposta de texto do assistente', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'text', messages: [], text: 'Você tem 1 visita quinta-feira.',
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'o que tenho quinta?')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/1 visita quinta-feira/i)).toBeTruthy()
  })

  it('escrita proposta aparece como card com o resumo e dois botões', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: {
        toolCallId: 'c1', name: 'atualizar_visita',
        args: { visita_id: 87, date: '2026-10-16' },
        resumo: 'Alterar a visita 87: data → 2026-10-16.',
      },
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'remarca pra sexta')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/Alterar a visita 87/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /confirmar/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /cancelar/i })).toBeTruthy()
  })

  it('o card mostra o contexto da visita alvo, não só o id', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: {
        toolCallId: 'c1', name: 'atualizar_visita',
        args: { visita_id: 87, date: '2026-10-16' }, resumo: 'Alterar a visita 87.',
      },
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/OS26-06-0002/)).toBeTruthy()
    expect(screen.getByText(/Hospital Central/)).toBeTruthy()
  })

  it('Cancelar não executa a escrita', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'r' },
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    await userEvent.click(await screen.findByRole('button', { name: /cancelar/i }))
    expect(confirmarEscritaMock).not.toHaveBeenCalled()
    expect(runToolMock).not.toHaveBeenCalled()
  })

  it('Confirmar executa a escrita uma vez só', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'proposal', messages: [],
      proposta: { toolCallId: 'c1', name: 'atualizar_visita', args: { visita_id: 87 }, resumo: 'r' },
    })
    confirmarEscritaMock.mockResolvedValue({ kind: 'text', messages: [], text: 'pronto' })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    const btn = await screen.findByRole('button', { name: /confirmar/i })
    await userEvent.click(btn)
    await userEvent.click(btn).catch(() => {})
    await waitFor(() => expect(confirmarEscritaMock).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/pronto/)).toBeTruthy()
  })

  it('erro da máquina aparece na conversa sem derrubar a tela', async () => {
    runTurnMock.mockResolvedValue({
      kind: 'error', messages: [], erro: 'IA indisponível no momento — use a agenda manual.',
    })
    montar()
    await userEvent.type(screen.getByPlaceholderText(/escreva/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: /enviar/i }))
    expect(await screen.findByText(/IA indisponível/)).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/ChatAgenda.test.tsx`
Expected: FAIL — `Failed to resolve import "../agenda/_ChatAgenda"`.

- [ ] **Step 3: Escrever o hook de status**

Criar `lib/hooks/useChatStatus.ts`:

```ts
// lib/hooks/useChatStatus.ts
'use client'
import { useQuery } from '@tanstack/react-query'

export function useChatStatus() {
  const q = useQuery({
    queryKey: ['chat-status'],
    queryFn: async () => {
      const res = await fetch('/api/chat/status')
      if (!res.ok) return { enabled: false }
      return (await res.json()) as { enabled: boolean }
    },
    staleTime: Infinity,
    gcTime: Infinity,
    refetchOnWindowFocus: false,
  })
  return { enabled: q.data?.enabled ?? false, isLoading: q.isLoading }
}
```

- [ ] **Step 4: Escrever o hook da conversa**

Criar `lib/hooks/useChatAgenda.ts`:

```ts
// lib/hooks/useChatAgenda.ts
'use client'
import { useCallback, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { LlmMessage, LlmTurn } from '@/lib/llm/client'
import type { AgendaPayload } from '@/lib/odoo/agenda'
import { runTurn, confirmarEscrita, coletarIds, type Proposta, type PassoResultado } from '@/lib/chat/machine'
import { runTool } from '@/lib/chat/tools'
import { buildSystemPrompt, resumirVisitas } from '@/lib/chat/prompt'

export interface Bolha {
  autor: 'user' | 'assistente' | 'erro'
  texto: string
}

const CHAVE_SESSAO = 'chat-agenda-transcript'

function lerSessao(): Bolha[] {
  try {
    const cru = sessionStorage.getItem(CHAVE_SESSAO)
    return cru ? (JSON.parse(cru) as Bolha[]) : []
  } catch {
    return []
  }
}

function gravarSessao(bolhas: Bolha[]): void {
  try {
    sessionStorage.setItem(CHAVE_SESSAO, JSON.stringify(bolhas))
  } catch {
    // Janela anônima ou storage bloqueado: a conversa só não persiste.
  }
}

async function chamarModelo(messages: LlmMessage[]) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
  })
  if (!res.ok) {
    const j = await res.json().catch(() => ({}))
    throw new Error(j?.error || 'Falha ao falar com a IA')
  }
  return (await res.json()) as LlmTurn
}

export function useChatAgenda(payload: AgendaPayload | undefined) {
  const qc = useQueryClient()
  const [bolhas, setBolhas] = useState<Bolha[]>(() =>
    typeof window === 'undefined' ? [] : lerSessao(),
  )
  const [proposta, setProposta] = useState<Proposta | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const historico = useRef<LlmMessage[]>([])
  // O conjunto de ids vive pela conversa inteira, não por pedido: um id
  // visto na primeira pergunta continua válido na terceira.
  const idsVistos = useRef<Set<number>>(new Set())

  const systemPrompt = useMemo(() => {
    if (!payload) return ''
    coletarIds(payload.visitas, idsVistos.current)
    return buildSystemPrompt({
      serverToday: payload.server_today,
      tecnicos: [...new Map(
        payload.visitas
          .filter((v) => v.tecnico_id)
          .map((v) => [v.tecnico_id as number, { id: v.tecnico_id as number, name: v.tecnico_name }]),
      ).values()],
      visitas: resumirVisitas(payload.visitas),
    })
  }, [payload])

  const empilhar = useCallback((b: Bolha) => {
    setBolhas((antigas) => {
      const novas = [...antigas, b]
      gravarSessao(novas)
      return novas
    })
  }, [])

  const aplicar = useCallback((r: PassoResultado) => {
    historico.current = r.messages
    if (r.kind === 'text') {
      setProposta(null)
      if (r.text) empilhar({ autor: 'assistente', texto: r.text })
    } else if (r.kind === 'proposal') {
      setProposta(r.proposta)
    } else {
      setProposta(null)
      empilhar({ autor: 'erro', texto: r.erro })
    }
  }, [empilhar])

  const deps = useMemo(
    () => ({ callModel: chamarModelo, runTool, idsVistos: idsVistos.current }),
    [],
  )

  const enviar = useCallback(async (texto: string) => {
    if (!texto.trim() || ocupado || !payload) return
    empilhar({ autor: 'user', texto })
    setOcupado(true)
    const base: LlmMessage[] = historico.current.length
      ? historico.current
      : [{ role: 'system', content: systemPrompt }]
    try {
      aplicar(await runTurn([...base, { role: 'user', content: texto }], deps))
    } finally {
      setOcupado(false)
    }
  }, [ocupado, payload, empilhar, systemPrompt, aplicar, deps])

  const confirmar = useCallback(async () => {
    if (!proposta || ocupado) return
    setOcupado(true)
    // Some com o card antes de executar: sem isso, um duplo toque dispara
    // a escrita duas vezes.
    const alvo = proposta
    setProposta(null)
    try {
      aplicar(await confirmarEscrita(historico.current, alvo, deps))
      qc.invalidateQueries({ queryKey: ['agenda'] })
      qc.invalidateQueries({ queryKey: ['tecnico-os'] })
    } finally {
      setOcupado(false)
    }
  }, [proposta, ocupado, aplicar, deps, qc])

  const cancelar = useCallback(() => {
    setProposta(null)
    empilhar({ autor: 'erro', texto: 'Alteração cancelada.' })
  }, [empilhar])

  return { bolhas, proposta, ocupado, enviar, confirmar, cancelar }
}
```

- [ ] **Step 5: Escrever o componente**

Criar `app/tecnico/qualificacao/agenda/_ChatAgenda.tsx`:

```tsx
'use client'
import { useState } from 'react'
import { Send } from 'lucide-react'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { useChatAgenda } from '@/lib/hooks/useChatAgenda'
import type { AgendaPayload } from '@/lib/odoo/agenda'

/** Contexto da visita alvo, para o gestor conferir antes de confirmar. */
function alvoDaProposta(payload: AgendaPayload, args: Record<string, unknown>) {
  const id = typeof args.visita_id === 'number' ? args.visita_id : null
  if (id === null) return null
  return payload.visitas.find((v) => v.id === id) ?? null
}

export function ChatAgenda({
  open,
  onClose,
  payload,
}: {
  open: boolean
  onClose: () => void
  payload: AgendaPayload | undefined
}) {
  const [texto, setTexto] = useState('')
  const { bolhas, proposta, ocupado, enviar, confirmar, cancelar } =
    useChatAgenda(payload)

  if (!payload?.can_manage) return null

  const alvo = proposta ? alvoDaProposta(payload, proposta.args) : null

  async function submeter(e: React.FormEvent) {
    e.preventDefault()
    const t = texto
    setTexto('')
    await enviar(t)
  }

  return (
    <BottomSheet open={open} title="Agendar por conversa" onClose={onClose}>
      <div className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto pb-2">
        {bolhas.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Peça em português: “remarca a visita do João de quinta pra sexta”,
            “quem está livre dia 20?”.
          </p>
        )}
        {bolhas.map((b, i) => (
          <div
            key={i}
            className={
              b.autor === 'user'
                ? 'self-end rounded-lg bg-primary/10 px-3 py-2 text-sm'
                : b.autor === 'erro'
                  ? 'self-start rounded-lg bg-destructive/10 px-3 py-2 text-sm'
                  : 'self-start rounded-lg bg-muted px-3 py-2 text-sm'
            }
          >
            {b.texto}
          </div>
        ))}

        {proposta && (
          <div className="rounded-lg border border-primary/40 bg-primary/5 p-3">
            <p className="text-sm font-medium">{proposta.resumo}</p>
            {alvo && (
              <p className="mt-1 text-xs text-muted-foreground">
                {alvo.os_name} · {alvo.partner_name} · {alvo.city} · {alvo.date}
                {alvo.tecnico_name ? ` · ${alvo.tecnico_name}` : ''}
              </p>
            )}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                className="min-h-[44px] flex-1 rounded-md bg-primary px-3 text-primary-foreground disabled:opacity-50"
                disabled={ocupado}
                onClick={confirmar}
              >
                Confirmar
              </button>
              <button
                type="button"
                className="min-h-[44px] flex-1 rounded-md border border-border px-3"
                onClick={cancelar}
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {ocupado && (
          <p className="text-xs text-muted-foreground">consultando a agenda…</p>
        )}
      </div>

      <form onSubmit={submeter} className="mt-3 flex gap-2">
        <input
          className="min-h-[44px] flex-1 rounded-md border border-border bg-background px-3"
          placeholder="Escreva o que precisa"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          disabled={ocupado}
        />
        <button
          type="submit"
          aria-label="Enviar"
          className="min-h-[44px] min-w-[44px] rounded-md bg-primary text-primary-foreground disabled:opacity-50"
          disabled={ocupado || !texto.trim()}
        >
          <Send className="mx-auto h-4 w-4" />
        </button>
      </form>
    </BottomSheet>
  )
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `npx vitest run app/tecnico/qualificacao/__tests__/ChatAgenda.test.tsx`
Expected: PASS — 7 testes. Se `BottomSheet` esconder o conteúdo quando `open` é falso, confirme que o teste passa `open`; não altere `BottomSheet`.

- [ ] **Step 7: Montar na agenda**

Em `app/tecnico/qualificacao/agenda/page.tsx`:

Acrescentar aos imports do topo (junto do import de `VisitaSheet`, linha 5):

```tsx
import { ChatAgenda } from './_ChatAgenda'
import { useChatStatus } from '@/lib/hooks/useChatStatus'
import { MessageCircle } from 'lucide-react'
```

Dentro do componente, junto dos outros `useState`:

```tsx
const [chatAberto, setChatAberto] = useState(false)
const chatIA = useChatStatus()
```

No JSX, imediatamente antes do primeiro `<VisitaSheet` (por volta da linha 965):

```tsx
{data?.can_manage && chatIA.enabled && (
  <>
    <button
      type="button"
      aria-label="Agendar por conversa"
      onClick={() => setChatAberto(true)}
      className="fixed bottom-24 right-4 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg"
    >
      <MessageCircle className="h-6 w-6" />
    </button>
    <ChatAgenda
      open={chatAberto}
      onClose={() => setChatAberto(false)}
      payload={data}
    />
  </>
)}
```

- [ ] **Step 8: Rodar a suíte inteira e o typecheck**

Run: `npx tsc --noEmit && npx vitest run`
Expected: `tsc` sem erro; todos os testes passam. A única falha tolerada é a já conhecida do backend Odoo, que não roda aqui — no front, o baseline de `docs/BASELINE.md` é limpo, então qualquer falha é regressão.

- [ ] **Step 9: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/lib/hooks/useChatStatus.ts pwa/lib/hooks/useChatAgenda.ts \
        pwa/app/tecnico/qualificacao/agenda/_ChatAgenda.tsx \
        pwa/app/tecnico/qualificacao/agenda/page.tsx \
        pwa/app/tecnico/qualificacao/__tests__/ChatAgenda.test.tsx
git commit -m "feat(pwa): scheduling chat drawer on the agenda screen

Floating button and drawer, shown only when the payload says can_manage
and the AI is configured. A proposed write renders as a card carrying
the OS, client and city of the target visit, so a wrong target is
visible before anything is written; confirming clears the card first so
a double tap cannot fire the write twice.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Entrada por voz

**Files:**
- Modify: `app/tecnico/qualificacao/agenda/_ChatAgenda.tsx`
- Create: `lib/hooks/useDitado.ts`
- Create: `lib/hooks/useDitado.test.ts`

**Interfaces:**
- Consumes: rota `/api/groq/transcribe` (já existe).
- Produces: `useDitado(): { gravando: boolean; transcrevendo: boolean; alternar: () => Promise<void> }`, recebendo `onTexto: (t: string) => void`.

- [ ] **Step 1: Write the failing test**

Criar `lib/hooks/useDitado.test.ts`:

```ts
// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useDitado } from './useDitado'

class FakeRecorder {
  static ultima: FakeRecorder | null = null
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  state = 'inactive'
  constructor(public stream: unknown) {
    FakeRecorder.ultima = this
  }
  start() { this.state = 'recording' }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['x'], { type: 'audio/webm' }) })
    this.onstop?.()
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
  FakeRecorder.ultima = null
  ;(globalThis as any).MediaRecorder = FakeRecorder
  ;(globalThis as any).navigator.mediaDevices = {
    getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] }),
  }
})

describe('useDitado', () => {
  it('grava, transcreve e entrega o texto pelo callback', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'remarca a visita do João' }), { status: 200 }),
    ) as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(true)

    await act(async () => { await result.current.alternar() })
    await waitFor(() => expect(onTexto).toHaveBeenCalledWith('remarca a visita do João'))
    expect(result.current.gravando).toBe(false)
  })

  it('falha de transcrição não deixa o hook travado em gravando', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: 'IA não configurada' }), { status: 503 }),
    ) as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() })
    await act(async () => { await result.current.alternar() })
    await waitFor(() => expect(result.current.transcrevendo).toBe(false))
    expect(result.current.gravando).toBe(false)
    expect(onTexto).not.toHaveBeenCalled()
  })

  it('permissão de microfone negada não quebra', async () => {
    ;(globalThis as any).navigator.mediaDevices.getUserMedia =
      vi.fn().mockRejectedValue(new Error('NotAllowedError'))
    const { result } = renderHook(() => useDitado(vi.fn()))
    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run lib/hooks/useDitado.test.ts`
Expected: FAIL — `Failed to resolve import "./useDitado"`.

- [ ] **Step 3: Write minimal implementation**

Criar `lib/hooks/useDitado.ts`:

```ts
// lib/hooks/useDitado.ts
// Ditado por voz reusando a rota Whisper que já serve a coleta. O texto
// cai no campo de entrada e NÃO é enviado sozinho: o gestor revisa antes,
// porque transcrição errada de nome próprio é comum.
'use client'
import { useCallback, useRef, useState } from 'react'

export function useDitado(onTexto: (t: string) => void) {
  const [gravando, setGravando] = useState(false)
  const [transcrevendo, setTranscrevendo] = useState(false)
  const recorder = useRef<MediaRecorder | null>(null)
  const pedacos = useRef<Blob[]>([])

  const parar = useCallback(() => {
    recorder.current?.stop()
    recorder.current = null
    setGravando(false)
  }, [])

  const alternar = useCallback(async () => {
    if (gravando) {
      parar()
      return
    }
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setGravando(false)
      return
    }
    pedacos.current = []
    const mr = new MediaRecorder(stream)
    recorder.current = mr
    mr.ondataavailable = (e) => {
      if (e.data && e.data.size) pedacos.current.push(e.data)
    }
    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      const blob = new Blob(pedacos.current, { type: 'audio/webm' })
      if (!blob.size) return
      setTranscrevendo(true)
      try {
        const form = new FormData()
        form.append('file', blob, 'audio.webm')
        const res = await fetch('/api/groq/transcribe', { method: 'POST', body: form })
        if (res.ok) {
          const j = (await res.json()) as { text?: string }
          if (j.text) onTexto(j.text)
        }
      } catch {
        // Silencioso de propósito: o gestor ainda pode digitar.
      } finally {
        setTranscrevendo(false)
      }
    }
    mr.start()
    setGravando(true)
  }, [gravando, parar, onTexto])

  return { gravando, transcrevendo, alternar }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run lib/hooks/useDitado.test.ts`
Expected: PASS — 3 testes.

- [ ] **Step 5: Ligar o botão de microfone no chat**

Em `app/tecnico/qualificacao/agenda/_ChatAgenda.tsx`:

Trocar o import de ícone por:

```tsx
import { Send, Mic } from 'lucide-react'
```

Acrescentar o import do hook:

```tsx
import { useDitado } from '@/lib/hooks/useDitado'
```

Dentro do componente, depois do `useState` de `texto`:

```tsx
const ditado = useDitado((t) => setTexto((antes) => (antes ? `${antes} ${t}` : t)))
```

No formulário, entre o `<input>` e o botão de enviar:

```tsx
<button
  type="button"
  aria-label={ditado.gravando ? 'Parar gravação' : 'Ditar'}
  onClick={ditado.alternar}
  disabled={ocupado || ditado.transcrevendo}
  className={`min-h-[44px] min-w-[44px] rounded-md border border-border ${
    ditado.gravando ? 'bg-destructive text-destructive-foreground' : ''
  }`}
>
  <Mic className="mx-auto h-4 w-4" />
</button>
```

- [ ] **Step 6: Acrescentar o teste de integração do botão**

Em `app/tecnico/qualificacao/__tests__/ChatAgenda.test.tsx`, acrescentar dentro do `describe('ChatAgenda')`:

```tsx
  it('tem botão de ditar que não envia sozinho', async () => {
    montar()
    const mic = screen.getByRole('button', { name: /ditar/i })
    expect(mic).toBeTruthy()
    expect(runTurnMock).not.toHaveBeenCalled()
  })
```

- [ ] **Step 7: Rodar tudo**

Run: `npx tsc --noEmit && npx vitest run`
Expected: `tsc` limpo; suíte inteira verde.

- [ ] **Step 8: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add pwa/lib/hooks/useDitado.ts pwa/lib/hooks/useDitado.test.ts \
        pwa/app/tecnico/qualificacao/agenda/_ChatAgenda.tsx \
        pwa/app/tecnico/qualificacao/__tests__/ChatAgenda.test.tsx
git commit -m "feat(pwa): voice input for the scheduling chat

Reuses the existing Whisper route. The transcript lands in the input
field rather than being sent, because a misheard technician name is
common and the gestor should see it first.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Validação empírica (depois das 8 tasks, exige chave)

Isto não é uma task de código: é o gate que a spec pede antes de considerar a escolha de modelo fechada. Precisa de `OPENROUTER_API_KEY` em `pwa/.env.local`, que **não existe neste checkout**.

Quando houver chave, subir o dev server pelo `devserver` (nunca `nohup npm run dev &`), aquecer a rota da agenda e rodar ~10 pedidos em pt-BR coloquial pelo `agent-browser`, pontuando:

1. A ferramenta certa foi escolhida.
2. A data saiu ISO e derivada do `server_today` injetado, nunca deduzida.
3. Nenhum id alucinado (o `machine.ts` barra; contar quantas vezes barrou).
4. A segunda chamada consumiu mesmo o resultado da primeira.
5. Wall-clock por mensagem do gestor.

Se o Gemma 4 falhar em 1, 2 ou 4, trocar a ordem de `OPENROUTER_MODELS` — é variável de ambiente, não código.
