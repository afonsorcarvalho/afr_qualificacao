'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister'
import { useEffect, useState } from 'react'

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

  // O ReactQueryDevtools injeta um `<div>` no body que o servidor nunca
  // renderizou. Isso quebrava a hidratação do documento inteiro em toda
  // navegação ("Expected server HTML to contain a matching <div> in <body>"
  // → "The server HTML was replaced with client content"), forçando um
  // re-render completo no cliente e enchendo o overlay de erro do Next —
  // erro fantasma que mascarava os de verdade. Só depois de montado.
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const [persister] = useState(() => {
    if (typeof window === 'undefined') return null
    return createSyncStoragePersister({
      storage: window.localStorage,
      key: 'rq-cache',
      throttleTime: 1500,
    })
  })

  // No SSR não há `localStorage`, então não há persister — mas o client ainda
  // precisa existir na árvore: sem ele, todo `useQuery`/`useQueryClient`
  // renderizado no servidor estoura "No QueryClient set" e o HTML do servidor
  // é descartado na hidratação.
  if (!persister) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
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
      {mounted && <ReactQueryDevtools initialIsOpen={false} />}
    </PersistQueryClientProvider>
  )
}
