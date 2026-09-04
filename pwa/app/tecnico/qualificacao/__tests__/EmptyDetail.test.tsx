// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EmptyDetail } from '../_components/EmptyDetail'

describe('EmptyDetail', () => {
  it('convida a escolher uma coleta', () => {
    render(<EmptyDetail />)
    expect(screen.getByText('Escolha uma coleta')).toBeInTheDocument()
  })

  it('nasce visível — não depende de animação de entrada', () => {
    const { container } = render(<EmptyDetail />)
    const root = container.firstElementChild as HTMLElement
    expect(root.className).not.toContain('opacity-0')
  })
})
