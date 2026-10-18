'use client'
import { useMemo, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { CameraInput } from '@/app/tecnico/qualificacao/_components/CameraInput'
import type { LocalPhoto } from '@/lib/levantamento/db'
import { useObjectUrls } from './equipInfo'

export interface FotoKind {
  kind: string
  label: string
}

function base64ToBlob(b64: string, type: string): Blob {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Blob([bytes], { type })
}

/**
 * Câmera por tipo (cada botão já define o `survey_kind`) + miniaturas com excluir.
 * Reaproveita `CameraInput`; depois de cada captura ele é remontado (key) para
 * ficar pronto para a próxima foto.
 */
export function FotoStrip({
  kinds,
  photos,
  onAdd,
  onDelete,
}: {
  kinds: FotoKind[]
  photos: LocalPhoto[]
  onAdd: (kind: string, blob: Blob) => Promise<void> | void
  onDelete: (key: string) => Promise<void> | void
}) {
  const [rodada, setRodada] = useState<Record<string, number>>({})
  // `photos` costuma chegar como array novo a cada render do pai; a assinatura
  // por chave mantém `mostradas` estável (senão as object URLs seriam
  // recriadas em loop).
  const assinatura = photos
    .filter((p) => kinds.some((k) => k.kind === p.survey_kind))
    .map((p) => p.key)
    .join('|')
  const photosRef = useRef(photos)
  photosRef.current = photos
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const mostradas = useMemo(() => photosRef.current.filter((p) => assinatura.split('|').includes(p.key)), [assinatura])
  const urls = useObjectUrls(useMemo(() => mostradas.map((p) => p.blob), [mostradas]))

  return (
    <div className="space-y-2">
      {kinds.map((k) => (
        <div key={k.kind}>
          <p className="mb-1 text-xs text-muted-foreground">Foto: {k.label}</p>
          <CameraInput
            key={`${k.kind}-${rodada[k.kind] ?? 0}`}
            onCapture={async ({ base64, mimetype }) => {
              await onAdd(k.kind, base64ToBlob(base64, mimetype))
              setRodada((r) => ({ ...r, [k.kind]: (r[k.kind] ?? 0) + 1 }))
            }}
          />
        </div>
      ))}
      {mostradas.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {mostradas.map((p, i) => (
            <li key={p.key} className="relative h-16 w-16 overflow-hidden rounded-md border border-border bg-muted">
              {urls[i] && (
                // Blob local: next/image não otimiza object URL.
                // eslint-disable-next-line @next/next/no-img-element
                <img src={urls[i]} alt={kinds.find((k) => k.kind === p.survey_kind)?.label ?? 'Foto'} className="h-full w-full object-cover" />
              )}
              <button
                type="button"
                aria-label="Excluir foto"
                onClick={() => void onDelete(p.key)}
                className="absolute right-0 top-0 flex h-6 w-6 items-center justify-center rounded-bl bg-background/80 text-danger"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
