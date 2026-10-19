import Dexie, { type Table } from 'dexie'
import { useAuthStore } from '@/lib/store/authStore'

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
  /**
   * Já foi entregue a `push` alguma vez (nunca volta a false). O servidor pode
   * ter gravado a op mesmo sem confirmação, e replay do mesmo `op_uuid` devolve
   * o resultado guardado ignorando o payload: não se funde edição nela.
   */
  sent?: boolean
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

export class LevantamentoDB extends Dexie {
  partners!: Table<LocalPartner, string>
  equipments!: Table<LocalEquipment, string>
  cycles!: Table<LocalCycle, string>
  photos!: Table<LocalPhoto, string>
  outbox!: Table<OutboxEntry, string>
  catalog!: Table<CatalogEntry, string>
  idmap!: Table<IdMapEntry, string>

  constructor(name = 'levantamento') {
    super(name)
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

/** Hash curto e estável (FNV-1a 32 bits, hex). */
function shortHash(s: string): string {
  let h = 0x811c9dc5
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

export interface SurveySession {
  serverUrl: string
  dbName: string
  userId: number | null
}

/** Chave da sessão: servidor + base Odoo + uid. */
export const sessionKeyOf = (s: SurveySession) => `${s.serverUrl}|${s.dbName}|${s.userId ?? ''}`
/** Nome do IndexedDB da sessão: `levantamento:<hash>`. */
export const surveyDbName = (sessionKey: string) => `levantamento:${shortHash(sessionKey)}`

const opened = new Map<string, LevantamentoDB>()

/**
 * Banco local de uma sessão (reaproveita a instância). Cada servidor/base/
 * usuário tem o seu: um não enxerga a outbox do outro.
 */
export function openSurveyDb(key: string): LevantamentoDB {
  const name = surveyDbName(key)
  let d = opened.get(name)
  if (!d) {
    d = new LevantamentoDB(name)
    opened.set(name, d)
  }
  return d
}

/** Chave da sessão corrente (servidor/base/uid do authStore). */
export const currentSessionKey = () => sessionKeyOf(useAuthStore.getState())

/** Banco local da sessão corrente. Use sempre isto (nada de singleton fixo). */
export function getDb(): LevantamentoDB {
  return openSurveyDb(currentSessionKey())
}

/**
 * Atalho para o banco da sessão corrente (resolve a cada acesso). Mantido
 * para testes; código de produção usa `getDb()`.
 */
export const db: LevantamentoDB = new Proxy({} as LevantamentoDB, {
  get(_t, prop) {
    const d = getDb()
    const v = Reflect.get(d, prop, d)
    return typeof v === 'function' ? v.bind(d) : v
  },
})
