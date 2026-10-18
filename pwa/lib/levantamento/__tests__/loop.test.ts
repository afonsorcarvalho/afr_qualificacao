import 'fake-indexeddb/auto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { db } from '../db'
import { enqueue, type PushResponse } from '../engine'
import { startSurveySync, _resetBootFlagForTests } from '../loop'

beforeEach(async () => {
  _resetBootFlagForTests()
  await Promise.all(db.tables.map((t) => t.clear()))
})
afterEach(() => vi.useRealTimers())

const okPush = () =>
  vi.fn(async (ops: { op_uuid: string }[]): Promise<PushResponse> => ({
    results: ops.map((o) => ({ op_uuid: o.op_uuid, state: 'done', id: 1, error: false })),
    idmap: {},
  }))

describe('startSurveySync', () => {
  it('loop_resets_enviando_on_start', async () => {
    const id = await enqueue({ kind: 'cycle.upsert', ref: 'tmp:c', payload: {} })
    await db.outbox.update(id, { state: 'enviando' })
    const push = vi.fn(async () => { throw new Error('offline') })
    const h = startSurveySync({ push, intervalMs: 1_000_000 })
    await vi.waitFor(async () => {
      expect((await db.outbox.get(id))!.state).toBe('pendente')
    })
    h.stop()
  })

  it('does not reset enviando again on a remount in the same page load', async () => {
    const h1 = startSurveySync({ push: vi.fn(async () => { throw new Error('offline') }), intervalMs: 1_000_000 })
    await new Promise((r) => setTimeout(r, 20))
    h1.stop()
    const id = await enqueue({ kind: 'cycle.upsert', ref: 'tmp:c', payload: {} })
    await db.outbox.update(id, { state: 'enviando' })
    const h2 = startSurveySync({ push: vi.fn(async () => { throw new Error('offline') }), intervalMs: 1_000_000 })
    await new Promise((r) => setTimeout(r, 50))
    h2.stop()
    expect((await db.outbox.get(id))!.state).toBe('enviando')
  })

  it('drains pending on start and on kick', async () => {
    await enqueue({ kind: 'cycle.upsert', ref: 'tmp:c', payload: {} })
    const push = okPush()
    const h = startSurveySync({ push, intervalMs: 1_000_000 })
    await vi.waitFor(() => expect(push).toHaveBeenCalledTimes(1))
    await enqueue({ kind: 'cycle.upsert', ref: 'tmp:d', payload: {} })
    h.kick()
    await vi.waitFor(() => expect(push).toHaveBeenCalledTimes(2))
    h.stop()
  })

  it('does not call push when nothing is pending', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    const push = okPush()
    const h = startSurveySync({ push, intervalMs: 1000 })
    await vi.advanceTimersByTimeAsync(3500)
    expect(push).not.toHaveBeenCalled()
    h.stop()
  })

  it('interval retries pending, honoring backoff after a failure', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    await enqueue({ kind: 'cycle.upsert', ref: 'tmp:c', payload: {} })
    const push = vi.fn(async () => { throw new Error('offline') })
    const h = startSurveySync({ push, intervalMs: 1000 })
    await vi.waitFor(() => expect(push).toHaveBeenCalledTimes(1))
    // backoff after 1 failure = 4000ms; ticks at 1s,2s,3s are skipped
    await vi.advanceTimersByTimeAsync(3000)
    expect(push).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(2000)
    await vi.waitFor(() => expect(push).toHaveBeenCalledTimes(2))
    h.stop()
  })

  it('stop halts further runs', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    const push = okPush()
    const h = startSurveySync({ push, intervalMs: 1000 })
    h.stop()
    await enqueue({ kind: 'cycle.upsert', ref: 'tmp:c', payload: {} })
    h.kick()
    await vi.advanceTimersByTimeAsync(5000)
    expect(push).not.toHaveBeenCalled()
  })

  it('terminal erro does not bump backoff', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    await enqueue({ kind: 'cycle.upsert', ref: 'tmp:a', payload: {} })
    await enqueue({ kind: 'cycle.upsert', ref: 'tmp:b', payload: {} })
    const push = vi.fn(async (ops: { op_uuid: string }[]): Promise<PushResponse> => ({
      results: ops.map((o) => ({ op_uuid: o.op_uuid, state: 'error', id: false, error: 'inválido' })),
      idmap: {},
    }))
    const h = startSurveySync({ push, intervalMs: 1000 })
    await vi.waitFor(async () => {
      expect(await db.outbox.where('state').equals('erro').count()).toBe(2)
    })
    await new Promise((r) => setTimeout(r, 20)) // let the tick finish (running=false)
    await enqueue({ kind: 'cycle.upsert', ref: 'tmp:c', payload: {} })
    await vi.advanceTimersByTimeAsync(1100)
    await vi.waitFor(() => expect(push).toHaveBeenCalledTimes(2))
    h.stop()
  })
})
