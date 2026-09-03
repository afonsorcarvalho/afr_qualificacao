'use client'
import { useEffect } from 'react'
import { PendingLink } from '@/components/ui/PendingLink'
import { LoadingState } from '@/components/ui/LoadingState'
import { FileText, CheckCircle2, Camera, ClipboardList, Clock, ChevronRight } from 'lucide-react'
import { useHistoricoSummary, useRelatoriosFechados } from '@/lib/hooks/useTecnicoQualif'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import type { RelatorioHistorico } from '@/lib/odoo/tecnico'

function fmtDate(s: string | false): string {
  if (!s) return '—'
  const d = new Date(s.includes('T') ? s : s.replace(' ', 'T') + 'Z')
  if (isNaN(d.getTime())) return s
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

function fmtTime(s: string | false): string {
  if (!s) return ''
  const d = new Date(s.includes('T') ? s : s.replace(' ', 'T') + 'Z')
  if (isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

/** Chave `YYYY-MM-DD` do dia **local** do instante — não do dia UTC.
 *
 * `toISOString().slice(0, 10)` devolve o dia UTC: um relatório fechado às 22h
 * de um fuso UTC-3 tem instante 01h UTC do dia seguinte e ia parar no grupo do
 * dia errado (e no rótulo "Hoje" errado). Estes rótulos são de exibição e
 * seguem o relógio do aparelho de propósito — os contadores do topo é que vêm
 * carimbados pelo servidor (`action_historico_hoje`).
 */
function localDayKey(d: Date): string {
  const mes = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mes}-${dia}`
}

function groupByDay(items: RelatorioHistorico[]): Array<{ key: string; label: string; items: RelatorioHistorico[] }> {
  const map = new Map<string, RelatorioHistorico[]>()
  for (const r of items) {
    const ref = r.data_fim || r.signature_technician_date
    if (!ref) {
      if (!map.has('sem-data')) map.set('sem-data', [])
      map.get('sem-data')!.push(r)
      continue
    }
    const d = new Date(ref.includes('T') ? ref : ref.replace(' ', 'T') + 'Z')
    const key = localDayKey(d)
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(r)
  }
  const today = localDayKey(new Date())
  const yest = localDayKey(new Date(Date.now() - 86400000))
  return Array.from(map.entries()).map(([key, items]) => {
    let label = key
    if (key === today) label = 'Hoje'
    else if (key === yest) label = 'Ontem'
    else if (key !== 'sem-data') {
      // `new Date('YYYY-MM-DD')` seria lido como meia-noite UTC e, em fuso
      // negativo, renderizaria o dia anterior. Montando por partes a data
      // nasce local, igual à chave.
      const [ano, mes, dia] = key.split('-').map(Number)
      const d = new Date(ano, mes - 1, dia)
      label = d.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' })
    } else label = 'Sem data'
    return { key, label, items }
  })
}

export default function HistoricoPage() {
  const { lastUserId, setLastUserId } = useTecnicoSettings()

  useEffect(() => {
    fetch('/api/odoo/session-info')
      .then((r) => r.json())
      .then((d) => d?.uid && setLastUserId(d.uid))
      .catch(() => {})
  }, [setLastUserId])

  const userId = lastUserId ?? 0
  const summary = useHistoricoSummary(userId)
  const relatorios = useRelatoriosFechados(userId, 50)

  const groups = relatorios.data ? groupByDay(relatorios.data) : []

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Histórico</h1>
        <p className="text-xs text-muted-foreground/80">Resumo do dia e relatórios fechados</p>
      </div>

      <div className="rounded-2xl border border-border/70 bg-gradient-to-br from-cyan-500/15 via-blue-500/10 to-transparent p-4 shadow-lg shadow-cyan-500/10">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-cyan-300/80">Hoje</p>
        {summary.isLoading ? (
          <LoadingState label="Carregando resumo..." className="py-3" />
        ) : summary.error ? (
          <p className="mt-2 text-sm text-red-400">Erro ao carregar resumo</p>
        ) : (
          <div className="mt-3 grid grid-cols-3 gap-2">
            <SummaryCell
              icon={<Camera className="h-4 w-4" />}
              value={summary.data?.hoje_coletas ?? 0}
              label="coletas"
              tone="cyan"
            />
            <SummaryCell
              icon={<ClipboardList className="h-4 w-4" />}
              value={summary.data?.hoje_oss ?? 0}
              label="OSs"
              tone="violet"
            />
            <SummaryCell
              icon={<CheckCircle2 className="h-4 w-4" />}
              value={summary.data?.hoje_relatorios_fechados ?? 0}
              label="rel. fechados"
              tone="emerald"
            />
          </div>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80">
            Relatórios fechados
          </h2>
          {relatorios.data && (
            <span className="text-xs text-muted-foreground/80">{relatorios.data.length}</span>
          )}
        </div>

        {relatorios.isLoading && (
          <LoadingState label="Carregando relatórios..." />
        )}
        {relatorios.error && (
          <p className="text-center text-sm text-red-400">Erro ao carregar relatórios</p>
        )}
        {relatorios.data && relatorios.data.length === 0 && (
          <p className="rounded-lg border border-border/70 bg-muted/20 p-4 text-center text-sm text-muted-foreground/90">
            Nenhum relatório fechado ainda.
          </p>
        )}

        {groups.map((g) => (
          <div key={g.key} className="space-y-2">
            <div className="sticky top-14 z-[5] -mx-3 bg-background/80 px-3 py-1 backdrop-blur">
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{g.label}</p>
            </div>
            {g.items.map((r) => <RelatorioCard key={r.id} r={r} />)}
          </div>
        ))}
      </div>
    </div>
  )
}

function SummaryCell({
  icon, value, label, tone,
}: {
  icon: React.ReactNode
  value: number
  label: string
  tone: 'cyan' | 'violet' | 'emerald'
}) {
  const color = tone === 'cyan' ? 'text-cyan-300' : tone === 'violet' ? 'text-violet-300' : 'text-emerald-300'
  return (
    <div className="rounded-lg bg-muted/30 p-2 text-center">
      <div className={`mx-auto mb-1 flex h-6 w-6 items-center justify-center ${color}`}>{icon}</div>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground/80">{label}</p>
    </div>
  )
}

function RelatorioCard({ r }: { r: RelatorioHistorico }) {
  const itemCount = r.collect_item_ids?.length ?? 0
  const time = r.signature_technician_date || r.data_fim
  return (
    <PendingLink href={`/tecnico/qualificacao/${r.os_id?.[0]}/relatorio/${r.id}`}>
      <div className="group rounded-lg border border-border/70 bg-muted/20 p-3 transition hover:border-emerald-400/40 hover:bg-emerald-500/[0.04]">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-emerald-500/15 text-emerald-300">
            <FileText className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <strong className="truncate text-sm text-foreground">REL #{r.id}</strong>
              <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">
                ✓ ASSINADO
              </span>
            </div>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {r.os_id?.[1] ?? '—'}
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground/90">
              <span className="inline-flex items-center gap-1">
                <Camera className="h-3 w-3" /> {itemCount} item{itemCount !== 1 ? 's' : ''}
              </span>
              {time && (
                <span className="inline-flex items-center gap-1">
                  <Clock className="h-3 w-3" /> {fmtDate(time)} · {fmtTime(time)}
                </span>
              )}
              {r.time_execution > 0 && (
                <span>{r.time_execution.toFixed(1)}h</span>
              )}
              {r.pending_collect_count > 0 && (
                <span className="text-amber-300">{r.pending_collect_count} pend.</span>
              )}
            </div>
          </div>
          <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground/60 transition group-hover:text-muted-foreground" />
        </div>
      </div>
    </PendingLink>
  )
}
