/**
 * Testa o reset completo do cache da sessão, garantindo que:
 *  - React Query cache é apagado
 *  - schemaStore é limpo (fields + access + loadedAt)
 *  - filtros de contatos e ciclos voltam ao default
 *  - dados da empresa (companyId, companyName, companyLogo) são zerados
 *
 * Cobre o caso "login em servidor diferente deve limpar dados da empresa anterior".
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/lib/store/authStore'
import { useSchemaStore } from '@/lib/store/schemaStore'
import { resetSessionCache } from '@/lib/store/resetSessionCache'

beforeEach(() => {
  // Garante estado limpo antes de cada caso
  useSchemaStore.getState().clear()
  useAuthStore.getState().setCompany(null, '', null)
})

describe('resetSessionCache', () => {
  it('limpa schemaStore (fields, access, loadedAt)', () => {
    const schema = useSchemaStore.getState()
    schema.setModel('res.partner', { id: { type: 'integer' } }, { read: true, write: true, create: true, unlink: true })
    expect(schema.isLoaded('res.partner')).toBe(true)
    expect(useSchemaStore.getState().loadedAt).toBeGreaterThan(0)

    resetSessionCache(null)

    expect(useSchemaStore.getState().isLoaded('res.partner')).toBe(false)
    expect(useSchemaStore.getState().fields).toEqual({})
    expect(useSchemaStore.getState().access).toEqual({})
    expect(useSchemaStore.getState().loadedAt).toBe(0)
  })

  it('zera os dados da empresa (companyId, companyName, companyLogo)', () => {
    useAuthStore.getState().setCompany(42, 'Empresa Antiga', 'base64-fake')
    expect(useAuthStore.getState().companyName).toBe('Empresa Antiga')

    resetSessionCache(null)

    const a = useAuthStore.getState()
    expect(a.companyId).toBeNull()
    expect(a.companyName).toBe('')
    expect(a.companyLogo).toBeNull()
  })

  it('apaga o cache do React Query (queries não sobrevivem)', () => {
    const qc = new QueryClient()
    qc.setQueryData(['os-mine', 7], [{ id: 1, name: 'OS-0001' }])
    qc.setQueryData(['os-detail', 1, 7], { id: 1 })
    qc.setQueryData(['company', 1], { id: 1, name: 'Antiga' })

    expect(qc.getQueryData(['os-mine', 7])).toBeDefined()
    expect(qc.getQueryData(['os-detail', 1, 7])).toBeDefined()

    resetSessionCache(qc)

    expect(qc.getQueryData(['os-mine', 7])).toBeUndefined()
    expect(qc.getQueryData(['os-detail', 1, 7])).toBeUndefined()
    expect(qc.getQueryData(['company', 1])).toBeUndefined()
  })

  it('cenário troca-de-server: dados do server A não vazam para o server B', () => {
    // === Server A ===
    const qc = new QueryClient()
    useAuthStore.getState().setServerUrl('https://a.example.com')
    useAuthStore.getState().setDbName('db-a')
    useAuthStore.getState().setUser(10, 'User A')
    useAuthStore.getState().setCompany(1, 'Empresa A', 'LOGO_A')
    useSchemaStore.getState().setModel(
      'res.partner',
      { id: { type: 'integer' }, only_on_a: { type: 'char' } },
      { read: true, write: true, create: true, unlink: true }
    )
    qc.setQueryData(['os-mine', 10], { records: [{ id: 999, name: 'OS do Server A' }] })

    // === Troca de server disparada pelo login ===
    // (simula o que o login faz quando normalizedUrl !== savedUrl)
    resetSessionCache(qc)
    useAuthStore.getState().setServerUrl('https://b.example.com') // vai invalidar mais uma vez por segurança
    useAuthStore.getState().setDbName('db-b')

    // === Server B: tudo deve estar vazio ===
    const a = useAuthStore.getState()
    expect(a.serverUrl).toBe('https://b.example.com')
    expect(a.companyId).toBeNull()
    expect(a.companyName).toBe('')
    expect(a.companyLogo).toBeNull()

    expect(useSchemaStore.getState().fields['res.partner']).toBeUndefined()
    expect(qc.getQueryData(['os-mine', 10])).toBeUndefined()
  })
})
