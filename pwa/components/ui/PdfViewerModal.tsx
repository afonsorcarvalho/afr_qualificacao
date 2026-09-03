'use client'

import * as Dialog from '@radix-ui/react-dialog'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X, Download, Search, ChevronUp, ChevronDown, ChevronLeft, ChevronRight,
  ZoomIn, ZoomOut, Maximize2, MoveHorizontal, FileText, Loader2,
} from 'lucide-react'
import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/esm/Page/AnnotationLayer.css'
import 'react-pdf/dist/esm/Page/TextLayer.css'
import { clsx } from 'clsx'

// Worker servido localmente a partir de /public (copiado em scripts/postinstall ou manualmente).
// Evita problemas de MIME type / CORS que o CDN pode ter com arquivos .mjs.
if (typeof window !== 'undefined') {
  pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'
}

interface PdfViewerModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  file: Blob | string | null     // Blob, URL, ou null (carregando)
  title?: string
  filename?: string
  onDownload?: () => void
  isLoading?: boolean
}

interface PageMatch {
  pageNumber: number
  count: number
}

export function PdfViewerModal({
  open, onOpenChange, file, title, filename, onDownload, isLoading,
}: PdfViewerModalProps) {
  const [numPages, setNumPages] = useState(0)
  const [pageNumber, setPageNumber] = useState(1)
  const [scale, setScale] = useState(1.2)
  const [pageWidth, setPageWidth] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [pageInputValue, setPageInputValue] = useState('1')

  // Para busca global entre páginas
  const [pageTexts, setPageTexts] = useState<string[]>([]) // index 0 = page 1
  const [searchIndex, setSearchIndex] = useState(0)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const pageContainerRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  // Reset ao abrir/trocar arquivo
  useEffect(() => {
    if (open) {
      setPageNumber(1)
      setPageInputValue('1')
      setScale(1.2)
      setQuery('')
      setSearchIndex(0)
      setPageTexts([])
      setTimeout(() => searchInputRef.current?.focus(), 120)
    }
  }, [open, file])

  useEffect(() => {
    setPageInputValue(String(pageNumber))
  }, [pageNumber])

  const [blobUrl, setBlobUrl] = useState<string | null>(null)

  // Usa blob URL (mais estável para react-pdf do que File) e revoga ao desmontar
  useEffect(() => {
    if (!file) {
      setBlobUrl(null)
      return
    }
    if (typeof file === 'string') {
      setBlobUrl(file)
      return
    }
    const url = URL.createObjectURL(file)
    setBlobUrl(url)
    return () => { URL.revokeObjectURL(url) }
  }, [file])

  const memoFile = blobUrl

  const onDocumentLoadSuccess = ({ numPages: n }: { numPages: number }) => {
    setNumPages(n)
    setPageTexts(new Array(n).fill(''))
  }

  // Captura o texto de cada página ao renderizar para busca global
  const onPageTextReady = useCallback((pageIndex: number, text: string) => {
    setPageTexts((prev) => {
      if (prev[pageIndex] === text) return prev
      const next = [...prev]
      next[pageIndex] = text
      return next
    })
  }, [])

  // Lista de páginas que contêm o termo (busca feita conforme texto é carregado)
  const pageMatches: PageMatch[] = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    const res: PageMatch[] = []
    for (let i = 0; i < pageTexts.length; i++) {
      const text = (pageTexts[i] || '').toLowerCase()
      if (!text) continue
      let count = 0, idx = 0
      while ((idx = text.indexOf(q, idx)) !== -1) {
        count++
        idx += q.length
      }
      if (count > 0) res.push({ pageNumber: i + 1, count })
    }
    return res
  }, [query, pageTexts])

  const totalMatches = pageMatches.reduce((sum, m) => sum + m.count, 0)

  // Reset ao trocar query
  useEffect(() => {
    setSearchIndex(0)
  }, [query])

  // Pula para a página do match ativo
  useEffect(() => {
    if (pageMatches.length === 0) return
    const target = pageMatches[searchIndex % pageMatches.length]
    if (target && target.pageNumber !== pageNumber) {
      setPageNumber(target.pageNumber)
    }
  }, [searchIndex, pageMatches, pageNumber])

  const goNextMatch = useCallback(() => {
    if (pageMatches.length === 0) return
    setSearchIndex((i) => (i + 1) % pageMatches.length)
  }, [pageMatches.length])

  const goPrevMatch = useCallback(() => {
    if (pageMatches.length === 0) return
    setSearchIndex((i) => (i - 1 + pageMatches.length) % pageMatches.length)
  }, [pageMatches.length])

  const goToPage = (n: number) => {
    if (n < 1 || n > numPages) return
    setPageNumber(n)
  }

  const handlePageInput = (e: React.FormEvent) => {
    e.preventDefault()
    const n = parseInt(pageInputValue, 10)
    if (!isNaN(n)) goToPage(n)
  }

  const handleSearchKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (e.shiftKey) goPrevMatch()
      else goNextMatch()
    } else if (e.key === 'Escape') {
      setQuery('')
    }
  }

  // Highlight dos matches dentro da textLayer
  const textRenderer = useCallback(
    (textItem: { str: string; itemIndex: number }) => {
      if (!query.trim()) return textItem.str
      const escaped = textItem.str.replace(/[<>&"']/g, (ch) =>
        ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' }[ch]!)
      )
      const q = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const re = new RegExp(q, 'gi')
      return escaped.replace(re, (m) => `<mark class="pdf-highlight">${m}</mark>`)
    },
    [query]
  )

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/85 backdrop-blur-md z-50"
              />
            </Dialog.Overlay>

            <Dialog.Content asChild>
              <motion.div
                initial={{ opacity: 0, scale: 0.97, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97, y: 10 }}
                transition={{ type: 'spring', stiffness: 320, damping: 28 }}
                className="fixed inset-4 md:inset-6 z-50 flex flex-col rounded-2xl border border-white/10 bg-dark-900/95 backdrop-blur-2xl shadow-glass-lg overflow-hidden"
              >
                <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-neon-pink/40 to-transparent pointer-events-none" />

                {/* Header */}
                <div className="flex items-center gap-3 px-5 py-3 border-b border-white/10">
                  <div className="p-2 rounded-xl bg-neon-pink/10 border border-neon-pink/20 flex-shrink-0">
                    <FileText size={16} className="text-neon-pink" />
                  </div>
                  <div className="flex-1 min-w-0">
                    {title && (
                      <Dialog.Title className="text-sm font-semibold text-white truncate">
                        {title}
                      </Dialog.Title>
                    )}
                    {filename && (
                      <Dialog.Description className="text-[11px] text-white/40 font-mono truncate">
                        {filename}{numPages > 0 && ` · ${numPages} página${numPages !== 1 ? 's' : ''}`}
                      </Dialog.Description>
                    )}
                  </div>

                  {onDownload && (
                    <ToolBtn icon={<Download size={15} />} onClick={onDownload} title="Baixar PDF" />
                  )}
                  <Dialog.Close asChild>
                    <ToolBtn icon={<X size={15} />} title="Fechar (Esc)" danger />
                  </Dialog.Close>
                </div>

                {/* Toolbar */}
                <div className="flex flex-wrap items-center gap-2 px-5 py-2.5 border-b border-white/10 bg-white/[0.02]">
                  {/* Paginação */}
                  <div className="flex items-center gap-1">
                    <ToolBtn
                      icon={<ChevronLeft size={15} />}
                      onClick={() => goToPage(pageNumber - 1)}
                      disabled={pageNumber <= 1}
                      title="Página anterior"
                    />
                    <form onSubmit={handlePageInput} className="flex items-center gap-1 text-xs">
                      <input
                        type="text"
                        value={pageInputValue}
                        onChange={(e) => setPageInputValue(e.target.value)}
                        onBlur={handlePageInput}
                        className="w-12 px-2 py-1.5 rounded-lg text-center bg-white/[0.04] border border-white/10 text-white font-mono tabular-nums focus:outline-none focus:border-neon-blue/40"
                      />
                      <span className="text-white/40 font-mono">/ {numPages || '—'}</span>
                    </form>
                    <ToolBtn
                      icon={<ChevronRight size={15} />}
                      onClick={() => goToPage(pageNumber + 1)}
                      disabled={pageNumber >= numPages}
                      title="Próxima página"
                    />
                  </div>

                  <div className="w-px h-6 bg-white/10 mx-1" />

                  {/* Zoom */}
                  <div className="flex items-center gap-1">
                    <ToolBtn
                      icon={<ZoomOut size={15} />}
                      onClick={() => setScale((s) => Math.max(s - 0.2, 0.5))}
                      title="Diminuir zoom"
                    />
                    <button
                      onClick={() => setScale(1.2)}
                      className="px-2.5 py-1.5 rounded-lg text-xs font-mono bg-white/5 border border-white/10 text-white/70 hover:text-white hover:bg-white/10 transition-all min-w-[52px]"
                      title="Reset zoom"
                    >
                      {Math.round(scale * 100)}%
                    </button>
                    <ToolBtn
                      icon={<ZoomIn size={15} />}
                      onClick={() => setScale((s) => Math.min(s + 0.2, 3))}
                      title="Aumentar zoom"
                    />
                    <ToolBtn icon={<Maximize2 size={15} />} onClick={() => setScale(1.2)} title="Ajustar padrão" />
                    <ToolBtn
                      icon={<MoveHorizontal size={15} />}
                      onClick={() => {
                        const c = pageContainerRef.current
                        if (!c || !pageWidth) return
                        const available = c.clientWidth - 48 // p-6 = 24px cada lado
                        const s = Math.max(0.3, Math.min(4, available / pageWidth))
                        setScale(s)
                      }}
                      title="Ajustar à largura"
                    />
                  </div>

                  <div className="w-px h-6 bg-white/10 mx-1" />

                  {/* Busca */}
                  <div className="flex-1 flex items-center gap-2 min-w-[200px]">
                    <div className="flex-1 relative flex items-center">
                      <Search size={14} className="absolute left-3 text-white/40 pointer-events-none" />
                      <input
                        ref={searchInputRef}
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleSearchKey}
                        placeholder="Buscar no PDF..."
                        className="w-full pl-9 pr-4 py-1.5 rounded-lg text-sm bg-white/[0.04] border border-white/10 text-white placeholder-white/30 focus:outline-none focus:border-neon-blue/40 focus:bg-white/[0.08] transition-all"
                      />
                    </div>

                    {query && (
                      <>
                        <span className="text-xs font-mono text-white/50 tabular-nums whitespace-nowrap">
                          {pageMatches.length > 0
                            ? `pág. ${pageMatches[searchIndex % pageMatches.length].pageNumber} · ${totalMatches} ocorrência${totalMatches !== 1 ? 's' : ''}`
                            : '0 resultados'}
                        </span>
                        <ToolBtn
                          icon={<ChevronUp size={14} />}
                          onClick={goPrevMatch}
                          disabled={pageMatches.length === 0}
                          title="Anterior (Shift+Enter)"
                        />
                        <ToolBtn
                          icon={<ChevronDown size={14} />}
                          onClick={goNextMatch}
                          disabled={pageMatches.length === 0}
                          title="Próximo (Enter)"
                        />
                      </>
                    )}
                  </div>
                </div>

                {/* PDF area */}
                <div ref={pageContainerRef} className="flex-1 overflow-auto bg-black/60 p-6">
                  {isLoading || !memoFile ? (
                    <LoadingBlock />
                  ) : (
                    <div className="flex justify-center">
                      <Document
                        file={memoFile}
                        onLoadSuccess={onDocumentLoadSuccess}
                        onLoadError={(err) => console.error('PDF load error:', err)}
                        loading={<LoadingBlock />}
                        error={<ErrorBlock />}
                      >
                        {numPages > 0 && (
                          <div
                            ref={(el) => {
                              if (el) pageRefs.current.set(pageNumber, el)
                            }}
                            className={clsx(
                              'shadow-[0_0_60px_rgba(236,72,153,0.15)] rounded-lg overflow-hidden bg-white'
                            )}
                          >
                            <Page
                              pageNumber={pageNumber}
                              scale={scale}
                              onLoadSuccess={(p) => {
                                // Largura natural (sem escala) em pontos CSS
                                const w = (p as unknown as { width: number; originalWidth?: number }).originalWidth
                                  ?? (p as unknown as { width: number }).width / scale
                                if (w && w !== pageWidth) setPageWidth(w)
                              }}
                              customTextRenderer={textRenderer}
                              onGetTextSuccess={(textContent) => {
                                const items = (textContent as { items: Array<unknown> }).items
                                const joined = items
                                  .filter((i): i is { str: string } => typeof (i as { str?: unknown }).str === 'string')
                                  .map((i) => i.str)
                                  .join(' ')
                                onPageTextReady(pageNumber - 1, joined)
                              }}
                              renderAnnotationLayer={true}
                              renderTextLayer={true}
                            />
                          </div>
                        )}
                      </Document>
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="px-5 py-2 border-t border-white/5 text-center">
                  <span className="text-[10px] text-white/30 font-mono">
                    Setas ← → para páginas  ·  Enter/Shift+Enter navegar busca  ·  Esc fechar
                  </span>
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>

    </Dialog.Root>
  )
}

function ToolBtn({
  icon, onClick, title, disabled, danger,
}: { icon: React.ReactNode; onClick?: () => void; title: string; disabled?: boolean; danger?: boolean }) {
  return (
    <motion.button
      onClick={onClick}
      disabled={disabled}
      title={title}
      whileHover={disabled ? undefined : { scale: 1.05 }}
      whileTap={disabled ? undefined : { scale: 0.92 }}
      className={clsx(
        'p-2 rounded-lg border transition-all disabled:opacity-30 disabled:cursor-not-allowed',
        danger
          ? 'bg-neon-pink/5 border-neon-pink/20 text-neon-pink hover:bg-neon-pink/15'
          : 'bg-white/5 border-white/10 text-white/70 hover:text-white hover:bg-white/10'
      )}
    >
      {icon}
    </motion.button>
  )
}

function LoadingBlock() {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 text-white/40 py-20">
      <Loader2 size={24} className="animate-spin text-neon-pink" />
      <span className="text-sm">Carregando PDF...</span>
    </div>
  )
}

function ErrorBlock() {
  return (
    <div className="h-full flex items-center justify-center text-neon-pink py-20 text-sm">
      Erro ao renderizar o PDF
    </div>
  )
}
