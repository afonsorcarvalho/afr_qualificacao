'use client'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { getDb } from '@/lib/levantamento/db'
import { downloadPartner, resolveKey } from '@/lib/levantamento/repo'
import { onSyncTick } from '@/lib/levantamento/events'
import { EquipCard, type EquipCardData } from './EquipCard'
import { PendenciasBanner } from './PendenciasBanner'
import { useCatalog } from './catalog'
import { tituloDoEquip, detalheDoEquip, useObjectUrls } from './equipInfo'
import { ClienteLink } from './ClienteLink'
import { EmptyOffline } from './EmptyOffline'
import { useCanEditCtx } from './canEdit'

/** Equipamentos do cliente (lista local; funciona sem sinal). */
export function ClienteView({ id: clienteParam }: { id: string }) {
  const podeEditar = useCanEditCtx()
  const cat = useCatalog()
  const [clienteNome, setClienteNome] = useState('')
  const [clienteKey, setClienteKey] = useState(clienteParam)
  const [itens, setItens] = useState<(EquipCardData & { capa?: Blob })[]>([])
  const [carregado, setCarregado] = useState(false)
  const [existe, setExiste] = useState(true)
  const tentouBaixar = useRef(false)

  const carregar = useCallback(async () => {
    const resolvida = await resolveKey(clienteParam)
    const chaves = Array.from(new Set([clienteParam, resolvida]))
    let partner = await getDb().partners.get(resolvida)
    // Deep link para cliente que não está no aparelho: com sinal, baixa uma vez.
    if (!partner && !tentouBaixar.current && /^\d+$/.test(resolvida) && navigator.onLine) {
      tentouBaixar.current = true
      try {
        await downloadPartner(Number(resolvida))
        partner = await getDb().partners.get(resolvida)
      } catch {
        // sem sinal de fato / sem acesso: cai no estado vazio
      }
    }
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
    setExiste(!!partner || eqs.length > 0)
    setItens(out)
    setCarregado(true)
  }, [clienteParam, cat])

  useEffect(() => {
    void carregar()
    return onSyncTick(() => void carregar())
  }, [carregar])

  const urls = useObjectUrls(useMemo(() => itens.map((i) => i.capa), [itens]))

  if (carregado && !existe) return <EmptyOffline volta={{}} voltaLabel="Voltar aos clientes" />

  return (
    <div className="mx-auto max-w-[720px]">
      <PendenciasBanner />
      <div className="mb-3 flex items-center justify-between gap-2">
        <ClienteLink to={{}} aria-label="Voltar aos clientes" className="flex h-11 w-11 shrink-0 items-center justify-center">
          <ArrowLeft className="h-5 w-5" aria-hidden />
        </ClienteLink>
        <h1 className="min-w-0 flex-1 truncate text-base font-semibold">{clienteNome || 'Cliente'}</h1>
        {podeEditar && (
          <ClienteLink
            to={{ id: clienteKey, eq: 'novo' }}
            className="inline-flex min-h-[44px] shrink-0 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
          >
            + Equipamento
          </ClienteLink>
        )}
      </div>
      {carregado && itens.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {podeEditar
            ? 'Nenhum equipamento neste cliente. Toque em + Equipamento para começar.'
            : 'Nenhum equipamento neste cliente.'}
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
