// app/api/groq/transcribe/route.ts
// Caminho histórico: continua em /api/groq/transcribe (renomear forçaria
// mudança de proxy Apache em produção só por motivo cosmético — ver task 2
// da migração Groq→OpenRouter). O provedor por trás agora é o OpenRouter.
import { NextRequest, NextResponse } from 'next/server'
import { openrouterTranscribe } from '@/lib/llm/transcribe'
import { LlmError } from '@/lib/llm/client'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

const MAX_SIZE = 25 * 1024 * 1024 // 25MB

export async function POST(request: NextRequest) {
  const session = request.cookies.get('session_id')?.value
  if (!session) {
    return NextResponse.json({ error: 'Sessão expirada' }, { status: 401 })
  }
  if (!process.env.OPENROUTER_API_KEY) {
    return NextResponse.json({ error: 'IA não configurada' }, { status: 503 })
  }
  let form: FormData
  try {
    form = await request.formData()
  } catch {
    return NextResponse.json({ error: 'multipart/form-data inválido' }, { status: 400 })
  }
  const audio = form.get('audio')
  if (!(audio instanceof Blob)) {
    return NextResponse.json({ error: 'Campo "audio" ausente' }, { status: 400 })
  }
  if (audio.size === 0) {
    return NextResponse.json({ error: 'Áudio vazio' }, { status: 400 })
  }
  if (audio.size > MAX_SIZE) {
    return NextResponse.json({ error: 'Áudio excede 25MB' }, { status: 413 })
  }

  try {
    const result = await openrouterTranscribe(audio, { language: 'pt' })
    return NextResponse.json(result)
  } catch (e) {
    if (e instanceof LlmError) {
      return NextResponse.json({ error: e.message }, { status: e.status })
    }
    return NextResponse.json({ error: 'Erro ao transcrever' }, { status: 500 })
  }
}
