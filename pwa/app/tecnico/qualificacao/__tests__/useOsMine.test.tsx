// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useOsMine } from '@/lib/hooks/useTecnicoQualif'
import * as tecnicoApi from '@/lib/odoo/tecnico'

vi.mock('@/lib/odoo/tecnico')

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('useOsMine', () => {
  beforeEach(() => vi.clearAllMocks())

  it('chama listOsMine com filterMine=true', async () => {
    vi.mocked(tecnicoApi.listOsMine).mockResolvedValue([])
    const { result } = renderHook(() => useOsMine(42, true), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(tecnicoApi.listOsMine).toHaveBeenCalledWith(42, true)
  })

  it('chama listOsMine com filterMine=false', async () => {
    vi.mocked(tecnicoApi.listOsMine).mockResolvedValue([])
    renderHook(() => useOsMine(42, false), { wrapper })
    await waitFor(() => expect(tecnicoApi.listOsMine).toHaveBeenCalledWith(42, false))
  })
})
