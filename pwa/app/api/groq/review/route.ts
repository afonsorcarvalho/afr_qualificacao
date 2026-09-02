// app/api/groq/review/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { groqChat, GroqError } from '@/lib/groq/client'
import { REVIEW_SYSTEM_PROMPT } from '@/lib/groq/prompts'
import type { SummaryRequestBody } from '@/app/api/groq/summary/route'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

export type ReviewIssueType =
  | 'contradiction'
  | 'vague_obs'
  | 'missing_attachment'
  | 'unexplained_skip'
  | 'pending_count'
  | 'value_anomaly'
  | 'inconsistent_term'

export interface ReviewIssue {
  severity: 'warning' | 'info'
  item_id: number | null
  type: ReviewIssueType
  message: string
  suggestion: string
}

export interface ReviewResponse {
  verdict: 'ok' | 'warnings'
  issues: ReviewIssue[]
}

function isValidBody(b: unknown): b is SummaryRequestBody {
  if (!b || typeof b !== 'object') return false
  const x = b as Record<string, unknown>
  if (typeof x.os_name !== 'string') return false
  if (!Array.isArray(x.equipments)) return false
  return x.equipments.every((e) => {
    if (!e || typeof e !== 'object') return false
    const eq = e as Record<string, unknown>
    return (
      typeof eq.tag === 'string' &&
      typeof eq.name === 'string' &&
      Array.isArray(eq.items)
    )
  })
}

const VALID_TYPES: ReviewIssueType[] = [
  'contradiction', 'vague_obs', 'missing_attachment',
  'unexplained_skip', 'pending_count', 'value_anomaly', 'inconsistent_term',
]

function parseReview(raw: string): ReviewResponse {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return { verdict: 'ok', issues: [] }
  }
  if (!parsed || typeof parsed !== 'object') return { verdict: 'ok', issues: [] }
  const obj = parsed as Record<string, unknown>
  const issues: ReviewIssue[] = []
  if (Array.isArray(obj.issues)) {
    for (const raw of obj.issues) {
      if (!raw || typeof raw !== 'object') continue
      const i = raw as Record<string, unknown>
      const type = typeof i.type === 'string' && (VALID_TYPES as string[]).includes(i.type) ? (i.type as ReviewIssueType) : null
      if (!type) continue
      const severity = i.severity === 'info' ? 'info' : 'warning'
      const item_id = typeof i.item_id === 'number' ? i.item_id : null
      const message = typeof i.message === 'string' ? i.message : ''
      const suggestion = typeof i.suggestion === 'string' ? i.suggestion : ''
      if (!message) continue
      issues.push({ severity, item_id, type, message, suggestion })
    }
  }
  const verdict = issues.length === 0 ? 'ok' : 'warnings'
  return { verdict, issues: issues.slice(0, 8) }
}

export async function POST(request: NextRequest) {
  const session = request.cookies.get('session_id')?.value
  if (!session) {
    return NextResponse.json({ error: 'Sessão expirada' }, { status: 401 })
  }
  if (!process.env.GROQ_API_KEY) {
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
    const { content } = await groqChat(
      [
        { role: 'system', content: REVIEW_SYSTEM_PROMPT },
        { role: 'user', content: JSON.stringify(body, null, 2) },
      ],
      {
        model: 'llama-3.3-70b-versatile',
        temperature: 0.1,
        max_tokens: 1500,
        response_format: { type: 'json_object' },
      },
    )
    return NextResponse.json(parseReview(content))
  } catch (e) {
    if (e instanceof GroqError) {
      return NextResponse.json({ error: e.message }, { status: e.status })
    }
    return NextResponse.json({ error: 'Erro ao revisar' }, { status: 500 })
  }
}
