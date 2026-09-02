'use client'

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

export interface FieldMeta {
  string?: string
  type: string
  required?: boolean
  readonly?: boolean
  selection?: Array<[string, string]>
  relation?: string
}

export interface AccessRights {
  read: boolean
  write: boolean
  create: boolean
  unlink: boolean
}

interface SchemaState {
  fields: Record<string, Record<string, FieldMeta>>
  access: Record<string, AccessRights>
  loadedAt: number

  setModel: (model: string, fields: Record<string, FieldMeta>, access: AccessRights) => void
  clear: () => void

  // Helpers
  hasField: (model: string, field: string) => boolean
  filterFields: (model: string, fields: string[]) => string[]
  canRead: (model: string) => boolean
  canWrite: (model: string) => boolean
  canCreate: (model: string) => boolean
  canUnlink: (model: string) => boolean
  isLoaded: (model: string) => boolean
}

export const useSchemaStore = create<SchemaState>()(
  devtools(
    persist(
      (set, get) => ({
        fields: {},
        access: {},
        loadedAt: 0,

        setModel: (model, fields, access) =>
          set((s) => ({
            fields: { ...s.fields, [model]: fields },
            access: { ...s.access, [model]: access },
            loadedAt: Date.now(),
          })),

        clear: () => set({ fields: {}, access: {}, loadedAt: 0 }),

        hasField: (model, field) => {
          const m = get().fields[model]
          if (!m) return true // sem cache: permite e deixa o Odoo decidir
          return Object.prototype.hasOwnProperty.call(m, field)
        },

        filterFields: (model, fields) => {
          const m = get().fields[model]
          if (!m) return fields
          return fields.filter((f) => Object.prototype.hasOwnProperty.call(m, f))
        },

        canRead: (model) => get().access[model]?.read ?? true,
        canWrite: (model) => get().access[model]?.write ?? true,
        canCreate: (model) => get().access[model]?.create ?? true,
        canUnlink: (model) => get().access[model]?.unlink ?? true,

        isLoaded: (model) =>
          Boolean(get().fields[model]) && Boolean(get().access[model]),
      }),
      {
        name: 'schema-store',
        version: 1,
      }
    ),
    { name: 'SchemaStore' }
  )
)
