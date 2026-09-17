import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchAgenda,
  agendaDisponivel,
  updateVisita,
  createVisita,
  deleteVisita,
  listTecnicoOptions,
  listOsOptions,
  listInstrumentoOptions,
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
  const qc = useQueryClient()
  const invalidar = useInvalidarAgenda()
  return useMutation({
    mutationFn: ({ id, vals }: { id: number; vals: VisitaVals }) => updateVisita(id, vals),
    // `pwa_visita_update` já devolve a visita serializada — usar esse
    // retorno para atualizar o cache NA HORA, antes do `invalidateQueries`
    // (assíncrono: dispara o refetch mas não espera por ele). Sem isto, dois
    // toques em sequência (ex. ligar dois instrumentos, um logo depois do
    // outro) partem do mesmo payload velho: o segundo lê `instrument_ids`
    // de antes do primeiro gravar, e o `(6, 0, ids)` do servidor apaga o que
    // o primeiro toque tinha acabado de ligar.
    onSuccess: (visita) => {
      qc.setQueriesData<AgendaPayload>({ queryKey: ['agenda'] }, (old) => {
        if (!old) return old
        return {
          ...old,
          visitas: old.visitas.map((v) => (v.id === visita.id ? visita : v)),
        }
      })
      invalidar()
    },
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

export function useInstrumentoOptions(enabled: boolean) {
  return useQuery({
    queryKey: ['agenda-instrumentos'],
    queryFn: listInstrumentoOptions,
    staleTime: 5 * 60_000,
    enabled,
  })
}
