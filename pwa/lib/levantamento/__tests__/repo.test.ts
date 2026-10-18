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
  compressImage: vi.fn(async (b: Blob) => new Blob(['compressed'], { type: 'image/jpeg' })),
}))

import { db } from '../db'
import {
  addPhoto, createPartner, loadCatalog, refreshCatalog, deleteCycle, deletePhoto, downloadPartner, missingRequired,
  pendingCount, saveCycle, saveEquipment,
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

  it('duas edições mesclam local e enfileiram só campos alterados + base_write_date', async () => {
    await saveEquipment('100', '7', { model: 'M2' })
    await saveEquipment('100', '7', { tag: 'T-1', category_id: 5 })
    const e = await db.equipments.get('100')
    expect(e).toMatchObject({ model: 'M2', tag: 'T-1', category_id: 5, serial_number: 'S1', sync: 'pendente' })
    const o = await ops()
    expect(o.map((x) => x.payload)).toEqual([{ model: 'M2' }, { tag: 'T-1', category_id: 5 }])
    expect(o.every((x) => x.kind === 'equipment.upsert' && x.ref === 100)).toBe(true)
    expect(o[0].base_write_date).toBe('2026-10-01 10:00:00')
  })

  it('campo não alterado não gera op', async () => {
    await saveEquipment('100', '7', { model: 'M1' })
    expect(await ops()).toHaveLength(0)
  })

  it('rejeita campo fora da whitelist', async () => {
    await expect(saveEquipment('100', '7', { bogus: 1 })).rejects.toThrow(/bogus/)
  })

  it('novo equipamento: só enfileira com categoria, marca e modelo; depois envia tudo', async () => {
    const key = await saveEquipment(null, '7', { name: 'Novo', category_id: 3 })
    expect(key.startsWith('tmp:')).toBe(true)
    expect(await ops()).toHaveLength(0)
    expect(missingRequired((await db.equipments.get(key))!)).toEqual(['marca_id', 'model'])
    await saveEquipment(key, '7', { marca_id: 4 })
    expect(await ops()).toHaveLength(0)
    await saveEquipment(key, '7', { model: 'X' })
    let o = await ops()
    expect(o).toHaveLength(1)
    expect(o[0]).toMatchObject({ kind: 'equipment.upsert', ref: key })
    expect(o[0].payload).toEqual({ partner_id: 7, name: 'Novo', category_id: 3, marca_id: 4, model: 'X' })
    await saveEquipment(key, '7', { tag: 'T' })
    o = await ops()
    expect(o).toHaveLength(2)
    expect(o[1].payload).toEqual({ tag: 'T' })
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

  it('edita ciclo real: só alterados + base_write_date', async () => {
    await saveCycle('200', '100', { duration: 6, temperature: 134 })
    const [o] = await ops()
    expect(o).toMatchObject({ ref: 200, base_write_date: '2026-10-01 11:00:00' })
    expect(o.payload).toEqual({ duration: 6 })
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
