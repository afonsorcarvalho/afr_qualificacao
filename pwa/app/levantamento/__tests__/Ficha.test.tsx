// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'

let params: Record<string, string> = { clienteId: '7', eqId: '10' }
const replace = vi.fn()
vi.mock('next/navigation', () => ({
  useParams: () => params,
  useRouter: () => ({ push: vi.fn(), replace }),
  usePathname: () => '/levantamento/7/10',
}))

const saveEquipment = vi.fn()
const saveCycle = vi.fn()
const deleteCycle = vi.fn()
const addPhoto = vi.fn()
const deletePhoto = vi.fn()
vi.mock('@/lib/levantamento/repo', async () => {
  const actual = await vi.importActual<typeof import('@/lib/levantamento/repo')>('@/lib/levantamento/repo')
  return {
    ...actual,
    saveEquipment: (...a: unknown[]) => saveEquipment(...a),
    saveCycle: (...a: unknown[]) => saveCycle(...a),
    deleteCycle: (...a: unknown[]) => deleteCycle(...a),
    addPhoto: (...a: unknown[]) => addPhoto(...a),
    deletePhoto: (...a: unknown[]) => deletePhoto(...a),
    refreshCatalog: vi.fn().mockResolvedValue({}),
  }
})
vi.mock('@/app/tecnico/qualificacao/_components/CameraInput', () => ({
  CameraInput: ({ onCapture }: { onCapture: (d: { base64: string; filename: string; mimetype: string }) => void }) => (
    <button type="button" onClick={() => onCapture({ base64: 'QUJD', filename: 'f.jpg', mimetype: 'image/jpeg' })}>
      camera
    </button>
  ),
}))
vi.mock('@/app/tecnico/qualificacao/_components/MicButton', () => ({
  MicButton: () => <button type="button">mic</button>,
}))

import { db } from '@/lib/levantamento/db'
import { emitSyncTick } from '@/lib/levantamento/events'
import FichaPage from '../[clienteId]/[eqId]/page'

const setOnline = (v: boolean) => Object.defineProperty(navigator, 'onLine', { value: v, configurable: true })

beforeEach(async () => {
  vi.clearAllMocks()
  params = { clienteId: '7', eqId: '10' }
  setOnline(true)
  await Promise.all(db.tables.map((t) => t.clear()))
  await db.partners.put({ key: '7', id: 7, name: 'Hospital Alfa', sync: 'ok' })
  await db.catalog.bulkPut([
    { name: 'categories', items: [{ id: 1, name: 'Autoclave' }] },
    { name: 'marcas', items: [{ id: 2, name: 'Baumer' }] },
    { name: 'cycle_types', items: [{ id: 5, name: 'Tecidos' }] },
    {
      name: 'selections',
      items: {
        thermocouple_access: [['porta_validacao', 'Porta de validação']],
        load_type: [['vazia', 'Câmara vazia']],
        survey_kind: [['plaqueta', 'Plaqueta'], ['termopar', 'Termopar'], ['geral', 'Geral'], ['ciclo', 'Tela do ciclo']],
      },
    },
  ])
  await db.equipments.put({
    key: '10', id: 10, partnerKey: '7', sync: 'ok', category_id: 1, marca_id: 2, model: 'X1', serial_number: '',
  })
  saveEquipment.mockImplementation(async (key: string | null) => key ?? 'tmp:new')
  saveCycle.mockImplementation(async (key: string | null) => key ?? 'tmp:cyc')
  addPhoto.mockResolvedValue('tmp:ph')
})

describe('FichaPage', () => {
  it('edita serie: um save com só o campo, após debounce', async () => {
    render(<FichaPage />)
    const input = await screen.findByLabelText('Número de série')
    fireEvent.change(input, { target: { value: 'ABC' } })
    expect(saveEquipment).not.toHaveBeenCalled()
    await waitFor(() => expect(saveEquipment).toHaveBeenCalledTimes(1), { timeout: 2000 })
    expect(saveEquipment).toHaveBeenCalledWith('10', '7', { serial_number: 'ABC' })
  })

  it('camera da seção Termopar chama addPhoto com kind termopar', async () => {
    render(<FichaPage />)
    const sec = (await screen.findByRole('region', { name: 'Termopar' })) as HTMLElement
    fireEvent.click(within(sec).getByRole('button', { name: 'camera' }))
    await waitFor(() => expect(addPhoto).toHaveBeenCalledTimes(1))
    expect(addPhoto).toHaveBeenCalledWith('10', 'termopar', expect.any(Blob))
  })

  it('+ ciclo cria e a edição chama saveCycle; foto do ciclo passa cycleKey e kind ciclo', async () => {
    render(<FichaPage />)
    fireEvent.click(await screen.findByRole('button', { name: '+ ciclo' }))
    await waitFor(() => expect(saveCycle).toHaveBeenCalledWith(null, '10', {}))
    // o mock não grava no banco; simula o que o repo faria
    await db.cycles.put({ key: 'tmp:cyc', equipmentKey: '10', sync: 'pendente' })
    await act(async () => emitSyncTick())
    const temp = await screen.findByLabelText('Temperatura')
    fireEvent.change(temp, { target: { value: '134' } })
    await waitFor(() => expect(saveCycle).toHaveBeenCalledWith('tmp:cyc', '10', { temperature: '134' }), { timeout: 2000 })
    const ciclo = screen.getByRole('group', { name: 'Ciclo 1' })
    fireEvent.click(within(ciclo).getByRole('button', { name: 'camera' }))
    await waitFor(() => expect(addPhoto).toHaveBeenCalledWith('10', 'ciclo', expect.any(Blob), 'tmp:cyc'))
  })

  it('mic escondido offline, visível online', async () => {
    const { unmount } = render(<FichaPage />)
    expect(await screen.findByRole('button', { name: 'mic' })).toBeInTheDocument()
    unmount()
    setOnline(false)
    render(<FichaPage />)
    await screen.findByLabelText('Número de série')
    expect(screen.queryByRole('button', { name: 'mic' })).toBeNull()
  })

  it('novo: avisa campos faltantes; duas edições rápidas criam um só equipamento e trocam a URL', async () => {
    params = { clienteId: '7', eqId: 'novo' }
    render(<FichaPage />)
    expect(await screen.findByText('Preencha categoria, marca e modelo para enviar')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Modelo'), { target: { value: 'M1' } })
    fireEvent.change(screen.getByLabelText('Número de série'), { target: { value: 'S1' } })
    await waitFor(() => expect(saveEquipment).toHaveBeenCalledTimes(2), { timeout: 2000 })
    const keys = saveEquipment.mock.calls.map((c) => c[0])
    expect(keys).toEqual([null, 'tmp:new'])
    expect(replace).toHaveBeenCalledTimes(1)
    expect(replace).toHaveBeenCalledWith('/levantamento/7/tmp%3Anew')
    expect(screen.getByText('Preencha categoria e marca para enviar')).toBeInTheDocument()
  })

  it('tmp reescrito para id real: redireciona para a chave real', async () => {
    params = { clienteId: '7', eqId: 'tmp%3Aold' }
    await db.idmap.put({ tmp: 'tmp:old', id: 10 })
    render(<FichaPage />)
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/levantamento/7/10'))
    expect(await screen.findByLabelText('Modelo')).toHaveValue('X1')
  })

  it('badge de erro mostra syncError ao tocar', async () => {
    await db.equipments.update('10', { sync: 'erro', syncError: 'Falhou feio' })
    render(<FichaPage />)
    fireEvent.click(await screen.findByRole('button', { name: /erro de envio/i }))
    expect(screen.getByText('Falhou feio')).toBeInTheDocument()
  })
})
