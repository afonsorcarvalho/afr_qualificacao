// app/api/groq/transcribe/route.ts
// Caminho histórico: continua em /api/groq/transcribe (renomear forçaria
// mudança de proxy Apache em produção só por motivo cosmético — ver task 2
// da migração Groq→OpenRouter). O provedor por trás agora é o OpenRouter.
import { NextRequest, NextResponse } from 'next/server'
import { openrouterTranscribe } from '@/lib/llm/transcribe'
import { LlmError } from '@/lib/llm/client'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

// 25MB é um teto de sanidade sobre o que o navegador pode enviar, não um
// limite do provedor — o "(limite Groq)" de antes era sobre multipart, que
// não usamos mais. `openrouterTranscribe` (lib/llm/transcribe.ts) manda o
// áudio como JSON+base64, ~1/3 maior que o Blob medido aqui: uma requisição
// no teto vira ~33MB na rede, e isso é esperado, não um bug. O que de fato
// aperta neste caminho é tempo, não byte — a OpenRouter documenta timeout de
// uns 60s por requisição nos provedores upstream; quem segura isso é o teto
// de duração da gravação no cliente (`MAX_DURATION_MS` em
// `MicButton.tsx`), não este arquivo.
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
