'use client'
import { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { useAuthStore } from '@/lib/store/authStore'
import { useHasGroup } from '@/lib/hooks/useHasGroup'
import { SURVEY_GROUP } from '@/lib/levantamento/constants'
import { openSurveyDb, sessionKeyOf } from '@/lib/levantamento/db'
import { startSurveySync } from '@/lib/levantamento/loop'
import { emitSyncTick, onSyncRequest } from '@/lib/levantamento/events'
import { push } from '@/lib/odoo/levantamento'

function Sync({ sessionKey }: { sessionKey: string }) {
  const temGrupo = useHasGroup(SURVEY_GROUP)
  useEffect(() => {
    if (!temGrupo) return
    // No iOS o IndexedDB pode ser despejado; a outbox é trabalho não enviado.
    try {
      navigator.storage?.persist?.()?.catch(() => {})
    } catch {
      /* noop */
    }
    // Um loop por sessão (servidor/base/uid): trocar de usuário reinicia no banco dele.
    const sync = startSurveySync({ push, db: openSurveyDb(sessionKey), onTick: () => emitSyncTick() })
    const off = onSyncRequest(() => sync.kick())
    return () => {
      off()
      sync.stop()
    }
  }, [temGrupo, sessionKey])
  return null
}

/** Loop de sync do levantamento no nível do app: roda só autenticado, com o grupo e fora do /login. */
export function SurveySyncProvider() {
  const pathname = usePathname()
  const autenticado = useAuthStore((s) => s.isAuthenticated)
  const serverUrl = useAuthStore((s) => s.serverUrl)
  const dbName = useAuthStore((s) => s.dbName)
  const userId = useAuthStore((s) => s.userId)
  // Na tela de login o `isAuthenticated` persistido pode estar velho.
  if (!autenticado || pathname?.startsWith('/login')) return null
  return <Sync sessionKey={sessionKeyOf({ serverUrl, dbName, userId })} />
}
