import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const pullPartner = vi.fn()
const pullCatalog = vi.fn()
vi.mock('@/lib/odoo/levantamento', () => ({
  pullPartner: (...a: unknown[]) => pullPartner(...a),
  pullCatalog: (...a: unknown[]) => pullCatalog(...a),
}))
vi.mock('../photo', async (orig) => ({
  ...(await orig<typeof import('../photo')>()),
  compressImage: vi.fn(async (_b: Blob) => new Blob(['compressed'], { type: 'image/jpeg' })),
}))

import { db } from '../db'
import {
  addPhoto, createPartner, loadCatalog, refreshCatalog, deleteCycle, deletePhoto, downloadPartner, missingRequired,
  pendingCount, saveCycle, saveEquipment, retryRecord, discardRecord,
} from '../repo'

beforeEach(async () => {
  pullPartner.mockReset()
  await Promise.all(db.tables.map((t) => t.clear()))
})

const ops = () => db.outbox.orderBy('createdAt').toArray()

const serverPartner = {
  partner: { id: 7, name: 'ACME', vat: '11.222.333/0001-81', city: 'SP' },
  equipments: [{
    id: 100, write_date: '2026-10-01 10:00:00', name: 'Autoclave', apelido: false, model: 'M1',
    serial_number: 'S1', tag: false, patrimony: false, chamber_volume_l: 50, chamber_dimensions: false,
    sensor_qty_estimated: 0, thermocouple_access: false, power_supply: false, survey_note: false,
    category_id: [3, 'Autoclave'], marca_id: [4, 'Acme'], location_id: false, survey_user_id: false,
    survey_date: false,
    cycles: [{
      id: 200, write_date: '2026-10-01 11:00:00', cycle_type_id: [9, '134C'], temperature: 134,
      duration: 4, load_type: 'tecido', note: false,
      pictures: [{ id: 301, survey_kind: 'ciclo', cycle_id: 200, name: 'c', thumb_b64: 'aGk=' }],
    }],
    pictures: [{ id: 300, survey_kind: 'geral', cycle_id: false, name: 'g', thumb_b64: false }],
  }],
}

describe('downloadPartner', () => {
  it('armazena cliente, equipamentos, ciclos e fotos com base_write_date', async () => {
    pullPartner.mockResolvedValue(serverPartner)
    await downloadPartner(7)
    const p = await db.partners.get('7')
    expect(p).toMatchObject({ id: 7, name: 'ACME', sync: 'ok' })
    const e = await db.equipments.get('100')
    expect(e).toMatchObject({
      partnerKey: '7', base_write_date: '2026-10-01 10:00:00', category_id: 3,
      category_id_name: 'Autoclave', location_id: false, sync: 'ok',
    })
    const c = await db.cycles.get('200')
    expect(c).toMatchObject({ equipmentKey: '100', cycle_type_id: 9, base_write_date: '2026-10-01 11:00:00' })
    const ph = await db.photos.get('301')
    expect(ph).toMatchObject({ equipmentKey: '100', cycleKey: '200', survey_kind: 'ciclo', isThumb: true })
    expect(ph!.blob.size).toBe(2)
    expect((await db.photos.get('300'))!.cycleKey).toBeUndefined()
    expect(await db.outbox.count()).toBe(0)
  })

  it('não sobrescreve registro com edição pendente e remove os apagados no servidor', async () => {
    pullPartner.mockResolvedValue(serverPartner)
    await downloadPartner(7)
    await saveEquipment('100', '7', { model: 'LOCAL' })
    await db.equipments.put({ key: '101', id: 101, partnerKey: '7', sync: 'ok' })
    pullPartner.mockResolvedValue(serverPartner)
    await downloadPartner(7)
    expect((await db.equipments.get('100'))!.model).toBe('LOCAL')
    expect(await db.equipments.get('101')).toBeUndefined()
  })

  it('não ressuscita ciclo com delete pendente', async () => {
    pullPartner.mockResolvedValue(serverPartner)
    await downloadPartner(7)
    await deleteCycle('200')
    await downloadPartner(7)
    expect(await db.cycles.get('200')).toBeUndefined()
  })
})

describe('createPartner', () => {
  it('grava local e enfileira partner.create', async () => {
    const key = await createPartner({ name: 'Novo', vat: '11222333000181', contact_name: 'Ze' })
    expect(key.startsWith('tmp:')).toBe(true)
    expect(await db.partners.get(key)).toMatchObject({ name: 'Novo', sync: 'pendente' })
    const [op] = await ops()
    expect(op).toMatchObject({ kind: 'partner.create', ref: key })
    expect(op.payload).toEqual({ name: 'Novo', vat: '11222333000181', contact_name: 'Ze' })
  })
})

describe('saveEquipment', () => {
  beforeEach(async () => {
    pullPartner.mockResolvedValue(serverPartner)
    await downloadPartner(7)
  })

  it('duas edições mesclam local; a 2a funde na op pendente (mantém base_write_date original)', async () => {
    await saveEquipment('100', '7', { model: 'M2' })
    await saveEquipment('100', '7', { tag: 'T-1', category_id: 5 })
    const e = await db.equipments.get('100')
    expect(e).toMatchObject({ model: 'M2', tag: 'T-1', category_id: 5, serial_number: 'S1', sync: 'pendente' })
    const o = await ops()
    expect(o).toHaveLength(1)
    expect(o[0].payload).toEqual({ model: 'M2', tag: 'T-1', category_id: 5 })
    expect(o[0]).toMatchObject({ kind: 'equipment.upsert', ref: 100, base_write_date: '2026-10-01 10:00:00' })
  })

  it('edição com op em voo (enviando) enfileira nova op', async () => {
    await saveEquipment('100', '7', { model: 'M2' })
    await db.outbox.toCollection().modify({ state: 'enviando' })
    await saveEquipment('100', '7', { tag: 'T-1' })
    const o = await ops()
    expect(o.map((x) => x.payload)).toEqual([{ model: 'M2' }, { tag: 'T-1' }])
  })

  it('string numérica igual ao número não conta como alteração', async () => {
    await saveEquipment('100', '7', { chamber_volume_l: '50' })
    expect(await ops()).toHaveLength(0)
    await saveCycle('200', '100', { temperature: '134' })
    expect(await ops()).toHaveLength(0)
  })

  it('foto adiada que escapou do flush é liberada na próxima gravação', async () => {
    const ek = await saveEquipment(null, '7', { category_id: 1, marca_id: 2, model: 'm' })
    await db.photos.put({ key: 'tmp:late', equipmentKey: ek, survey_kind: 'geral', blob: new Blob(['zz']), sync: 'pendente' } as never)
    expect((await ops()).map((x) => x.kind)).toEqual(['equipment.upsert'])
    await saveEquipment(ek, '7', { tag: 'x' })
    const o = await ops()
    expect(o.map((x) => x.kind)).toEqual(['equipment.upsert', 'photo.add'])
    expect(o[1]).toMatchObject({ ref: 'tmp:late' })
    expect(o[1].payload.image_b64).toBe(btoa('zz'))
  })

  it('campo não alterado não gera op', async () => {
    await saveEquipment('100', '7', { model: 'M1' })
    expect(await ops()).toHaveLength(0)
  })

  it('rejeita campo fora da whitelist', async () => {
    await expect(saveEquipment('100', '7', { bogus: 1 })).rejects.toThrow(/bogus/)
  })

  it('novo equipamento: só enfileira com categoria; depois envia tudo', async () => {
    const key = await saveEquipment(null, '7', { name: 'Novo' })
    expect(key.startsWith('tmp:')).toBe(true)
    expect(await ops()).toHaveLength(0)
    expect(missingRequired((await db.equipments.get(key))!)).toEqual(['category_id'])
    await saveEquipment(key, '7', { category_id: 3 })
    let o = await ops()
    expect(o).toHaveLength(1)
    expect(o[0]).toMatchObject({ kind: 'equipment.upsert', ref: key })
    expect(o[0].payload).toEqual({ partner_id: 7, name: 'Novo', category_id: 3 })
    await saveEquipment(key, '7', { tag: 'T' })
    o = await ops()
    expect(o).toHaveLength(1) // funde na op de criação ainda pendente
    expect(o[0].payload).toMatchObject({ category_id: 3, tag: 'T' })
    await db.outbox.toCollection().modify({ state: 'enviando' })
    await saveEquipment(key, '7', { tag: 'T2' })
    o = await ops()
    expect(o).toHaveLength(2)
    expect(o[1].payload).toEqual({ tag: 'T2' })
  })

  it('cliente tmp vai como partner_id tmp', async () => {
    const pk = await createPartner({ name: 'N' })
    const key = await saveEquipment(null, pk, { category_id: 1, marca_id: 2, model: 'm' })
    const o = await ops()
    expect(o[1].payload.partner_id).toBe(pk)
    expect(await db.equipments.get(key)).toMatchObject({ partnerKey: pk })
  })

  it('chave tmp obsoleta é resolvida via idmap, sem recriar registro tmp', async () => {
    const key = await saveEquipment(null, '7', { category_id: 1, marca_id: 2, model: 'm' })
    // engine reescreveu tmp -> 555
    const rec = (await db.equipments.get(key))!
    await db.equipments.delete(key)
    await db.equipments.put({ ...rec, key: '555', id: 555 })
    await db.idmap.put({ tmp: key, id: 555 })
    const out = await saveEquipment(key, '7', { tag: 'Z' })
    expect(out).toBe('555')
    expect(await db.equipments.get(key)).toBeUndefined()
    expect((await db.equipments.get('555'))!.tag).toBe('Z')
    const last = (await ops()).at(-1)!
    expect(last.ref).toBe(555)
  })
})

describe('saveCycle / deleteCycle', () => {
  beforeEach(async () => {
    pullPartner.mockResolvedValue(serverPartner)
    await downloadPartner(7)
  })

  it('cria ciclo em equipamento real com payload completo', async () => {
    const key = await saveCycle(null, '100', { cycle_type_id: 9, temperature: 121 })
    const [o] = await ops()
    expect(o).toMatchObject({ kind: 'cycle.upsert', ref: key })
    expect(o.payload).toEqual({ equipment_id: 100, cycle_type_id: 9, temperature: 121 })
  })

  it('saveCycle com chave tmp obsoleta (reescrita pelo engine) edita o ciclo real', async () => {
    await db.idmap.put({ tmp: 'tmp:stale', id: 200 })
    const k = await saveCycle('tmp:stale', '100', { note: 'via tmp' })
    expect(k).toBe('200')
    expect((await db.cycles.get('200'))!.note).toBe('via tmp')
    expect(await db.cycles.get('tmp:stale')).toBeUndefined()
  })

  it('edita ciclo real: só alterados + base_write_date; 2a edição funde', async () => {
    await saveCycle('200', '100', { duration: 6, temperature: 134 })
    await saveCycle('200', '100', { note: 'n' })
    const o = await ops()
    expect(o).toHaveLength(1)
    expect(o[0]).toMatchObject({ ref: 200, base_write_date: '2026-10-01 11:00:00' })
    expect(o[0].payload).toEqual({ duration: 6, note: 'n' })
  })

  it('ciclo em equipamento tmp incompleto fica adiado e é liberado quando o equipamento é enfileirado', async () => {
    const ek = await saveEquipment(null, '7', { name: 'N' })
    const ck = await saveCycle(null, ek, { temperature: 100 })
    const pk = await addPhoto(ek, 'geral', new Blob(['p']), ck)
    expect(await ops()).toHaveLength(0)
    expect(await pendingCount()).toBe(0)
    await saveEquipment(ek, '7', { category_id: 1, marca_id: 2, model: 'm' })
    const o = await ops()
    expect(o.map((x) => x.kind)).toEqual(['equipment.upsert', 'cycle.upsert', 'photo.add'])
    expect(o[1].payload).toEqual({ equipment_id: ek, temperature: 100 })
    expect(o[2]).toMatchObject({ ref: pk })
    expect(o[2].payload).toMatchObject({ equipment_id: ek, cycle_id: ck, survey_kind: 'geral' })
  })

  it('deleteCycle de ciclo real: remove local (e fotos) e enfileira cycle.delete', async () => {
    await deleteCycle('200')
    expect(await db.cycles.get('200')).toBeUndefined()
    expect(await db.photos.get('301')).toBeUndefined()
    const o = await ops()
    expect(o).toHaveLength(1)
    expect(o[0]).toMatchObject({ kind: 'cycle.delete', ref: 200 })
  })

  it('deleteCycle de ciclo tmp não enviado: descarta ops pendentes, sem delete', async () => {
    const ck = await saveCycle(null, '100', { temperature: 1 })
    const pk = await addPhoto('100', 'ciclo', new Blob(['x']), ck)
    expect(await ops()).toHaveLength(2)
    await deleteCycle(ck)
    expect(await ops()).toHaveLength(0)
    expect(await db.cycles.get(ck)).toBeUndefined()
    expect(await db.photos.get(pk)).toBeUndefined()
  })

  it('deleteCycle de tmp com op em voo enfileira delete', async () => {
    const ck = await saveCycle(null, '100', { temperature: 1 })
    await db.outbox.toCollection().modify({ state: 'enviando' })
    await deleteCycle(ck)
    const o = await ops()
    expect(o.map((x) => x.kind)).toEqual(['cycle.upsert', 'cycle.delete'])
    expect(o[1].ref).toBe(ck)
  })
})

describe('photos', () => {
  beforeEach(async () => {
    pullPartner.mockResolvedValue(serverPartner)
    await downloadPartner(7)
  })

  it('addPhoto precompressed não recomprime', async () => {
    const { compressImage } = await import('../photo')
    vi.mocked(compressImage).mockClear()
    const blob = new Blob(['ja-comprimida'], { type: 'image/jpeg' })
    const key = await addPhoto('100', 'geral', blob, undefined, { precompressed: true })
    expect(compressImage).not.toHaveBeenCalled()
    expect((await db.photos.get(key))!.blob.size).toBe(blob.size)
  })

  it('addPhoto guarda blob comprimido e enfileira photo.add com base64', async () => {
    const key = await addPhoto('100', 'placa', new Blob(['raw']))
    const rec = (await db.photos.get(key))!
    expect(rec.equipmentKey).toBe('100')
    expect(rec.blob.size).toBe('compressed'.length)
    expect(rec.isThumb).toBeUndefined()
    const [o] = await ops()
    expect(o).toMatchObject({ kind: 'photo.add', ref: key })
    expect(o.payload).toEqual({
      equipment_id: 100, survey_kind: 'placa', image_b64: btoa('compressed'),
    })
  })

  it('deletePhoto real enfileira photo.delete; tmp pendente só descarta', async () => {
    await deletePhoto('300')
    expect((await ops()).map((x) => [x.kind, x.ref])).toEqual([['photo.delete', 300]])
    const k = await addPhoto('100', 'geral', new Blob(['x']))
    await deletePhoto(k)
    expect(await db.photos.get(k)).toBeUndefined()
    expect((await ops()).map((x) => x.kind)).toEqual(['photo.delete'])
  })

  it('pendingCount conta pendente+enviando', async () => {
    await addPhoto('100', 'geral', new Blob(['x']))
    await addPhoto('100', 'geral', new Blob(['y']))
    expect(await pendingCount()).toBe(2)
    await db.outbox.toCollection().modify({ state: 'erro' })
    expect(await pendingCount()).toBe(0)
  })
})

describe('catálogo', () => {
  it('refreshCatalog guarda em db.catalog e loadCatalog devolve', async () => {
    pullCatalog.mockResolvedValue({ categories: [{ id: 1, name: 'A' }], selections: { load_type: [] } })
    await refreshCatalog()
    expect(await db.catalog.count()).toBe(2)
    expect(await loadCatalog()).toEqual({ categories: [{ id: 1, name: 'A' }], selections: { load_type: [] } })
  })
})

describe('retryRecord / discardRecord', () => {
  const failAll = async (msg: string) => {
    await db.outbox.toCollection().modify({ state: 'erro', error: msg, attempts: 7 })
  }

  it('Reenviar: ops em erro do registro e dependentes voltam a pendente; create tmp refeito com o registro completo', async () => {
    const pk = await createPartner({ name: 'Novo', vat: '1' })
    const ek = await saveEquipment(null, pk, { category_id: 3, marca_id: 4, model: 'M' })
    const ck = await saveCycle(null, ek, { temperature: 121 })
    await failAll('boom')
    await db.equipments.update(ek, { sync: 'erro', syncError: 'boom' })
    // edição local depois da falha (vai como op nova, não fundida)
    await saveEquipment(ek, pk, { name: 'Autoclave A' })
    await db.equipments.update(ek, { sync: 'erro', syncError: 'boom' })

    const n = await retryRecord(ek)
    expect(n).toBe(2) // create do equipamento + ciclo (partner não é dependente)
    const all = await ops()
    const eqCreate = all.find((o) => o.kind === 'equipment.upsert' && 'partner_id' in o.payload)!
    expect(eqCreate).toMatchObject({ state: 'pendente', attempts: 0 })
    expect(eqCreate.error).toBeUndefined()
    expect(eqCreate.payload).toMatchObject({ partner_id: pk, category_id: 3, marca_id: 4, model: 'M', name: 'Autoclave A' })
    expect(all.find((o) => o.kind === 'cycle.upsert')!.state).toBe('pendente')
    expect(all.find((o) => o.kind === 'partner.create')!.state).toBe('erro')
    expect((await db.equipments.get(ek))!.sync).toBe('pendente')
    expect((await db.equipments.get(ek))!.syncError).toBeUndefined()
    expect((await db.cycles.get(ck))!.sync).toBe('pendente')
  })

  it('Reenviar dá op_uuid novo às ops em erro (mesmo payload/ref, original apagada, ordem mantida)', async () => {
    const pk = await createPartner({ name: 'Novo' })
    const ek = await saveEquipment(null, pk, { category_id: 3, marca_id: 4, model: 'M' })
    const ck = await saveCycle(null, ek, { temperature: 121 })
    await failAll('boom')
    await db.outbox.toCollection().modify({ sent: true })
    const antes = (await ops()).filter((o) => o.kind !== 'partner.create')
    await retryRecord(ek)
    const depois = (await ops()).filter((o) => o.kind !== 'partner.create')
    expect(depois).toHaveLength(antes.length)
    depois.forEach((o, i) => {
      expect(o.op_uuid).not.toBe(antes[i].op_uuid)
      expect(o.kind).toBe(antes[i].kind)
      expect(o.ref).toBe(antes[i].ref)
      expect(o.createdAt).toBe(antes[i].createdAt)
      expect(o).toMatchObject({ state: 'pendente', attempts: 0 })
      expect(o.error).toBeUndefined()
      expect(o.sent).toBeFalsy()
    })
    for (const o of antes) expect(await db.outbox.get(o.op_uuid)).toBeUndefined()
    expect(ck).toBeTruthy()
  })

  it('Reenviar no cliente tmp alcança equipamentos dependentes', async () => {
    const pk = await createPartner({ name: 'Novo', contact_name: 'Zé' })
    await saveEquipment(null, pk, { category_id: 3, marca_id: 4, model: 'M' })
    await failAll('x')
    await db.partners.update(pk, { name: 'Novo Nome' })
    expect(await retryRecord(pk)).toBe(2)
    const pc = (await ops()).find((o) => o.kind === 'partner.create')!
    expect(pc.payload).toMatchObject({ name: 'Novo Nome', contact_name: 'Zé' })
    expect((await ops()).every((o) => o.state === 'pendente')).toBe(true)
  })

  it('Descartar: remove registro, ops e dependentes', async () => {
    const pk = await createPartner({ name: 'Novo' })
    const ek = await saveEquipment(null, pk, { category_id: 3, marca_id: 4, model: 'M' })
    const ck = await saveCycle(null, ek, { temperature: 121 })
    const fk = await addPhoto(ek, 'geral', new Blob(['a']), ck)
    const outro = await createPartner({ name: 'Outro' })
    await discardRecord(pk)
    expect(await db.partners.get(pk)).toBeUndefined()
    expect(await db.equipments.get(ek)).toBeUndefined()
    expect(await db.cycles.get(ck)).toBeUndefined()
    expect(await db.photos.get(fk)).toBeUndefined()
    const rest = await ops()
    expect(rest).toHaveLength(1)
    expect(rest[0].ref).toBe(outro)
  })

  it('Descartar equipamento real não mexe em op de outro modelo com o mesmo id', async () => {
    await db.equipments.put({ key: '5', id: 5, partnerKey: '7', sync: 'erro' })
    await db.cycles.put({ key: '5', id: 5, equipmentKey: '99', sync: 'ok' })
    await saveEquipment('5', '7', { model: 'Z' })
    await saveCycle('5', '99', { temperature: 1 })
    await discardRecord('5', 'equipment')
    expect(await db.equipments.get('5')).toBeUndefined()
    expect(await db.cycles.get('5')).toBeDefined()
    expect((await ops()).map((o) => o.kind)).toEqual(['cycle.upsert'])
  })
})

it('Descartar ciclo real pelo tipo explícito', async () => {
  await db.equipments.put({ key: '5', id: 5, partnerKey: '7', sync: 'ok' })
  await db.cycles.put({ key: '5', id: 5, equipmentKey: '99', sync: 'erro' })
  await saveCycle('5', '99', { temperature: 1 })
  await discardRecord('5', 'cycle')
  expect(await db.cycles.get('5')).toBeUndefined()
  expect(await db.equipments.get('5')).toBeDefined()
  expect(await db.outbox.count()).toBe(0)
})
