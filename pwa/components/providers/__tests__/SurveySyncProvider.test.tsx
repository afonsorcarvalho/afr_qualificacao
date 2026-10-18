// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from '@testing-library/react'

const stop = vi.fn()
const startSurveySync = vi.fn((_o: unknown) => ({ stop, kick: vi.fn() }))
vi.mock('@/lib/levantamento/loop', () => ({ startSurveySync: (o: unknown) => startSurveySync(o) }))
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
  useAuthStore.setState({ isAuthenticated: true, groups: { [G]: true } })
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
})
