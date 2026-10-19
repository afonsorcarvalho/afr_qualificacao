import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/odoo/levantamento', () => ({ pullPartner: vi.fn(), pullCatalog: vi.fn() }))

import { db } from '../db'
import { drain, type PushFn, type PushResponse, type SurveyOp } from '../engine'
import { _resetBootFlagForTests, startSurveySync } from '../loop'
import { saveCycle, saveEquipment } from '../repo'

/**
 * Servidor falso com o contrato real do backend: idempotente por `op_uuid`
 * (replay devolve o resultado guardado e IGNORA o payload novo); tmp
 * desconhecido em upsert = criar; tmp já resolvido = editar.
 */
function fakeServer() {
  const stored = new Map<string, { id: number; tmp?: string }>()
  const tmps = new Map<string, number>()
  const cycles = new Map<number, Record<string, unknown>>()
  let seq = 500
  const run = (op: SurveyOp): number => {
    const res = (v: unknown) => (typeof v === 'string' && v.startsWith('tmp:') ? tmps.get(v)! : (v as number))
    const payload = { ...op.payload }
    if ('equipment_id' in payload) payload.equipment_id = res(payload.equipment_id)
    const ref = typeof op.ref === 'string' && op.ref.startsWith('tmp:') ? tmps.get(op.ref) : (op.ref as number)
    if (ref) {
      if (op.kind === 'cycle.upsert') Object.assign(cycles.get(ref)!, payload)
      return ref
    }
    const id = ++seq
    if (op.kind === 'cycle.upsert') cycles.set(id, payload)
    return id
  }
  const apply = (ops: SurveyOp[]): PushResponse => {
    const idmap: Record<string, number> = {}
    const results = ops.map((op) => {
      let s = stored.get(op.op_uuid)
      if (!s) {
        const tmp = typeof op.ref === 'string' && op.ref.startsWith('tmp:') ? op.ref : undefined
        s = { id: run(op), tmp }
        stored.set(op.op_uuid, s)
        if (tmp) tmps.set(tmp, s.id)
      }
      if (s.tmp) idmap[s.tmp] = s.id
      return { op_uuid: op.op_uuid, state: 'done' as const, id: s.id, error: false as const, write_date: '2026-10-19 10:00:00' }
    })
    return { results, idmap }
  }
  return { apply, cycles }
}

const EQ = { category_id: 3, marca_id: 4, model: 'M1' }

beforeEach(async () => {
  await Promise.all(db.tables.map((t) => t.clear()))
})

describe('edição de ciclo cuja criação já chegou ao servidor sem confirmação', () => {
  /** Equipamento tmp + "+ ciclo" (create vazio) enviados; o servidor grava; o cliente não confirma. */
  async function cenario(perde: (server: ReturnType<typeof fakeServer>) => Promise<void>) {
    const server = fakeServer()
    const ek = await saveEquipment(null, '7', EQ)
    const ck = await saveCycle(null, ek, {})
    await perde(server)
    // usuário preenche o ciclo depois do envio não confirmado
    await saveCycle(ck, ek, { cycle_type_id: 9 })
    await saveCycle(ck, ek, { temperature: '92' })
    await saveCycle(ck, ek, { duration: '00:20' })
    const ok: PushFn = async (o) => server.apply(o)
    await drain(ok)
    await drain(ok)
    expect(await db.outbox.count()).toBe(0)
    const [c] = Array.from(server.cycles.values())
    expect(server.cycles.size).toBe(1)
    expect(c).toMatchObject({ cycle_type_id: 9, temperature: '92', duration: '00:20' })
  }

  it('push rejeita depois de o servidor gravar (timeout)', async () => {
    await cenario(async (server) => {
      await drain(async (o) => {
        server.apply(o)
        throw new Error('timeout of 30000ms exceeded')
      })
    })
  })

  it('resposta sem o resultado da op', async () => {
    await cenario(async (server) => {
      await drain(async (o) => {
        const r = server.apply(o)
        return { results: r.results.filter((x) => x.op_uuid !== o[1].op_uuid), idmap: { [String(o[0].ref)]: r.idmap[String(o[0].ref)] } }
      })
    })
  })

  it('app recarregado com a op em envio (boot reset enviando -> pendente)', async () => {
    await cenario(async (server) => {
      let release!: () => void
      const hang = new Promise<void>((r) => (release = r))
      const p = drain(async (o) => {
        server.apply(o)
        await hang
        throw new Error('página fechada')
      })
      await vi.waitFor(async () => expect(await db.outbox.where('state').equals('enviando').count()).toBe(2))
      // simula nova carga de página: o loop devolve 'enviando' a 'pendente'
      _resetBootFlagForTests()
      const loop = startSurveySync({ push: async () => new Promise(() => {}), intervalMs: 1e9 })
      await vi.waitFor(async () => expect(await db.outbox.where('state').equals('enviando').count()).toBe(0))
      loop.stop()
      release()
      await p
      // loop parado antes de enviar? garante estado pendente para o resto do cenário
      await db.outbox.toCollection().modify({ state: 'pendente' })
    })
  })
})
