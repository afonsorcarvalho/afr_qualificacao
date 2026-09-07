'use client'
import { useState } from 'react'
import { ColetaCard } from './ColetaCard'
import { CollectedCard } from './CollectedCard'
import { ColetaFilter, type SegmentoColeta } from './ColetaFilter'
import { EquipmentHeader } from './EquipmentHeader'
import type { ColetaItemDetail, OsDetailData } from '@/lib/odoo/tecnico'

type Grupo = {
  key: string
  label: string
  eqId: number | null
  items: ColetaItemDetail[]
}

const FEITO = ['collected', 'skipped']

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
  const done_items = collect_items.filter((i) => FEITO.includes(i.state))

  function chaveDoEquipamento(it: ColetaItemDetail) {
    return it.equipment_id ? `eq-${it.equipment_id[0]}` : 'sem-equip'
  }

  function groupByEquipment(items: ColetaItemDetail[]): Grupo[] {
    const groups = new Map<string, Grupo>()
    for (const it of items) {
      const key = chaveDoEquipamento(it)
      const label = it.equipment_id ? it.equipment_id[1] : 'Sem equipamento'
      if (!groups.has(key)) {
        groups.set(key, { key, label, eqId: it.equipment_id ? it.equipment_id[0] : null, items: [] })
      }
      groups.get(key)!.items.push(it)
    }
    return Array.from(groups.values()).sort((a, b) => a.label.localeCompare(b.label))
  }

  // Progresso por equipamento na OS inteira — é o que o cabeçalho mostra, e
  // por isso sai de `collect_items`, não do segmento em exibição.
  const progresso = new Map<string, { feitas: number; total: number }>()
  for (const it of collect_items) {
    const key = chaveDoEquipamento(it)
    const p = progresso.get(key) ?? { feitas: 0, total: 0 }
    p.total += 1
    if (FEITO.includes(it.state)) p.feitas += 1
    progresso.set(key, p)
  }

  const groupList = groupByEquipment(pending_items)
  const doneGroupList = groupByEquipment(done_items)

  const segmentoDoItem = (id?: number): SegmentoColeta | null =>
    done_items.some((i) => i.id === id)
      ? 'feitas'
      : pending_items.some((i) => i.id === id)
        ? 'pendentes'
        : null

  const grupoDoItem = (id?: number) => {
    const it = collect_items.find((i) => i.id === id)
    return it ? chaveDoEquipamento(it) : null
  }

  // Duas razões pra não nascer em "Pendentes": a OS já terminou (a lista
  // abriria vazia justo quando não há mais nada a fazer) ou o deep link já
  // trouxe uma coleta realizada aberta no painel. Só o valor inicial — depois
  // disso o segmento é do técnico.
  const segmentoInicial =
    segmentoDoItem(selectedId) ??
    (pending_items.length === 0 && done_items.length > 0 ? 'feitas' : 'pendentes')
  const [segmento, setSegmento] = useState<SegmentoColeta>(segmentoInicial)

  // Só as exceções ao padrão ficam guardadas, com a chave carregando o
  // segmento: o mesmo equipamento pode estar aberto de um lado e fechado do
  // outro, e o padrão de cada lado depende de quantos grupos ele tem.
  const [abertos, setAbertos] = useState<Record<string, boolean>>(() => {
    const g = grupoDoItem(selectedId)
    return g ? { [`${segmentoInicial}|${g}`]: true } : {}
  })

  // Ajuste de estado durante o render (padrão documentado do React, sem
  // efeito e sem piscada): abrir uma coleta traz junto o segmento e o grupo
  // dela. Sem isso a linha com `aria-current` ficaria no lado escondido ou
  // dentro de um grupo fechado.
  const [ultimoSelecionado, setUltimoSelecionado] = useState<number | undefined>(
    selectedId,
  )
  if (selectedId !== ultimoSelecionado) {
    setUltimoSelecionado(selectedId)
    const alvo = segmentoDoItem(selectedId)
    if (alvo) {
      if (alvo !== segmento) setSegmento(alvo)
      const g = grupoDoItem(selectedId)
      if (g) setAbertos((a) => ({ ...a, [`${alvo}|${g}`]: true }))
    }
  }

  const listaAtiva = segmento === 'pendentes' ? groupList : doneGroupList
  // Recolher o único grupo esconderia a lista inteira atrás de um toque, sem
  // ganho nenhum de rolagem.
  const padraoAberto = listaAtiva.length <= 1
  const estaAberto = (key: string) => abertos[`${segmento}|${key}`] ?? padraoAberto
  const alternar = (key: string) =>
    setAbertos((a) => ({ ...a, [`${segmento}|${key}`]: !estaAberto(key) }))

  // A etiqueta de tipo (QI/QO/QD) só ganha sentido quando há mais de um tipo
  // na mesma OS; senão repetiria a mesma sigla em toda linha.
  const tiposNaOs = new Set(
    collect_items
      .map((i) => (i.qualif_id ? qualifs[i.qualif_id[0]]?.qualification_type : null))
      .filter(Boolean),
  )
  const mostrarTipo = tiposNaOs.size > 1

  function grupoRenderizado(g: Grupo, conteudo: React.ReactNode) {
    const aberto = estaAberto(g.key)
    const painelId = `grupo-${segmento}-${g.key}`
    const p = progresso.get(g.key) ?? { feitas: 0, total: g.items.length }
    return (
      <div key={`${segmento}-${g.key}`} className="space-y-2">
        <EquipmentHeader
          label={g.label}
          eq={g.eqId ? equipments[g.eqId] : undefined}
          feitas={p.feitas}
          total={p.total}
          tone={segmento === 'pendentes' ? 'cyan' : 'emerald'}
          aberto={aberto}
          onToggle={() => alternar(g.key)}
          controlsId={painelId}
        />
        {/* O container existe mesmo fechado — `aria-controls` precisa apontar
            pra um nó que esteja no DOM —, mas vazio: manter 25 cartões
            montados atrás de um `hidden` gastaria render e deixaria conteúdo
            invisível ao alcance de busca de texto e de leitor mal configurado.
            Nada se perde ao desmontar: os cartões não têm estado próprio. */}
        <div id={painelId} hidden={!aberto} className="space-y-2 pl-2">
          {aberto && conteudo}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <ColetaFilter
        segmento={segmento}
        onChange={setSegmento}
        pendentes={pending_items.length}
        feitas={done_items.length}
      />

      {segmento === 'pendentes' ? (
        <div className="space-y-4">
          {/* O rótulo e a contagem já estão no filtro; repetir na tela seria
              dizer duas vezes a mesma coisa. Fica para leitor de tela, que
              precisa do título de seção pra navegar. */}
          <h2 className="sr-only">
            {open_relatorio_id
              ? `Coletas pendentes (${pending_items.length})`
              : `Prévia das coletas (${pending_items.length})`}
          </h2>
          {pending_items.length === 0 ? (
            <p className="rounded-lg border border-border/70 bg-muted/30 p-3 text-center text-sm text-muted-foreground">
              {collect_items.length === 0
                ? 'Nenhuma coleta cadastrada.'
                : 'Nenhuma coleta pendente.'}
            </p>
          ) : (
            groupList.map((g) =>
              grupoRenderizado(
                g,
                g.items.map((item) =>
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
                    /* Sem opacidade no container: isto é a "Prévia das
                       coletas" (ver o `sr-only` acima) — o técnico LÊ estes
                       nomes pra saber o que o turno vai pedir. A 60% o nome
                       media 3,39:1 e a instrução 2,82:1 no tema claro (6,01 e
                       3,71 no escuro): abaixo do piso, e exatamente a classe
                       de defeito que abriu esta branch. O "ainda não dá pra
                       coletar" continua dito por três coisas que não são
                       tinta — borda tracejada, ausência das affordances do
                       ColetaCard, e o aviso âmbar logo abaixo. */
                    <div
                      key={item.id}
                      className="rounded-lg border border-dashed border-border/70 bg-muted/20 p-3"
                    >
                      <p className="truncate text-sm text-foreground/90">{item.name}</p>
                      {item.instruction && (
                        <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                          {item.instruction}
                        </p>
                      )}
                    </div>
                  ),
                ),
              ),
            )
          )}
          {!open_relatorio_id && pending_items.length > 0 && (
            /* `bg-warn/5`, não `bg-warn-surface`: aqui havia a shade crua de
               âmbar a 5%, um tinte quase invisível, e a tradução o mandou para a
               superfície de estado — que foi calibrada a 15%. No escuro isso
               levou rgb(15,15,17) para rgb(45,36,27): marrom nítido onde havia
               um véu. `/5` nem estava na faixa `/10..15` que a tabela cobria.
               Token bruto com opacidade é o mecanismo certo para TINGIMENTO de
               fundo (não é tinta de texto, não responde a piso de contraste);
               `-surface` fica para o chip que precisa de fundo de verdade. */
            <p className="rounded-md border border-warn/20 bg-warn/5 p-2 text-center text-xs text-warn">
              Inicie o relatório do dia pra coletar.
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <h2 className="sr-only">Já coletadas ({done_items.length})</h2>
          {done_items.length === 0 ? (
            <p className="rounded-lg border border-border/70 bg-muted/30 p-3 text-center text-sm text-muted-foreground">
              Nada coletado ainda.
            </p>
          ) : (
            doneGroupList.map((g) =>
              grupoRenderizado(
                g,
                g.items.map((item) => (
                  <CollectedCard
                    key={item.id}
                    osId={osId}
                    item={item}
                    canEdit={!!open_relatorio_id}
                    instruments={instruments}
                    selected={item.id === selectedId}
                  />
                )),
              ),
            )
          )}
        </div>
      )}
    </div>
  )
}
