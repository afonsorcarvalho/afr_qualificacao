// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useCollectItem } from '@/lib/hooks/useTecnicoQualif'
import * as tecnicoApi from '@/lib/odoo/tecnico'

vi.mock('@/lib/odoo/tecnico')

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('useCollectItem', () => {
  beforeEach(() => vi.clearAllMocks())

  it('chama collectItem com payload e state=collected default', async () => {
    vi.mocked(tecnicoApi.collectItem).mockResolvedValue()
    const { result } = renderHook(() => useCollectItem(99), { wrapper })
    await act(async () => {
      result.current.mutate({
        itemId: 5,
        payload: { relatorio_id: 7, description: 'teste' },
      })
    })
    await waitFor(() =>
      expect(tecnicoApi.collectItem).toHaveBeenCalledWith(5, {
        relatorio_id: 7,
        description: 'teste',
      }),
    )
  })
})
