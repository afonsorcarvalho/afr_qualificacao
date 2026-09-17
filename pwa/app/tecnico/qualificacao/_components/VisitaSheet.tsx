'use client'
import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { mensagemDeFalha } from '@/lib/odoo/client'
import {
  useUpdateVisita,
  useCreateVisita,
  useDeleteVisita,
  useTecnicoOptions,
  useOsOptions,
  useInstrumentoOptions,
} from '@/lib/hooks/useAgenda'
import { horaOdoo } from './VisitaCard'
import { rosterTecnicos } from '../agenda/carga'
import type { VisitaAgenda, InstrumentoOpcao } from '@/lib/odoo/agenda'

/** "08:30" → 8.5, o float de hora do Odoo. */
function paraFloat(hhmm: string): number {
  const [h, m] = hhmm.split(':').map(Number)
  return (h || 0) + (m || 0) / 60
}

const campo = 'min-h-[44px] w-full rounded-md border border-border bg-background px-3'

export function VisitaSheet({
  open,
  modo,
  visita,
  onClose,
}: {
  open: boolean
  modo: 'editar' | 'criar'
  visita: VisitaAgenda | null
  onClose: () => void
}) {
  const update = useUpdateVisita()
  const criar = useCreateVisita()
  const apagar = useDeleteVisita()
  const tecnicos = useTecnicoOptions(open)
  const oss = useOsOptions(open && modo === 'criar')
  // Só busca a lista de instrumentos quando a folha realmente precisa dela:
  // no modo criar não há visita, logo não há o que marcar.
  const instrumentos = useInstrumentoOptions(open && modo === 'editar')

  const [data, setData] = useState(visita?.date ?? '')
  const [inicio, setInicio] = useState(horaOdoo(visita?.time_start ?? 8))
  const [fim, setFim] = useState(horaOdoo(visita?.time_stop ?? 12))
  const [tecnicoId, setTecnicoId] = useState(String(visita?.tecnico_id ?? ''))
  const [osId, setOsId] = useState(String(visita?.os_id ?? ''))
  const [nota, setNota] = useState(visita?.note ?? '')
  const [instrumentoIds, setInstrumentoIds] = useState<number[]>(visita?.instrument_ids ?? [])
  const [erro, setErro] = useState('')
  const [confirmando, setConfirmando] = useState(false)

  const ocupado = update.isPending || criar.isPending || apagar.isPending

  // União do roster oficial com o técnico já gravado na visita — reaproveita
  // `rosterTecnicos` do painel de carga (Task 4) em vez de reimplementar a
  // união aqui: sem isso, um técnico que perdeu a flag `is_tecnico` (ou nunca
  // teve) some do <select> ao editar visita já dele, e salvar sem tocar no
  // campo troca o técnico por engano.
  const tecnicoOpcoes = rosterTecnicos(tecnicos.data ?? [], visita ? [visita] : [])

  function alternarInstrumento(id: number) {
    setInstrumentoIds((atuais) =>
      atuais.includes(id) ? atuais.filter((x) => x !== id) : [...atuais, id],
    )
  }

  /**
   * Mesma regra de "vencido" de `usoPorInstrumento` em `carga.ts`
   * (`!validade || validade < dia`), mas contra a data escolhida no próprio
   * formulário — o técnico pode estar reagendando a visita para outro dia, e
   * o aviso tem de refletir a data nova, não a original da visita.
   */
  function instrumentoVencido(i: InstrumentoOpcao): boolean {
    return !i.validade || i.validade < data
  }

  async function salvar() {
    setErro('')
    if (modo === 'criar' && (!osId || !tecnicoId || !data)) {
      setErro('Preencha OS, técnico e data antes de criar a visita.')
      return
    }
    try {
      if (modo === 'criar') {
        await criar.mutateAsync({
          osId: Number(osId), tecnicoId: Number(tecnicoId), date: data,
        })
      } else if (visita) {
        await update.mutateAsync({
          id: visita.id,
          vals: {
            date: data,
            time_start: paraFloat(inicio),
            time_stop: paraFloat(fim),
            tecnico_id: Number(tecnicoId),
            note: nota,
            // Só em modo editar: `pwa_visita_create` tem outra assinatura e
            // não aceita `instrument_ids`.
            instrument_ids: instrumentoIds,
          },
        })
      }
      onClose()
    } catch (e) {
      // A mensagem do servidor é a que o usuário precisa ler (constraint de
      // equipamento sobreposto, data passada, OS travada). A folha fica
      // aberta com o que ele digitou.
      setErro(e instanceof Error && e.message ? e.message : mensagemDeFalha(e))
    }
  }

  async function confirmarExclusao() {
    if (!visita) return
    setErro('')
    try {
      await apagar.mutateAsync(visita.id)
      onClose()
    } catch (e) {
      setErro(e instanceof Error && e.message ? e.message : mensagemDeFalha(e))
    }
  }

  return (
    <BottomSheet
      open={open}
      title={modo === 'criar' ? 'Nova visita' : `Visita ${visita?.os_name ?? ''}`}
      onClose={onClose}
    >
      <div className="space-y-3">
        {modo === 'criar' && (
          <label className="block text-sm">
            OS
            <select aria-label="OS" className={campo} value={osId} onChange={(e) => setOsId(e.target.value)}>
              <option value="">—</option>
              {(oss.data ?? []).map((o) => (
                <option key={o.id} value={o.id}>{o.name}</option>
              ))}
            </select>
          </label>
        )}

        <label className="block text-sm">
          Data
          <input aria-label="Data" type="date" className={campo} value={data} onChange={(e) => setData(e.target.value)} />
        </label>

        {modo === 'editar' && (
          <div className="flex gap-3">
            <label className="block flex-1 text-sm">
              Início
              <input aria-label="Início" type="time" className={campo} value={inicio} onChange={(e) => setInicio(e.target.value)} />
            </label>
            <label className="block flex-1 text-sm">
              Fim
              <input aria-label="Fim" type="time" className={campo} value={fim} onChange={(e) => setFim(e.target.value)} />
            </label>
          </div>
        )}

        <label className="block text-sm">
          Técnico
          <select aria-label="Técnico" className={campo} value={tecnicoId} onChange={(e) => setTecnicoId(e.target.value)}>
            <option value="">—</option>
            {tecnicoOpcoes.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </label>

        {modo === 'editar' && (
          <fieldset className="rounded-md border border-border p-3 text-sm">
            <legend className="px-1 font-medium">Instrumentos</legend>
            {(instrumentos.data ?? []).length === 0 ? (
              <p className="text-muted-foreground">Nenhum instrumento cadastrado.</p>
            ) : (
              <div className="space-y-1">
                {(instrumentos.data ?? []).map((i) => (
                  <label key={i.id} className="flex min-h-[44px] items-center gap-2">
                    <input
                      type="checkbox"
                      checked={instrumentoIds.includes(i.id)}
                      onChange={() => alternarInstrumento(i.id)}
                    />
                    <span className="flex-1">{i.name}</span>
                    {/* Aviso em texto, não só em cor: quem não distingue a
                        cor (ou está com o aparelho ao sol) precisa ler. Não
                        bloqueia a marcação — quem decide é o servidor. */}
                    {instrumentoVencido(i) && (
                      <span className="flex shrink-0 items-center gap-1 text-xs text-danger">
                        <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
                        certificado vencido
                      </span>
                    )}
                  </label>
                ))}
              </div>
            )}
          </fieldset>
        )}

        {modo === 'editar' && (
          <label className="block text-sm">
            Observações
            <textarea aria-label="Observações" rows={3} className="w-full rounded-md border border-border bg-background p-3" value={nota} onChange={(e) => setNota(e.target.value)} />
          </label>
        )}

        {erro && <p className="text-sm text-danger">{erro}</p>}

        <div className="flex gap-2 pt-1">
          <button type="button" disabled={ocupado} onClick={salvar} className="min-h-[44px] flex-1 rounded-md bg-primary px-4 font-semibold text-primary-foreground disabled:opacity-50">
            {modo === 'criar' ? 'Criar' : 'Salvar'}
          </button>
          {modo === 'editar' && !confirmando && (
            <button type="button" disabled={ocupado} onClick={() => setConfirmando(true)} className="min-h-[44px] rounded-md border border-destructive px-4 font-semibold text-destructive disabled:opacity-50">
              Apagar
            </button>
          )}
          {modo === 'editar' && confirmando && (
            <button type="button" disabled={ocupado} onClick={confirmarExclusao} className="min-h-[44px] rounded-md bg-destructive px-4 font-semibold text-destructive-foreground disabled:opacity-50">
              Confirmar exclusão
            </button>
          )}
        </div>
      </div>
    </BottomSheet>
  )
}
