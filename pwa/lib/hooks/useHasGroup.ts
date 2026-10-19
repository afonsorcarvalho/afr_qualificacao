'use client'
import { useEffect } from 'react'
import { useAuthStore } from '@/lib/store/authStore'
import { hasGroup } from '@/lib/odoo/levantamento'

/**
 * Pertencimento a um grupo do Odoo. Devolve o valor em cache (persistido, vale
 * offline) e o atualiza uma vez por montagem; falha de rede mantém o cache.
 * `false` até a primeira resposta: a aba que depende disto só aparece depois.
 */
export function useHasGroup(xmlid: string): boolean {
  const cached = useAuthStore((s) => s.groups[xmlid] ?? false)
  const setGroup = useAuthStore((s) => s.setGroup)
  useEffect(() => {
    let vivo = true
    hasGroup(xmlid)
      .then((v) => vivo && setGroup(xmlid, v === true))
      .catch(() => {})
    return () => {
      vivo = false
    }
  }, [xmlid, setGroup])
  return cached
}
