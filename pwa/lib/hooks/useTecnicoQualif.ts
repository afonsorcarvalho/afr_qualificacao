import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listOsMine,
  getOsDetail,
  getRelatorioDetail,
  startDailyRelatorio,
  collectItem,
  finalizeRelatorio,
  listRelatoriosFechados,
  getHistoricoSummary,
  type CollectItemPayload,
  type FinalizeRelatorioPayload,
} from '@/lib/odoo/tecnico'

export function useOsMine(userId: number, filterMine: boolean) {
  return useQuery({
    queryKey: ['tecnico-os', userId, filterMine],
    queryFn: () => listOsMine(userId, filterMine),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
    enabled: userId > 0,
  })
}

export function useOsDetail(osId: number, userId: number) {
  return useQuery({
    // `userId` entra na key: sem isso, trocar de usuário (logout/login) serviria
    // o relatório aberto do usuário anterior a partir do cache do React Query.
    queryKey: ['os-detail', osId, userId],
    queryFn: () => getOsDetail(osId, userId),
    staleTime: 30_000,
    enabled: osId > 0 && userId > 0,
  })
}

export function useRelatorioDetail(relId: number) {
  return useQuery({
    queryKey: ['relatorio-detail', relId],
    queryFn: () => getRelatorioDetail(relId),
    staleTime: 60_000,
    enabled: relId > 0,
  })
}

export function useStartDailyRelatorio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: startDailyRelatorio,
    onSuccess: (relId, osId) => {
      // Escreve o id devolvido pelo servidor direto no cache do detalhe
      // antes de invalidar — a UI vira na hora, sem esperar o refetch.
      // Sem `exact`, o filtro casa qualquer key que comece com
      // ['os-detail', osId], incluindo o `userId` que a key real carrega.
      qc.setQueriesData(
        { queryKey: ['os-detail', osId] },
        (old: unknown) =>
          old && typeof old === 'object'
            ? { ...old, open_relatorio_id: relId }
            : old,
      )
      qc.invalidateQueries({ queryKey: ['os-detail', osId] })
    },
  })
}

export function useCollectItem(osId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, payload }: { itemId: number; payload: CollectItemPayload }) =>
      collectItem(itemId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['os-detail', osId] })
    },
  })
}

export function useHistoricoSummary(userId: number) {
  return useQuery({
    queryKey: ['historico-summary', userId],
    queryFn: () => getHistoricoSummary(userId),
    staleTime: 60_000,
    enabled: userId > 0,
  })
}

export function useRelatoriosFechados(userId: number, limit = 50) {
  return useQuery({
    queryKey: ['historico-relatorios', userId, limit],
    queryFn: () => listRelatoriosFechados(userId, limit),
    staleTime: 60_000,
    enabled: userId > 0,
  })
}

export function useFinalizeRelatorio(osId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ relId, payload }: { relId: number; payload: FinalizeRelatorioPayload }) =>
      finalizeRelatorio(relId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['os-detail', osId] })
    },
  })
}
