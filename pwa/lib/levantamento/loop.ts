import { db } from './db'
import { backoffMs, drain, type PushFn } from './engine'

// Uma vez por carga de página: remontar o provider não pode devolver a
// 'pendente' entradas que o loop anterior ainda está enviando.
let bootResetDone = false
/** Só para testes: simula uma página recém-carregada. */
export function _resetBootFlagForTests() {
  bootResetDone = false
}

export interface SurveySyncOptions {
  push: PushFn
  intervalMs?: number
  /** Chamado após cada ciclo que enviou algo ou falhou. */
  onTick?: (r: { sent: number; failed: number; authError?: boolean }) => void
}

/**
 * Loop de sincronização do levantamento. Roda ao iniciar, em `online`, em
 * `kick()` e a cada `intervalMs` quando há pendências; após falha respeita
 * `backoffMs` (intervalo e `online` honram; `kick` manual ignora).
 */
export function startSurveySync(opts: SurveySyncOptions): { stop(): void; kick(): void } {
  const intervalMs = opts.intervalMs ?? 15_000
  let stopped = false
  let running = false
  let failures = 0
  let nextAllowed = 0

  async function tick(force: boolean) {
    if (stopped || running) return
    if (!force && Date.now() < nextAllowed) return
    running = true
    try {
      const pending = await db.outbox.where('state').equals('pendente').count()
      if (stopped || pending === 0) return
      const r = await drain(opts.push)
      if (stopped || r.skipped) return
      // Só falha transitória (voltou a pendente) conta para o backoff; `erro`
      // terminal é resposta do servidor e não indica problema de conexão.
      if ((r.retried ?? 0) > 0 && r.sent === 0) {
        failures += 1
        nextAllowed = Date.now() + backoffMs(failures)
      } else {
        failures = 0
        nextAllowed = 0
      }
      opts.onTick?.(r)
    } catch {
      failures += 1
      nextAllowed = Date.now() + backoffMs(failures)
    } finally {
      running = false
    }
  }

  const onOnline = () => {
    // Voltou o sinal: o backoff acumulado offline não vale mais.
    failures = 0
    nextAllowed = 0
    void tick(true)
  }

  // Entradas 'enviando' sobraram de um app fechado no meio do envio.
  const ready = bootResetDone
    ? tick(true)
    : ((bootResetDone = true),
      db.outbox
        .where('state')
        .equals('enviando')
        .modify({ state: 'pendente' })
        .catch(() => 0)
        .then(() => tick(true)))

  const id = setInterval(() => void tick(false), intervalMs)
  if (typeof window !== 'undefined') window.addEventListener('online', onOnline)

  return {
    stop() {
      stopped = true
      clearInterval(id)
      if (typeof window !== 'undefined') window.removeEventListener('online', onOnline)
    },
    kick() {
      void ready.then(() => tick(true))
    },
  }
}
