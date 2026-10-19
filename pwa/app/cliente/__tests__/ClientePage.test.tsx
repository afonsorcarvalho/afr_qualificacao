// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import 'fake-indexeddb/auto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

const pullPartners = vi.fn()
const downloadPartner = vi.fn()
vi.mock('@/lib/odoo/levantamento', () => ({
  pullPartners: (...a: unknown[]) => pullPartners(...a),
  hasGroup: () => new Promise(() => {}),
}))
vi.mock('@/lib/levantamento/repo', async () => {
  const actual = await vi.importActual<typeof import('@/lib/levantamento/repo')>('@/lib/levantamento/repo')
  return {
    ...actual,
    downloadPartner: (...a: unknown[]) => downloadPartner(...a),
    refreshCatalog: vi.fn().mockResolvedValue({}),
  }
})
const routerPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: routerPush, replace: routerPush }),
  usePathname: () => '/cliente',
}))
vi.mock('@/app/tecnico/qualificacao/_components/CameraInput', () => ({
  CameraInput: () => <button type="button">camera</button>,
}))
vi.mock('@/app/tecnico/qualificacao/_components/MicButton', () => ({ MicButton: () => null }))

import { db } from '@/lib/levantamento/db'
import { useAuthStore } from '@/lib/store/authStore'
import { SURVEY_GROUP } from '@/lib/levantamento/constants'
import ClientePage from '../page'

const setOnline = (v: boolean) => Object.defineProperty(navigator, 'onLine', { value: v, configurable: true })
const irPara = (url: string) => window.history.replaceState(null, '', url)
const voltar = (url: string) =>
  act(() => {
    window.history.replaceState(null, '', url)
    window.dispatchEvent(new PopStateEvent('popstate'))
  })

beforeEach(async () => {
  vi.clearAllMocks()
  setOnline(false)
  irPara('/cliente')
  useAuthStore.setState({ groups: { [SURVEY_GROUP]: true } })
  pullPartners.mockRejectedValue(new Error('offline'))
  downloadPartner.mockRejectedValue(new Error('offline'))
  await Promise.all(db.tables.map((t) => t.clear()))
  await db.partners.bulkPut([
    { key: '7', id: 7, name: 'Hospital Alfa', sync: 'ok', offline: true },
    { key: '8', id: 8, name: 'Clinica Beta', sync: 'ok', offline: false },
  ])
  await db.equipments.put({ key: '10', id: 10, partnerKey: '7', sync: 'erro', syncError: 'falhou', apelido: 'Autoclave 1', model: 'X1' })
  await db.cycles.put({ key: '50', id: 50, equipmentKey: '10', sync: 'ok' })
  await db.photos.put({ key: '60', id: 60, equipmentKey: '10', survey_kind: 'plaqueta', blob: new Blob(['a']), sync: 'ok' })
})
afterEach(() => irPara('/cliente'))

describe('/cliente — navegação por history', () => {
  it('clique no cliente usa pushState (não o router), troca a tela; popstate volta', async () => {
    const push = vi.spyOn(window.history, 'pushState')
    render(<ClientePage />)
    fireEvent.click(await screen.findByText('Hospital Alfa'))
    expect(push).toHaveBeenCalledWith(null, '', '/cliente?id=7')
    expect(routerPush).not.toHaveBeenCalled()
    expect(await screen.findByText('Autoclave 1')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Autoclave 1'))
    expect(window.location.search).toBe('?id=7&eq=10')
    expect(await screen.findByDisplayValue('X1')).toBeInTheDocument()
    voltar('/cliente?id=7')
    expect(await screen.findByText('Autoclave 1')).toBeInTheDocument()
    expect(screen.queryByLabelText('Modelo')).toBeNull()
    voltar('/cliente')
    expect(await screen.findByText('Clinica Beta')).toBeInTheDocument()
    push.mockRestore()
  })

  it('"+ Equipamento" abre a ficha nova; o 1º save troca eq=novo pela chave tmp via replaceState', async () => {
    irPara('/cliente?id=7')
    const repl = vi.spyOn(window.history, 'replaceState')
    render(<ClientePage />)
    fireEvent.click(await screen.findByRole('link', { name: '+ Equipamento' }))
    expect(window.location.search).toBe('?id=7&eq=novo')
    fireEvent.change(await screen.findByLabelText('Modelo'), { target: { value: 'M1' } })
    await waitFor(() => expect(window.location.search).toMatch(/^\?id=7&eq=tmp%3A/), { timeout: 2000 })
    expect(repl).toHaveBeenCalledWith(null, '', expect.stringMatching(/^\/cliente\?id=7&eq=tmp%3A/))
    expect(screen.getByLabelText('Modelo')).toHaveValue('M1')
    repl.mockRestore()
  })

  it('deep link para chave desconhecida offline: "Registro não disponível offline"', async () => {
    irPara('/cliente?id=999')
    const { unmount } = render(<ClientePage />)
    expect(await screen.findByText('Registro não disponível offline')).toBeInTheDocument()
    unmount()
    irPara('/cliente?id=7&eq=tmp%3Anada')
    render(<ClientePage />)
    expect(await screen.findByText('Registro não disponível offline')).toBeInTheDocument()
  })
})

describe('/cliente — modo leitura (sem o grupo)', () => {
  beforeEach(() => useAuthStore.setState({ groups: { [SURVEY_GROUP]: false } }))

  it('lista: sem "+ Cliente novo", com "Baixar para offline"', async () => {
    render(<ClientePage />)
    await screen.findByText('Hospital Alfa')
    expect(screen.queryByRole('button', { name: '+ Cliente novo' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Baixar Clinica Beta para offline' })).toBeInTheDocument()
  })

  it('cliente: sem "+ Equipamento"; ficha: campos desabilitados, sem câmera/ciclo/excluir/Reenviar/Descartar', async () => {
    irPara('/cliente?id=7')
    render(<ClientePage />)
    await screen.findByText('Autoclave 1')
    expect(screen.queryByRole('link', { name: '+ Equipamento' })).toBeNull()
    fireEvent.click(screen.getByText('Autoclave 1'))
    expect(await screen.findByLabelText('Modelo')).toBeDisabled()
    await waitFor(() => expect(screen.getByLabelText('Categoria')).toBeDisabled())
    expect(await screen.findByLabelText('Tipo de ciclo')).toBeDisabled()
    expect(screen.queryByText('camera')).toBeNull()
    expect(screen.queryByRole('button', { name: '+ ciclo' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Excluir/ })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /^erro de envio$/ }))
    expect(screen.getByText('falhou')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reenviar' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Descartar' })).toBeNull()
  })
})
