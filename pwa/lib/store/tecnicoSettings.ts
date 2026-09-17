'use client'

/**
 * F7.0 — Settings persistentes do PWA Técnico (toggle "Só minhas" + cache user id).
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ModoAgenda = 'lista' | 'semana'

interface TecnicoSettings {
  filterMine: boolean
  lastUserId: number | null
  modoAgenda: ModoAgenda
  setFilterMine: (v: boolean) => void
  setLastUserId: (id: number | null) => void
  setModoAgenda: (m: ModoAgenda) => void
}

export const useTecnicoSettings = create<TecnicoSettings>()(
  persist(
    (set) => ({
      filterMine: true,
      lastUserId: null,
      modoAgenda: 'lista',
      setFilterMine: (filterMine) => set({ filterMine }),
      setLastUserId: (lastUserId) => set({ lastUserId }),
      setModoAgenda: (modoAgenda) => set({ modoAgenda }),
    }),
    { name: 'tecnico-settings' },
  ),
)
