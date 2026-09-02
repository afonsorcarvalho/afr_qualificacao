import odooClient from './client'

export interface OdooCompany {
  id: number
  name: string
}

export async function fetchAvailableCompanies(): Promise<OdooCompany[]> {
  return odooClient.searchRead<OdooCompany>(
    'res.company',
    [],
    ['id', 'name'],
    { limit: 100, order: 'name asc' }
  )
}
