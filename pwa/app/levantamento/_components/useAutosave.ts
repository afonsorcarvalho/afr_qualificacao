'use client'
import { useCallback, useEffect, useRef } from 'react'

const DEBOUNCE_MS = 500

/**
 * Autosave com debounce por campo e saves SERIALIZADOS por formulário.
 *
 * Cada campo tem seu timer (500 ms); ao disparar, o save entra numa fila de
 * promessas — nunca há dois saves em voo no mesmo formulário. Isso garante que
 * o segundo save já enxergue a chave devolvida pelo primeiro (sem criar dois
 * registros `tmp:` para "novo"). Ao desmontar (ou com a página indo para segundo plano), os campos pendentes são
 * enviados na hora (não se perde edição de quem sai da tela em < 500 ms).
 *
 * `save(changed)` recebe só o(s) campo(s) alterado(s).
 */
export function useAutosave(
  save: (changed: Record<string, unknown>) => Promise<unknown>,
  onError?: (e: unknown) => void,
) {
  const saveRef = useRef(save)
  saveRef.current = save
  const errRef = useRef(onError)
  errRef.current = onError
  const queue = useRef<Promise<unknown>>(Promise.resolve())
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>())
  const pending = useRef(new Map<string, unknown>())

  /** Entra na fila serial; erros não travam a fila. */
  const enqueue = useCallback(<T,>(job: () => Promise<T>): Promise<T> => {
    const run = queue.current.then(job, job)
    queue.current = run.catch(() => undefined)
    return run
  }, [])

  const fire = useCallback(
    (field: string) => {
      const t = timers.current.get(field)
      if (t) clearTimeout(t)
      timers.current.delete(field)
      if (!pending.current.has(field)) return
      const value = pending.current.get(field)
      pending.current.delete(field)
      enqueue(() => saveRef.current({ [field]: value })).catch((e) => errRef.current?.(e))
    },
    [enqueue],
  )

  const edit = useCallback(
    (field: string, value: unknown) => {
      pending.current.set(field, value)
      const t = timers.current.get(field)
      if (t) clearTimeout(t)
      timers.current.set(field, setTimeout(() => fire(field), DEBOUNCE_MS))
    },
    [fire],
  )

  useEffect(() => {
    const t = timers.current
    const p = pending.current
    const flush = () => {
      for (const field of Array.from(p.keys())) fire(field)
    }
    // App indo para segundo plano / página sendo fechada: não espera o debounce.
    const onVis = () => {
      if (document.visibilityState === 'hidden') flush()
    }
    document.addEventListener('visibilitychange', onVis)
    window.addEventListener('pagehide', flush)
    return () => {
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener('pagehide', flush)
      flush()
      t.clear()
    }
  }, [fire])

  return { edit, enqueue }
}
