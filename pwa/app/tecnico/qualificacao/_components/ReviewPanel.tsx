'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { Search, AlertTriangle, Info, CheckCircle2, EyeOff, RotateCw, X, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useGroqStatus } from '@/lib/hooks/useGroqStatus'
import { useReviewDismissed } from '@/lib/hooks/useReviewDismissed'
import { useReviewCache } from '@/lib/hooks/useReviewCache'
import toast from 'react-hot-toast'
import type { SummaryRequestBody } from '@/app/api/groq/summary/route'
import type { ReviewIssue, ReviewIssueType, ReviewResponse } from '@/app/api/groq/review/route'

interface ReviewPanelProps {
  buildContext: () => SummaryRequestBody
  osId: number
  relId: number
  autoTrigger?: boolean
  collapsedByDefault?: boolean
  className?: string
}

const TYPE_LABEL: Record<ReviewIssueType, string> = {
  contradiction: 'Contradição',
  vague_obs: 'Observação vaga',
  missing_attachment: 'Anexo possivelmente ausente',
  unexplained_skip: 'Pulado sem justificativa',
  pending_count: 'Pendentes',
  value_anomaly: 'Valor suspeito',
  inconsistent_term: 'Terminologia inconsistente',
}

export function ReviewPanel({
  buildContext,
  osId,
  relId,
  autoTrigger = false,
  collapsedByDefault = false,
  className,
}: ReviewPanelProps) {
  const { enabled } = useGroqStatus()
  const { dismiss, restore, isDismissed: isDism } = useReviewDismissed(relId)
  const { data: cachedData, fetchedAt, hydrated, save: saveCache } = useReviewCache(relId)
  const [open, setOpen] = useState(!collapsedByDefault)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<ReviewResponse | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [showDismissed, setShowDismissed] = useState(false)
  const autoTriggeredRef = useRef(false)

  useEffect(() => {
    if (!hydrated) return
    if (cachedData && !data) setData(cachedData)
  }, [hydrated, cachedData, data])

  const runReview = useCallback(async () => {
    if (loading) return
    setLoading(true)
    setErrorMsg(null)
    try {
      const ctx = buildContext()
      const res = await fetch('/api/groq/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ctx),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const j = await res.json()
          if (j?.error) msg = j.error
        } catch { /* ignore */ }
        throw new Error(msg)
      }
      const json = (await res.json()) as ReviewResponse
      setData(json)
      saveCache(json)
    } catch (e: any) {
      const m = e?.message || 'indisponível'
      setErrorMsg(m)
      toast.error(`IA revisão: ${m}`)
    } finally {
      setLoading(false)
    }
  }, [buildContext, loading, saveCache])

  useEffect(() => {
    if (!autoTrigger) return
    if (autoTriggeredRef.current) return
    if (!enabled) return
    if (!hydrated) return
    if (typeof navigator !== 'undefined' && navigator.onLine === false) return
    if (cachedData) {
      autoTriggeredRef.current = true
      return
    }
    autoTriggeredRef.current = true
    void runReview()
  }, [autoTrigger, enabled, hydrated, cachedData, runReview])

  if (!enabled) return null

  const issues = data?.issues ?? []
  const visibleIssues = issues.filter((i) => !isDism({ item_id: i.item_id, type: i.type }))
  const hiddenCount = issues.length - visibleIssues.length
  const verdict = data?.verdict
  const hasAny = issues.length > 0
  const noVisible = visibleIssues.length === 0 && hasAny
  const warningsBadge = visibleIssues.filter((i) => i.severity === 'warning').length

  return (
    <section className={`rounded-xl border border-border/70 bg-muted/20 ${className ?? ''}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
      >
        <div className="flex items-center gap-2">
          <Search className="h-4 w-4 text-violet-500 dark:text-violet-300" />
          <span className="text-sm font-semibold text-foreground">Revisão automática</span>
          {loading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
          {!loading && data && (
            verdict === 'ok' || visibleIssues.length === 0 ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 dark:text-emerald-200">
                <CheckCircle2 className="h-2.5 w-2.5" /> OK
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold text-amber-800 dark:text-amber-200">
                <AlertTriangle className="h-2.5 w-2.5" /> {warningsBadge}
              </span>
            )
          )}
          {!loading && !data && !errorMsg && (
            <span className="text-[11px] text-muted-foreground/80">não executada</span>
          )}
          {errorMsg && (
            <span className="text-[11px] text-red-500">erro</span>
          )}
        </div>
        <span className="text-[11px] text-muted-foreground/80">{open ? 'recolher' : 'expandir'}</span>
      </button>

      {open && (
        <div className="border-t border-border/50 p-3 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div className="space-y-0.5">
              <p className="text-[11px] text-muted-foreground/90">
                A IA analisa coletas, observações e status e sinaliza inconsistências.
                Nada disto bloqueia o fechamento.
              </p>
              {fetchedAt && (
                <p className="text-[10px] text-muted-foreground/70">
                  Última revisão: {formatFetched(fetchedAt)}
                </p>
              )}
            </div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={runReview}
              disabled={loading}
              className="shrink-0"
            >
              {loading ? (
                <><Loader2 className="mr-1 h-3 w-3 animate-spin" /> Analisando</>
              ) : (
                <><RotateCw className="mr-1 h-3 w-3" /> {data ? 'Re-revisar' : 'Revisar'}</>
              )}
            </Button>
          </div>

          {errorMsg && (
            <p className="rounded-md bg-destructive/10 px-2 py-1 text-xs text-destructive">
              {errorMsg}
            </p>
          )}

          {!loading && data && visibleIssues.length === 0 && !hasAny && (
            <p className="rounded-md border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-800 dark:text-emerald-200">
              ✓ Nenhuma inconsistência detectada.
            </p>
          )}

          {!loading && noVisible && (
            <p className="rounded-md border border-border/60 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              Todas as {issues.length} atenções foram ignoradas.
            </p>
          )}

          {visibleIssues.length > 0 && (
            <ul className="space-y-2">
              {visibleIssues.map((i, idx) => (
                <IssueRow
                  key={`${i.item_id ?? 'os'}-${i.type}-${idx}`}
                  issue={i}
                  osId={osId}
                  onDismiss={() => dismiss({ item_id: i.item_id, type: i.type })}
                />
              ))}
            </ul>
          )}

          {hiddenCount > 0 && (
            <button
              type="button"
              onClick={() => setShowDismissed((v) => !v)}
              className="flex w-full items-center justify-center gap-1 rounded-md border border-dashed border-border/60 bg-muted/10 px-2 py-1.5 text-[11px] text-muted-foreground hover:text-foreground"
            >
              <EyeOff className="h-3 w-3" />
              {showDismissed ? 'Esconder' : 'Mostrar'} ignoradas ({hiddenCount})
            </button>
          )}

          {showDismissed && hiddenCount > 0 && (
            <ul className="space-y-2 border-t border-dashed border-border/40 pt-2">
              {issues
                .filter((i) => isDism({ item_id: i.item_id, type: i.type }))
                .map((i, idx) => (
                  <IssueRow
                    key={`dism-${i.item_id ?? 'os'}-${i.type}-${idx}`}
                    issue={i}
                    osId={osId}
                    dismissed
                    onRestore={() => restore({ item_id: i.item_id, type: i.type })}
                  />
                ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}

function formatFetched(ts: number): string {
  const d = new Date(ts)
  const now = Date.now()
  const diffMin = Math.round((now - ts) / 60000)
  if (diffMin < 1) return 'agora há pouco'
  if (diffMin < 60) return `há ${diffMin}min`
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  return `${dd}/${mo} ${hh}:${mm}`
}

function IssueRow({
  issue,
  osId,
  dismissed,
  onDismiss,
  onRestore,
}: {
  issue: ReviewIssue
  osId: number
  dismissed?: boolean
  onDismiss?: () => void
  onRestore?: () => void
}) {
  const iconCls = issue.severity === 'warning'
    ? 'text-amber-600 dark:text-amber-300'
    : 'text-cyan-600 dark:text-cyan-300'
  const Icon = issue.severity === 'warning' ? AlertTriangle : Info
  const containerCls = dismissed
    ? 'opacity-60'
    : 'bg-muted/30 dark:bg-muted/40'

  return (
    <li className={`rounded-md border border-border/60 px-3 py-2 ${containerCls}`}>
      <div className="flex items-start gap-2">
        <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${iconCls}`} />
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80">
            {TYPE_LABEL[issue.type] ?? issue.type}
          </p>
          <p className="text-xs text-foreground/95">{issue.message}</p>
          {issue.suggestion && (
            <p className="mt-0.5 text-[11px] italic text-muted-foreground/85">
              → {issue.suggestion}
            </p>
          )}
          <div className="mt-1.5 flex items-center gap-2">
            {issue.item_id != null && (
              <Link
                href={`/tecnico/qualificacao/${osId}/coleta/${issue.item_id}`}
                className="rounded bg-cyan-600/10 px-2 py-0.5 text-[11px] font-semibold text-cyan-700 hover:bg-cyan-600/20 dark:text-cyan-300"
              >
                Ir para item
              </Link>
            )}
            {!dismissed && onDismiss && (
              <button
                type="button"
                onClick={onDismiss}
                className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted/40"
              >
                <X className="h-3 w-3" /> Ignorar
              </button>
            )}
            {dismissed && onRestore && (
              <button
                type="button"
                onClick={onRestore}
                className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted/40"
              >
                <RotateCw className="h-3 w-3" /> Restaurar
              </button>
            )}
          </div>
        </div>
      </div>
    </li>
  )
}
