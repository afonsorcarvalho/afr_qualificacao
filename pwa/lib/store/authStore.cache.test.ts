// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from './authStore'
import { clearSwCaches } from '@/lib/pwa/clearSwCaches'

const del = vi.fn().mockResolvedValue(true)

beforeEach(() => {
  del.mockClear()
  vi.stubGlobal('caches', { delete: del })
  useAuthStore.setState({ userId: null, isAuthenticated: false })
})

const apagados = () => del.mock.calls.map((c) => c[0]).sort()

describe('limpeza dos caches do SW', () => {
  it('clearSwCaches apaga pages, rsc e start-url', async () => {
    await clearSwCaches()
    expect(apagados()).toEqual(['pages', 'rsc', 'start-url'])
  })

  it('não quebra sem a Cache API', async () => {
    vi.stubGlobal('caches', undefined)
    // typeof undefined-valued global ainda é 'undefined'
    await expect(clearSwCaches()).resolves.toBeUndefined()
  })

  it('logout limpa', () => {
    useAuthStore.getState().logout()
    expect(apagados()).toEqual(['pages', 'rsc', 'start-url'])
  })

  it('setUser com outro usuário limpa; mesmo usuário ou primeiro login não', () => {
    useAuthStore.getState().setUser(1, 'a')
    expect(del).not.toHaveBeenCalled()
    useAuthStore.getState().setUser(1, 'a')
    expect(del).not.toHaveBeenCalled()
    useAuthStore.getState().setUser(2, 'b')
    expect(apagados()).toEqual(['pages', 'rsc', 'start-url'])
  })
})
