import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import { db } from '../db'

beforeEach(async () => {
  await Promise.all(db.tables.map((t) => t.clear()))
})

describe('levantamento db', () => {
  it('declares all tables', () => {
    expect(db.tables.map((t) => t.name).sort()).toEqual(
      ['catalog', 'cycles', 'equipments', 'idmap', 'outbox', 'partners', 'photos'],
    )
  })

  it('key is unique primary key', async () => {
    await db.equipments.put({ key: 'tmp:a', partnerKey: '1', sync: 'pendente' })
    await db.equipments.put({ key: 'tmp:a', partnerKey: '2', sync: 'pendente' })
    expect(await db.equipments.count()).toBe(1)
    expect((await db.equipments.get('tmp:a'))!.partnerKey).toBe('2')
  })

  it('stores photo blobs and queries by equipmentKey', async () => {
    await db.photos.put({
      key: 'tmp:p', equipmentKey: 'tmp:e', blob: new Blob(['x']), sync: 'pendente',
    })
    expect(await db.photos.where('equipmentKey').equals('tmp:e').count()).toBe(1)
  })
})
