// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from '@testing-library/react'

const stop = vi.fn()
const startSurveySync = vi.fn((_o: unknown) => ({ stop, kick: vi.fn() }))
vi.mock('@/lib/levantamento/loop', () => ({ startSurveySync: (o: unknown) => startSurveySync(o) }))
vi.mock('@/lib/odoo/levantamento', () => ({ push: vi.fn(), hasGroup: vi.fn().mockResolvedValue(true) }))
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/levantamento',
}))

import Layout from '../layout'

beforeEach(() => vi.clearAllMocks())

describe('LevantamentoLayout', () => {
  it('inicia o sync uma vez com push, pede storage persistente e para ao desmontar', () => {
    const persist = vi.fn().mockResolvedValue(true)
    Object.defineProperty(navigator, 'storage', { value: { persist }, configurable: true })
    const { unmount } = render(<Layout>x</Layout>)
    expect(startSurveySync).toHaveBeenCalledTimes(1)
    expect(startSurveySync).toHaveBeenCalledWith(expect.objectContaining({ push: expect.any(Function) }))
    expect(persist).toHaveBeenCalledTimes(1)
    unmount()
    expect(stop).toHaveBeenCalled()
  })
})
