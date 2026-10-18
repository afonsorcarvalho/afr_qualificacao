'use client'
import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { saveCycle } from '@/lib/levantamento/repo'
import type { LocalCycle, LocalPhoto } from '@/lib/levantamento/db'
import { CampoSelect, CampoTexto } from './Campo'
import { FotoStrip } from './FotoStrip'
import { useAutosave } from './useAutosave'
import { SyncErrorBadge } from './SyncErrorBadge'
import type { Catalog } from './catalog'

/** Um ciclo usado: tipo, temperatura, duração, carga, nota e foto da tela do programa. */
export function CicloEditor({
  indice, cycle, equipmentKey, cat, photos, onAddPhoto, onDeletePhoto, onDelete,
}: {
  indice: number
  cycle: LocalCycle
  equipmentKey: string
  cat: Catalog
  photos: LocalPhoto[]
  onAddPhoto: (kind: string, blob: Blob, cycleKey: string) => Promise<void>
  onDeletePhoto: (key: string) => Promise<void>
  onDelete: (key: string) => Promise<void>
}) {
  const [vals, setVals] = useState<Record<string, unknown>>({ ...cycle })
  const [erro, setErro] = useState('')
  // `cycle.key` / `equipmentKey` são lidos a cada save (ref interna do hook): sobrevivem ao tmp -> id real.
  const { edit } = useAutosave(
    (changed) => saveCycle(cycle.key, equipmentKey, changed),
    (e) => setErro(e instanceof Error ? e.message : 'Falha ao salvar o ciclo'),
    () => setErro(''),
  )

  const set = (campo: string, valor: unknown) => {
    setVals((v) => ({ ...v, [campo]: valor }))
    edit(campo, valor)
  }
  const m2o = (campo: string) => (v: string) => set(campo, v ? Number(v) : false)
  const telaCiclo = [{ kind: 'ciclo', label: 'Tela do programa' }]

  return (
    <fieldset aria-label={`Ciclo ${indice}`} role="group" className="space-y-3 rounded-md border border-border p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Ciclo {indice}</span>
        <button
          type="button"
          aria-label={`Excluir ciclo ${indice}`}
          onClick={() => void onDelete(cycle.key)}
          className="flex h-11 w-11 items-center justify-center rounded-md text-danger hover:bg-accent"
        >
          <Trash2 className="h-4 w-4" aria-hidden />
        </button>
      </div>
      {cycle.sync === 'erro' && (
        <SyncErrorBadge error={cycle.syncError} recordKey={cycle.key} recordKind="cycle" />
      )}
      {erro && <p role="alert" className="text-sm text-danger">{erro}</p>}
      <CampoSelect
        label="Tipo de ciclo"
        value={vals.cycle_type_id}
        onChange={m2o('cycle_type_id')}
        options={cat.cycle_types.map((c) => ({ value: String(c.id), label: c.name }))}
      />
      <div className="grid grid-cols-2 gap-2">
        <CampoTexto label="Temperatura" value={vals.temperature} onChange={(v) => set('temperature', v)} />
        <CampoTexto label="Duração" value={vals.duration} onChange={(v) => set('duration', v)} />
      </div>
      <CampoSelect
        label="Tipo de carga"
        value={vals.load_type}
        onChange={(v) => set('load_type', v || false)}
        options={cat.selections.load_type.map(([value, label]) => ({ value, label }))}
      />
      <CampoTexto label="Observação do ciclo" value={vals.note} onChange={(v) => set('note', v)} multiline />
      <FotoStrip
        kinds={telaCiclo}
        photos={photos}
        onAdd={(kind, blob) => onAddPhoto(kind, blob, cycle.key)}
        onDelete={onDeletePhoto}
      />
    </fieldset>
  )
}
