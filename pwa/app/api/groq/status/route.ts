// app/api/groq/status/route.ts
// Caminho histórico: continua em /api/groq/status (ver task 2 da migração
// Groq→OpenRouter). O provedor por trás agora é o OpenRouter.
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
  return NextResponse.json({ enabled: !!process.env.OPENROUTER_API_KEY })
}
