'use client'

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import { useSchemaStore } from './schemaStore'

export interface AvailableCompany {
  id: number
  name: string
}

interface AuthState {
  serverUrl: string
  dbName: string
  userId: number | null
  userName: string
  isAuthenticated: boolean

  // Empresa do usuário — mantida após logout como "última empresa" até trocar de server/db
  companyId: number | null
  companyName: string
  companyLogo: string | null  // base64 sem prefixo

  // Seletor global de empresa
  availableCompanies: AvailableCompany[]
  selectedCompanyId: number | null  // null = todas as empresas

  // Histórico de servidores usados
  serverUrlHistory: string[]

  setServerUrl: (url: string) => void
  setDbName: (db: string) => void
  setUser: (id: number, name: string) => void
  setCompany: (id: number | null, name: string, logo: string | null) => void
  setAvailableCompanies: (companies: AvailableCompany[]) => void
  setSelectedCompany: (id: number | null) => void
  addServerUrlToHistory: (url: string) => void
  removeServerUrlFromHistory: (url: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  devtools(
    persist(
      (set, get) => ({
        serverUrl: '',
        dbName: '',
        userId: null,
        userName: '',
        isAuthenticated: false,
        companyId: null,
        companyName: '',
        companyLogo: null,
        availableCompanies: [],
        selectedCompanyId: null,
        serverUrlHistory: [],

        setServerUrl: (serverUrl) => {
          if (serverUrl !== get().serverUrl) {
            useSchemaStore.getState().clear()
            set({ companyId: null, companyName: '', companyLogo: null, availableCompanies: [], selectedCompanyId: null })
          }
          set({ serverUrl })
        },
        setDbName: (dbName) => {
          if (dbName !== get().dbName) {
            useSchemaStore.getState().clear()
            set({ companyId: null, companyName: '', companyLogo: null, availableCompanies: [], selectedCompanyId: null })
          }
          set({ dbName })
        },

        setUser: (userId, userName) =>
          set({ userId, userName, isAuthenticated: true }),

        setCompany: (companyId, companyName, companyLogo) =>
          set({ companyId, companyName, companyLogo }),

        setAvailableCompanies: (availableCompanies) =>
          set({ availableCompanies }),

        setSelectedCompany: (selectedCompanyId) =>
          set({ selectedCompanyId }),

        addServerUrlToHistory: (url) => {
          const prev = get().serverUrlHistory.filter((u) => u !== url)
          set({ serverUrlHistory: [url, ...prev].slice(0, 8) })
        },

        removeServerUrlFromHistory: (url) => {
          set({ serverUrlHistory: get().serverUrlHistory.filter((u) => u !== url) })
        },

        logout: () => {
          useSchemaStore.getState().clear()
          // Preserva serverUrl e dbName para o próximo login reabrir no mesmo
          // contexto (pré-preenchimento via URL ou último server/db usado).
          set({
            userId: null,
            userName: '',
            isAuthenticated: false,
            availableCompanies: [],
            selectedCompanyId: null,
          })
        },
      }),
      {
        name: 'auth-store',
        partialize: (s) => ({
          serverUrl: s.serverUrl,
          dbName: s.dbName,
          userId: s.userId,
          userName: s.userName,
          isAuthenticated: s.isAuthenticated,
          companyId: s.companyId,
          companyName: s.companyName,
          companyLogo: s.companyLogo,
          selectedCompanyId: s.selectedCompanyId,
          serverUrlHistory: s.serverUrlHistory,
        }),
      }
    ),
    { name: 'AuthStore' }
  )
)
