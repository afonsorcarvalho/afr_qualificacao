'use client'
import { useEffect } from 'react'
import { useAuthStore } from '@/lib/store/authStore'
import { useHasGroup } from '@/lib/hooks/useHasGroup'
import { SURVEY_GROUP } from '@/lib/levantamento/constants'
import { startSurveySync } from '@/lib/levantamento/loop'
import { emitSyncTick } from '@/lib/levantamento/events'
import { push } from '@/lib/odoo/levantamento'

function Sync() {
  const temGrupo = useHasGroup(SURVEY_GROUP)
  useEffect(() => {
    if (!temGrupo) return
    // No iOS o IndexedDB pode ser despejado; a outbox é trabalho não enviado.
    try {
      navigator.storage?.persist?.()?.catch(() => {})
    } catch {
      /* noop */
    }
    const sync = startSurveySync({ push, onTick: () => emitSyncTick() })
    return () => sync.stop()
  }, [temGrupo])
  return null
}

/** Loop de sync do levantamento no nível do app: roda só autenticado e com o grupo. */
export function SurveySyncProvider() {
  const autenticado = useAuthStore((s) => s.isAuthenticated)
  return autenticado ? <Sync /> : null
}
