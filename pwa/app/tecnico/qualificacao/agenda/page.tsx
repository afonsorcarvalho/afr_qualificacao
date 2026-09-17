'use client'
import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { VisitaCard } from '../_components/VisitaCard'
import { VisitaSheet } from '../_components/VisitaSheet'
import { LoadingState } from '@/components/ui/LoadingState'
import { useAgenda, useAgendaDisponivel, useTecnicoOptions, useInstrumentoOptions, useUpdateVisita } from '@/lib/hooks/useAgenda'
import { useTecnicoSettings } from '@/lib/store/tecnicoSettings'
import type { VisitaAgenda, VisitaVals } from '@/lib/odoo/agenda'
import { mensagemDeFalha } from '@/lib/odoo/client'
import { clsx } from 'clsx'
import { agruparPorDia, deslocarJanela } from './janela'
import { FaixaDias } from './_FaixaDias'
import { PainelRecursos, type Dimensao } from './_PainelRecursos'
import { cargaPorDia, cargaPorTecnico, usoPorInstrumento, diasDaSemana, rosterTecnicos, picoDaSemana } from './carga'

function rotuloDia(iso: string): string {
  const [a, m, d] = iso.split('-').map(Number)
  return new Intl.DateTimeFormat('pt-BR', {
    weekday: 'short', day: '2-digit', month: 'short', timeZone: 'UTC',
  }).format(new Date(Date.UTC(a, m - 1, d)))
}

export default function AgendaPage() {
  const disponivel = useAgendaDisponivel()
  const { filterMine, setFilterMine, modoAgenda, setModoAgenda } = useTecnicoSettings()
  const semana = modoAgenda === 'semana'
  // `null` na primeira carga: o servidor decide a janela e devolve
  // `date_from`, que passa a ancorar a navegação.
  const [inicio, setInicio] = useState<string | null>(null)
  const janelaDias = semana ? 7 : 14
  const fim = inicio ? deslocarJanela(inicio, janelaDias - 1) : null
  // `disponivel.data` é `undefined` enquanto a query de disponibilidade
  // carrega (não `false`) — só o `false` explícito (módulo ausente) deve
  // segurar o `pwa_agenda_fetch`. Enquanto carrega, a busca segue normal.
  // No modo Semana o filtro "Só minhas" fica sempre desligado (ver o
  // checkbox desabilitado abaixo): a carga é da equipe, não de uma pessoa —
  // passar `filterMine` aqui mostraria uma faixa de dias que contradiz o
  // painel logo abaixo.
  const { data, isLoading, error } = useAgenda(inicio, fim, semana ? false : filterMine, disponivel.data !== false)
  const [selecionada, setSelecionada] = useState<VisitaAgenda | null>(null)
  const [criando, setCriando] = useState(false)
  // Muda a cada abertura: sem isto, os `useState` internos da folha em modo
  // criar sobrevivem a fechar/reabrir e o FAB reabre com OS/data anteriores.
  const [criarSeq, setCriarSeq] = useState(0)
  const [diaSel, setDiaSel] = useState<string | null>(null)
  const [dimensao, setDimensao] = useState<Dimensao>('tecnico')
  const [emAjuste, setEmAjuste] = useState<VisitaAgenda | null>(null)
  const [erroAjuste, setErroAjuste] = useState('')
  const update = useUpdateVisita()
  const tecnicos = useTecnicoOptions(semana)
  const instrumentos = useInstrumentoOptions(semana && dimensao === 'instrumento')

  // Rede de segurança: se a visita em ajuste sumir do payload (apagada em
  // outro lugar, saiu da janela) OU continuar lá mas ter travado (outro
  // lugar tirou a OS de `scheduled`, ex. `in_progress`), a seleção não pode
  // ficar presa a um alvo que não aceita mais gravação. Sem o segundo caso,
  // o card passa a renderizar o ramo travado (sem "Concluir"), mas
  // `alvoAtivo` continua ligado — cada toque na faixa/painel dispara uma
  // gravação que o servidor recusa, sem saída a não ser trocar de modo.
  useEffect(() => {
    if (!emAjuste || !data) return
    const atual = data.visitas.find((v) => v.id === emAjuste.id)
    if (!atual || !atual.editable) {
      encerrarAjuste()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, emAjuste])

  // Modo Semana na primeiríssima carga: `inicio` nasce `null`, e sem
  // `date_from`/`date_to` explícitos o servidor aplica a janela padrão de 14
  // dias (`pwa_agenda_fetch`), enquanto a faixa (`diasDaSemana`) sempre
  // mostra 7. Ancorar `inicio` assim que o payload chega alinha cabeçalho e
  // faixa, e evita buscar uma semana inteira de visitas a mais até a
  // próxima navegação.
  useEffect(() => {
    if (semana && inicio === null && data?.date_from) {
      setInicio(data.date_from)
    }
  }, [semana, inicio, data?.date_from])

  if (disponivel.data === false) {
    return (
      <p className="mx-auto max-w-[880px] p-4 text-center text-muted-foreground">
        Agenda de visitas indisponível: o módulo de agendamento não está
        instalado neste servidor.
      </p>
    )
  }

  const ancora = inicio ?? data?.date_from ?? null
  const semEmpregado = data ? !data.my_employee_id : false
  const grupos = agruparPorDia(data?.visitas ?? [])
  const dias = ancora ? diasDaSemana(ancora) : []
  const diaAtual = diaSel && dias.includes(diaSel) ? diaSel : dias[0] ?? ''
  const visitas = data?.visitas ?? []
  const doDia = visitas.filter((v) => v.date === diaAtual)
  // `pwa_tecnico_options` filtra por `is_tecnico=True`, mas `tecnico_id` na
  // visita não é restrito a isso — um painel de capacidade que só mostra o
  // roster oficial esconderia carga real de quem tem visita mas não a flag.
  // União com quem aparece nas visitas da janela, sem duplicar por id.
  const roster = rosterTecnicos(tecnicos.data ?? [], visitas)
  // `emAjuste` guarda a visita como ela estava ao ser selecionada. Depois de
  // cada gravação bem-sucedida, o `onSuccess` do `useUpdateVisita` invalida a
  // busca e o payload volta atualizado — mas `emAjuste` continua com a cópia
  // velha. Ressincronizar a partir do payload evita que ligar dois
  // instrumentos em sequência desligue o primeiro.
  const emAjusteAtual = emAjuste
    ? visitas.find((v) => v.id === emAjuste.id) ?? emAjuste
    : null

  /** A seleção termina (toque em "Concluir", ou a visita some do payload):
   * nada de tarja de erro sobrevivendo a uma seleção que já acabou. */
  function encerrarAjuste() {
    setEmAjuste(null)
    setErroAjuste('')
  }

  /**
   * Cada toque no painel grava UM campo. A visita em ajuste continua
   * selecionada depois do erro: o Gestor precisa poder tentar outro alvo sem
   * recomeçar.
   */
  async function ajustar(vals: VisitaVals) {
    if (!emAjuste) return
    setErroAjuste('')
    try {
      await update.mutateAsync({ id: emAjuste.id, vals })
      // A vista segue a visita: sem isto, mover para outro dia tirava o
      // card de `doDia` (some o "Concluir" junto), e cada novo toque na
      // faixa reaplicava o mesmo `date` — sem jeito de navegar ou
      // desselecionar sem sair do modo Semana.
      if (typeof vals.date === 'string') {
        setDiaSel(vals.date)
      }
    } catch (e) {
      setErroAjuste(e instanceof Error && e.message ? e.message : mensagemDeFalha(e))
    }
  }

  return (
    <div className="mx-auto w-full max-w-[880px] space-y-4">
      <div className="flex gap-1 rounded-lg border border-border bg-card p-1">
        {(['lista', 'semana'] as const).map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={modoAgenda === m}
            onClick={() => setModoAgenda(m)}
            className={clsx(
              'min-h-[44px] flex-1 rounded-md text-sm',
              modoAgenda === m ? 'bg-accent font-semibold' : 'text-muted-foreground',
            )}
          >
            {m === 'lista' ? 'Lista' : 'Semana'}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-2 py-1">
        <button
          type="button"
          aria-label="Período anterior"
          className="flex h-11 w-11 items-center justify-center rounded-md hover:bg-accent"
          onClick={() => ancora && setInicio(deslocarJanela(ancora, -janelaDias))}
        >
          <ChevronLeft className="h-5 w-5" aria-hidden />
        </button>
        <span className="text-sm font-medium">
          {data ? `${rotuloDia(data.date_from)} – ${rotuloDia(data.date_to)}` : '—'}
        </span>
        <button
          type="button"
          aria-label="Próximo período"
          className="flex h-11 w-11 items-center justify-center rounded-md hover:bg-accent"
          onClick={() => ancora && setInicio(deslocarJanela(ancora, janelaDias))}
        >
          <ChevronRight className="h-5 w-5" aria-hidden />
        </button>
      </div>

      <label
        htmlFor="agenda-filter-mine"
        className="flex min-h-[44px] cursor-pointer items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2"
      >
        <span className="text-sm font-medium">
          Só minhas
          <span className="block text-xs font-normal text-muted-foreground">
            {semana
              ? 'Desligado na semana: a carga é da equipe'
              : semEmpregado
                ? 'Seu usuário não tem técnico vinculado'
                : filterMine
                  ? 'Visitas atribuídas a você'
                  : 'Visitas de toda a equipe'}
          </span>
        </span>
        <input
          id="agenda-filter-mine"
          type="checkbox"
          checked={semana ? false : filterMine && !semEmpregado}
          disabled={semana || semEmpregado}
          onChange={(e) => setFilterMine(e.target.checked)}
          className="h-6 w-6 shrink-0 cursor-pointer accent-ok disabled:opacity-40"
        />
      </label>

      {isLoading && <LoadingState label="Carregando sua agenda..." />}
      {error && (
        <p className="text-center text-danger">
          Erro ao carregar a agenda. Verifique conexão.
        </p>
      )}
      {!isLoading && !error && !semana && grupos.length === 0 && (
        <p className="py-8 text-center text-muted-foreground">
          Nenhuma visita neste período.
        </p>
      )}

      {!semana && grupos.map((g) => (
        <section key={g.date} className="space-y-2">
          <h2 className="sticky top-0 z-10 bg-background py-1 text-sm font-semibold uppercase text-muted-foreground">
            {rotuloDia(g.date)}
          </h2>
          {g.visitas.map((v) => (
            <VisitaCard key={v.id} visita={v} onSelect={setSelecionada} />
          ))}
        </section>
      ))}

      {semana && (
        <>
          <FaixaDias
            dias={cargaPorDia(visitas, dias)}
            selecionado={diaAtual}
            onSelecionar={(d) => (emAjuste ? ajustar({ date: d }) : setDiaSel(d))}
          />
          {erroAjuste && <p className="text-sm text-danger">{erroAjuste}</p>}
          <PainelRecursos
            dimensao={dimensao}
            onTrocarDimensao={setDimensao}
            tecnicos={cargaPorTecnico(visitas, diaAtual, roster)}
            pico={picoDaSemana(visitas, dias, roster)}
            instrumentos={usoPorInstrumento(visitas, diaAtual, instrumentos.data ?? [])}
            instrumentoIdsDaVisita={emAjusteAtual?.instrument_ids ?? []}
            tecnicoIdDaVisita={emAjusteAtual && emAjusteAtual.tecnico_id !== false ? emAjusteAtual.tecnico_id : undefined}
            alvoAtivo={!!emAjuste}
            onTocarTecnico={(id) => ajustar({ tecnico_id: id })}
            onTocarInstrumento={(id) => {
              const atuais = emAjusteAtual?.instrument_ids ?? []
              ajustar({
                instrument_ids: atuais.includes(id)
                  ? atuais.filter((x) => x !== id)
                  : [...atuais, id],
              })
            }}
          />
          {doDia.map((v) => (
            <VisitaCard
              key={v.id}
              visita={v}
              onSelect={setSelecionada}
              onAjustar={data?.can_manage ? (x) => (emAjuste?.id === x.id ? encerrarAjuste() : setEmAjuste(x)) : undefined}
              emAjuste={emAjuste?.id === v.id}
            />
          ))}
          {doDia.length === 0 && (
            <p className="py-6 text-center text-muted-foreground">Nenhuma visita neste dia.</p>
          )}
        </>
      )}

      {data?.can_manage && (
        <button
          type="button"
          onClick={() => {
            setCriarSeq((s) => s + 1)
            setCriando(true)
          }}
          className="fixed bottom-20 right-4 z-40 flex h-14 items-center gap-2 rounded-full bg-primary px-5 font-semibold text-primary-foreground shadow-[0_8px_24px_rgba(0,0,0,0.45)] lg:bottom-6"
        >
          <Plus className="h-5 w-5" aria-hidden />
          Nova visita
        </button>
      )}

      <VisitaSheet
        key={selecionada?.id ?? 'nenhuma'}
        open={!!selecionada}
        modo="editar"
        visita={selecionada}
        onClose={() => setSelecionada(null)}
      />
      <VisitaSheet
        key={`criar-${criarSeq}`}
        open={criando}
        modo="criar"
        visita={null}
        onClose={() => setCriando(false)}
      />
    </div>
  )
}
