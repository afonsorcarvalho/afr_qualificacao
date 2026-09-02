'use client'
import { useEffect } from 'react'
import { OsCard } from './_components/OsCard'
import { useOsMine } from '@/lib/hooks/useTecnicoQualif'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'

export default function HomePage() {
  const { filterMine, setFilterMine, lastUserId, setLastUserId } = useTecnicoSettings()
  useEffect(() => {
    fetch('/api/odoo/session-info')
      .then((r) => r.json())
      .then((d) => d?.uid && setLastUserId(d.uid))
      .catch(() => {})
  }, [setLastUserId])

  const userId = lastUserId ?? 0
  const { data, isLoading, error } = useOsMine(userId, filterMine)

  const inProgress = (data ?? []).filter((o) =>
    ['in_progress', 'in_approved'].includes(o.state),
  )
  const scheduled = (data ?? []).filter((o) => o.state === 'scheduled')
  const draft = filterMine ? (data ?? []).filter((o) => o.state === 'draft') : []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between rounded-lg bg-card p-3 shadow-sm">
        <label htmlFor="filter-mine" className="text-sm font-medium">Só minhas</label>
        <input
          id="filter-mine"
          type="checkbox"
          checked={filterMine}
          onChange={(e) => setFilterMine(e.target.checked)}
          className="h-5 w-9 cursor-pointer"
        />
      </div>

      {isLoading && <p className="text-center text-muted-foreground">Carregando...</p>}
      {error && (
        <p className="text-center text-destructive">
          Erro ao carregar OSs. Verifique conexão.
        </p>
      )}

      {inProgress.length > 0 && (
        <Section title={`Em andamento (${inProgress.length})`}>
          {inProgress.map((os) => <OsCard key={os.id} os={os} />)}
        </Section>
      )}
      {scheduled.length > 0 && (
        <Section title={`Agendadas (${scheduled.length})`}>
          {scheduled.map((os) => <OsCard key={os.id} os={os} />)}
        </Section>
      )}
      {draft.length > 0 && (
        <Section title={`Rascunhos (${draft.length})`}>
          {draft.map((os) => <OsCard key={os.id} os={os} />)}
        </Section>
      )}
      {!isLoading && data?.length === 0 && (
        <p className="mt-12 text-center text-muted-foreground">
          Nenhuma OS atribuída.
        </p>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h2>
      <div className="space-y-2">{children}</div>
    </div>
  )
}
