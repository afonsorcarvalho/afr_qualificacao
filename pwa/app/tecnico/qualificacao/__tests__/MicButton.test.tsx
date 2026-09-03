// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MicButton } from '../_components/MicButton'

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ enabled: true }), { status: 200 }),
  ) as unknown as typeof fetch
  ;(globalThis as any).MediaRecorder = class {
    static isTypeSupported() { return true }
  }
  Object.defineProperty(navigator, 'mediaDevices', {
    value: { getUserMedia: vi.fn() },
    configurable: true,
  })
})

describe('MicButton', () => {
  it('não renderiza quando Groq desabilitado', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ enabled: false }), { status: 200 }),
    ) as unknown as typeof fetch
    wrap(<MicButton onTranscribe={() => {}} />)
    await new Promise((r) => setTimeout(r, 30))
    expect(screen.queryByLabelText('Segurar para gravar')).toBeNull()
  })

  it('renderiza botão quando habilitado e suportado', async () => {
    wrap(<MicButton onTranscribe={() => {}} />)
    await new Promise((r) => setTimeout(r, 30))
    expect(screen.getByLabelText('Segurar para gravar')).toBeTruthy()
  })
})
