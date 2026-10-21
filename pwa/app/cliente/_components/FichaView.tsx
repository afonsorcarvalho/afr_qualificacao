'use client'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { MicButton } from '@/app/tecnico/qualificacao/_components/MicButton'
import { getDb, type LocalCycle, type LocalEquipment, type LocalPhoto } from '@/lib/levantamento/db'
import { onSyncTick } from '@/lib/levantamento/events'
import {
  addPhoto, deleteCycle, deletePhoto, missingRequired, resolveKey, saveCycle, saveEquipment,
} from '@/lib/levantamento/repo'
import { CampoSelect, CampoTexto } from './Campo'
import { CicloEditor } from './CicloEditor'
import { FichaSecao } from './FichaSecao'
import { FotoStrip, type FotoKind } from './FotoStrip'
import { SyncErrorBadge } from './SyncErrorBadge'
import { labelOf, useCatalog } from './catalog'
import { tituloDoEquip } from './equipInfo'
import { useAutosave } from './useAutosave'
import { useOnline } from './useOnline'
import { ClienteLink } from './ClienteLink'
import { EmptyOffline } from './EmptyOffline'
import { useCanEditCtx } from './canEdit'
import { goCliente } from '@/lib/cliente/nav'

const FALLBACK_KIND: Record<string, string> = {
  plaqueta: 'Plaqueta', geral: 'Geral', camara: 'Câmara', porta: 'Porta', termopar: 'Termopar', alimentacao: 'Alimentação',
}

/** Ficha do equipamento: autosave local (IndexedDB), sem botão salvar. */
export function FichaView({ id: clienteParam, eq: eqParam }: { id: string; eq: string }) {
  const podeEditar = useCanEditCtx()
  const novo = eqParam === 'novo'
  const cat = useCatalog()
  const online = useOnline()

  const [eq, setEq] = useState<LocalEquipment | undefined>()
  const [vals, setVals] = useState<Record<string, unknown>>({})
  const [cycles, setCycles] = useState<LocalCycle[]>([])
  const [photos, setPhotos] = useState<LocalPhoto[]>([])
  const [carregado, setCarregado] = useState(false)
  const [erro, setErro] = useState('')

  // Chave mais recente do equipamento (null = ainda não criado). Sempre aqui, nunca só na URL.
  const keyRef = useRef<string | null>(null)
  const iniciado = useRef(false)
  const montado = useRef(true)
  useEffect(() => {
    montado.current = true
    return () => {
      montado.current = false
    }
  }, [])
  const [criado, setCriado] = useState(false)
  const [chavesEstaveis, setChavesEstaveis] = useState<Map<string, string>>(new Map())
  const redirecionado = useRef<string | null>(null)

  const irParaChave = useCallback(
    (k: string) => {
      if (!montado.current || redirecionado.current === k) return
      redirecionado.current = k
      goCliente({ id: clienteParam, eq: k }, { replace: true })
    },
    [clienteParam],
  )

  const carregar = useCallback(async () => {
    const base = keyRef.current ?? (novo ? null : eqParam)
    const key = base ? await resolveKey(base) : null
    keyRef.current = key
    // URL com tmp já reescrito pelo engine -> troca pela chave real.
    if (key && !novo && key !== eqParam) irParaChave(key)
    if (!key) {
      iniciado.current = true
      setCarregado(true)
      return
    }
    const rec = await getDb().equipments.get(key)
    const [mapa, cs, ps] = await Promise.all([
      getDb().idmap.toArray(),
      
      getDb().cycles.where('equipmentKey').equals(key).toArray(),
      getDb().photos.where('equipmentKey').equals(key).toArray(),
    ])
    if (!montado.current) return
    // id real -> chave tmp original: identidade React do ciclo que sobrevive ao rekey.
    setChavesEstaveis(new Map(mapa.map((m) => [String(m.id), m.tmp])))
    setEq(rec)
    setCycles(cs)
    setPhotos(ps)
    // Valores dos campos só semeiam uma vez: o que o usuário digita não é atropelado por tick de sync.
    if (rec && !iniciado.current) {
      iniciado.current = true
      setVals({ ...rec })
    }
    setCarregado(true)
  }, [novo, eqParam, irParaChave])

  useEffect(() => {
    void carregar()
    return onSyncTick(() => void carregar())
  }, [carregar])

  const salvar = useCallback(
    async (changed: Record<string, unknown>) => {
      const primeira = keyRef.current === null
      const k = await saveEquipment(keyRef.current, clienteParam, changed)
      keyRef.current = k
      if (!montado.current) return // saiu da tela: só persistir, sem navegar
      setCriado(true)
      if (primeira) irParaChave(k)
      void carregar()
    },
    [clienteParam, irParaChave, carregar],
  )
  const { edit, enqueue } = useAutosave(
    salvar,
    (e) => {
      if (montado.current) setErro(e instanceof Error ? e.message : 'Falha ao salvar')
    },
    () => {
      if (montado.current) setErro('')
    },
  )

  const set = (campo: string, valor: unknown) => {
    setVals((v) => ({ ...v, [campo]: valor }))
    edit(campo, valor)
  }
  const m2o = (campo: string) => (v: string) => set(campo, v ? Number(v) : false)
  const num = (campo: string) => (v: string) => set(campo, v.trim() === '' ? false : Number(v))

  /** Garante que o equipamento existe localmente (fotos/ciclos precisam da chave), na mesma fila dos saves. */
  const garantirChave = () =>
    enqueue(async () => {
      if (keyRef.current === null) await salvar({})
      return keyRef.current as unknown as string
    })

  const guardado = useCallback(
    async (fn: () => Promise<unknown>) => {
      setErro('')
      try {
        await fn()
        await carregar()
      } catch (e) {
        setErro(e instanceof Error ? e.message : 'Falha ao salvar')
      }
    },
    [carregar],
  )

  const adicionarFoto = (kind: string, blob: Blob, cycleKey?: string) =>
    guardado(async () => {
      const ek = await garantirChave()
      await addPhoto(ek, kind, blob, cycleKey, { precompressed: true }) // CameraInput já entrega JPEG <= 1600px
    })
  const excluirFoto = (key: string) => guardado(() => deletePhoto(key))
  const novoCiclo = () =>
    guardado(async () => {
      const ek = await garantirChave()
      await saveCycle(null, ek, {})
    })
  const excluirCiclo = (key: string) => guardado(() => deleteCycle(key))

  const k = useMemo(() => {
    const kinds = (...ks: string[]): FotoKind[] =>
      ks.map((kd) => ({ kind: kd, label: labelOf(cat.selections.survey_kind, kd) ?? FALLBACK_KIND[kd] ?? kd }))
    return {
      ident: kinds('plaqueta', 'geral'),
      camara: kinds('camara', 'porta'),
      termopar: kinds('termopar'),
      alim: kinds('alimentacao'),
    }
  }, [cat.selections.survey_kind])

  const faltando = missingRequired(vals)
  const aindaLocal = novo || (keyRef.current?.startsWith('tmp:') ?? false)
  const opts = (items: { id: number; name: string }[]) => items.map((i) => ({ value: String(i.id), label: i.name }))
  const volta = { id: clienteParam }

  if (carregado && !novo && !eq && !criado) {
    return (
      <EmptyOffline volta={volta} voltaLabel="Voltar aos equipamentos" />
    )
  }

  return (
    <div className="mx-auto max-w-[720px] space-y-3 pb-8">
      <div className="flex items-center gap-2">
        <ClienteLink to={volta} aria-label="Voltar aos equipamentos" className="flex h-11 w-11 items-center justify-center">
          <ArrowLeft className="h-5 w-5" aria-hidden />
        </ClienteLink>
        <h1 className="min-w-0 flex-1 truncate text-base font-semibold">
          {novo && !eq ? 'Novo equipamento' : tituloDoEquip({ ...(eq ?? { key: '', partnerKey: '', sync: 'ok' }), ...vals } as LocalEquipment, cat)}
        </h1>
      </div>

      {eq?.sync === 'erro' && (
        <SyncErrorBadge
          error={eq.syncError}
          recordKey={eq.key}
          recordKind="equipment"
          onDiscarded={() => goCliente(volta, { replace: true })}
        />
      )}
      {podeEditar && aindaLocal && faltando.length > 0 && (
        <p role="status" className="rounded-md border border-warn/30 bg-warn-surface p-3 text-sm text-warn">
          Preencha a categoria para enviar
        </p>
      )}
      {erro && <p role="alert" className="text-sm text-danger">{erro}</p>}

      <FichaSecao titulo="Identificação">
        <CampoSelect label="Categoria" value={vals.category_id} onChange={m2o('category_id')} options={opts(cat.categories)} />
        <CampoSelect label="Marca" value={vals.marca_id} onChange={m2o('marca_id')} options={opts(cat.marcas)} />
        <CampoTexto label="Modelo" value={vals.model} onChange={(v) => set('model', v)} />
        {cat.locations.length > 0 && (
          <CampoSelect label="Local" value={vals.location_id} onChange={m2o('location_id')} options={opts(cat.locations)} />
        )}
        <CampoTexto label="Número de série" value={vals.serial_number} onChange={(v) => set('serial_number', v)} />
        <CampoTexto label="Apelido" value={vals.apelido} onChange={(v) => set('apelido', v)} />
        <CampoTexto label="Tag" value={vals.tag} onChange={(v) => set('tag', v)} />
        <CampoTexto label="Patrimônio" value={vals.patrimony} onChange={(v) => set('patrimony', v)} />
        <FotoStrip kinds={k.ident} photos={photos} onAdd={(kd, b) => adicionarFoto(kd, b)} onDelete={excluirFoto} />
      </FichaSecao>

      <FichaSecao titulo="Câmara">
        <CampoTexto label="Volume útil (L)" type="number" value={vals.chamber_volume_l} onChange={num('chamber_volume_l')} />
        <CampoTexto label="Dimensões" value={vals.chamber_dimensions} onChange={(v) => set('chamber_dimensions', v)} />
        <CampoTexto label="Sensores estimados" type="number" value={vals.sensor_qty_estimated} onChange={num('sensor_qty_estimated')} />
        <FotoStrip kinds={k.camara} photos={photos} onAdd={(kd, b) => adicionarFoto(kd, b)} onDelete={excluirFoto} />
      </FichaSecao>

      <FichaSecao titulo="Termopar">
        <CampoSelect
          label="Acesso para termopares"
          value={vals.thermocouple_access}
          onChange={(v) => set('thermocouple_access', v || false)}
          options={cat.selections.thermocouple_access.map(([value, label]) => ({ value, label }))}
        />
        <FotoStrip kinds={k.termopar} photos={photos} onAdd={(kd, b) => adicionarFoto(kd, b)} onDelete={excluirFoto} />
      </FichaSecao>

      <FichaSecao titulo="Alimentação">
        <CampoTexto label="Alimentação" value={vals.power_supply} onChange={(v) => set('power_supply', v)} />
        <FotoStrip kinds={k.alim} photos={photos} onAdd={(kd, b) => adicionarFoto(kd, b)} onDelete={excluirFoto} />
      </FichaSecao>

      <FichaSecao titulo="Ciclos">
        {cycles.map((c, i) => (
          <CicloEditor
            key={chavesEstaveis.get(c.key) ?? c.key}
            indice={i + 1}
            cycle={c}
            equipmentKey={keyRef.current ?? c.equipmentKey}
            cat={cat}
            photos={photos.filter((p) => p.cycleKey === c.key)}
            onAddPhoto={(kd, b, ck) => adicionarFoto(kd, b, ck)}
            onDeletePhoto={excluirFoto}
            onDelete={excluirCiclo}
          />
        ))}
        {podeEditar && (
          <Button type="button" variant="outline" className="min-h-[44px] w-full" onClick={() => void novoCiclo()}>
            + ciclo
          </Button>
        )}
      </FichaSecao>

      <FichaSecao titulo="Observações">
        <CampoTexto label="Observações do levantamento" multiline value={vals.survey_note} onChange={(v) => set('survey_note', v)} />
        {online && podeEditar && (
          <MicButton
            onTranscribe={(texto) => {
              const atual = typeof vals.survey_note === 'string' ? vals.survey_note : ''
              set('survey_note', atual ? `${atual}\n${texto}` : texto)
            }}
          />
        )}
      </FichaSecao>
    </div>
  )
}
