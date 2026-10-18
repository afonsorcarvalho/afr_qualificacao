// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

const callKw = vi.fn()
vi.mock('@/lib/odoo/client', () => ({ default: { callKw: (...a: unknown[]) => callKw(...a) } }))

import { useAuthStore } from '@/lib/store/authStore'
import { hasGroup } from '@/lib/odoo/levantamento'
import { useHasGroup } from '../useHasGroup'

const G = 'afr_qualificacao_levantamento.group_survey_user'

beforeEach(() => {
  callKw.mockReset()
  useAuthStore.setState({ groups: {} })
})

describe('hasGroup', () => {
  it('chama res.users/has_group com o xmlid', async () => {
    callKw.mockResolvedValue(true)
    expect(await hasGroup(G)).toBe(true)
    expect(callKw).toHaveBeenCalledWith('res.users', 'has_group', [G])
  })
})

describe('useHasGroup', () => {
  it('false até o servidor responder e depois reflete e guarda em cache', async () => {
    callKw.mockResolvedValue(true)
    const { result } = renderHook(() => useHasGroup(G))
    expect(result.current).toBe(false)
    await waitFor(() => expect(result.current).toBe(true))
    expect(useAuthStore.getState().groups[G]).toBe(true)
  })

  it('offline/erro mantém o valor em cache', async () => {
    useAuthStore.setState({ groups: { [G]: true } })
    callKw.mockRejectedValue(new Error('offline'))
    const { result } = renderHook(() => useHasGroup(G))
    expect(result.current).toBe(true)
    await waitFor(() => expect(callKw).toHaveBeenCalled())
    expect(result.current).toBe(true)
  })

  it('logout limpa o cache de grupos', () => {
    useAuthStore.setState({ groups: { [G]: true } })
    useAuthStore.getState().logout()
    expect(useAuthStore.getState().groups).toEqual({})
  })
})
