import { db, type OutboxEntry, type SurveyOp, type SurveyOpKind, type SyncFields } from './db'
import type { Table } from 'dexie'

export type { SurveyOp, SurveyOpKind } from './db'

const BACKOFF_BASE_MS = 2000
const BACKOFF_CAP_MS = 5 * 60 * 1000
export const MAX_BATCH_SIZE = 50

/** Mensagem do backend para op cuja dependência falhou — retentável. */
const DEP_FAILED = 'dependência falhou'

export function backoffMs(attempts: number) {
  return Math.min(BACKOFF_BASE_MS * 2 ** attempts, BACKOFF_CAP_MS)
}

export interface PushResult {
  op_uuid: string
  state: 'done' | 'error'
  id: number | false
  error: string | false
}
export interface PushResponse {
  results: PushResult[]
  idmap: Record<string, number>
}
export type PushFn = (ops: SurveyOp[]) => Promise<PushResponse>
export interface DrainResult {
  sent: number
  failed: number
  /** Push falhou por sessão expirada/401/403: o chamador deve reautenticar. */
  authError?: boolean
}

const isTmp = (v: unknown): v is string => typeof v === 'string' && v.startsWith('tmp:')

/** Tabela onde mora o registro a que a op se refere. */
function tableFor(kind: SurveyOpKind): Table<SyncFields, string> {
  switch (kind) {
    case 'partner.create':
      return db.partners as unknown as Table<SyncFields, string>
    case 'equipment.upsert':
      return db.equipments as unknown as Table<SyncFields, string>
    case 'photo.add':
    case 'photo.delete':
      return db.photos as unknown as Table<SyncFields, string>
    default:
      return db.cycles as unknown as Table<SyncFields, string>
  }
}

/** Enfileira uma op; devolve o `op_uuid`. `createdAt` é estritamente crescente. */
export async function enqueue(op: Omit<SurveyOp, 'op_uuid'>): Promise<string> {
  const op_uuid = crypto.randomUUID()
  await db.transaction('rw', db.outbox, async () => {
    const last = await db.outbox.orderBy('createdAt').last()
    const createdAt = Math.max(Date.now(), (last?.createdAt ?? 0) + 1)
    await db.outbox.add({ ...op, op_uuid, state: 'pendente', attempts: 0, createdAt })
  })
  return op_uuid
}

function isAuthError(e: unknown): boolean {
  if (typeof e !== 'object' || e === null) return false
  const x = e as { status?: unknown; code?: unknown; name?: unknown; response?: { status?: unknown } }
  const status = x.status ?? x.response?.status
  // OdooSessionError (lib/odoo/client.ts) traz code 401.
  return status === 401 || status === 403 || x.code === 401 || x.name === 'OdooSessionError'
}

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** Reescreve `tmp:x` → id real em tabelas locais e em ops ainda na outbox. */
async function applyIdMap(idmap: Record<string, number>) {
  const entries = Object.entries(idmap)
  if (!entries.length) return
  await db.transaction(
    'rw',
    [db.partners, db.equipments, db.cycles, db.photos, db.outbox, db.idmap],
    async () => {
      for (const [tmp, id] of entries) {
        await db.idmap.put({ tmp, id })
      }
      const map = new Map(entries)
      const fk = (v: unknown): string | undefined => {
        const id = isTmp(v) ? map.get(v) : undefined
        return id === undefined ? undefined : String(id)
      }

      // Chave primária: troca `tmp:x` por "<id>".
      const tables = [db.partners, db.equipments, db.cycles, db.photos] as unknown as Table<
        Record<string, unknown> & SyncFields,
        string
      >[]
      for (const t of tables) {
        for (const [tmp, id] of entries) {
          const rec = await t.get(tmp)
          if (!rec) continue
          await t.delete(tmp)
          await t.put({ ...rec, key: String(id), id })
        }
      }
      // Chaves estrangeiras locais.
      for (const rec of await db.equipments.toArray()) {
        const v = fk(rec.partnerKey)
        if (v) await db.equipments.update(rec.key, { partnerKey: v })
      }
      for (const rec of await db.cycles.toArray()) {
        const v = fk(rec.equipmentKey)
        if (v) await db.cycles.update(rec.key, { equipmentKey: v })
      }
      for (const rec of await db.photos.toArray()) {
        const patch: Record<string, string> = {}
        const e = fk(rec.equipmentKey)
        const c = fk(rec.cycleKey)
        if (e) patch.equipmentKey = e
        if (c) patch.cycleKey = c
        if (Object.keys(patch).length) await db.photos.update(rec.key, patch)
      }
      // Ops pendentes: ref e valores do payload.
      for (const op of await db.outbox.toArray()) {
        const payload: Record<string, unknown> = { ...op.payload }
        let changed = false
        for (const [k, v] of Object.entries(payload)) {
          if (isTmp(v) && map.has(v)) {
            payload[k] = map.get(v)
            changed = true
          }
        }
        const ref = isTmp(op.ref) && map.has(op.ref) ? map.get(op.ref)! : op.ref
        if (changed || ref !== op.ref) await db.outbox.update(op.op_uuid, { payload, ref })
      }
    },
  )
}

async function markRecord(op: OutboxEntry, sync: SyncFields['sync'], syncError?: string) {
  const t = tableFor(op.kind)
  const key = String(op.ref)
  if (await t.get(key)) await t.update(key, { sync, syncError })
}

let draining = false

/**
 * Drena a outbox: envia `pendente` em ordem de `createdAt` (máx. 50) e
 * aplica o resultado por op.
 *
 *  - `done`: remove da outbox, grava idmap e reescreve referências;
 *  - `error`: entrada e registro viram `erro` (não reenvia sozinho) — EXCETO
 *    "dependência falhou", que é retentável (volta a `pendente`, attempts++);
 *  - push lança (rede/auth): todas voltam a `pendente`, attempts++.
 *
 * A ordem estrita por `createdAt` garante que a op criadora vá antes das
 * dependentes dentro do lote.
 */
export async function drain(push: PushFn): Promise<DrainResult> {
  if (draining) return { sent: 0, failed: 0 }
  draining = true
  try {
    const batch = (await db.outbox.where('state').equals('pendente').sortBy('createdAt')).slice(
      0,
      MAX_BATCH_SIZE,
    )
    if (!batch.length) return { sent: 0, failed: 0 }
    const ids = batch.map((e) => e.op_uuid)
    await db.outbox.where('op_uuid').anyOf(ids).modify({ state: 'enviando' })

    const retry = async (entries: OutboxEntry[]) => {
      for (const e of entries) {
        await db.outbox.update(e.op_uuid, { state: 'pendente', attempts: e.attempts + 1 })
      }
    }

    let resp: PushResponse
    try {
      resp = await push(
        batch.map(({ op_uuid, kind, ref, base_write_date, payload }) => ({
          op_uuid,
          kind,
          ref,
          base_write_date,
          payload,
        })),
      )
    } catch (e) {
      await retry(batch)
      return { sent: 0, failed: batch.length, authError: isAuthError(e) || undefined }
    }

    // Idmap primeiro: mesmo ops com erro podem ter criado ids antes.
    await applyIdMap(resp.idmap ?? {})

    const byUuid = new Map((resp.results ?? []).map((r) => [r.op_uuid, r]))
    let sent = 0
    let failed = 0
    for (const e of batch) {
      const r = byUuid.get(e.op_uuid)
      if (!r) {
        await retry([e])
        failed++
      } else if (r.state === 'done') {
        await db.outbox.delete(e.op_uuid)
        // Registro só volta a 'ok' se não restar outra op pendente sobre ele.
        // (`ref` da entrada pode ter sido reescrito pelo idmap acima.)
        const fresh = e.ref
        const real = isTmp(fresh) ? (resp.idmap?.[fresh] ?? fresh) : fresh
        const restante = (await db.outbox.toArray()).some((o) => String(o.ref) === String(real))
        if (!restante) await markRecord({ ...e, ref: real }, 'ok', undefined)
        sent++
      } else {
        const msg = r.error || 'erro'
        failed++
        if (msg.includes(DEP_FAILED)) {
          await retry([e])
        } else {
          await db.outbox.update(e.op_uuid, { state: 'erro', error: msg })
          await markRecord(e, 'erro', msg)
        }
      }
    }
    return { sent, failed }
  } finally {
    draining = false
  }
}
