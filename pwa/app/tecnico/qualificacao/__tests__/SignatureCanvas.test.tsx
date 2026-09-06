// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { render } from '@testing-library/react'

// Mock react-signature-canvas since happy-dom lacks full canvas 2D context
vi.mock('react-signature-canvas', () => {
  // vi.mock factories são hoisted pelo Vitest para antes dos imports do módulo,
  // então um `import React from 'react'` no topo do arquivo não estaria
  // disponível aqui dentro — require() é a única forma de obter o módulo
  // dentro da factory.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react')
  const MockSignatureCanvas = React.forwardRef(
    (_props: Record<string, unknown>, _ref: React.Ref<unknown>) => {
      return React.createElement('canvas', { 'data-testid': 'signature-canvas' })
    },
  )
  MockSignatureCanvas.displayName = 'SignatureCanvas'
  return { default: MockSignatureCanvas }
})

import { SignaturePad } from '../_components/SignatureCanvas'

describe('SignaturePad', () => {
  it('renderiza canvas e botão limpar', () => {
    const { container, getByText } = render(<SignaturePad onChange={() => {}} />)
    expect(container.querySelector('canvas')).toBeTruthy()
    expect(getByText(/Limpar/i)).toBeTruthy()
  })

  it('traço não usa literal de cor branca (assinatura branca sobre papel branco é invisível)', () => {
    // A área do pad é `bg-white` fixo de propósito (DESIGN.md "Signature
    // Pad": única superfície branca permitida no tema escuro, porque
    // assinatura é documento sobre papel). O risco é o TRAÇO: se algum dia
    // ele virar branco/`#fff` — por exemplo pra "combinar" com um tema
    // escuro — o traço some sobre o próprio papel branco do pad. `penColor`
    // é JS, não classe Tailwind: o teste-catraca não alcança este arquivo.
    const src = readFileSync(
      join(__dirname, '..', '_components', 'SignatureCanvas.tsx'),
      'utf8',
    )
    expect(src).not.toMatch(/penColor\s*=\s*["'](?:white|#fff|#ffffff)["']/i)
    expect(src).not.toMatch(/strokeStyle\s*=\s*["'](?:white|#fff|#ffffff)["']/i)
  })
})
