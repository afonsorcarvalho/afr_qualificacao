import type { SummaryRequestBody } from '@/app/api/groq/summary/route'
import type { getOsDetail } from '@/lib/odoo/tecnico'

type OsDetailData = Awaited<ReturnType<typeof getOsDetail>>

export function buildSummaryContext(data: OsDetailData): SummaryRequestBody {
  const byEquip = new Map<number, { tag: string; name: string; items: SummaryRequestBody['equipments'][number]['items'] }>()
  for (const it of data.collect_items ?? []) {
    const equipId = Array.isArray(it.equipment_id) ? it.equipment_id[0] : 0
    const eq = data.equipments?.[equipId]
    const tag = (eq?.tag && typeof eq.tag === 'string' ? eq.tag : null)
      ?? (eq?.apelido && typeof eq.apelido === 'string' ? eq.apelido : null)
      ?? (Array.isArray(it.equipment_id) ? String(it.equipment_id[0]) : 'sem-tag')
    const name = eq?.name
      ?? (Array.isArray(it.equipment_id) ? it.equipment_id[1] : 'Sem equipamento')
    if (!byEquip.has(equipId)) {
      byEquip.set(equipId, { tag, name, items: [] })
    }
    byEquip.get(equipId)!.items.push({
      id: it.id,
      name: it.name,
      status: it.state as 'collected' | 'skipped' | 'pending',
      obs: typeof it.description === 'string' ? it.description : '',
      at: typeof it.captured_at === 'string' ? it.captured_at : null,
    })
  }
  return {
    os_name: data.os.name,
    equipments: Array.from(byEquip.values()),
  }
}
