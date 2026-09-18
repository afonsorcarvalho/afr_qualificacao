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
import { VistaMes } from './_VistaMes'
import { cargaPorDia, cargaPorTecnico, usoPorInstrumento, diasDaSemana, rosterTecnicos, picoDaSemana } from './carga'
import { primeiroDiaDoMes, deslocarMes, gradeDoMes, noMes, rotuloMes, tecnicosPorDia, instrumentosPorDia } from './mes'

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
  const mes = modoAgenda === 'mes'
  // Semana e Mês são as duas visões de EQUIPE — "Só minhas" desligado e
  // desabilitado, `onlyMine=false` no fetch, roster carregado pra
  // legenda/painel. Usar esta flag em todos esses pontos (em vez de
  // acrescentar `|| mes` em cada `semana ? ... : ...` já existente) evita
  // que um dos sítios fique para trás — foi exatamente esse o risco
  // apontado no brief.
  const visaoEquipe = modoAgenda !== 'lista'
  // `null` na primeira carga: o servidor decide a janela e devolve
  // `date_from`, que passa a ancorar a navegação.
  const [inicio, setInicio] = useState<string | null>(null)
  const janelaDias = semana ? 7 : 14
  const fim = inicio ? deslocarJanela(inicio, janelaDias - 1) : null
  // `ancoraMes` é o 1º dia do mês visível — estado SEPARADO de `inicio`,
  // que ancora lista/semana. Misturar as duas semânticas no mesmo estado
  // faria o mês virar "14 dias a partir de", não um mês de calendário.
  const [ancoraMes, setAncoraMes] = useState<string | null>(null)
  const gradeMes = ancoraMes ? gradeDoMes(ancoraMes) : []
  const dateFrom = mes ? (gradeMes[0] ?? null) : inicio
  const dateTo = mes ? (gradeMes[41] ?? null) : fim
  // `disponivel.data` é `undefined` enquanto a query de disponibilidade
  // carrega (não `false`) — só o `false` explícito (módulo ausente) deve
  // segurar o `pwa_agenda_fetch`. Enquanto carrega, a busca segue normal.
  // Em Semana/Mês o filtro "Só minhas" fica sempre desligado (ver o
  // checkbox desabilitado abaixo): a carga é da equipe, não de uma pessoa —
  // passar `filterMine` aqui mostraria uma faixa de dias que contradiz o
  // painel/grade logo abaixo.
  const { data, isLoading, error } = useAgenda(dateFrom, dateTo, visaoEquipe ? false : filterMine, disponivel.data !== false)
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
  const tecnicos = useTecnicoOptions(visaoEquipe)
  // `pwa_instrumento_options` alimenta três telas distintas: o painel de
  // recursos da Semana (só quando a dimensão é "instrumento", pra não gastar
  // fetch enquanto o Gestor olha "Técnico"), e a legenda + lista do dia do
  // Mês (task 3), que precisam da lista inteira sempre que o mês está
  // aberto — daí a expressão única em vez de espalhar `|| mes` pelos sítios
  // que já checavam `semana`.
  const querInstrumentos = mes || (semana && dimensao === 'instrumento')
  const instrumentos = useInstrumentoOptions(querInstrumentos)

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

  // Modo Mês na primeiríssima carga: `ancoraMes` nasce `null`, e sem ele
  // não há faixa (`grade[0]`..`grade[41]`) para pedir — a primeira busca
  // sai sem datas, o servidor aplica a janela padrão e devolve
  // `server_today` (nunca o relógio do aparelho). Assim que o payload
  // chega, ancora `ancoraMes` no 1º dia do mês de `server_today`, e a
  // segunda busca já traz a grade completa. Duas buscas na primeira
  // abertura é o preço aceito (brief 3c) — enquanto isso, `mesCarregando`
  // mais abaixo mantém o `LoadingState` em vez de uma grade meio vazia.
  useEffect(() => {
    if (mes && ancoraMes === null && data?.server_today) {
      setAncoraMes(primeiroDiaDoMes(data.server_today))
    }
  }, [mes, ancoraMes, data?.server_today])

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
  // União com quem aparece nas visitas da janela, sem duplicar por id. Este
  // roster já unificado é o que `tecnicosPorDia` (mês) e `cargaPorTecnico`
  // (semana) exigem — passar o retorno cru de `useTecnicoOptions` faria uma
  // visita de técnico sem a flag `is_tecnico` contar no `total` do dia sem
  // gerar pontinho, silenciosamente.
  const roster = rosterTecnicos(tecnicos.data ?? [], visitas)
  const hoje = data?.server_today ?? null
  // Enquanto `ancoraMes` não ancorou (primeiríssima carga do mês) OU a
  // busca da faixa completa ainda está em voo (2ª busca, cada toque em
  // ◀ ▶ com `queryKey` novo), não há grade utilizável pra mostrar —
  // `mesCarregando` segura o `LoadingState` mais abaixo em vez de uma
  // grade meio vazia (42 células sem pontinho, sem anel de "hoje", sob o
  // spinner). Fix round 1 (achado 1): o gate original só cobria a 1ª
  // busca; `isLoading` sozinho já cobre as duas, porque também é `true`
  // durante a 1ª.
  //
  // `!error` é do fix round 2 (achado 1): com a busca falhando, `data` fica
  // `undefined`, o `useEffect` de ancoragem acima nunca roda e `ancoraMes`
  // fica `null` PARA SEMPRE — o gate ficava `true` para sempre junto, e a
  // tela mostrava o spinner e "Erro ao carregar a agenda" ao mesmo tempo,
  // indefinidamente, sem saída a não ser sair do modo.
  const mesCarregando = mes && !error && (ancoraMes === null || isLoading)
  // Um gate só, sem redundância: `mesCarregando` já embute `isLoading`, mas
  // só vale no mês — `mes && ...` é `false` na Lista e na Semana, onde o
  // spinner continua sendo o `isLoading` cru.
  const carregando = mes ? mesCarregando : isLoading
  const pontosDia = mes ? tecnicosPorDia(visitas, gradeMes, roster) : []
  // Instrumentos da grade do mês — mesma fonte (`pwa_instrumento_options`)
  // que alimenta o painel da Semana, mas aqui cobrindo os 42 dias da janela
  // visível de uma vez, pros triângulos da `_GradeMes` e pra legenda.
  const pontosInstrumentoDia = mes ? instrumentosPorDia(visitas, gradeMes, instrumentos.data ?? []) : []
  // Dia default quando não há seleção válida na grade: primeiro tenta
  // `hoje` (server_today) — mesmo critério da Semana, que nasce ancorada
  // em `data.date_from` = hoje — e só cai no 1º dia do mês quando "hoje"
  // está fora da grade visível (mês diferente do atual). Cair direto no
  // dia 1 (fix round 1, achado 4) marcava dois dias ao mesmo tempo na
  // primeira abertura: o anel de "hoje" no dia certo e o fundo de seleção
  // no dia 1, com a lista de cards dizendo "Nenhuma visita neste dia."
  const diaSelMes = diaSel && gradeMes.includes(diaSel)
    ? diaSel
    : (hoje && gradeMes.includes(hoje) ? hoje : (ancoraMes ?? ''))
  // "Instrumentos do dia" (brief 3c): reusa `usoPorInstrumento` (a mesma
  // agregação do painel da Semana) sobre o dia selecionado do mês, filtrando
  // pra só quem tem uso — ao contrário do painel da Semana, que lista todo
  // instrumento (inclusive "livre") pra mostrar quem está disponível, a
  // seção do Mês é só um resumo do que o dia já tem marcado.
  const usoInstrumentosDia = mes
    ? usoPorInstrumento(visitas, diaSelMes, instrumentos.data ?? []).filter((u) => u.usos.length > 0)
    : []
  // `emAjuste` guarda a visita como ela estava ao ser selecionada. Depois de
  // cada gravação bem-sucedida, o `onSuccess` do `useUpdateVisita` invalida a
  // busca e o payload volta atualizado — mas `emAjuste` continua com a cópia
  // velha. Ressincronizar a partir do payload evita que ligar dois
  // instrumentos em sequência desligue o primeiro.
  const emAjusteAtual = emAjuste
    ? visitas.find((v) => v.id === emAjuste.id) ?? emAjuste
    : null
  // A visita armada só é ALVO de gravação enquanto ela própria está visível
  // na janela atual (fix round 2, achado 2). Sem isto, navegar de mês (ou
  // trocar de modo) tirava o card da tela sem desarmar nada, e o toque
  // seguinte num dia qualquer reagendava a visita em silêncio — três toques
  // e a visita tinha mudado de mês sem ninguém pedir. O que a janela mostra
  // e o que o toque grava passam a ser a mesma coisa.
  const janelaVisivel = mes ? gradeMes : dias
  const alvoVisivel = !!emAjusteAtual && janelaVisivel.includes(emAjusteAtual.date)

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
        // Mês: mover a visita pra fora do mês visível tira o card da
        // grade (ela mudou de mês), mas a âncora sozinha não segue — sem
        // isto a seleção fica presa olhando pro mês errado. É estado da
        // PÁGINA (`ancoraMes`), não da `_VistaMes`: passar a âncora pra
        // baixo só pro filho escrever de volta inverteria o fluxo de dados
        // dos outros modos (ruling do controlador, brief 3d).
        if (mes && ancoraMes && !noMes(vals.date, ancoraMes)) {
          setAncoraMes(primeiroDiaDoMes(vals.date))
        }
      }
    } catch (e) {
      setErroAjuste(e instanceof Error && e.message ? e.message : mensagemDeFalha(e))
    }
  }

  return (
    <div className="mx-auto w-full max-w-[880px] space-y-4">
      <div className="flex gap-1 rounded-lg border border-border bg-card p-1">
        {(['lista', 'semana', 'mes'] as const).map((m) => (
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
            {m === 'lista' ? 'Lista' : m === 'semana' ? 'Semana' : 'Mês'}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-2 py-1">
        <button
          type="button"
          aria-label="Período anterior"
          className="flex h-11 w-11 items-center justify-center rounded-md hover:bg-accent"
          onClick={() => {
            // Mês navega de calendário (±1 mês), não ±N dias — misturar as
            // duas aritméticas aqui é o mesmo erro que motivou `ancoraMes`
            // ser um estado à parte de `inicio`.
            if (mes) {
              if (ancoraMes) setAncoraMes(deslocarMes(ancoraMes, -1))
            } else if (ancora) {
              setInicio(deslocarJanela(ancora, -janelaDias))
            }
          }}
        >
          <ChevronLeft className="h-5 w-5" aria-hidden />
        </button>
        <span className="text-sm font-medium">
          {mes
            // "setembro de 2026", não `date_from`–`date_to` do payload — a
            // grade de 42 dias transborda pro mês vizinho nas duas pontas, e
            // "dom 30 ago – sáb 10 out" mentiria sobre qual mês está aberto.
            ? (ancoraMes ? rotuloMes(ancoraMes) : '—')
            : (data ? `${rotuloDia(data.date_from)} – ${rotuloDia(data.date_to)}` : '—')}
        </span>
        <button
          type="button"
          aria-label="Próximo período"
          className="flex h-11 w-11 items-center justify-center rounded-md hover:bg-accent"
          onClick={() => {
            if (mes) {
              if (ancoraMes) setAncoraMes(deslocarMes(ancoraMes, 1))
            } else if (ancora) {
              setInicio(deslocarJanela(ancora, janelaDias))
            }
          }}
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
            {visaoEquipe
              ? (mes ? 'Desligado no mês: a carga é da equipe' : 'Desligado na semana: a carga é da equipe')
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
          checked={visaoEquipe ? false : filterMine && !semEmpregado}
          disabled={visaoEquipe || semEmpregado}
          onChange={(e) => setFilterMine(e.target.checked)}
          className="h-6 w-6 shrink-0 cursor-pointer accent-ok disabled:opacity-40"
        />
      </label>

      {/* Tarja de ajuste em curso — FORA dos ramos de modo de propósito
          (ruling do controlador): o indicador de "tem visita armada" não
          pode depender do `VisitaCard`, que só é renderizado quando a visita
          cai no dia selecionado. Vale para Semana E Mês, e carrega o
          identificador da visita e uma saída explícita — nada aqui depende
          de cor. */}
      {emAjusteAtual && (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-muted px-3 py-2">
          <span className="min-w-0 text-sm">
            Movendo a visita {emAjusteAtual.os_name} de {rotuloDia(emAjusteAtual.date)}
            <span className="block text-xs text-muted-foreground">
              {alvoVisivel
                ? 'Toque num dia para mover.'
                : 'Fora do período visível: volte ao período dela ou cancele.'}
            </span>
          </span>
          <button
            type="button"
            onClick={encerrarAjuste}
            className="min-h-[44px] shrink-0 rounded-md border border-border px-3 text-sm font-medium"
          >
            Cancelar
          </button>
        </div>
      )}

      {carregando && <LoadingState label="Carregando sua agenda..." />}
      {error && (
        <p className="text-center text-danger">
          Erro ao carregar a agenda. Verifique conexão.
        </p>
      )}
      {!isLoading && !error && modoAgenda === 'lista' && grupos.length === 0 && (
        <p className="py-8 text-center text-muted-foreground">
          Nenhuma visita neste período.
        </p>
      )}

      {modoAgenda === 'lista' && grupos.map((g) => (
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
            onSelecionar={(d) => (alvoVisivel ? ajustar({ date: d }) : setDiaSel(d))}
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
            alvoAtivo={alvoVisivel}
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

      {/* `!error` e `ancoraMes !== null`: com `mesCarregando` agora falso no
          erro (achado 1), sem estes dois a grade vazaria vazia — 0 células,
          âncora '' e "Nenhuma visita neste dia." — por baixo da mensagem de
          falha. */}
      {mes && !mesCarregando && !error && ancoraMes !== null && (
        <VistaMes
          visitas={visitas}
          dias={pontosDia}
          instrumentos={pontosInstrumentoDia}
          usoInstrumentosDia={usoInstrumentosDia}
          ancora={ancoraMes ?? ''}
          hoje={hoje}
          diaSel={diaSelMes}
          onSelecionarDia={setDiaSel}
          roster={roster}
          podeAjustar={!!data?.can_manage}
          emAjuste={emAjusteAtual}
          alvoAtivo={alvoVisivel}
          onAjustar={ajustar}
          onAlternarAjuste={(x) => (emAjuste?.id === x.id ? encerrarAjuste() : setEmAjuste(x))}
          erroAjuste={erroAjuste}
          onSelecionarVisita={setSelecionada}
        />
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
