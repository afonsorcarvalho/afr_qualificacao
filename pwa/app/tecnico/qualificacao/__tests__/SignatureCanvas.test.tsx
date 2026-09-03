// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
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
})
