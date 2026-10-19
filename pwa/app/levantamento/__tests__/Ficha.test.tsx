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
    expect(addPhoto).toHaveBeenCalledWith('10', 'termopar', expect.any(Blob), undefined, { precompressed: true })
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
    await waitFor(() => expect(addPhoto).toHaveBeenCalledWith('10', 'ciclo', expect.any(Blob), 'tmp:cyc', { precompressed: true }))
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

  it('picker Local aparece só quando o catálogo traz locations', async () => {
    const { unmount } = render(<FichaPage />)
    await screen.findByLabelText('Modelo')
    expect(screen.queryByLabelText('Local')).toBeNull()
    unmount()
    await db.catalog.put({ name: 'locations', items: [{ id: 9, name: 'CME' }] })
    render(<FichaPage />)
    const sel = await screen.findByLabelText('Local')
    fireEvent.change(sel, { target: { value: '9' } })
    await waitFor(() => expect(saveEquipment).toHaveBeenCalledWith('10', '7', { location_id: 9 }), { timeout: 2000 })
  })

  it('sair do novo antes de 500ms salva uma vez e não navega', async () => {
    params = { clienteId: '7', eqId: 'novo' }
    const { unmount } = render(<FichaPage />)
    fireEvent.change(await screen.findByLabelText('Modelo'), { target: { value: 'M1' } })
    unmount()
    await waitFor(() => expect(saveEquipment).toHaveBeenCalledTimes(1))
    await new Promise((r) => setTimeout(r, 50))
    expect(saveEquipment).toHaveBeenCalledWith(null, '7', { model: 'M1' })
    expect(replace).not.toHaveBeenCalled()
  })

  it('vários campos pendentes são enviados ao desmontar', async () => {
    const { unmount } = render(<FichaPage />)
    fireEvent.change(await screen.findByLabelText('Modelo'), { target: { value: 'M9' } })
    fireEvent.change(screen.getByLabelText('Número de série'), { target: { value: 'S9' } })
    unmount()
    await waitFor(() => expect(saveEquipment).toHaveBeenCalledTimes(2))
    const campos = saveEquipment.mock.calls.map((c) => Object.keys(c[2] as object)[0]).sort()
    expect(campos).toEqual(['model', 'serial_number'])
  })

  it('visibilitychange para hidden envia sem esperar o debounce', async () => {
    render(<FichaPage />)
    fireEvent.change(await screen.findByLabelText('Número de série'), { target: { value: 'V1' } })
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    await waitFor(() => expect(saveEquipment).toHaveBeenCalledWith('10', '7', { serial_number: 'V1' }), { timeout: 300 })
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  })

  it('falha de autosave aparece na tela', async () => {
    saveEquipment.mockRejectedValue(new Error('Servidor caiu'))
    render(<FichaPage />)
    fireEvent.change(await screen.findByLabelText('Número de série'), { target: { value: 'X' } })
    expect(await screen.findByRole('alert', {}, { timeout: 2000 })).toHaveTextContent('Servidor caiu')
  })

  it('falha de autosave de ciclo aparece no ciclo', async () => {
    await db.cycles.put({ key: '50', id: 50, equipmentKey: '10', sync: 'ok' })
    saveCycle.mockRejectedValue(new Error('Ciclo recusado'))
    render(<FichaPage />)
    fireEvent.change(await screen.findByLabelText('Temperatura'), { target: { value: '1' } })
    const ciclo = screen.getByRole('group', { name: 'Ciclo 1' })
    expect(await within(ciclo).findByRole('alert', {}, { timeout: 2000 })).toHaveTextContent('Ciclo recusado')
  })

  it('ciclo reescrito tmp -> id real não perde o texto digitado', async () => {
    await db.cycles.put({ key: 'tmp:c1', equipmentKey: '10', sync: 'pendente' })
    render(<FichaPage />)
    const antes = await screen.findByLabelText('Temperatura')
    fireEvent.change(antes, { target: { value: '134' } })
    await db.cycles.delete('tmp:c1')
    await db.cycles.put({ key: '77', id: 77, equipmentKey: '10', sync: 'ok' })
    await db.idmap.put({ tmp: 'tmp:c1', id: 77 })
    await act(async () => emitSyncTick())
    await waitFor(() => expect(screen.getByLabelText('Temperatura')).toHaveValue('134'))
    expect(screen.getByLabelText('Temperatura')).toBe(antes)
    await waitFor(() => expect(saveCycle).toHaveBeenCalledWith('77', '10', { temperature: '134' }), { timeout: 2000 })
  })

  it('novo: após o primeiro save a ficha continua renderizada mesmo sem o registro no banco', async () => {
    params = { clienteId: '7', eqId: 'novo' }
    const { rerender } = render(<FichaPage />)
    fireEvent.change(await screen.findByLabelText('Modelo'), { target: { value: 'M1' } })
    await waitFor(() => expect(replace).toHaveBeenCalled(), { timeout: 2000 })
    params = { clienteId: '7', eqId: 'tmp%3Anew' }
    rerender(<FichaPage />)
    await new Promise((r) => setTimeout(r, 50))
    expect(screen.queryByText(/não encontrado/)).toBeNull()
    expect(screen.getByLabelText('Modelo')).toBeInTheDocument()
  })

  it('revoga object URLs das miniaturas ao desmontar', async () => {
    const create = vi.fn(() => 'blob:abc')
    const revoke = vi.fn()
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke })
    await db.photos.put({ key: 'p1', equipmentKey: '10', survey_kind: 'termopar', blob: new Blob(['x']), sync: 'ok' })
    const { unmount } = render(<FichaPage />)
    await waitFor(() => expect(create).toHaveBeenCalled())
    unmount()
    expect(revoke).toHaveBeenCalledWith('blob:abc')
  })

  it('erro de autosave some depois de um save bem-sucedido (ficha e ciclo)', async () => {
    await db.cycles.put({ key: '50', id: 50, equipmentKey: '10', sync: 'ok' })
    saveEquipment.mockRejectedValueOnce(new Error('Servidor caiu'))
    saveCycle.mockRejectedValueOnce(new Error('Ciclo recusado'))
    render(<FichaPage />)
    fireEvent.change(await screen.findByLabelText('Temperatura'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Número de série'), { target: { value: 'X' } })
    await screen.findByText('Servidor caiu', {}, { timeout: 2000 })
    const ciclo = screen.getByRole('group', { name: 'Ciclo 1' })
    await within(ciclo).findByText('Ciclo recusado', {}, { timeout: 2000 })
    fireEvent.change(screen.getByLabelText('Número de série'), { target: { value: 'XY' } })
    fireEvent.change(screen.getByLabelText('Temperatura'), { target: { value: '12' } })
    await waitFor(() => expect(screen.queryByText('Servidor caiu')).toBeNull(), { timeout: 2000 })
    await waitFor(() => expect(within(ciclo).queryByText('Ciclo recusado')).toBeNull(), { timeout: 2000 })
  })

  it('ciclo e foto com erro de envio mostram selo; Reenviar devolve as ops à fila', async () => {
    await db.cycles.put({ key: '50', id: 50, equipmentKey: '10', sync: 'erro', syncError: 'Ciclo inválido' })
    await db.photos.put({
      key: '60', id: 60, equipmentKey: '10', survey_kind: 'plaqueta', blob: new Blob(['a']), sync: 'erro', syncError: 'Foto grande',
    })
    await db.outbox.add({
      op_uuid: 'u1', kind: 'cycle.upsert', ref: 50, payload: { temperature: 1 }, state: 'erro', attempts: 3, createdAt: 1, error: 'Ciclo inválido',
    })
    render(<FichaPage />)
    const ciclo = await screen.findByRole('group', { name: 'Ciclo 1' })
    fireEvent.click(within(ciclo).getByRole('button', { name: /erro de envio/ }))
    expect(within(ciclo).getByText('Ciclo inválido')).toBeInTheDocument()
    fireEvent.click(within(ciclo).getByRole('button', { name: 'Reenviar' }))
    await waitFor(async () => expect((await db.outbox.toArray())[0].state).toBe('pendente'))
    const [reenviada] = await db.outbox.toArray()
    expect(reenviada.attempts).toBe(0)
    expect(reenviada.op_uuid).not.toBe('u1') // uuid novo: o servidor guarda o erro por op_uuid
    await waitFor(async () => expect((await db.cycles.get('50'))!.sync).toBe('pendente'))

    const foto = await screen.findByRole('button', { name: /erro de envio da foto \(Plaqueta\)/ })
    fireEvent.click(foto)
    expect(screen.getByText('Foto grande')).toBeInTheDocument()
  })

  it('Descartar o equipamento com erro apaga local e volta para a lista', async () => {
    await db.equipments.update('10', { sync: 'erro', syncError: 'x' })
    await db.cycles.put({ key: '50', id: 50, equipmentKey: '10', sync: 'ok' })
    Object.defineProperty(window, 'confirm', { value: vi.fn(() => true), configurable: true, writable: true })
    render(<FichaPage />)
    fireEvent.click(await screen.findByRole('button', { name: /^erro de envio$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Descartar' }))
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/levantamento/7'))
    expect(await db.equipments.get('10')).toBeUndefined()
    expect(await db.cycles.get('50')).toBeUndefined()
  })
})
