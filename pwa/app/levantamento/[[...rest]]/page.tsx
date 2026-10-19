'use client'
import { useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { LoadingState } from '@/components/ui/LoadingState'
import { levantamentoRedirect } from '@/lib/cliente/nav'

/** Rotas antigas `/levantamento[/<cliente>[/<equip>]]` -> `/cliente?id=&eq=`. */
export default function LevantamentoRedirect() {
  const params = useParams<{ rest?: string[] }>()
  const router = useRouter()
  const rest = params?.rest
  const destino = levantamentoRedirect(Array.isArray(rest) ? rest : rest ? [rest] : [])
  useEffect(() => {
    router.replace(destino)
  }, [router, destino])
  return <LoadingState label="Abrindo clientes..." />
}
