// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const pullPartners = vi.fn()
const downloadPartner = vi.fn()
const createPartner = vi.fn()
const pendingCount = vi.fn()
vi.mock('@/lib/odoo/levantamento', () => ({
  pullPartners: (...a: unknown[]) => pullPartners(...a),
}))
vi.mock('@/lib/levantamento/repo', () => ({
  downloadPartner: (...a: unknown[]) => downloadPartner(...a),
  createPartner: (...a: unknown[]) => createPartner(...a),
  pendingCount: () => pendingCount(),
}))
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/levantamento',
}))

import { db } from '@/lib/levantamento/db'
import ClientesPage from '../page'

const VALID = '11.222.333/0001-81'

beforeEach(async () => {
  vi.clearAllMocks()
  await Promise.all(db.tables.map((t) => t.clear()))
  pendingCount.mockResolvedValue(0)
  pullPartners.mockRejectedValue(new Error('offline'))
  downloadPartner.mockResolvedValue(undefined)
  createPartner.mockResolvedValue('tmp:1')
})

const seed = () =>
  db.partners.bulkPut([
    { key: '7', id: 7, name: 'Hospital Alfa', vat: '11.222.333/0001-81', city: 'SP', sync: 'ok', offline: true },
    { key: '8', id: 8, name: 'Clinica Beta', vat: '44.555.666/0001-00', city: 'RJ', sync: 'ok', offline: true },
  ])

describe('ClientesPage', () => {
  it('lista clientes locais quando offline e filtra por nome', async () => {
    await seed()
    render(<ClientesPage />)
    expect(await screen.findByText('Hospital Alfa')).toBeInTheDocument()
    expect(screen.getByText('Clinica Beta')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'beta' } })
    await waitFor(() => expect(screen.queryByText('Hospital Alfa')).toBeNull())
    expect(screen.getByText('Clinica Beta')).toBeInTheDocument()
  })

  it('filtra por dígitos do CNPJ ignorando pontuação', async () => {
    await seed()
    render(<ClientesPage />)
    await screen.findByText('Hospital Alfa')
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '112223330001' } })
    await waitFor(() => expect(screen.queryByText('Clinica Beta')).toBeNull())
    expect(screen.getByText('Hospital Alfa')).toBeInTheDocument()
  })

  it('mostra indicador de baixado só para clientes no banco local e oferece baixar os demais', async () => {
    await db.partners.put({ key: '7', id: 7, name: 'Hospital Alfa', sync: 'ok', offline: true })
    pullPartners.mockResolvedValue({
      records: [
        { id: 7, name: 'Hospital Alfa', vat: false, city: false },
        { id: 9, name: 'Remoto Gama', vat: false, city: false },
      ],
      total: 2,
    })
    render(<ClientesPage />)
    expect(await screen.findByText('Remoto Gama')).toBeInTheDocument()
    expect(screen.getAllByText('Offline')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: /Baixar Remoto Gama para offline/ }))
    await waitFor(() => expect(downloadPartner).toHaveBeenCalledWith(9))
    expect(screen.queryByRole('button', { name: /Baixar Hospital Alfa/ })).toBeNull()
  })

  it('linha leva a /levantamento/[clienteKey]', async () => {
    await seed()
    render(<ClientesPage />)
    const link = (await screen.findByText('Hospital Alfa')).closest('a')
    expect(link).toHaveAttribute('href', '/levantamento/7')
  })

  it('banner mostra a contagem de pendências', async () => {
    pendingCount.mockResolvedValue(3)
    render(<ClientesPage />)
    expect(await screen.findByText('3 alterações aguardando sinal')).toBeInTheDocument()
  })

  it('sem pendências não mostra banner', async () => {
    render(<ClientesPage />)
    await waitFor(() => expect(pendingCount).toHaveBeenCalled())
    expect(screen.queryByText(/aguardando sinal/)).toBeNull()
  })

  it('novo cliente: CNPJ inválido bloqueia o envio', async () => {
    render(<ClientesPage />)
    fireEvent.click(screen.getByRole('button', { name: '+ Cliente novo' }))
    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Novo Ltda' } })
    fireEvent.change(screen.getByLabelText('CNPJ'), { target: { value: '11.222.333/0001-00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('CNPJ inválido')).toBeInTheDocument()
    expect(createPartner).not.toHaveBeenCalled()
  })

  it('novo cliente: CNPJ válido chama createPartner com a máscara aplicada', async () => {
    render(<ClientesPage />)
    fireEvent.click(screen.getByRole('button', { name: '+ Cliente novo' }))
    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Novo Ltda' } })
    fireEvent.change(screen.getByLabelText('CNPJ'), { target: { value: '11222333000181' } })
    expect(screen.getByLabelText('CNPJ')).toHaveValue(VALID)
    fireEvent.change(screen.getByLabelText('Cidade'), { target: { value: 'SP' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    await waitFor(() =>
      expect(createPartner).toHaveBeenCalledWith({ name: 'Novo Ltda', vat: VALID, city: 'SP' }),
    )
  })

  it('novo cliente exige nome', async () => {
    render(<ClientesPage />)
    fireEvent.click(screen.getByRole('button', { name: '+ Cliente novo' }))
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Informe o nome')).toBeInTheDocument()
    expect(createPartner).not.toHaveBeenCalled()
  })
})
