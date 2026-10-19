// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/lib/odoo/levantamento', () => ({ hasGroup: () => new Promise(() => {}) }))
vi.mock('@/components/providers/NavProgress', () => ({
  NavProgressBar: () => null,
  NavProgressProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))
vi.mock('@/app/tecnico/qualificacao/_components/TecnicoNav', () => ({ TecnicoNav: () => null }))

import { useAuthStore } from '@/lib/store/authStore'
import { SURVEY_GROUP } from '@/lib/levantamento/constants'
import ClienteLayout from '../layout'

const ui = () =>
  render(
    <ClienteLayout>
      <div>conteudo-cliente</div>
    </ClienteLayout>,
  )

beforeEach(() => useAuthStore.setState({ groups: {} }))

describe('ClienteLayout', () => {
  it('sem o grupo: renderiza os filhos (modo leitura), sem bloqueio', () => {
    useAuthStore.setState({ groups: { [SURVEY_GROUP]: false } })
    ui()
    expect(screen.getByText('conteudo-cliente')).toBeInTheDocument()
    expect(screen.getByText('Somente leitura')).toBeInTheDocument()
    expect(screen.queryByText('Sem acesso ao Levantamento de campo')).toBeNull()
  })

  it('com o grupo: filhos sem selo de leitura', () => {
    useAuthStore.setState({ groups: { [SURVEY_GROUP]: true } })
    ui()
    expect(screen.getByText('conteudo-cliente')).toBeInTheDocument()
    expect(screen.queryByText('Somente leitura')).toBeNull()
  })
})
