'use client'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import { PendingLink } from '@/components/ui/PendingLink'
import { getDb } from '@/lib/levantamento/db'
import { resolveKey } from '@/lib/levantamento/repo'
import { onSyncTick } from '@/lib/levantamento/events'
import { EquipCard, type EquipCardData } from '../_components/EquipCard'
import { PendenciasBanner } from '../_components/PendenciasBanner'
import { useCatalog } from '../_components/catalog'
import { tituloDoEquip, detalheDoEquip, useObjectUrls } from '../_components/equipInfo'

/** Equipamentos do cliente (lista local; funciona sem sinal). */
export default function EquipamentosPage() {
  const params = useParams<{ clienteId: string }>()
  const clienteParam = decodeURIComponent(params.clienteId)
  const cat = useCatalog()
  const [clienteNome, setClienteNome] = useState('')
  const [clienteKey, setClienteKey] = useState(clienteParam)
  const [itens, setItens] = useState<(EquipCardData & { capa?: Blob })[]>([])
  const [carregado, setCarregado] = useState(false)

  const carregar = useCallback(async () => {
    const resolvida = await resolveKey(clienteParam)
    const chaves = Array.from(new Set([clienteParam, resolvida]))
    const partner = await getDb().partners.get(resolvida)
    const eqs = await getDb().equipments.where('partnerKey').anyOf(chaves).toArray()
    const out: (EquipCardData & { capa?: Blob })[] = []
    for (const eq of eqs) {
      const [cycles, photos] = await Promise.all([
        getDb().cycles.where('equipmentKey').equals(eq.key).count(),
        getDb().photos.where('equipmentKey').equals(eq.key).toArray(),
      ])
      const doEquip = photos.filter((p) => !p.cycleKey)
      const capa = doEquip.find((p) => p.survey_kind === 'geral') ?? doEquip[0]
      out.push({
        key: eq.key,
        titulo: tituloDoEquip(eq, cat),
        detalhe: detalheDoEquip(eq, cat),
        ciclos: cycles,
        semPlaqueta: !photos.some((p) => p.survey_kind === 'plaqueta'),
        sync: eq.sync,
        syncError: eq.syncError,
        capa: capa?.blob,
      })
    }
    out.sort((a, b) => a.titulo.localeCompare(b.titulo, 'pt-BR'))
    setClienteKey(resolvida)
    setClienteNome(partner?.name ?? '')
    setItens(out)
    setCarregado(true)
  }, [clienteParam, cat])

  useEffect(() => {
    void carregar()
    return onSyncTick(() => void carregar())
  }, [carregar])

  const urls = useObjectUrls(useMemo(() => itens.map((i) => i.capa), [itens]))

  return (
    <div className="mx-auto max-w-[720px]">
      <PendenciasBanner />
      <div className="mb-3 flex items-center justify-between gap-2">
        <h1 className="truncate text-base font-semibold">{clienteNome || 'Cliente'}</h1>
        <PendingLink
          href={`/levantamento/${encodeURIComponent(clienteKey)}/novo`}
          className="inline-flex min-h-[44px] shrink-0 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
        >
          + Equipamento
        </PendingLink>
      </div>
      {carregado && itens.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          Nenhum equipamento neste cliente. Toque em + Equipamento para começar.
        </p>
      ) : (
        <ul className="space-y-2">
          {itens.map((i, n) => (
            <EquipCard key={i.key} clienteKey={clienteKey} eq={{ ...i, capaUrl: urls[n] }} />
          ))}
        </ul>
      )}
    </div>
  )
}
