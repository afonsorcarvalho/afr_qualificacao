import 'fake-indexeddb/auto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { db } from '../db'
import { backoffMs, drain, enqueue, type PushResponse, type SurveyOp } from '../engine'

beforeEach(async () => {
  await Promise.all(db.tables.map((t) => t.clear()))
})

const ok = (op: SurveyOp, id: number | false = 1) => ({
  op_uuid: op.op_uuid, state: 'done' as const, id, error: false as const,
})

describe('backoffMs', () => {
  it('doubles and caps', () => {
    expect(backoffMs(0)).toBe(2000)
    expect(backoffMs(2)).toBe(8000)
    expect(backoffMs(50)).toBe(5 * 60 * 1000)
  })
})

describe('enqueue', () => {
  it('enqueue_orders_by_createdAt', async () => {
    const a = await enqueue({ kind: 'partner.create', ref: 'tmp:p', payload: {} })
    const b = await enqueue({ kind: 'equipment.upsert', ref: 'tmp:e', payload: { partner_id: 'tmp:p' } })
    const c = await enqueue({ kind: 'cycle.upsert', ref: 'tmp:c', payload: {} })
    const all = await db.outbox.orderBy('createdAt').toArray()
    expect(all.map((e) => e.op_uuid)).toEqual([a, b, c])
    expect(new Set(all.map((e) => e.createdAt)).size).toBe(3)
    expect(all.every((e) => e.state === 'pendente' && e.attempts === 0)).toBe(true)
  })
})

describe('drain', () => {
  it('sends in createdAt order, max 50, deleting done entries', async () => {
    for (let i = 0; i < 55; i++) await enqueue({ kind: 'cycle.upsert', ref: `tmp:c${i}`, payload: { i } })
    const sizes: number[] = []
    let first: SurveyOp[] = []
    const push = vi.fn(async (ops: SurveyOp[]): Promise<PushResponse> => {
      sizes.push(ops.length)
      if (!first.length) first = ops
      return { results: ops.map((o) => ok(o)), idmap: {} }
    })
    const r = await drain(push)
    expect(sizes).toEqual([50])
    expect(first.map((o) => o.payload.i)).toEqual(Array.from({ length: 50 }, (_, i) => i))
    expect(r).toMatchObject({ sent: 50, failed: 0 })
    expect(await db.outbox.count()).toBe(5)
  })

  it('drain_rewrites_tmp_keys_everywhere', async () => {
    await db.equipments.put({ key: 'tmp:e', partnerKey: '7', sync: 'pendente' })
    await db.cycles.put({ key: 'tmp:c', equipmentKey: 'tmp:e', sync: 'pendente' })
    await db.photos.put({ key: 'tmp:ph', equipmentKey: 'tmp:e', cycleKey: 'tmp:c', blob: new Blob(['x']), sync: 'pendente' })
    const eq = await enqueue({ kind: 'equipment.upsert', ref: 'tmp:e', payload: { name: 'x' } })
    const photo = await enqueue({
      kind: 'photo.add', ref: 'tmp:ph', payload: { equipment_id: 'tmp:e', cycle_id: 'tmp:c' },
    })
    // backend answers only for the equipment op; the photo op stays pending
    await drain(async (ops) => ({ results: [ok(ops[0], 42)], idmap: { 'tmp:e': 42 } }))
    const e = await db.equipments.get('42')
    expect(e).toBeTruthy()
    expect(e!.id).toBe(42)
    expect(e!.sync).toBe('ok')
    expect(await db.equipments.get('tmp:e')).toBeUndefined()
    expect((await db.cycles.get('tmp:c'))!.equipmentKey).toBe('42')
    expect((await db.photos.get('tmp:ph'))!.equipmentKey).toBe('42')
    expect((await db.idmap.get('tmp:e'))!.id).toBe(42)
    const pending = await db.outbox.get(photo)
    expect(pending!.payload.equipment_id).toBe(42)
    expect(pending!.payload.cycle_id).toBe('tmp:c')
    expect(await db.outbox.get(eq)).toBeUndefined()
  })

  it('rewrites tmp ref of own record and ops that reference it by ref', async () => {
    await db.partners.put({ key: 'tmp:p', sync: 'pendente' })
    await enqueue({ kind: 'partner.create', ref: 'tmp:p', payload: {} })
    const later = await enqueue({ kind: 'equipment.upsert', ref: 'tmp:p', payload: {} })
    await drain(async (ops) => ({ results: [ok(ops[0], 9)], idmap: { 'tmp:p': 9 } }))
    expect((await db.partners.get('9'))!.id).toBe(9)
    expect((await db.outbox.get(later))!.ref).toBe(9)
  })

  it('drain_error_marks_record', async () => {
    await db.equipments.put({ key: 'tmp:e', partnerKey: '7', sync: 'pendente' })
    const id = await enqueue({ kind: 'equipment.upsert', ref: 'tmp:e', payload: {} })
    const r = await drain(async (ops) => ({
      results: [{ op_uuid: ops[0].op_uuid, state: 'error', id: false, error: 'Campo inválido' }],
      idmap: {},
    }))
    expect(r).toMatchObject({ sent: 0, failed: 1, retried: 0 })
    const entry = await db.outbox.get(id)
    expect(entry!.state).toBe('erro')
    expect(entry!.error).toBe('Campo inválido')
    const rec = await db.equipments.get('tmp:e')
    expect(rec!.sync).toBe('erro')
    expect(rec!.syncError).toBe('Campo inválido')
    // erro entries are not resent
    const push = vi.fn()
    await drain(push)
    expect(push).not.toHaveBeenCalled()
  })

  it('dependency failure is retryable: back to pendente, attempts++, record not erro', async () => {
    await db.cycles.put({ key: 'tmp:c', equipmentKey: 'tmp:e', sync: 'pendente' })
    const id = await enqueue({ kind: 'cycle.upsert', ref: 'tmp:c', payload: {} })
    const r = await drain(async (ops) => ({
      results: [{ op_uuid: ops[0].op_uuid, state: 'error', id: false, error: 'Op tmp:e: dependência falhou (x)' }],
      idmap: {},
    }))
    expect(r.failed).toBe(1)
    const entry = await db.outbox.get(id)
    expect(entry!.state).toBe('pendente')
    expect(entry!.attempts).toBe(1)
    expect((await db.cycles.get('tmp:c'))!.sync).toBe('pendente')
  })

  it('network_error_keeps_pending_and_increments_attempts', async () => {
    const a = await enqueue({ kind: 'cycle.upsert', ref: 'tmp:a', payload: {} })
    const b = await enqueue({ kind: 'cycle.upsert', ref: 'tmp:b', payload: {} })
    const r = await drain(async () => { throw new Error('Network Error') })
    expect(r).toMatchObject({ sent: 0, failed: 2 })
    for (const id of [a, b]) {
      const e = await db.outbox.get(id)
      expect(e!.state).toBe('pendente')
      expect(e!.attempts).toBe(1)
    }
  })

  it('auth_error_keeps_pending', async () => {
    const a = await enqueue({ kind: 'cycle.upsert', ref: 'tmp:a', payload: {} })
    const err = Object.assign(new Error('Unauthorized'), { status: 401 })
    const r = await drain(async () => { throw err })
    expect(r.authError).toBe(true)
    const e = await db.outbox.get(a)
    expect(e!.state).toBe('pendente')
    expect(e!.attempts).toBe(1)
  })

  it('odoo session expired error counts as auth error', async () => {
    await enqueue({ kind: 'cycle.upsert', ref: 'tmp:a', payload: {} })
    const { OdooSessionError } = await import('@/lib/odoo/client')
    const r = await drain(async () => { throw new OdooSessionError() })
    expect(r.authError).toBe(true)
  })

  it('op without result goes back to pendente', async () => {
    const a = await enqueue({ kind: 'cycle.upsert', ref: 'tmp:a', payload: {} })
    const r = await drain(async () => ({ results: [], idmap: {} }))
    expect(r.failed).toBe(1)
    const e = await db.outbox.get(a)
    expect(e!.state).toBe('pendente')
    expect(e!.attempts).toBe(1)
  })

  it('rewrites partnerKey and photo.cycleKey', async () => {
    await db.partners.put({ key: 'tmp:p', sync: 'pendente' })
    await db.equipments.put({ key: 'tmp:e', partnerKey: 'tmp:p', sync: 'pendente' })
    await db.cycles.put({ key: 'tmp:c', equipmentKey: 'tmp:e', sync: 'pendente' })
    await db.photos.put({ key: 'tmp:ph', equipmentKey: 'tmp:e', cycleKey: 'tmp:c', blob: new Blob(['x']), sync: 'pendente' })
    await enqueue({ kind: 'partner.create', ref: 'tmp:p', payload: {} })
    await drain(async (ops) => ({ results: [ok(ops[0], 5)], idmap: { 'tmp:p': 5, 'tmp:c': 8 } }))
    expect((await db.equipments.get('tmp:e'))!.partnerKey).toBe('5')
    expect((await db.photos.get('tmp:ph'))!.cycleKey).toBe('8')
    expect((await db.cycles.get('8'))!.id).toBe(8)
  })

  it('replay: already-rewritten ref with idempotent response is consistent', async () => {
    await db.equipments.put({ key: '42', id: 42, partnerKey: '1', sync: 'pendente' })
    const id = await enqueue({ kind: 'equipment.upsert', ref: 42, payload: {} })
    await drain(async (ops) => ({ results: [ok(ops[0], 42)], idmap: { 'tmp:e': 42 } }))
    expect(await db.outbox.get(id)).toBeUndefined()
    expect((await db.equipments.get('42'))!.sync).toBe('ok')
  })

  it('applyIdMap failure returns entries to pendente and rolls back', async () => {
    await db.equipments.put({ key: 'tmp:e', partnerKey: '1', sync: 'pendente' })
    const id = await enqueue({ kind: 'equipment.upsert', ref: 'tmp:e', payload: {} })
    const spy = vi.spyOn(db.idmap, 'put').mockRejectedValueOnce(new Error('boom'))
    const r = await drain(async (ops) => ({ results: [ok(ops[0], 42)], idmap: { 'tmp:e': 42 } }))
    spy.mockRestore()
    expect(r.failed).toBe(1)
    const e = await db.outbox.get(id)
    expect(e!.state).toBe('pendente')
    expect(e!.attempts).toBe(1)
    expect(await db.equipments.get('tmp:e')).toBeTruthy()
    expect(await db.equipments.get('42')).toBeUndefined()
  })

  it('atomic: no record left pendente without outbox entry after done', async () => {
    await db.equipments.put({ key: 'tmp:e', partnerKey: '1', sync: 'pendente' })
    await enqueue({ kind: 'equipment.upsert', ref: 'tmp:e', payload: {} })
    await drain(async (ops) => ({ results: [ok(ops[0], 42)], idmap: { 'tmp:e': 42 } }))
    const orphans = (await db.equipments.toArray()).filter((r) => r.sync === 'pendente')
    expect(orphans.length === 0 || (await db.outbox.count()) > 0).toBe(true)
    expect(orphans).toEqual([])
  })

  it('error on later op of a record created in the same batch marks rewritten key', async () => {
    await db.equipments.put({ key: 'tmp:e', partnerKey: '1', sync: 'pendente' })
    await enqueue({ kind: 'equipment.upsert', ref: 'tmp:e', payload: {} })
    const edit = await enqueue({ kind: 'equipment.upsert', ref: 'tmp:e', payload: { x: 1 } })
    await drain(async (ops) => ({
      results: [ok(ops[0], 42), { op_uuid: ops[1].op_uuid, state: 'error', id: false, error: 'inválido' }],
      idmap: { 'tmp:e': 42 },
    }))
    const rec = await db.equipments.get('42')
    expect(rec!.sync).toBe('erro')
    expect(rec!.syncError).toBe('inválido')
    expect((await db.outbox.get(edit))!.state).toBe('erro')
  })

  it('dependency failure whose creator is in erro becomes erro (no starvation)', async () => {
    await db.equipments.put({ key: 'tmp:e', partnerKey: '1', sync: 'pendente' })
    await db.cycles.put({ key: 'tmp:c', equipmentKey: 'tmp:e', sync: 'pendente' })
    await enqueue({ kind: 'equipment.upsert', ref: 'tmp:e', payload: {} })
    const dep = await enqueue({ kind: 'cycle.upsert', ref: 'tmp:c', payload: { equipment_id: 'tmp:e' } })
    await drain(async (ops) => ({
      results: [
        { op_uuid: ops[0].op_uuid, state: 'error', id: false, error: 'inválido' },
        { op_uuid: ops[1].op_uuid, state: 'error', id: false, error: 'dependência falhou' },
      ],
      idmap: {},
    }))
    const e = await db.outbox.get(dep)
    expect(e!.state).toBe('erro')
    expect(e!.error).toBe('depende de registro com erro')
    expect((await db.cycles.get('tmp:c'))!.sync).toBe('erro')
  })

  it('dependency failure becomes erro at attempts cap', async () => {
    const id = await enqueue({ kind: 'cycle.upsert', ref: 'tmp:c', payload: {} })
    await db.outbox.update(id, { attempts: 19 })
    await drain(async (ops) => ({
      results: [{ op_uuid: ops[0].op_uuid, state: 'error', id: false, error: 'dependência falhou' }],
      idmap: {},
    }))
    expect((await db.outbox.get(id))!.state).toBe('erro')
  })

  it('terminal erro/done without a local record does not abort the transaction', async () => {
    await enqueue({ kind: 'cycle.upsert', ref: 'tmp:a', payload: {} })
    await enqueue({ kind: 'cycle.upsert', ref: 'tmp:b', payload: {} })
    const r = await drain(async (ops) => ({
      results: [
        { op_uuid: ops[0].op_uuid, state: 'error', id: false, error: 'inválido' },
        ok(ops[1], 3),
      ],
      idmap: {},
    }))
    expect(r).toMatchObject({ sent: 1, failed: 1, retried: 0 })
    expect(await db.outbox.count()).toBe(1)
  })
})

describe('write_date do push', () => {
  it('done com write_date atualiza base_write_date do registro', async () => {
    await db.equipments.put({ key: '5', id: 5, partnerKey: '1', sync: 'pendente', base_write_date: 'old' })
    await enqueue({ kind: 'equipment.upsert', ref: 5, base_write_date: 'old', payload: { a: 1 } })
    await drain(async (ops) => ({
      results: [{ ...ok(ops[0], 5), write_date: '2026-10-18 12:00:00' }],
      idmap: {},
    }))
    expect((await db.equipments.get('5'))!.base_write_date).toBe('2026-10-18 12:00:00')
  })

  it('op posterior pendente (fora do lote) herda a nova base', async () => {
    await db.equipments.put({ key: '5', id: 5, partnerKey: '1', sync: 'pendente', base_write_date: 'old' })
    await enqueue({ kind: 'equipment.upsert', ref: 5, base_write_date: 'old', payload: { a: 1 } })
    for (let i = 0; i < 49; i++) await enqueue({ kind: 'cycle.upsert', ref: `tmp:f${i}`, payload: {} })
    const later = await enqueue({ kind: 'equipment.upsert', ref: 5, base_write_date: 'old', payload: { b: 2 } })
    await drain(async (ops) => ({
      results: ops.map((o) => ({ ...ok(o, 5), ...(o.payload.a ? { write_date: 'NEW' } : {}) })),
      idmap: {},
    }))
    expect((await db.outbox.get(later))!.base_write_date).toBe('NEW')
  })
})

describe('lote limitado por bytes', () => {
  it('para de juntar ops ao passar ~4 MB, sempre leva ao menos 1', async () => {
    const big = 'x'.repeat(1.5 * 1024 * 1024)
    for (let i = 0; i < 4; i++) await enqueue({ kind: 'photo.add', ref: `tmp:f${i}`, payload: { image_b64: big } })
    const sizes: number[] = []
    const push = vi.fn(async (ops: SurveyOp[]): Promise<PushResponse> => {
      sizes.push(ops.length)
      return { results: ops.map((o) => ok(o)), idmap: {} }
    })
    await drain(push)
    await drain(push)
    expect(sizes).toEqual([2, 2])

    await enqueue({ kind: 'photo.add', ref: 'tmp:huge', payload: { image_b64: 'y'.repeat(5 * 1024 * 1024) } })
    await drain(push)
    expect(sizes[2]).toBe(1)
    expect(await db.outbox.count()).toBe(0)
  })
})

describe('isolamento por sessão', () => {
  it('duas chaves de sessão não veem a outbox uma da outra', async () => {
    const { openSurveyDb, surveyDbName } = await import('../db')
    const a = openSurveyDb('https://a|db1|1')
    const b = openSurveyDb('https://a|db1|2')
    expect(a.name).not.toBe(b.name)
    expect(a.name).toBe(surveyDbName('https://a|db1|1'))
    expect(a.name.startsWith('levantamento:')).toBe(true)
    await a.outbox.clear()
    await b.outbox.clear()
    await enqueue({ kind: 'partner.create', ref: 'tmp:p', payload: {} }, a)
    expect(await a.outbox.count()).toBe(1)
    expect(await b.outbox.count()).toBe(0)
    const push = vi.fn()
    expect((await drain(push, b)).sent).toBe(0)
    expect(push).not.toHaveBeenCalled()
  })

  it('getDb segue servidor/base/uid do authStore', async () => {
    const { getDb } = await import('../db')
    const { useAuthStore } = await import('@/lib/store/authStore')
    useAuthStore.setState({ serverUrl: 'https://s', dbName: 'x', userId: 1 })
    const d1 = getDb()
    useAuthStore.setState({ userId: 2 })
    const d2 = getDb()
    expect(d1.name).not.toBe(d2.name)
    useAuthStore.setState({ userId: 1 })
    expect(getDb()).toBe(d1)
    useAuthStore.setState({ serverUrl: '', dbName: '', userId: null })
  })
})
