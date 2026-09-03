'use client'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Camera, RefreshCcw } from 'lucide-react'
import toast from 'react-hot-toast'

const MAX_BYTES = 5 * 1024 * 1024  // 5MB
const RETRY_QUALITY = 0.7
const MAX_DIMENSION = 1600
const JPEG_QUALITY = 0.85

function base64ByteLength(base64: string): number {
  // base64 encoding: 4 chars = 3 bytes, ignorando padding
  return Math.floor((base64.length * 3) / 4)
}

export function CameraInput({
  onCapture,
}: {
  onCapture: (data: { base64: string; filename: string; mimetype: string }) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<string | null>(null)

  const handleFile = (file: File) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        const ratio = Math.min(MAX_DIMENSION / img.width, MAX_DIMENSION / img.height, 1)
        canvas.width = img.width * ratio
        canvas.height = img.height * ratio
        const ctx = canvas.getContext('2d')!
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

        // Primeira compressão com quality 0.85
        let dataUrl = canvas.toDataURL('image/jpeg', JPEG_QUALITY)
        let base64 = dataUrl.replace(/^data:image\/jpeg;base64,/, '')
        let byteLen = base64ByteLength(base64)

        // Se ainda grande, retry com quality menor
        if (byteLen > MAX_BYTES) {
          dataUrl = canvas.toDataURL('image/jpeg', RETRY_QUALITY)
          base64 = dataUrl.replace(/^data:image\/jpeg;base64,/, '')
          byteLen = base64ByteLength(base64)
          toast('Imagem recomprimida pra reduzir tamanho')
        }

        // Ainda grande → bloqueia upload
        if (byteLen > MAX_BYTES) {
          const mb = (byteLen / 1024 / 1024).toFixed(1)
          toast.error(
            `Imagem muito grande (${mb}MB). Tente foto com menor resolução.`
          )
          return  // NÃO chama onCapture
        }

        const timestamp = Date.now()
        onCapture({
          base64,
          filename: `coleta_${timestamp}.jpg`,
          mimetype: 'image/jpeg',
        })
        setPreview(dataUrl)
      }
      img.src = e.target?.result as string
    }
    reader.readAsDataURL(file)
  }

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
        }}
      />
      {preview ? (
        <div className="space-y-2">
          <img src={preview} alt="Coleta" className="w-full rounded border" />
          <Button
            variant="outline"
            type="button"
            onClick={() => {
              setPreview(null)
              inputRef.current?.click()
            }}
            className="w-full"
          >
            <RefreshCcw className="mr-2 h-4 w-4" /> Trocar foto
          </Button>
        </div>
      ) : (
        <Button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="h-24 w-full"
          variant="outline"
        >
          <Camera className="mr-2 h-6 w-6" /> Tocar pra abrir câmera
        </Button>
      )}
    </div>
  )
}
