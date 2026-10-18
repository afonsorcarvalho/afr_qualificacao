/** Redimensiona (lado maior <= maxSide, sem ampliar) e recodifica em JPEG. */
export async function compressImage(file: Blob, maxSide = 1600, quality = 0.8): Promise<Blob> {
  const bmp = await createImageBitmap(file, { imageOrientation: 'from-image' } as ImageBitmapOptions)
  try {
    const scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height))
    const w = Math.max(1, Math.round(bmp.width * scale))
    const h = Math.max(1, Math.round(bmp.height * scale))
    if (typeof document !== 'undefined') {
      const canvas = document.createElement('canvas')
      canvas.width = w
      canvas.height = h
      const ctx = canvas.getContext('2d')
      if (!ctx) throw new Error('canvas 2d indisponível')
      ctx.drawImage(bmp, 0, 0, w, h)
      return await new Promise<Blob>((resolve, reject) =>
        canvas.toBlob(
          (b) => (b ? resolve(b) : reject(new Error('falha ao comprimir imagem'))),
          'image/jpeg',
          quality,
        ),
      )
    }
    const off = new OffscreenCanvas(w, h)
    const ctx = off.getContext('2d')
    if (!ctx) throw new Error('canvas 2d indisponível')
    ctx.drawImage(bmp, 0, 0, w, h)
    return await off.convertToBlob({ type: 'image/jpeg', quality })
  } finally {
    bmp.close?.()
  }
}

/** Base64 puro (sem prefixo `data:`), como `image_b64` do backend. */
export async function blobToBase64(b: Blob): Promise<string> {
  const bytes = new Uint8Array(await b.arrayBuffer())
  let bin = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    bin += String.fromCharCode.apply(null, Array.from(bytes.subarray(i, i + 0x8000)))
  }
  return btoa(bin)
}
