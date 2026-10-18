import Dexie, { type Table } from 'dexie'

/** Estado de sincronização de um registro local. */
export type SyncState = 'ok' | 'pendente' | 'erro'

/** Campos comuns a todo registro local. `key` = id do servidor (string) ou `"tmp:<uuid>"`. */
export interface SyncFields {
  key: string
  /** Id real no servidor; ausente enquanto o registro só existe como `tmp:`. */
  id?: number
  sync: SyncState
  syncError?: string
}

export interface LocalPartner extends SyncFields {
  name?: string
  vat?: string
  [campo: string]: unknown
}
export interface LocalEquipment extends SyncFields {
  partnerKey: string
  [campo: string]: unknown
}
export interface LocalCycle extends SyncFields {
  equipmentKey: string
  [campo: string]: unknown
}
export interface LocalPhoto extends SyncFields {
  equipmentKey: string
  cycleKey?: string
  blob: Blob
  [campo: string]: unknown
}

export type OutboxState = 'pendente' | 'enviando' | 'erro'

export type SurveyOpKind =
  | 'partner.create'
  | 'equipment.upsert'
  | 'cycle.upsert'
  | 'cycle.delete'
  | 'photo.add'
  | 'photo.delete'

/** Espelha o formato de op do backend (`survey_push`). */
export interface SurveyOp {
  op_uuid: string
  kind: SurveyOpKind
  /** `tmp:<uuid>` ou id real. */
  ref: string | number
  base_write_date?: string | false
  payload: Record<string, unknown>
}

export interface OutboxEntry extends SurveyOp {
  state: OutboxState
  attempts: number
  createdAt: number
  error?: string
}

export interface CatalogEntry {
  name: string
  items: unknown
  [campo: string]: unknown
}
export interface IdMapEntry {
  tmp: string
  id: number
}

class LevantamentoDB extends Dexie {
  partners!: Table<LocalPartner, string>
  equipments!: Table<LocalEquipment, string>
  cycles!: Table<LocalCycle, string>
  photos!: Table<LocalPhoto, string>
  outbox!: Table<OutboxEntry, string>
  catalog!: Table<CatalogEntry, string>
  idmap!: Table<IdMapEntry, string>

  constructor() {
    super('levantamento')
    this.version(1).stores({
      partners: '&key, id, vat',
      equipments: '&key, partnerKey, id',
      cycles: '&key, equipmentKey',
      photos: '&key, equipmentKey, cycleKey',
      outbox: '&op_uuid, state, createdAt',
      catalog: '&name',
      idmap: '&tmp',
    })
    // v2: índice `ref` na outbox (busca de ops por registro sem varrer tudo).
    this.version(2).stores({ outbox: '&op_uuid, state, createdAt, ref' })
  }
}

export const db = new LevantamentoDB()
