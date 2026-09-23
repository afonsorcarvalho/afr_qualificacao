// app/api/groq/summary/route.ts
// Caminho histórico: continua em /api/groq/summary (ver task 2 da migração
// Groq→OpenRouter). O provedor por trás agora é o OpenRouter.
import { NextRequest, NextResponse } from 'next/server'
import { llmChat, LlmError } from '@/lib/llm/client'
import { SUMMARY_SYSTEM_PROMPT } from '@/lib/groq/prompts'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

const OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
const MODEL = 'meta-llama/llama-3.3-70b-instruct'

export interface SummaryItem {
  id: number
  name: string
  status: 'collected' | 'skipped' | 'pending'
  obs: string
  at: string | null
}
export interface SummaryEquipment {
  tag: string
  name: string
  items: SummaryItem[]
}
export interface SummaryRequestBody {
  os_name: string
  equipments: SummaryEquipment[]
}

function isValidBody(b: unknown): b is SummaryRequestBody {
  if (!b || typeof b !== 'object') return false
  const x = b as Record<string, unknown>
  if (typeof x.os_name !== 'string') return false
  if (!Array.isArray(x.equipments)) return false
  return x.equipments.every((e: unknown) => {
    if (!e || typeof e !== 'object') return false
    const eq = e as Record<string, unknown>
    return (
      typeof eq.tag === 'string' &&
      typeof eq.name === 'string' &&
      Array.isArray(eq.items)
    )
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
  if (!isValidBody(body)) {
    return NextResponse.json({ error: 'Schema inválido' }, { status: 400 })
  }

  try {
    const turn = await llmChat(
      [
        { role: 'system', content: SUMMARY_SYSTEM_PROMPT },
        { role: 'user', content: JSON.stringify(body, null, 2) },
      ],
      {
        baseUrl: OPENROUTER_BASE_URL,
        apiKey: process.env.OPENROUTER_API_KEY,
        model: MODEL,
        temperature: 0.3,
        max_tokens: 1500,
      },
    )
    if (typeof turn.content !== 'string') {
      throw new LlmError('Resposta OpenRouter sem content', 502)
    }
    return NextResponse.json({ summary: turn.content.trim() })
  } catch (e) {
    if (e instanceof LlmError) {
      return NextResponse.json({ error: e.message }, { status: e.status })
    }
    return NextResponse.json({ error: 'Erro ao gerar resumo' }, { status: 500 })
  }
}
