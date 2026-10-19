// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'


import { db } from '@/lib/levantamento/db'
import { emitSyncTick } from '@/lib/levantamento/events'
import { ClienteView } from '../_components/ClienteView'

const EquipListPage = () => <ClienteView id="7" />

const blob = () => new Blob(['x'], { type: 'image/jpeg' })

beforeEach(async () => {
  await Promise.all(db.tables.map((t) => t.clear()))
  await db.partners.put({ key: '7', id: 7, name: 'Hospital Alfa', sync: 'ok' })
  await db.catalog.bulkPut([
    { name: 'categories', items: [{ id: 1, name: 'Autoclave' }] },
    { name: 'marcas', items: [{ id: 2, name: 'Baumer' }] },
  ])
})

describe('EquipListPage', () => {
  it('mostra cards com badges de pendência', async () => {
    await db.equipments.bulkPut([
      { key: '10', id: 10, partnerKey: '7', sync: 'ok', apelido: 'Autoclave 1', category_id: 1, marca_id: 2, model: 'X1', serial_number: 'S1' },
      { key: '11', id: 11, partnerKey: '7', sync: 'ok', apelido: 'Autoclave 2', category_id: 1, marca_id: 2, model: 'X2' },
      { key: '12', id: 12, partnerKey: '99', sync: 'ok', apelido: 'De outro cliente' },
    ])
    await db.photos.put({ key: 'p1', equipmentKey: '10', survey_kind: 'plaqueta', blob: blob(), sync: 'ok' })
    await db.cycles.put({ key: 'c1', equipmentKey: '10', sync: 'ok' })
    render(<EquipListPage />)
    expect(await screen.findByText('Autoclave 1')).toBeInTheDocument()
    expect(screen.getByText('Autoclave 2')).toBeInTheDocument()
    expect(screen.queryByText('De outro cliente')).toBeNull()
    // Eq 10 tem plaqueta e ciclo; só o 11 tem as duas pendências.
    expect(screen.getAllByText('sem foto plaqueta')).toHaveLength(1)
    expect(screen.getAllByText('sem ciclos')).toHaveLength(1)
    expect(screen.getByText(/Baumer · X1 · S1/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /\+ Equipamento/ })).toHaveAttribute('href', '/app/cliente?id=7&eq=novo')
  })

  it('badge de erro vermelho mostra o syncError ao tocar', async () => {
    await db.equipments.put({ key: '10', id: 10, partnerKey: '7', sync: 'erro', syncError: 'Série duplicada', apelido: 'Eq' })
    render(<EquipListPage />)
    const badge = await screen.findByRole('button', { name: /erro de envio/i })
    expect(screen.queryByText('Série duplicada')).toBeNull()
    fireEvent.click(badge)
    expect(screen.getByText('Série duplicada')).toBeInTheDocument()
  })

  it('recarrega no sync tick', async () => {
    render(<EquipListPage />)
    await screen.findByText(/Nenhum equipamento/)
    await db.equipments.put({ key: '10', id: 10, partnerKey: '7', sync: 'ok', apelido: 'Novo aqui' })
    await act(async () => emitSyncTick())
    expect(await screen.findByText('Novo aqui')).toBeInTheDocument()
  })
})
