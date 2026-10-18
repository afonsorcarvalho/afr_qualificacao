/**
 * Repositório do levantamento — camada que a UI usa. Cada função grava no
 * IndexedDB (otimista) e enfileira a op correspondente na outbox (`enqueue`).
 *
 * Convenções de armazenamento local (documentadas p/ as telas):
 *  - many2one é guardado como id (`number | false`) em `<campo>` e o nome em
 *    `<campo>_name` (ex.: `category_id: 3`, `category_id_name: 'Autoclave'`).
 *    Os nomes de catálogo vêm de `loadCatalog()`.
 *  - `base_write_date` = `write_date` do servidor no último download; é o que
 *    segue nas ops de edição (detecção de conflito last-write-wins no backend).
 *  - Fotos baixadas guardam o THUMBNAIL (JPEG 128px) como `Blob` em `blob`,
 *    com `isThumb: true`. Fotos tiradas no aparelho guardam o JPEG comprimido
 *    (sem `isThumb`). Para exibir: `URL.createObjectURL(photo.blob)`.
 *  - Toda função que recebe uma chave a resolve antes por `db.idmap`
 *    (a UI pode ainda segurar `tmp:x` já reescrito pelo engine para o id real).
 *    As funções devolvem sempre a chave resolvida.
 *  - Nunca se faz `await` de algo que não seja Dexie dentro de transação:
 *    compressão e base64 acontecem antes.
 */
import {
  db,
  type LocalCycle,
  type LocalEquipment,
  type LocalPartner,
  type LocalPhoto,
  type OutboxEntry,
  type SurveyOpKind,
} from './db'
import { enqueue } from './engine'
import { blobToBase64, compressImage } from './photo'
import { pullCatalog, pullPartner, type M2o, type RemotePicture } from '@/lib/odoo/levantamento'

export const EQUIPMENT_FIELDS = [
  'name', 'apelido', 'model', 'serial_number', 'tag', 'patrimony', 'category_id', 'marca_id',
  'location_id', 'chamber_volume_l', 'chamber_dimensions', 'sensor_qty_estimated',
  'thermocouple_access', 'power_supply', 'survey_note',
] as const
export const CYCLE_FIELDS = ['cycle_type_id', 'temperature', 'duration', 'load_type', 'note'] as const
/** Obrigatórios para o backend CRIAR um equipamento. */
export const EQUIPMENT_CREATE_REQUIRED = ['category_id', 'marca_id', 'model'] as const

const EQUIPMENT_M2O = ['category_id', 'marca_id', 'location_id', 'survey_user_id']
const CYCLE_M2O = ['cycle_type_id']

type Rec = Record<string, unknown>

const isTmp = (v: unknown): v is string => typeof v === 'string' && v.startsWith('tmp:')
const newTmp = () => `tmp:${crypto.randomUUID()}`
/** Valor de referência numa op: `tmp:x` ou id numérico. */
const refOf = (key: string): string | number => (isTmp(key) ? key : Number(key))
const isEmpty = (v: unknown) => v === undefined || v === null || v === false || v === ''

const allTables = () => [db.partners, db.equipments, db.cycles, db.photos, db.outbox, db.idmap]

/** `tmp:x` já reescrito pelo engine → id real (string); senão devolve a própria chave. */
export async function resolveKey(key: string): Promise<string> {
  if (!isTmp(key)) return key
  const m = await db.idmap.get(key)
  return m ? String(m.id) : key
}

/** Campos obrigatórios (para criar) ainda vazios — nomes de campo do backend. */
export function missingRequired(equipment: Rec): string[] {
  return EQUIPMENT_CREATE_REQUIRED.filter((f) => {
    const v = equipment[f]
    return typeof v === 'string' ? !v.trim() : isEmpty(v)
  })
}

function opsFor(key: string): Promise<OutboxEntry[]> {
  return db.outbox.where('ref').equals(refOf(key)).toArray()
}

/**
 * Edição de registro que já tem upsert `pendente` (não enviado): funde os
 * campos na op existente (mantém o `base_write_date` original). Devolve false
 * se não há op a fundir (então o chamador enfileira uma nova).
 */
async function coalesce(key: string, kind: SurveyOpKind, diff: Rec): Promise<boolean> {
  const pend = (await opsFor(key)).filter((o) => o.kind === kind && o.state === 'pendente')
  if (!pend.length) return false
  const last = pend.reduce((a, b) => (b.createdAt > a.createdAt ? b : a))
  await db.outbox.update(last.op_uuid, { payload: { ...last.payload, ...diff } })
  return true
}
/** O registro já existe no servidor ou tem op de criação na outbox? */
async function isReady(key: string): Promise<boolean> {
  return !isTmp(key) || (await opsFor(key)).length > 0
}

function checkFields(changed: Rec, allowed: readonly string[]) {
  const bad = Object.keys(changed).filter((k) => !allowed.includes(k))
  if (bad.length) throw new Error(`Campos não permitidos: ${bad.join(', ')}`)
}

/** Aceita `number | false | [id, nome]` e normaliza para id. */
function normM2o(v: unknown): number | false {
  if (Array.isArray(v)) return (v[0] as number) || false
  return typeof v === 'number' && v ? v : false
}

/** Igualdade tolerante a `'12'` vs `12` (inputs de formulário devolvem string). */
function sameValue(a: unknown, b: unknown): boolean {
  if (a === b) return true
  const num = (x: unknown, y: unknown) =>
    typeof x === 'number' && typeof y === 'string' && y.trim() !== '' && Number(y) === x
  return num(a, b) || num(b, a)
}

function diffFields(existing: Rec | undefined, changed: Rec, m2o: string[]): Rec {
  const diff: Rec = {}
  for (const [k, raw] of Object.entries(changed)) {
    const v = m2o.includes(k) ? normM2o(raw) : raw
    const cur = existing?.[k]
    if (isEmpty(cur) && isEmpty(v)) {
      if (!existing || !(k in existing)) diff[k] = v
      continue
    }
    if (!sameValue(cur, v)) diff[k] = v
  }
  return diff
}

function fullPayload(rec: Rec, fields: readonly string[]): Rec {
  const out: Rec = {}
  for (const f of fields) if (!isEmpty(rec[f])) out[f] = rec[f]
  return out
}

function splitM2o(src: Rec, m2o: string[]): Rec {
  const out: Rec = {}
  for (const [k, v] of Object.entries(src)) {
    if (m2o.includes(k)) {
      const pair = v as M2o
      out[k] = pair ? pair[0] : false
      out[`${k}_name`] = pair ? pair[1] : false
    } else out[k] = v
  }
  return out
}

function b64ToBlob(b64: string): Blob {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Blob([bytes], { type: 'image/jpeg' })
}

// --------------------------------------------------------------------- catálogo

/** Baixa o catálogo e guarda cada chave em `db.catalog` (`{name, items}`). */
export async function refreshCatalog() {
  const cat = await pullCatalog()
  await db.transaction('rw', db.catalog, async () => {
    for (const [name, items] of Object.entries(cat)) await db.catalog.put({ name, items })
  })
  return cat
}
/** Catálogo local como objeto `{categories, marcas, cycle_types, selections}`. */
export async function loadCatalog(): Promise<Record<string, unknown>> {
  const rows = await db.catalog.toArray()
  return Object.fromEntries(rows.map((r) => [r.name, r.items]))
}

// --------------------------------------------------------------------- download

/**
 * Baixa cliente + equipamentos + ciclos + fotos para o IndexedDB.
 * Registros com edição local não sincronizada (`sync !== 'ok'`) NÃO são
 * sobrescritos; registros `ok` que sumiram do servidor são removidos; ciclos/
 * fotos com delete pendente na outbox não ressuscitam.
 */
export async function downloadPartner(id: number): Promise<void> {
  const data = await pullPartner(id)
  const pKey = String(data.partner.id)
  const thumbs = new Map<number, Blob>()
  const picsOf = (pics: RemotePicture[]) => {
    for (const p of pics) thumbs.set(p.id, p.thumb_b64 ? b64ToBlob(p.thumb_b64) : new Blob([], { type: 'image/jpeg' }))
  }
  for (const e of data.equipments) {
    picsOf(e.pictures ?? [])
    for (const c of e.cycles ?? []) picsOf(c.pictures ?? [])
  }

  await db.transaction('rw', allTables(), async () => {
    const outbox = await db.outbox.toArray()
    const delCycles = new Set(outbox.filter((o) => o.kind === 'cycle.delete').map((o) => String(o.ref)))
    const delPhotos = new Set(outbox.filter((o) => o.kind === 'photo.delete').map((o) => String(o.ref)))
    const canWrite = (r?: { sync: string }) => !r || r.sync === 'ok'

    const prev = await db.partners.get(pKey)
    if (canWrite(prev)) {
      const { id: pid, name, vat, city } = data.partner
      await db.partners.put({ key: pKey, id: pid, name, vat: vat || undefined, city: city || undefined, sync: 'ok', offline: true })
    }

    const srvEq = new Set<string>()
    const srvCyc = new Set<string>()
    const srvPh = new Set<string>()

    for (const e of data.equipments) {
      const eKey = String(e.id)
      srvEq.add(eKey)
      if (canWrite(await db.equipments.get(eKey))) {
        const { cycles: _c, pictures: _p, write_date, ...rest } = e
        await db.equipments.put({
          ...splitM2o(rest, EQUIPMENT_M2O),
          key: eKey, id: e.id, partnerKey: pKey, base_write_date: write_date, sync: 'ok',
        } as LocalEquipment)
      }
      const putPhoto = async (p: RemotePicture, cycleKey?: string) => {
        const k = String(p.id)
        srvPh.add(k)
        if (delPhotos.has(k) || !canWrite(await db.photos.get(k))) return
        const rec: Rec = {
          key: k, id: p.id, equipmentKey: eKey, survey_kind: p.survey_kind, name: p.name,
          blob: thumbs.get(p.id)!, isThumb: true, sync: 'ok',
        }
        if (cycleKey) rec.cycleKey = cycleKey
        await db.photos.put(rec as unknown as LocalPhoto)
      }
      for (const p of e.pictures ?? []) await putPhoto(p)
      for (const c of e.cycles ?? []) {
        const cKey = String(c.id)
        srvCyc.add(cKey)
        if (delCycles.has(cKey)) continue
        if (canWrite(await db.cycles.get(cKey))) {
          const { pictures: _pp, write_date, ...rest } = c
          await db.cycles.put({
            ...splitM2o(rest, CYCLE_M2O),
            key: cKey, id: c.id, equipmentKey: eKey, base_write_date: write_date, sync: 'ok',
          } as LocalCycle)
        }
        for (const p of c.pictures ?? []) await putPhoto(p, cKey)
      }
    }

    // Remoções: só o que é do servidor (id real) e está sincronizado.
    const synced = (r: { sync: string; id?: number }) => r.sync === 'ok' && r.id !== undefined
    for (const eq of await db.equipments.where('partnerKey').equals(pKey).toArray()) {
      const gone = synced(eq) && !srvEq.has(eq.key)
      const cycles = await db.cycles.where('equipmentKey').equals(eq.key).toArray()
      const photos = await db.photos.where('equipmentKey').equals(eq.key).toArray()
      for (const c of cycles) {
        if (synced(c) && (gone || !srvCyc.has(c.key))) {
          await db.cycles.delete(c.key)
          for (const ph of photos) if (ph.cycleKey === c.key && synced(ph)) await db.photos.delete(ph.key)
        }
      }
      for (const ph of photos) if (synced(ph) && (gone || !srvPh.has(ph.key))) await db.photos.delete(ph.key)
      if (gone) await db.equipments.delete(eq.key)
    }
  })
}

// ---------------------------------------------------------------------- cliente

export interface NewPartnerInput {
  name: string
  vat?: string
  city?: string
  contact_name?: string
  contact_phone?: string
}

export async function createPartner(input: NewPartnerInput): Promise<string> {
  const key = newTmp()
  const payload = fullPayload(input as unknown as Rec, ['name', 'vat', 'city', 'contact_name', 'contact_phone'])
  await db.transaction('rw', allTables(), async () => {
    await db.partners.put({ key, name: input.name, vat: input.vat, city: input.city, sync: 'pendente' } as LocalPartner)
    await enqueue({ kind: 'partner.create', ref: key, payload })
  })
  return key
}

// ------------------------------------------------------------- liberação (defer)

/**
 * Ao enfileirar a criação do equipamento `ek`, libera ciclos e fotos que
 * ficaram só locais esperando por ele (evita dependências falhando na fila).
 * `b64` = base64 pré-calculado das fotos (sem await não-Dexie aqui dentro).
 */
async function flushChildren(ek: string, b64: Map<string, string>) {
  const cycles = await db.cycles.where('equipmentKey').equals(ek).toArray()
  for (const c of cycles) {
    if ((await opsFor(c.key)).length) continue
    await enqueue({
      kind: 'cycle.upsert', ref: refOf(c.key),
      payload: { equipment_id: refOf(ek), ...fullPayload(c, CYCLE_FIELDS) },
    })
  }
  const photos = await db.photos.where('equipmentKey').equals(ek).toArray()
  for (const p of photos) {
    if (p.isThumb || (await opsFor(p.key)).length) continue
    if (p.cycleKey && !(await isReady(p.cycleKey))) continue
    const image_b64 = b64.get(p.key)
    if (!image_b64) continue
    await enqueue({ kind: 'photo.add', ref: refOf(p.key), payload: photoPayload(p, image_b64) })
  }
}

function photoPayload(p: LocalPhoto, image_b64: string): Rec {
  const payload: Rec = { equipment_id: refOf(p.equipmentKey), survey_kind: p.survey_kind, image_b64 }
  if (p.cycleKey) payload.cycle_id = refOf(p.cycleKey)
  return payload
}

async function photosB64(ek: string): Promise<Map<string, string>> {
  const out = new Map<string, string>()
  for (const p of await db.photos.where('equipmentKey').equals(ek).toArray()) {
    if (!p.isThumb) out.set(p.key, await blobToBase64(p.blob))
  }
  return out
}

// ------------------------------------------------------------------ equipamento

/**
 * Cria (key null) ou edita um equipamento. `changed` usa nomes de campo do
 * backend (many2one como id numérico ou false). Só os campos efetivamente
 * alterados vão na op, junto do `base_write_date` local.
 *
 * Equipamento NOVO só é enfileirado quando `category_id`, `marca_id` e
 * `model` estão preenchidos (senão o backend rejeita); até lá fica só local
 * (use `missingRequired`). Devolve a chave resolvida.
 */
export async function saveEquipment(key: string | null, partnerKey: string, changed: Rec): Promise<string> {
  checkFields(changed, EQUIPMENT_FIELDS)
  // Pré-cálculo fora da transação (best-effort; a chave definitiva é resolvida dentro dela).
  const preK = key ? await resolveKey(key) : newTmp()
  const b64 = isTmp(preK) && !(await opsFor(preK)).length ? await photosB64(preK) : new Map<string, string>()

  const k = await db.transaction('rw', allTables(), async () => {
    const pKey = await resolveKey(partnerKey)
    const k = key ? await resolveKey(key) : preK
    const existing = await db.equipments.get(k)
    if (key && !existing) throw new Error(`Equipamento ${k} não encontrado`)
    const diff = diffFields(existing, changed, EQUIPMENT_M2O)
    const merged = { ...(existing ?? { key: k, partnerKey: pKey }), ...diff, sync: 'pendente', syncError: undefined } as LocalEquipment
    if (!existing || Object.keys(diff).length) await db.equipments.put(merged)

    const hasOp = (await opsFor(k)).length > 0
    if (!isTmp(k) || hasOp) {
      if (!Object.keys(diff).length) return k
      if (await coalesce(k, 'equipment.upsert', diff)) return k
      await enqueue({
        kind: 'equipment.upsert', ref: refOf(k), payload: diff,
        ...(isTmp(k) ? {} : { base_write_date: (existing?.base_write_date as string | undefined) ?? false }),
      })
    } else if (!missingRequired(merged).length) {
      await enqueue({
        kind: 'equipment.upsert', ref: k,
        payload: { partner_id: refOf(merged.partnerKey), ...fullPayload(merged, EQUIPMENT_FIELDS) },
      })
      await flushChildren(k, b64)
    }
    return k
  })
  if (isTmp(k)) await releaseDeferredPhotos(k)
  return k
}

/**
 * Rede de segurança pós-criação: fotos que entraram durante a janela do
 * flush (sem base64 pré-calculado) e seguem sem op são enfileiradas agora.
 */
async function releaseDeferredPhotos(ek: string): Promise<void> {
  if (!(await opsFor(ek)).length) return
  const orphans: LocalPhoto[] = []
  for (const p of await db.photos.where('equipmentKey').equals(ek).toArray()) {
    if (!p.isThumb && !(await opsFor(p.key)).length) orphans.push(p)
  }
  if (!orphans.length) return
  const b64 = new Map<string, string>()
  for (const p of orphans) b64.set(p.key, await blobToBase64(p.blob))
  await db.transaction('rw', allTables(), async () => {
    for (const p of orphans) {
      if (!(await db.photos.get(p.key)) || (await opsFor(p.key)).length) continue
      if (p.cycleKey && !(await isReady(p.cycleKey))) continue
      await enqueue({ kind: 'photo.add', ref: refOf(p.key), payload: photoPayload(p, b64.get(p.key)!) })
    }
  })
}

// ------------------------------------------------------------------------ ciclo

/** Cria (key null) ou edita um ciclo. Mesmas regras de `saveEquipment`. */
export async function saveCycle(key: string | null, equipmentKey: string, changed: Rec): Promise<string> {
  checkFields(changed, CYCLE_FIELDS)
  const newKey = newTmp()
  return db.transaction('rw', allTables(), async () => {
    const ek = await resolveKey(equipmentKey)
    const k = key ? await resolveKey(key) : newKey
    const existing = await db.cycles.get(k)
    if (key && !existing) throw new Error(`Ciclo ${k} não encontrado`)
    const diff = diffFields(existing, changed, CYCLE_M2O)
    const merged = { ...(existing ?? { key: k, equipmentKey: ek }), ...diff, sync: 'pendente', syncError: undefined } as LocalCycle
    if (!existing || Object.keys(diff).length) await db.cycles.put(merged)

    const hasOp = (await opsFor(k)).length > 0
    if (!isTmp(k) || hasOp) {
      if (!Object.keys(diff).length) return k
      if (await coalesce(k, 'cycle.upsert', diff)) return k
      await enqueue({
        kind: 'cycle.upsert', ref: refOf(k), payload: diff,
        ...(isTmp(k) ? {} : { base_write_date: (existing?.base_write_date as string | undefined) ?? false }),
      })
    } else if (await isReady(merged.equipmentKey)) {
      await enqueue({
        kind: 'cycle.upsert', ref: k,
        payload: { equipment_id: refOf(merged.equipmentKey), ...fullPayload(merged, CYCLE_FIELDS) },
      })
    } // senão: adiado até o equipamento ser enfileirado (flushChildren)
    return k
  })
}

/**
 * Remove ops da outbox de um registro que nunca chegou ao servidor. Devolve
 * true se NENHUMA estava em voo (nesse caso não há o que apagar no servidor).
 */
async function dropUnsent(key: string): Promise<boolean> {
  const ops = await opsFor(key)
  if (ops.some((o) => o.state === 'enviando')) return false
  await db.outbox.bulkDelete(ops.map((o) => o.op_uuid))
  return true
}

/** Apaga o registro local, e a op: some se nunca foi enviado, senão vira delete. */
async function removeRecord(key: string, deleteKind: SurveyOpKind, enqueueDelete: boolean) {
  if (!enqueueDelete) {
    await dropUnsent(key)
    return
  }
  if (isTmp(key)) {
    if (await dropUnsent(key)) return
  } else {
    // upserts ainda não enviados perdem o sentido
    const ops = (await opsFor(key)).filter((o) => o.state === 'pendente' && o.kind !== deleteKind)
    await db.outbox.bulkDelete(ops.map((o) => o.op_uuid))
  }
  await enqueue({ kind: deleteKind, ref: refOf(key), payload: {} })
}

/** Remove o ciclo localmente já; fotos do ciclo saem junto (cascata local). */
export async function deleteCycle(key: string): Promise<void> {
  await db.transaction('rw', allTables(), async () => {
    const k = await resolveKey(key)
    const cycle = await db.cycles.get(k)
    if (!cycle) return
    for (const p of await db.photos.where('cycleKey').equals(k).toArray()) {
      await db.photos.delete(p.key)
      await removeRecord(p.key, 'photo.delete', false)
    }
    await db.cycles.delete(k)
    await removeRecord(k, 'cycle.delete', true)
  })
}

// ------------------------------------------------------------------------ fotos

/**
 * Comprime (JPEG ~1600px/0.8), guarda o blob local e enfileira `photo.add`
 * com base64. Se o equipamento/ciclo ainda não foi enfileirado, a op espera.
 */
export async function addPhoto(equipmentKey: string, kind: string, file: Blob, cycleKey?: string): Promise<string> {
  const blob = await compressImage(file)
  const b64 = await blobToBase64(blob)
  const key = newTmp()
  await db.transaction('rw', allTables(), async () => {
    const ek = await resolveKey(equipmentKey)
    const ck = cycleKey ? await resolveKey(cycleKey) : undefined
    const rec = {
      key, equipmentKey: ek, survey_kind: kind, blob, sync: 'pendente',
      ...(ck ? { cycleKey: ck } : {}),
    } as LocalPhoto
    await db.photos.put(rec)
    if ((await isReady(ek)) && (!ck || (await isReady(ck)))) {
      await enqueue({ kind: 'photo.add', ref: key, payload: photoPayload(rec, b64) })
    }
  })
  return key
}

export async function deletePhoto(key: string): Promise<void> {
  await db.transaction('rw', allTables(), async () => {
    const k = await resolveKey(key)
    if (!(await db.photos.get(k))) return
    await db.photos.delete(k)
    await removeRecord(k, 'photo.delete', true)
  })
}

// ------------------------------------------------------------------------ outbox

/** Ops aguardando envio (pendente + enviando); `erro` fica fora. */
export const pendingCount = (): Promise<number> =>
  db.outbox.where('state').anyOf('pendente', 'enviando').count()

/** Ops paradas em erro terminal (precisam de ação do usuário). */
export const errorCount = (): Promise<number> => db.outbox.where('state').equals('erro').count()
