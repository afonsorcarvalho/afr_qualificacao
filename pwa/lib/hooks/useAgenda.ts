import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchAgenda,
  agendaDisponivel,
  updateVisita,
  createVisita,
  deleteVisita,
  listTecnicoOptions,
  listOsOptions,
  type AgendaPayload,
  type VisitaVals,
} from '@/lib/odoo/agenda'

export function useAgendaDisponivel() {
  return useQuery({
    queryKey: ['agenda-disponivel'],
    queryFn: agendaDisponivel,
    staleTime: Infinity,
    retry: false,
  })
}

export function useAgenda(
  dateFrom: string | null,
  dateTo: string | null,
  onlyMine: boolean,
  enabled: boolean,
) {
  return useQuery<AgendaPayload>({
    queryKey: ['agenda', dateFrom, dateTo, onlyMine],
    queryFn: () => fetchAgenda(dateFrom, dateTo, onlyMine),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
    enabled,
  })
}

/**
 * Invalida a agenda E a lista de OSs: `date_planned_start`/`date_planned_end`
 * da OS são rollup computado das visitas, e a home mostra esse campo no card.
 */
function useInvalidarAgenda() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['agenda'] })
    qc.invalidateQueries({ queryKey: ['tecnico-os'] })
  }
}

export function useUpdateVisita() {
  const invalidar = useInvalidarAgenda()
  return useMutation({
    mutationFn: ({ id, vals }: { id: number; vals: VisitaVals }) => updateVisita(id, vals),
    onSuccess: invalidar,
  })
}

export function useCreateVisita() {
  const invalidar = useInvalidarAgenda()
  return useMutation({
    mutationFn: ({ osId, tecnicoId, date }: { osId: number; tecnicoId: number; date: string }) =>
      createVisita(osId, tecnicoId, date),
    onSuccess: invalidar,
  })
}

export function useDeleteVisita() {
  const invalidar = useInvalidarAgenda()
  return useMutation({
    mutationFn: (id: number) => deleteVisita(id),
    onSuccess: invalidar,
  })
}

export function useTecnicoOptions(enabled: boolean) {
  return useQuery({
    queryKey: ['agenda-tecnicos'],
    queryFn: listTecnicoOptions,
    staleTime: 5 * 60_000,
    enabled,
  })
}

export function useOsOptions(enabled: boolean) {
  return useQuery({
    queryKey: ['agenda-os'],
    queryFn: listOsOptions,
    staleTime: 5 * 60_000,
    enabled,
  })
}
