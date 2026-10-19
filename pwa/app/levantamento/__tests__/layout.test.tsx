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
import LevantamentoLayout from '../layout'

const ui = () =>
  render(
    <LevantamentoLayout>
      <div>conteudo-levantamento</div>
    </LevantamentoLayout>,
  )

beforeEach(() => useAuthStore.setState({ groups: {} }))

describe('LevantamentoLayout — controle de acesso', () => {
  it('grupo desconhecido: spinner, sem filhos nem mensagem', () => {
    ui()
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByText('conteudo-levantamento')).toBeNull()
    expect(screen.queryByText('Sem acesso ao Levantamento de campo')).toBeNull()
  })

  it('sem o grupo: mensagem bloqueante, link de volta e filhos não renderizados', () => {
    useAuthStore.setState({ groups: { [SURVEY_GROUP]: false } })
    ui()
    expect(screen.getByText('Sem acesso ao Levantamento de campo')).toBeInTheDocument()
    expect(screen.getByText(/Peça ao administrador para incluir você no grupo/)).toBeInTheDocument()
    expect(screen.getByRole('link')).toHaveAttribute('href', '/tecnico/qualificacao')
    expect(screen.queryByText('conteudo-levantamento')).toBeNull()
  })

  it('com o grupo: renderiza os filhos', () => {
    useAuthStore.setState({ groups: { [SURVEY_GROUP]: true } })
    ui()
    expect(screen.getByText('conteudo-levantamento')).toBeInTheDocument()
    expect(screen.queryByText('Sem acesso ao Levantamento de campo')).toBeNull()
  })
})
