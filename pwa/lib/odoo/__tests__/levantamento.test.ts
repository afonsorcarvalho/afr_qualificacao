import { describe, it, expect, vi, beforeEach } from 'vitest'

const callKw = vi.fn()
vi.mock('../client', () => ({ default: { callKw: (...a: unknown[]) => callKw(...a) } }))

import { pullCatalog, pullPartners, pullPartner, push } from '../levantamento'

const MODEL = 'afr.survey.op'

describe('levantamento RPC', () => {
  beforeEach(() => callKw.mockReset())

  it('pullCatalog', async () => {
    callKw.mockResolvedValue({ categories: [] })
    await pullCatalog()
    expect(callKw).toHaveBeenCalledWith(MODEL, 'survey_pull_catalog', [])
  })
  it('pullPartners passa query/offset/limit com defaults', async () => {
    callKw.mockResolvedValue({ records: [], total: 0 })
    await pullPartners('acme')
    expect(callKw).toHaveBeenCalledWith(MODEL, 'survey_pull_partners', ['acme', 0, 50])
    await pullPartners('x', 10, 20)
    expect(callKw).toHaveBeenLastCalledWith(MODEL, 'survey_pull_partners', ['x', 10, 20])
  })
  it('pullPartner', async () => {
    callKw.mockResolvedValue({})
    await pullPartner(7)
    expect(callKw).toHaveBeenCalledWith(MODEL, 'survey_pull_partner', [7])
  })
  it('push envia a lista de ops', async () => {
    callKw.mockResolvedValue({ results: [], idmap: {} })
    const ops = [{ op_uuid: 'u', kind: 'partner.create' as const, ref: 'tmp:a', payload: {} }]
    await push(ops)
    expect(callKw).toHaveBeenCalledWith(MODEL, 'survey_push', [ops])
  })
})
