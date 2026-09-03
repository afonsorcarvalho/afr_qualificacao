// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SummaryButton } from '../_components/SummaryButton'

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

const ctx = { os_name: 'QOS00001', equipments: [] }

beforeEach(() => {
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes('/api/groq/status')) {
      return Promise.resolve(new Response(JSON.stringify({ enabled: true }), { status: 200 }))
    }
    if (url.includes('/api/groq/summary')) {
      return Promise.resolve(new Response(JSON.stringify({ summary: 'resumo OK' }), { status: 200 }))
    }
    return Promise.resolve(new Response('{}', { status: 200 }))
  }) as unknown as typeof fetch
})

describe('SummaryButton', () => {
  it('chama onGenerate com summary', async () => {
    const onGen = vi.fn()
    wrap(<SummaryButton onGenerate={onGen} buildContext={() => ctx as any} />)
    await new Promise((r) => setTimeout(r, 30))
    fireEvent.click(screen.getByRole('button'))
    await new Promise((r) => setTimeout(r, 30))
    expect(onGen).toHaveBeenCalledWith('resumo OK')
  })

  it('confirmOverwrite=true pede confirmação antes', async () => {
    const onGen = vi.fn()
    const confirmMock = vi.fn(() => false)
    const original = window.confirm
    window.confirm = confirmMock
    try {
      wrap(
        <SummaryButton
          onGenerate={onGen}
          buildContext={() => ctx as any}
          confirmOverwrite
        />,
      )
      await new Promise((r) => setTimeout(r, 30))
      fireEvent.click(screen.getByRole('button'))
      await new Promise((r) => setTimeout(r, 30))
      expect(confirmMock).toHaveBeenCalled()
      expect(onGen).not.toHaveBeenCalled()
    } finally {
      window.confirm = original
    }
  })
})
