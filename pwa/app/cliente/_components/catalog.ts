'use client'
import { useEffect, useState } from 'react'
import { loadCatalog, refreshCatalog } from '@/lib/levantamento/repo'

export interface CatItem {
  id: number
  name: string
}
export type Sel = [string, string][]
export interface Catalog {
  categories: CatItem[]
  marcas: CatItem[]
  cycle_types: CatItem[]
  /** Ausente em servidores antigos: o seletor de Local some. */
  locations: CatItem[]
  selections: { load_type: Sel; thermocouple_access: Sel; survey_kind: Sel }
}

const VAZIO: Catalog = {
  categories: [],
  marcas: [],
  cycle_types: [],
  locations: [],
  selections: { load_type: [], thermocouple_access: [], survey_kind: [] },
}

function norm(raw: Record<string, unknown>): Catalog {
  const sel = (raw.selections ?? {}) as Partial<Catalog['selections']>
  return {
    categories: (raw.categories as CatItem[]) ?? [],
    marcas: (raw.marcas as CatItem[]) ?? [],
    cycle_types: (raw.cycle_types as CatItem[]) ?? [],
    locations: (raw.locations as CatItem[]) ?? [],
    selections: {
      load_type: sel.load_type ?? [],
      thermocouple_access: sel.thermocouple_access ?? [],
      survey_kind: sel.survey_kind ?? [],
    },
  }
}

/** Catálogo local; se estiver vazio e houver sinal, tenta baixar uma vez. */
export function useCatalog(): Catalog {
  const [cat, setCat] = useState<Catalog>(VAZIO)
  useEffect(() => {
    let vivo = true
    void (async () => {
      const local = norm(await loadCatalog())
      if (!vivo) return
      setCat(local)
      if (!local.categories.length) {
        try {
          await refreshCatalog()
          const novo = norm(await loadCatalog())
          if (vivo) setCat(novo)
        } catch {
          /* offline: segue com o que há */
        }
      }
    })()
    return () => {
      vivo = false
    }
  }, [])
  return cat
}

export const nameOf = (items: CatItem[], id: unknown) =>
  typeof id === 'number' ? items.find((i) => i.id === id)?.name : undefined
export const labelOf = (sel: Sel, v: unknown) => sel.find(([k]) => k === v)?.[1]
