// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import { CameraInput } from '../_components/CameraInput'

describe('CameraInput', () => {
  it('exibe input file com capture=environment', () => {
    const { container } = render(<CameraInput onCapture={() => {}} />)
    const input = container.querySelector('input[type=file]') as HTMLInputElement
    expect(input).toBeTruthy()
    expect(input.accept).toContain('image/*')
    expect(input.getAttribute('capture')).toBe('environment')
  })

  it('chama onCapture com base64 após resize ao receber arquivo', async () => {
    const onCapture = vi.fn()
    const { container } = render(<CameraInput onCapture={onCapture} />)
    const input = container.querySelector('input[type=file]') as HTMLInputElement
    const file = new File(['dummy'], 'test.jpg', { type: 'image/jpeg' })
    Object.defineProperty(HTMLCanvasElement.prototype, 'toDataURL', {
      value: () => 'data:image/jpeg;base64,XYZ',
    })
    fireEvent.change(input, { target: { files: [file] } })
    await new Promise((r) => setTimeout(r, 50))
    expect(input.files?.[0]).toBe(file)
  })
})
