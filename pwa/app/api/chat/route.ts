// app/api/chat/route.ts
// UM turno do modelo, sem estado. Esta rota não importa o dispatch das
// ferramentas: o servidor não tem como gravar no Odoo nem se o prompt for
// subvertido. As ferramentas executam no cliente.
import { NextRequest, NextResponse } from 'next/server'
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

// Limites para proteger a quota diária compartilhada (50 requisições/dia),
// não para aplicar regra de negócio. Cada mensagem do usuário pode gastar
// de 2 a 5 requisições de fallback se os primeiros modelos falharem.
const MAX_MENSAGENS = 40
const MAX_CHARS_CONTEUDO = 8000
const ROLES_VALIDOS = ['system', 'user', 'assistant', 'tool'] as const

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
  if (!Array.isArray(m) || m.length === 0 || m.length > MAX_MENSAGENS) {
    return false
  }
  return m.every((x) => {
    if (!x || typeof x !== 'object') return false
    const msg = x as Record<string, unknown>
    const role = msg.role
    if (typeof role !== 'string' || !ROLES_VALIDOS.includes(role as any)) {
      return false
    }
    const content = msg.content
    if (typeof content === 'string' && content.length > MAX_CHARS_CONTEUDO) {
      return false
    }
    return true
  })
}

export async function POST(request: NextRequest) {
  const session = request.cookies.get('session_id')?.value
  if (!session) {
    return NextResponse.json({ error: 'Sessão expirada' }, { status: 401 })
  }
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
      if (!(e instanceof LlmError)) {
        // Erro genérico (TypeError, network error, etc.) — retornar JSON
        // em vez do default 500 de Next, mantendo consistência com erro path
        return NextResponse.json(
          { error: 'Falha na conexão com a IA' },
          { status: 502 },
        )
      }
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
