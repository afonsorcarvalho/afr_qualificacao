'use client'
import { useState } from 'react'
import Link from 'next/link'
import { FileText, FileSpreadsheet, Database, File as FileIcon, X, Download, Pencil, Clock, User as UserIcon } from 'lucide-react'
import { GlassCard } from '@/components/ui/GlassCard'
import { PdfViewerModal } from '@/components/ui/PdfViewerModal'
import { InstrumentBadges } from './InstrumentBadges'
import type { ColetaItemDetail, InstrumentInfo } from '@/lib/odoo/tecnico'

const NON_IMAGE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  excel: FileSpreadsheet,
  pdf: FileText,
  qualificador_data: Database,
  outro: FileIcon,
}

function fileUrl(itemId: number, kind: 'image' | 'content', download = false) {
  const base = `/api/odoo/web/${kind}/afr.qualificacao.collect.item/${itemId}/file`
  return download ? `${base}?download=true` : base
}

function detectFileType(item: ColetaItemDetail): 'image' | 'pdf' | 'other' {
  if (item.kind === 'foto') return 'image'
  if (item.kind === 'pdf') return 'pdf'
  const mt = (item.mimetype || '').toLowerCase()
  if (mt.startsWith('image/')) return 'image'
  if (mt === 'application/pdf') return 'pdf'
  const fn = (item.filename || '').toLowerCase()
  if (/\.(jpe?g|png|gif|webp|bmp|heic|heif)$/.test(fn)) return 'image'
  if (fn.endsWith('.pdf')) return 'pdf'
  return 'other'
}

function fmtCapturedAt(s: string): string {
  const d = new Date(s.includes('T') ? s : s.replace(' ', 'T') + 'Z')
  if (isNaN(d.getTime())) return s
  return d.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export function CollectedCard({
  osId,
  item,
  canEdit = true,
  instruments = {},
  selected = false,
}: {
  osId: number
  item: ColetaItemDetail
  canEdit?: boolean
  instruments?: Record<number, InstrumentInfo>
  /** Coleta aberta no painel direito, em desktop. O marcador fica no cartão
   *  (e não num link, como no `ColetaCard`) porque aqui o único link é
   *  "Recoletar", que some quando não há relatório aberto — e o deep link
   *  para a coleta continua valendo nesse caso. */
  selected?: boolean
}) {
  const [lightbox, setLightbox] = useState(false)
  const [pdfOpen, setPdfOpen] = useState(false)
  const hasFile = !!item.filename
  const fileType = detectFileType(item)
  const isFoto = fileType === 'image'
  const isPdf = fileType === 'pdf'
  const Icon = NON_IMAGE_ICONS[item.kind] ?? FileIcon

  return (
    <>
      <GlassCard
        variant={selected ? 'selected' : 'default'}
        noPadding
        className="p-3"
        aria-current={selected ? 'true' : undefined}
      >
        <div className="flex items-start gap-3">
          {hasFile && isFoto ? (
            <button
              type="button"
              onClick={() => setLightbox(true)}
              className="shrink-0 overflow-hidden rounded-md border border-border/70 transition hover:border-info/60"
            >
              {/* Tentado next/image aqui (56x56 fixo, URL real — parecia
                  candidato óbvio) e revertido: `fileUrl` é uma rota própria
                  que exige cookie de sessão pra falar com o Odoo, e o
                  otimizador embutido do next/image busca a imagem
                  server-to-server SEM repassar os cookies do navegador —
                  todo pedido volta 403 do proxy e a miniatura quebra
                  (confirmado em tela, /_next/image respondendo 400).
                  Verificado nesta sessão em 2026-09-06. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={fileUrl(item.id, 'image')}
                alt={item.name}
                className="h-14 w-14 object-cover"
              />
            </button>
          ) : (
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-md bg-muted/30 border border-border/70">
              <Icon className="h-6 w-6 text-muted-foreground" />
            </div>
          )}

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <strong className="truncate text-sm text-foreground">{item.name}</strong>
              {item.state === 'skipped' && (
                <span className="rounded bg-warn-surface px-1.5 py-0.5 text-[10px] text-warn">PULADO</span>
              )}
            </div>
            {item.filename && (
              <p className="mt-0.5 truncate text-xs text-muted-foreground">{item.filename}</p>
            )}

            {typeof item.description === 'string' && item.description.trim() && (
              <p className="mt-1 line-clamp-2 whitespace-pre-wrap rounded bg-muted/30 px-2 py-1 text-[11px] italic text-foreground/85">
                &ldquo;{item.description}&rdquo;
              </p>
            )}

            <InstrumentBadges item={item} instruments={instruments} />

            {(item.captured_at || item.captured_by) && (
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
                {item.captured_at && (
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" /> {fmtCapturedAt(item.captured_at)}
                  </span>
                )}
                {item.captured_by && (
                  <span className="inline-flex items-center gap-1">
                    <UserIcon className="h-3 w-3" /> {item.captured_by[1]}
                  </span>
                )}
              </div>
            )}

            <div className="mt-2 flex flex-wrap gap-2">
              {hasFile && isFoto && (
                <button
                  type="button"
                  onClick={() => setLightbox(true)}
                  className="text-xs text-info hover:underline"
                >
                  Ver foto
                </button>
              )}
              {hasFile && isPdf && (
                <button
                  type="button"
                  onClick={() => setPdfOpen(true)}
                  className="text-xs text-info hover:underline"
                >
                  Abrir PDF
                </button>
              )}
              {hasFile && fileType === 'other' && (
                <a
                  href={fileUrl(item.id, 'content', true)}
                  className="inline-flex items-center gap-1 text-xs text-info hover:underline"
                >
                  <Download className="h-3 w-3" /> Baixar
                </a>
              )}
              {canEdit && (
                <Link
                  href={`/tecnico/qualificacao/${osId}/coleta/${item.id}`}
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground/90"
                >
                  <Pencil className="h-3 w-3" /> Recoletar
                </Link>
              )}
            </div>
          </div>
        </div>
      </GlassCard>

      {isPdf && (
        <PdfViewerModal
          open={pdfOpen}
          onOpenChange={setPdfOpen}
          file={pdfOpen ? fileUrl(item.id, 'content') : null}
          title={item.name}
          filename={item.filename || undefined}
          onDownload={() => window.open(fileUrl(item.id, 'content', true), '_blank')}
        />
      )}

      {lightbox && hasFile && isFoto && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
          onClick={() => setLightbox(false)}
        >
          <button
            type="button"
            onClick={() => setLightbox(false)}
            className="absolute right-4 top-4 rounded-full bg-muted/60 p-2 text-foreground hover:bg-foreground/10"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
          {/* Mesma rota autenticada por cookie de `fileUrl` acima — o
              otimizador do next/image não repassa cookie no fetch
              server-to-server, então next/image nunca funcionaria aqui
              (ver nota na miniatura). Fora isso, a caixa do lightbox segue
              o aspect ratio natural da foto (max-h/max-w + object-contain),
              sem dimensão fixa pra declarar. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={fileUrl(item.id, 'image')}
            alt={item.name}
            className="max-h-[90vh] max-w-[95vw] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  )
}
