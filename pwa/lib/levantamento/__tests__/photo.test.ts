import { afterEach, describe, expect, it, vi } from 'vitest'
import { blobToBase64, compressImage } from '../photo'

afterEach(() => vi.unstubAllGlobals())

describe('compressImage', () => {
  it('reduz 4000x3000 para lado maior 1600 (JPEG, qualidade 0.8)', async () => {
    const close = vi.fn()
    vi.stubGlobal('createImageBitmap', vi.fn(async () => ({ width: 4000, height: 3000, close })))
    const canvas: Record<string, unknown> = {
      getContext: () => ({ drawImage: vi.fn() }),
      toBlob: vi.fn((cb: (b: Blob) => void, type: string, q: number) => {
        canvas.args = [type, q]
        cb(new Blob(['jpg'], { type }))
      }),
    }
    vi.stubGlobal('document', { createElement: () => canvas })
    const out = await compressImage(new Blob(['raw']))
    expect(canvas.width).toBe(1600)
    expect(canvas.height).toBe(1200)
    expect(canvas.args).toEqual(['image/jpeg', 0.8])
    expect(out.type).toBe('image/jpeg')
    expect(close).toHaveBeenCalled()
  })
  it('não amplia imagem pequena', async () => {
    vi.stubGlobal('createImageBitmap', vi.fn(async () => ({ width: 800, height: 1000, close: vi.fn() })))
    const canvas: Record<string, unknown> = {
      getContext: () => ({ drawImage: vi.fn() }),
      toBlob: (cb: (b: Blob) => void, type: string) => cb(new Blob(['j'], { type })),
    }
    vi.stubGlobal('document', { createElement: () => canvas })
    await compressImage(new Blob(['raw']))
    expect([canvas.width, canvas.height]).toEqual([800, 1000])
  })
})

describe('blobToBase64', () => {
  it('codifica sem prefixo data:', async () => {
    expect(await blobToBase64(new Blob(['hello']))).toBe('aGVsbG8=')
  })
})
