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

/**
 * Object URLs para Blobs (alinhadas por índice). `blobs` deve ser memoizado.
 * As URLs são criadas/revogadas em efeito; enquanto o efeito não rodou para o
 * `blobs` atual devolve [] (nunca URLs de outro conjunto -> sem miniatura trocada).
 */
export function useObjectUrls(blobs: (Blob | undefined)[]): (string | undefined)[] {
  const [estado, setEstado] = useState<{ para: (Blob | undefined)[]; urls: (string | undefined)[] }>({
    para: [],
    urls: [],
  })
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
    setEstado({ para: blobs, urls: lista })
    return () => {
      for (const u of criadas) URL.revokeObjectURL?.(u)
    }
  }, [blobs])
  return estado.para === blobs ? estado.urls : []
}
