// app/api/chat/status/route.ts
// Deliberadamente sem autenticação: devolve apenas um booleano sobre a
// configuração, e a UI precisa consultar sem session para decidir se
// renderiza o botão do chat.
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
  return NextResponse.json({ enabled: !!process.env.OPENROUTER_API_KEY })
}
