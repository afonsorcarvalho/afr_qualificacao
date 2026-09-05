'use client'
import { ColetaCard } from './ColetaCard'
import { CollectedCard } from './CollectedCard'
import { EquipmentHeader } from './EquipmentHeader'
import type { OsDetailData } from '@/lib/odoo/tecnico'

export function ColetaList({
  data,
  osId,
  selectedId,
}: {
  data: OsDetailData
  osId: number
  /** Item aberto no painel direito, em desktop. */
  selectedId?: number
}) {
  const { collect_items, open_relatorio_id, equipments, instruments, qualifs } = data
  const pending_items = collect_items.filter((i) => i.state === 'pending')
  const done_items = collect_items.filter(
    (i) => i.state === 'collected' || i.state === 'skipped',
  )

  function groupByEquipment(items: typeof collect_items) {
    const groups = new Map<
      string,
      { label: string; eqId: number | null; items: typeof collect_items }
    >()
    for (const it of items) {
      const eqId = it.equipment_id ? it.equipment_id[0] : null
      const key = eqId !== null ? `eq-${eqId}` : 'sem-equip'
      const label = it.equipment_id ? it.equipment_id[1] : 'Sem equipamento'
      if (!groups.has(key)) groups.set(key, { label, eqId, items: [] })
      groups.get(key)!.items.push(it)
    }
    return Array.from(groups.values()).sort((a, b) => a.label.localeCompare(b.label))
  }

  // A etiqueta de tipo (QI/QO/QD) só ganha sentido quando há mais de um tipo
  // na mesma OS; senão repetiria a mesma sigla em toda linha.
  const tiposNaOs = new Set(
    collect_items
      .map((i) => (i.qualif_id ? qualifs[i.qualif_id[0]]?.qualification_type : null))
      .filter(Boolean),
  )
  const mostrarTipo = tiposNaOs.size > 1

  const groupList = groupByEquipment(pending_items)
  const doneGroupList = groupByEquipment(done_items)

  return (
    <div className="space-y-4">
      {(pending_items.length > 0 || done_items.length === 0) && (
        <div className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80">
            {open_relatorio_id
              ? `Coletas pendentes (${pending_items.length})`
              : `Prévia das coletas (${pending_items.length})`}
          </h2>
          {pending_items.length === 0 ? (
            <p className="rounded-lg border border-border/70 bg-muted/30 p-3 text-center text-sm text-muted-foreground/90">
              Nenhuma coleta cadastrada.
            </p>
          ) : (
            groupList.map((g) => (
              <div key={g.label} className="space-y-2">
                <EquipmentHeader
                  label={g.label}
                  eq={g.eqId ? equipments[g.eqId] : undefined}
                  count={g.items.length}
                  tone="cyan"
                />
                <div className="space-y-2 pl-2">
                  {g.items.map((item) =>
                    open_relatorio_id ? (
                      <ColetaCard
                        key={item.id}
                        osId={osId}
                        item={item}
                        instruments={instruments}
                        qualifs={qualifs}
                        mostrarTipo={mostrarTipo}
                        selected={item.id === selectedId}
                      />
                    ) : (
                      <div
                        key={item.id}
                        className="rounded-lg border border-border/40 bg-muted/20 p-3 opacity-60"
                      >
                        <p className="truncate text-sm text-foreground/90">{item.name}</p>
                        {item.instruction && (
                          <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground/80">
                            {item.instruction}
                          </p>
                        )}
                      </div>
                    ),
                  )}
                </div>
              </div>
            ))
          )}
          {!open_relatorio_id && pending_items.length > 0 && (
            <p className="rounded-md border border-amber-500/20 bg-amber-500/5 p-2 text-center text-xs text-amber-300/80">
              Inicie o relatório do dia pra coletar.
            </p>
          )}
        </div>
      )}

      {done_items.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80">
            Já coletadas ({done_items.length})
          </h2>
          {doneGroupList.map((g) => (
            <div key={`done-${g.label}`} className="space-y-2">
              <EquipmentHeader
                label={g.label}
                eq={g.eqId ? equipments[g.eqId] : undefined}
                count={g.items.length}
                tone="emerald"
              />
              <div className="space-y-2 pl-2">
                {g.items.map((item) => (
                  <CollectedCard
                    key={item.id}
                    osId={osId}
                    item={item}
                    canEdit={!!open_relatorio_id}
                    instruments={instruments}
                    selected={item.id === selectedId}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
