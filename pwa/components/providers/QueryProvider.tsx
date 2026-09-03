'use client'

import { QueryClient } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister'
import { useState } from 'react'

const PERSIST_BUSTER = 'v1'
const MAX_AGE_MS = 24 * 60 * 60 * 1000

const STATIC_KEYS = new Set<string>([
  'equipments',
  'cycle-types',
  'cycle-features',
  'ib-lotes',
  'materials-catalog',
  'employees',
  'departments',
  'os-equipments',
  'os-partners',
])

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  )

  const [persister] = useState(() => {
    if (typeof window === 'undefined') return null
    return createSyncStoragePersister({
      storage: window.localStorage,
      key: 'rq-cache',
      throttleTime: 1500,
    })
  })

  if (!persister) {
    return <>{children}</>
  }

  return (
    <PersistQueryClientProvider
      client={client}
      persistOptions={{
        persister,
        maxAge: MAX_AGE_MS,
        buster: PERSIST_BUSTER,
        dehydrateOptions: {
          shouldDehydrateQuery: (query) => {
            if (query.state.status !== 'success') return false
            const first = query.queryKey[0]
            return typeof first === 'string' && STATIC_KEYS.has(first)
          },
        },
      }}
    >
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </PersistQueryClientProvider>
  )
}
