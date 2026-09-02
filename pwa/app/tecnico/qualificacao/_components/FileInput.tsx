'use client'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Upload, RefreshCcw, FileText, FileSpreadsheet, Database, File as FileIcon } from 'lucide-react'
import toast from 'react-hot-toast'

const MAX_BYTES = 20 * 1024 * 1024 // 20MB

const ACCEPT_BY_KIND: Record<string, string> = {
  pdf: 'application/pdf,.pdf',
  excel: '.xls,.xlsx,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  qualificador_data: '*/*',
  outro: '*/*',
}

const ICON_BY_KIND: Record<string, React.ComponentType<{ className?: string }>> = {
  pdf: FileText,
  excel: FileSpreadsheet,
  qualificador_data: Database,
  outro: FileIcon,
}

const LABEL_BY_KIND: Record<string, string> = {
  pdf: 'PDF',
  excel: 'Planilha (.xls/.xlsx)',
  qualificador_data: 'Arquivo do qualificador',
  outro: 'Arquivo',
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function FileInput({
  kind,
  onCapture,
}: {
  kind: string
  onCapture: (data: { base64: string; filename: string; mimetype: string }) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [picked, setPicked] = useState<{ filename: string; size: number; mimetype: string } | null>(null)

  const accept = ACCEPT_BY_KIND[kind] ?? '*/*'
  const Icon = ICON_BY_KIND[kind] ?? FileIcon
  const label = LABEL_BY_KIND[kind] ?? 'Arquivo'

  const handleFile = (file: File) => {
    if (file.size > MAX_BYTES) {
      toast.error(`Arquivo muito grande (${fmtSize(file.size)}). Máx ${fmtSize(MAX_BYTES)}.`)
      return
    }
    const reader = new FileReader()
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string
      const base64 = dataUrl.split(',', 2)[1] ?? ''
      const mimetype = file.type || 'application/octet-stream'
      onCapture({ base64, filename: file.name, mimetype })
      setPicked({ filename: file.name, size: file.size, mimetype })
    }
    reader.onerror = () => toast.error('Falha ao ler arquivo')
    reader.readAsDataURL(file)
  }

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
        }}
      />
      {picked ? (
        <div className="space-y-2">
          <div className="flex items-center gap-3 rounded-md border border-border/70 bg-muted/30 p-3">
            <Icon className="h-8 w-8 shrink-0 text-cyan-300" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">{picked.filename}</p>
              <p className="text-xs text-muted-foreground/90">{fmtSize(picked.size)}</p>
            </div>
          </div>
          <Button
            variant="outline"
            type="button"
            onClick={() => {
              setPicked(null)
              inputRef.current?.click()
            }}
            className="w-full"
          >
            <RefreshCcw className="mr-2 h-4 w-4" /> Trocar arquivo
          </Button>
        </div>
      ) : (
        <Button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="h-24 w-full"
          variant="outline"
        >
          <Upload className="mr-2 h-6 w-6" /> Selecionar {label}
        </Button>
      )}
    </div>
  )
}
