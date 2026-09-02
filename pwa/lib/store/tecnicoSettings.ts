'use client'

/**
 * F7.0 — Settings persistentes do PWA Técnico (toggle "Só minhas" + cache user id).
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface TecnicoSettings {
  filterMine: boolean
  lastUserId: number | null
  setFilterMine: (v: boolean) => void
  setLastUserId: (id: number | null) => void
}

export const useTecnicoSettings = create<TecnicoSettings>()(
  persist(
    (set) => ({
      filterMine: true,
      lastUserId: null,
      setFilterMine: (filterMine) => set({ filterMine }),
      setLastUserId: (lastUserId) => set({ lastUserId }),
    }),
    { name: 'tecnico-settings' },
  ),
)
