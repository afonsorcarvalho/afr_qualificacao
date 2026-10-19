// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import 'fake-indexeddb/auto'
import { act, render } from '@testing-library/react'

const stop = vi.fn()
const startSurveySync = vi.fn((_o: unknown) => ({ stop, kick: vi.fn() }))
vi.mock('@/lib/levantamento/loop', () => ({ startSurveySync: (o: unknown) => startSurveySync(o) }))
let pathname = '/levantamento'
vi.mock('next/navigation', () => ({ usePathname: () => pathname }))
const hasGroup = vi.fn()
vi.mock('@/lib/odoo/levantamento', () => ({ push: vi.fn(), hasGroup: (...a: unknown[]) => hasGroup(...a) }))

import { useAuthStore } from '@/lib/store/authStore'
import { SurveySyncProvider } from '../SurveySyncProvider'
import { onSyncTick } from '@/lib/levantamento/events'

const G = 'afr_qualificacao_levantamento.group_survey_user'
const persist = vi.fn().mockResolvedValue(true)

beforeEach(() => {
  vi.clearAllMocks()
  hasGroup.mockResolvedValue(true)
  Object.defineProperty(navigator, 'storage', { value: { persist }, configurable: true })
  pathname = '/levantamento'
  useAuthStore.setState({ isAuthenticated: true, groups: { [G]: true }, serverUrl: 'https://s', dbName: 'd', userId: 1 })
})

describe('SurveySyncProvider', () => {
  it('inicia uma vez com push, pede storage persistente e para ao desmontar', () => {
    const { unmount } = render(<SurveySyncProvider />)
    expect(startSurveySync).toHaveBeenCalledTimes(1)
    expect(startSurveySync).toHaveBeenCalledWith(expect.objectContaining({ push: expect.any(Function) }))
    expect(persist).toHaveBeenCalledTimes(1)
    unmount()
    expect(stop).toHaveBeenCalledTimes(1)
  })

  it('não inicia sem o grupo nem sem autenticação', () => {
    useAuthStore.setState({ groups: { [G]: false } })
    hasGroup.mockResolvedValue(false)
    render(<SurveySyncProvider />)
    useAuthStore.setState({ isAuthenticated: false, groups: { [G]: true } })
    render(<SurveySyncProvider />)
    expect(startSurveySync).not.toHaveBeenCalled()
  })

  it('onTick emite o evento de sync', () => {
    render(<SurveySyncProvider />)
    const fn = vi.fn()
    const off = onSyncTick(fn)
    ;(startSurveySync.mock.calls[0][0] as { onTick: () => void }).onTick()
    expect(fn).toHaveBeenCalledTimes(1)
    off()
  })

  it('persist que rejeita não estoura', () => {
    persist.mockRejectedValueOnce(new Error('x'))
    expect(() => render(<SurveySyncProvider />)).not.toThrow()
  })

  it('não inicia em /login', () => {
    pathname = '/login'
    render(<SurveySyncProvider />)
    expect(startSurveySync).not.toHaveBeenCalled()
  })

  it('reinicia no banco do novo usuário ao trocar de sessão', async () => {
    const { openSurveyDb } = await import('@/lib/levantamento/db')
    render(<SurveySyncProvider />)
    expect(startSurveySync).toHaveBeenCalledTimes(1)
    const db1 = (startSurveySync.mock.calls[0][0] as { db: { name: string } }).db
    expect(db1.name).toBe(openSurveyDb('https://s|d|1').name)
    act(() => useAuthStore.setState({ userId: 2, groups: { [G]: true } }))
    expect(stop).toHaveBeenCalledTimes(1)
    expect(startSurveySync).toHaveBeenCalledTimes(2)
    const db2 = (startSurveySync.mock.calls[1][0] as { db: { name: string } }).db
    expect(db2.name).toBe(openSurveyDb('https://s|d|2').name)
    expect(db2.name).not.toBe(db1.name)
  })

  it('requestSync chama kick do loop', async () => {
    const kick = vi.fn()
    startSurveySync.mockReturnValueOnce({ stop, kick })
    const { requestSync } = await import('@/lib/levantamento/events')
    render(<SurveySyncProvider />)
    requestSync()
    expect(kick).toHaveBeenCalledTimes(1)
  })
})
