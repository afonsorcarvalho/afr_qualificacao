'use client'

/**
 * F7.0 — Settings persistentes do PWA Técnico (toggle "Só minhas" + cache user id).
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ModoAgenda = 'lista' | 'semana' | 'mes'

const MODOS_VALIDOS: ModoAgenda[] = ['lista', 'semana', 'mes']

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
    {
      name: 'tecnico-settings',
      // `modoAgenda` ganhou o valor `'mes'` nesta task. Um `localStorage`
      // gravado por uma versão anterior só conhece `'lista'`/`'semana'`, e
      // esses dois continuam válidos sem saneamento — o risco é o inverso:
      // storage editado à mão, ou um rollback de versão futura, deixando
      // vazar um valor desconhecido. Sem este `merge`, esse valor passaria
      // direto pro estado e nenhum `? :` da página bateria (a tela cairia
      // no ramo "nem lista, nem semana, nem mês" e ficaria em branco) — mais
      // seguro sanear pro default do que confiar cegamente no que veio do
      // storage.
      merge: (persistedState, currentState) => {
        const persisted = persistedState as Partial<TecnicoSettings> | undefined
        const modoAgenda = persisted?.modoAgenda && MODOS_VALIDOS.includes(persisted.modoAgenda)
          ? persisted.modoAgenda
          : currentState.modoAgenda
        return { ...currentState, ...persisted, modoAgenda }
      },
    },
  ),
)
