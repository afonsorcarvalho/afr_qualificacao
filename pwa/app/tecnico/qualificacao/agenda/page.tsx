'use client'
import { useState } from 'react'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { VisitaCard } from '../_components/VisitaCard'
import { VisitaSheet } from '../_components/VisitaSheet'
import { LoadingState } from '@/components/ui/LoadingState'
import { useAgenda, useAgendaDisponivel } from '@/lib/hooks/useAgenda'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import type { VisitaAgenda } from '@/lib/odoo/agenda'
import { agruparPorDia, deslocarJanela } from './janela'

const JANELA_DIAS = 14

function rotuloDia(iso: string): string {
  const [a, m, d] = iso.split('-').map(Number)
  return new Intl.DateTimeFormat('pt-BR', {
    weekday: 'short', day: '2-digit', month: 'short', timeZone: 'UTC',
  }).format(new Date(Date.UTC(a, m - 1, d)))
}

export default function AgendaPage() {
  const disponivel = useAgendaDisponivel()
  const { filterMine, setFilterMine } = useTecnicoSettings()
  // `null` na primeira carga: o servidor decide a janela e devolve
  // `date_from`, que passa a ancorar a navegação.
  const [inicio, setInicio] = useState<string | null>(null)
  const fim = inicio ? deslocarJanela(inicio, JANELA_DIAS - 1) : null
  // `disponivel.data` é `undefined` enquanto a query de disponibilidade
  // carrega (não `false`) — só o `false` explícito (módulo ausente) deve
  // segurar o `pwa_agenda_fetch`. Enquanto carrega, a busca segue normal.
  const { data, isLoading, error } = useAgenda(inicio, fim, filterMine, disponivel.data !== false)
  const [selecionada, setSelecionada] = useState<VisitaAgenda | null>(null)
  const [criando, setCriando] = useState(false)
  // Muda a cada abertura: sem isto, os `useState` internos da folha em modo
  // criar sobrevivem a fechar/reabrir e o FAB reabre com OS/data anteriores.
  const [criarSeq, setCriarSeq] = useState(0)

  if (disponivel.data === false) {
    return (
      <p className="mx-auto max-w-[880px] p-4 text-center text-muted-foreground">
        Agenda de visitas indisponível: o módulo de agendamento não está
        instalado neste servidor.
      </p>
    )
  }

  const ancora = inicio ?? data?.date_from ?? null
  const semEmpregado = data ? !data.my_employee_id : false
  const grupos = agruparPorDia(data?.visitas ?? [])

  return (
    <div className="mx-auto w-full max-w-[880px] space-y-4">
      <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-2 py-1">
        <button
          type="button"
          aria-label="Semanas anteriores"
          className="flex h-11 w-11 items-center justify-center rounded-md hover:bg-accent"
          onClick={() => ancora && setInicio(deslocarJanela(ancora, -JANELA_DIAS))}
        >
          <ChevronLeft className="h-5 w-5" aria-hidden />
        </button>
        <span className="text-sm font-medium">
          {data ? `${rotuloDia(data.date_from)} – ${rotuloDia(data.date_to)}` : '—'}
        </span>
        <button
          type="button"
          aria-label="Próximas semanas"
          className="flex h-11 w-11 items-center justify-center rounded-md hover:bg-accent"
          onClick={() => ancora && setInicio(deslocarJanela(ancora, JANELA_DIAS))}
        >
          <ChevronRight className="h-5 w-5" aria-hidden />
        </button>
      </div>

      <label
        htmlFor="agenda-filter-mine"
        className="flex min-h-[44px] cursor-pointer items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2"
      >
        <span className="text-sm font-medium">
          Só minhas
          <span className="block text-xs font-normal text-muted-foreground">
            {semEmpregado
              ? 'Seu usuário não tem técnico vinculado'
              : filterMine
                ? 'Visitas atribuídas a você'
                : 'Visitas de toda a equipe'}
          </span>
        </span>
        <input
          id="agenda-filter-mine"
          type="checkbox"
          checked={filterMine && !semEmpregado}
          disabled={semEmpregado}
          onChange={(e) => setFilterMine(e.target.checked)}
          className="h-6 w-6 shrink-0 cursor-pointer accent-ok disabled:opacity-40"
        />
      </label>

      {isLoading && <LoadingState label="Carregando sua agenda..." />}
      {error && (
        <p className="text-center text-danger">
          Erro ao carregar a agenda. Verifique conexão.
        </p>
      )}
      {!isLoading && !error && grupos.length === 0 && (
        <p className="py-8 text-center text-muted-foreground">
          Nenhuma visita neste período.
        </p>
      )}

      {grupos.map((g) => (
        <section key={g.date} className="space-y-2">
          <h2 className="sticky top-0 z-10 bg-background py-1 text-sm font-semibold uppercase text-muted-foreground">
            {rotuloDia(g.date)}
          </h2>
          {g.visitas.map((v) => (
            <VisitaCard key={v.id} visita={v} onSelect={setSelecionada} />
          ))}
        </section>
      ))}

      {data?.can_manage && (
        <button
          type="button"
          onClick={() => {
            setCriarSeq((s) => s + 1)
            setCriando(true)
          }}
          className="fixed bottom-20 right-4 z-40 flex h-14 items-center gap-2 rounded-full bg-primary px-5 font-semibold text-primary-foreground shadow-[0_8px_24px_rgba(0,0,0,0.45)] lg:bottom-6"
        >
          <Plus className="h-5 w-5" aria-hidden />
          Nova visita
        </button>
      )}

      <VisitaSheet
        key={selecionada?.id ?? 'nenhuma'}
        open={!!selecionada}
        modo="editar"
        visita={selecionada}
        onClose={() => setSelecionada(null)}
      />
      <VisitaSheet
        key={`criar-${criarSeq}`}
        open={criando}
        modo="criar"
        visita={null}
        onClose={() => setCriando(false)}
      />
    </div>
  )
}
