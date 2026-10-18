import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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
    expect(r).toEqual({ sent: 50, failed: 0 })
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
    const push = vi.fn(async (ops: SurveyOp[]): Promise<PushResponse> => ({
      results: [ok(ops[0], 42)], idmap: { 'tmp:e': 42 },
    }))
    // only the equipment op is sent in first call? send both: respond only to first
    await drain(async (ops) => {
      const res = await push(ops.slice(0, 1))
      return res
    })
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
    expect(r).toEqual({ sent: 0, failed: 1 })
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
})
