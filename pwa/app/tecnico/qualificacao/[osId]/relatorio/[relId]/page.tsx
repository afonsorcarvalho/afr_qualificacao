'use client'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, ClipboardList, CheckCircle2, Clock, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { LoadingState } from '@/components/ui/LoadingState'
import { useRelatorioDetail } from '@/lib/hooks/useTecnicoQualif'
import { CollectedCard } from '../../../_components/CollectedCard'

function fmtDateTime(s: string | false): string {
  if (!s) return '—'
  const d = new Date(s.includes('T') ? s : s.replace(' ', 'T') + 'Z')
  if (isNaN(d.getTime())) return s
  return d.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtDuration(hours: number): string {
  if (!hours || hours <= 0) return '—'
  const total = Math.round(hours * 60)
  const h = Math.floor(total / 60)
  const m = total % 60
  if (h === 0) return `${m}min`
  if (m === 0) return `${h}h`
  return `${h}h ${m}min`
}

export default function RelatorioDetailPage() {
  const { osId, relId } = useParams<{ osId: string; relId: string }>()
  const rid = parseInt(relId, 10)
  const router = useRouter()
  const { data, isLoading, error } = useRelatorioDetail(rid)

  if (isLoading) return <LoadingState label="Carregando relatório..." />
  if (error || !data) {
    return (
      <div className="space-y-3">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="mr-1 h-4 w-4" /> Voltar
        </Button>
        <p className="rounded-lg bg-destructive/10 p-3 text-center text-sm text-destructive">
          Erro ao carregar relatório
        </p>
      </div>
    )
  }

  const { relatorio, collect_items } = data
  const sigB64 = typeof relatorio.signature_technician === 'string' ? relatorio.signature_technician : null
  const stateBadge = relatorio.state === 'done'
    ? { label: '✓ Fechado', cls: 'bg-emerald-500/20 text-emerald-300 border-emerald-400/30' }
    : relatorio.state === 'cancel'
    ? { label: '✗ Cancelado', cls: 'bg-red-500/20 text-red-300 border-red-400/30' }
    : { label: '● Aberto', cls: 'bg-amber-500/20 text-amber-300 border-amber-400/30' }

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => router.back()}>
        <ArrowLeft className="mr-1 h-4 w-4" /> Voltar
        <kbd className="ml-2 hidden rounded border border-border/60 bg-muted/30 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground/90 sm:inline">Esc</kbd>
      </Button>

      <div className="rounded-2xl border border-border/70 bg-gradient-to-br from-emerald-500/10 via-cyan-500/5 to-transparent p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-300/80">
              Relatório
            </p>
            <h1 className="mt-0.5 truncate text-lg font-semibold text-foreground">{relatorio.name}</h1>
            <Link
              href={`/tecnico/qualificacao/${osId}`}
              className="mt-0.5 inline-block truncate text-xs text-cyan-300 hover:underline"
            >
              ↗ {relatorio.os_id?.[1] ?? '—'}
            </Link>
          </div>
          <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold ${stateBadge.cls}`}>
            {stateBadge.label}
          </span>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <Field icon={<Clock className="h-3 w-3" />} label="Início" value={fmtDateTime(relatorio.data_inicio)} />
          <Field icon={<CheckCircle2 className="h-3 w-3" />} label="Fim" value={fmtDateTime(relatorio.data_fim)} />
          <Field icon={<Clock className="h-3 w-3" />} label="Duração" value={fmtDuration(relatorio.time_execution)} />
          <Field icon={<ClipboardList className="h-3 w-3" />} label="Itens" value={String(collect_items.length)} />
        </div>
      </div>

      {relatorio.descricao && typeof relatorio.descricao === 'string' && (
        <section className="rounded-xl border border-border/70 bg-muted/20 p-3">
          <div className="mb-1 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/90">
            <FileText className="h-3 w-3" /> Descrição do turno
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
            {relatorio.descricao}
          </p>
        </section>
      )}

      {sigB64 && (
        <section className="rounded-xl border border-border/70 bg-muted/20 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/90">
              Assinatura técnico
            </div>
            <span className="text-[10px] text-muted-foreground/80">
              {fmtDateTime(relatorio.signature_technician_date)}
            </span>
          </div>
          <div className="flex items-center justify-center rounded-lg bg-white p-2">
            <img
              src={`data:image/png;base64,${sigB64}`}
              alt="Assinatura técnico"
              className="max-h-40 max-w-full object-contain"
            />
          </div>
        </section>
      )}

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/90">
            Coletas ({collect_items.length})
          </h2>
        </div>
        {collect_items.length === 0 ? (
          <p className="rounded-lg border border-border/70 bg-muted/20 p-4 text-center text-sm text-muted-foreground/90">
            Nenhuma coleta vinculada a este relatório.
          </p>
        ) : (
          <div className="space-y-2">
            {collect_items.map((it) => (
              <CollectedCard
                key={it.id}
                osId={parseInt(osId, 10)}
                item={it}
                canEdit={false}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function Field({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/30 px-2 py-1.5">
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground/80">
        {icon} {label}
      </div>
      <p className="mt-0.5 truncate text-xs font-medium text-foreground">{value}</p>
    </div>
  )
}
