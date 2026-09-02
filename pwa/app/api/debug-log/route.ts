import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const payload = await request.json()
    const { kind, message, stack, source, lineno, colno, url, userAgent, timestamp } = payload as {
      kind?: string
      message?: string
      stack?: string
      source?: string
      lineno?: number
      colno?: number
      url?: string
      userAgent?: string
      timestamp?: number
    }

    const when = new Date(timestamp ?? Date.now()).toISOString()

    console.error('\n━━━━━━━━━━━━━━━━━━ CLIENT ERROR ━━━━━━━━━━━━━━━━━━')
    console.error(`⏰ ${when}`)
    console.error(`📍 ${url ?? '?'}`)
    console.error(`🏷️  kind: ${kind ?? '?'}`)
    console.error(`💥 ${message ?? '(sem mensagem)'}`)
    if (source) console.error(`📄 ${source}:${lineno ?? '?'}:${colno ?? '?'}`)
    if (stack) console.error(`🧵 stack:\n${stack}`)
    if (userAgent) console.error(`🖥️  UA: ${userAgent}`)
    console.error('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n')
  } catch (err) {
    console.error('[debug-log] Falha ao parsear payload:', err)
  }

  return NextResponse.json({ ok: true })
}
