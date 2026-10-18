'use client'
import { useEffect, useState } from 'react'
import type { LocalEquipment } from '@/lib/levantamento/db'
import { nameOf, type Catalog } from './catalog'

export function tituloDoEquip(eq: LocalEquipment, cat: Catalog): string {
  const s = (v: unknown) => (typeof v === 'string' ? v.trim() : '')
  return (
    s(eq.apelido) ||
    s(eq.name) ||
    [nameOf(cat.categories, eq.category_id), s(eq.model)].filter(Boolean).join(' ') ||
    'Novo equipamento'
  )
}

export function detalheDoEquip(eq: LocalEquipment, cat: Catalog): string {
  const model = typeof eq.model === 'string' ? eq.model.trim() : ''
  const serie = typeof eq.serial_number === 'string' ? eq.serial_number.trim() : ''
  return [nameOf(cat.marcas, eq.marca_id), model, serie].filter(Boolean).join(' · ')
}

/** Object URLs para Blobs (alinhados por índice); `blobs` deve ser memoizado. Revogadas ao trocar/desmontar. */
export function useObjectUrls(blobs: (Blob | undefined)[]): (string | undefined)[] {
  const [urls, setUrls] = useState<(string | undefined)[]>([])
  useEffect(() => {
    const criadas: string[] = []
    const lista = blobs.map((b) => {
      if (!b || typeof URL.createObjectURL !== 'function') return undefined
      try {
        const u = URL.createObjectURL(b)
        criadas.push(u)
        return u
      } catch {
        return undefined // blob inválido/corrompido: cai no ícone
      }
    })
    setUrls(lista)
    return () => {
      for (const u of criadas) URL.revokeObjectURL?.(u)
    }
  }, [blobs])
  return urls
}
