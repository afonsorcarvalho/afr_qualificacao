'use client'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { db } from '@/lib/levantamento/db'
import { downloadPartner } from '@/lib/levantamento/repo'
import { onlyDigits } from '@/lib/levantamento/cnpj'
import { pullPartners } from '@/lib/odoo/levantamento'
import { ClienteNovoSheet } from './_components/ClienteNovoSheet'
import { ClienteRow, type ClienteItem } from './_components/ClienteRow'
import { PendenciasBanner } from './_components/PendenciasBanner'

const norm = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

function combina(c: ClienteItem, q: string): boolean {
  const termo = norm(q.trim())
  if (!termo) return true
  if (norm(c.name).includes(termo)) return true
  const digitos = onlyDigits(q)
  return digitos.length > 0 && onlyDigits(c.vat ?? '').includes(digitos)
}

/**
 * Clientes do levantamento. Local primeiro (funciona sem sinal); quando há
 * sinal, junta os resultados do servidor para achar quem ainda não foi baixado.
 */
export default function ClientesPage() {
  const [q, setQ] = useState('')
  const [locais, setLocais] = useState<ClienteItem[]>([])
  const [remotos, setRemotos] = useState<ClienteItem[]>([])
  const [novoAberto, setNovoAberto] = useState(false)

  const recarregarLocais = useCallback(async () => {
    const rows = await db.partners.toArray()
    setLocais(
      rows.map((p) => ({
        key: p.key,
        id: p.id,
        name: p.name ?? '',
        vat: p.vat || undefined,
        city: typeof p.city === 'string' && p.city ? p.city : undefined,
        offline: p.offline === true,
        pendente: p.sync === 'pendente',
      })),
    )
  }, [])

  useEffect(() => {
    void recarregarLocais()
  }, [recarregarLocais])

  // Busca no servidor com debounce. Falha (offline) só deixa a lista local.
  useEffect(() => {
    let vivo = true
    const t = setTimeout(() => {
      pullPartners(q.trim())
        .then((r) => {
          if (!vivo) return
          setRemotos(
            r.records.map((p) => ({
              key: String(p.id),
              id: p.id,
              name: p.name,
              vat: p.vat || undefined,
              city: p.city || undefined,
              offline: false,
              pendente: false,
            })),
          )
        })
        .catch(() => vivo && setRemotos([]))
    }, 300)
    return () => {
      vivo = false
      clearTimeout(t)
    }
  }, [q])

  const lista = useMemo(() => {
    const porKey = new Map<string, ClienteItem>()
    for (const r of remotos) porKey.set(r.key, r)
    // O registro local manda: tem o estado offline/pendente.
    for (const l of locais) porKey.set(l.key, { ...porKey.get(l.key), ...l })
    return Array.from(porKey.values())
      .filter((c) => combina(c, q))
      .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'))
  }, [locais, remotos, q])

  const baixar = useCallback(
    async (c: ClienteItem) => {
      if (c.id === undefined) return
      await downloadPartner(c.id)
      await recarregarLocais()
    },
    [recarregarLocais],
  )

  return (
    <div className="mx-auto max-w-[720px]">
      <PendenciasBanner />
      <div className="mb-3 flex items-center gap-2">
        <input
          type="search"
          role="searchbox"
          aria-label="Buscar cliente por nome ou CNPJ"
          placeholder="Nome ou CNPJ"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="min-h-[44px] min-w-0 flex-1 rounded-md border border-input bg-background px-3 text-sm"
        />
        <Button className="min-h-[44px] shrink-0" onClick={() => setNovoAberto(true)}>
          + Cliente novo
        </Button>
      </div>
      {lista.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          Nenhum cliente encontrado. Sem sinal, só aparecem os clientes baixados.
        </p>
      ) : (
        <ul className="space-y-2">
          {lista.map((c) => (
            <ClienteRow key={c.key} cliente={c} onBaixar={baixar} />
          ))}
        </ul>
      )}
      <ClienteNovoSheet
        open={novoAberto}
        onClose={() => setNovoAberto(false)}
        onCreated={() => void recarregarLocais()}
      />
    </div>
  )
}
