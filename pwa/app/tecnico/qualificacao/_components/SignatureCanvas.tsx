'use client'
import { useEffect, useRef, useState } from 'react'
import SignatureCanvas from 'react-signature-canvas'
import { Button } from '@/components/ui/button'
import { Eraser } from 'lucide-react'

const HEIGHT = 160

export function SignaturePad({
  onChange,
}: {
  onChange: (base64: string | null) => void
}) {
  const ref = useRef<SignatureCanvas>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState<number>(320)

  useEffect(() => {
    if (!wrapRef.current) return
    const el = wrapRef.current
    const measure = () => {
      const w = Math.floor(el.clientWidth)
      if (w > 0) setWidth(w)
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const handleEnd = () => {
    if (!ref.current || ref.current.isEmpty()) {
      onChange(null)
      return
    }
    const dataUrl = ref.current.toDataURL('image/png')
    const base64 = dataUrl.replace(/^data:image\/png;base64,/, '')
    onChange(base64)
  }

  const handleClear = () => {
    ref.current?.clear()
    onChange(null)
  }

  return (
    <div className="space-y-2">
      <div ref={wrapRef} className="overflow-hidden rounded border bg-white" style={{ height: HEIGHT }}>
        <SignatureCanvas
          key={`sig-${width}`}
          ref={ref}
          penColor="black"
          canvasProps={{
            width,
            height: HEIGHT,
            style: { display: 'block', width: `${width}px`, height: `${HEIGHT}px`, touchAction: 'none' },
          }}
          onEnd={handleEnd}
        />
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={handleClear}
        className="w-full"
      >
        <Eraser className="mr-2 h-4 w-4" /> Limpar
      </Button>
    </div>
  )
}
