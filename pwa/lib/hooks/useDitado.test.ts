// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useDitado } from './useDitado'

class FakeRecorder {
  static ultima: FakeRecorder | null = null
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  state = 'inactive'
  constructor(public stream: unknown) {
    FakeRecorder.ultima = this
  }
  start() { this.state = 'recording' }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['x'], { type: 'audio/webm' }) })
    this.onstop?.()
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
  FakeRecorder.ultima = null
  ;(globalThis as any).MediaRecorder = FakeRecorder
  ;(globalThis as any).navigator.mediaDevices = {
    getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] }),
  }
})

describe('useDitado', () => {
  it('grava, transcreve e entrega o texto pelo callback', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'remarca a visita do João' }), { status: 200 }),
    ) as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(true)

    await act(async () => { await result.current.alternar() })
    await waitFor(() => expect(onTexto).toHaveBeenCalledWith('remarca a visita do João'))
    expect(result.current.gravando).toBe(false)
  })

  it('falha de transcrição não deixa o hook travado em gravando', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: 'IA não configurada' }), { status: 503 }),
    ) as unknown as typeof fetch
    const onTexto = vi.fn()
    const { result } = renderHook(() => useDitado(onTexto))

    await act(async () => { await result.current.alternar() })
    await act(async () => { await result.current.alternar() })
    await waitFor(() => expect(result.current.transcrevendo).toBe(false))
    expect(result.current.gravando).toBe(false)
    expect(onTexto).not.toHaveBeenCalled()
  })

  it('permissão de microfone negada não quebra', async () => {
    ;(globalThis as any).navigator.mediaDevices.getUserMedia =
      vi.fn().mockRejectedValue(new Error('NotAllowedError'))
    const { result } = renderHook(() => useDitado(vi.fn()))
    await act(async () => { await result.current.alternar() })
    expect(result.current.gravando).toBe(false)
  })
})
