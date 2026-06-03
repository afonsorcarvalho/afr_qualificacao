# Agendamento de Visitas de OS de Qualificação — Design

- **Módulo (entrega):** `afr_qualificacao_agendamento` — módulo satélite novo, `depends: ['afr_qualificacao']` (Odoo 16.0 Community)
- **Data:** 2026-06-03
- **Status:** Design aprovado (aguarda revisão do spec antes do plano)
- **Autor:** brainstorming sessão 2026-06-03

## 1. Problema e objetivo

A OS de qualificação (`afr.qualificacao.os`) já tem campos de data planejada
(`date_planned_start`/`date_planned_end`), uma calendar view por técnico,
a ação `action_schedule` (draft→scheduled), a jornada h/dia por equipamento
(F5.8.0) e o plano de recursos por bin-packing (F10). O que falta é
**agendar o trabalho de campo em si**: hoje a OS é um único bloco de datas,
sem representar que o serviço acontece ao longo de vários dias, por um ou mais
técnicos, em deslocamento entre clientes.

Este feature entrega um **subsistema de agendamento de visitas de campo**:

1. **Quebra multi-dia / visitas** — uma OS vira N visitas diárias.
2. **Auto-sugestão de datas** — motor assistivo gera as visitas a partir das
   horas estimadas e da jornada.
3. **Detecção de conflito** — técnico em dois lugares, recurso metrológico
   duplo-alocado, calibração de instrumento vencida, e tempo de deslocamento
   entre cidades.
4. **Board interativo** — visualização própria (OWL) da agenda técnico×dia.

### Decisões de escopo (sessão de brainstorming)

| Tema | Decisão |
|---|---|
| Unidade agendável | **Visita = OS × dia × técnico** (registro próprio) |
| Granularidade | **Misto**: dia como base, hora início/fim opcional |
| Cardinalidade de técnico | 1 técnico por visita; múltiplos técnicos por OS (visitas paralelas no mesmo dia) |
| Motor de sugestão | **Assistivo**: humano escolhe técnico + data início; sistema gera e sinaliza; humano confirma/ajusta |
| Grupos paralelos | **Manual caso a caso**: motor emite tudo num técnico (sequencial); `tecnico_id` editável → humano reatribui visitas pra paralelizar |
| Conflito — escopo | técnico-duplo + recurso metrológico + calibração vencida + **tempo de deslocamento** (sem folga/férias / `resource.calendar`) |
| Fonte do deslocamento | **Buffer manual por visita** (campo em horas) |
| Board | **Componente OWL custom** (Community, sem widget Gantt enterprise) |
| Empacotamento | **Módulo satélite separado** `afr_qualificacao_agendamento` (`depends: afr_qualificacao`) — agendamento opcional, fronteira limpa |

## 2. Arquitetura

### Empacotamento — módulo satélite `afr_qualificacao_agendamento`

Todo o feature vive num módulo novo `afr_qualificacao_agendamento`
(`depends: ['afr_qualificacao']`), no padrão dos satélites do monorepo
(`afr_supervisorio_ciclos_{extras,bus,dashboard,eto}`). Vantagens: agendamento
vira opcional (cliente que não faz campo não instala), `afr_qualificacao` não
incha mais, versão/deploy independentes, unidade pequena e bem-delimitada.

Quase tudo é **adição pura** (modelo `visita`, views, motor, board) e mora 100%
no módulo novo, lendo `estimated_hours` / `work_hours_per_day` / `parallel_group`
/ plano F10 do `afr_qualificacao` sem alterá-los.

O **único acoplamento invasivo** é fazer `date_planned_start/end` da OS virarem
rollup das visitas. Decisão: **opção X — o satélite redefine os campos herdados
como `computed store`** (`_inherit = 'afr.qualificacao.os'`). Garante fonte única
de verdade, é padrão suportado pelo Odoo, e reverte ao definir base no uninstall.
Alternativas descartadas: (Y) sincronizar via create/write da visita — fronteira
mais limpa mas com risco de drift; (Z) deixar as datas da OS independentes das
visitas — duas fontes de verdade divergentes, ruim.

### Unidade — novo modelo `afr.qualificacao.os.visita`

Cada visita é um registro próprio (OS × dia × técnico). A OS ganha um
`one2many` para suas visitas. Casa com todas as decisões: multi-dia natural,
técnico editável por visita, calendar/board arrastam um registro real, lógica
de conflito localizada no registro da visita.

### Abordagens rejeitadas (unidade)

- **Estender campos na `afr.qualificacao`** — uma qualificação de 24h não vira
  multi-dia num só registro sem sub-records; nada concreto pra arrastar no
  board; deslocamento e conflito ficam tortos.
- **Reusar `calendar.event` / `project.task`** — backbone genérico demais pra
  prender equipamentos, recursos e regras de conflito de domínio; `project`
  não está instalado; atrito alto.

## 3. Faseamento

Um único design doc cobre a visão completa; o plano de implementação
(writing-plans) mira **apenas a Fase A**. As fases B–D ganham seus próprios
ciclos spec→plano quando chegarem.

| Fase | Entrega | Dependência |
|---|---|---|
| **A — Fundação** | Modelo `visita` + agendamento manual + calendar nativo sobre visitas + conflito técnico-duplo + deslocamento | — |
| **B — Motor assistivo** | `action_suggest_visitas(técnico, data início)` gera visitas sequenciais a partir de técnico-dias | A |
| **C — Recurso↔visita** | Prende instrumento F10 à visita → conflito de recurso + calibração vencida | A, F10 |
| **D — Board OWL custom** | Timeline técnico×dia, ocupação, conflitos, drag-reschedule | A (calendar nativo cobre o intervalo) |

**Por que o calendar nativo entra já na Fase A** (e não só no fim): a agenda
fica usável antes do build pesado do OWL, e de-risca a peça mais cara —
o board OWL — que foi escolhida contra a recomendação inicial. Se o OWL
escorregar, o calendar nativo já entrega valor.

## 4. Fase A — Fundação (alvo do plano de implementação)

### 4.0 Esqueleto do módulo `afr_qualificacao_agendamento`

```
afr_qualificacao_agendamento/      depends: ['afr_qualificacao']
├── __manifest__.py                versão 16.0.1.0.0
├── models/
│   ├── os_visita.py               modelo novo afr.qualificacao.os.visita
│   └── qualificacao_os.py         _inherit: visita_ids + rollup datas (X) + action_schedule
├── views/
│   ├── os_visita_views.xml        tree / form / calendar da visita
│   └── qualificacao_os_views.xml  embed visita_ids + stat button na OS
├── security/ir.model.access.csv
└── tests/test_visita.py
```

### 4.1 Modelo `afr.qualificacao.os.visita`

| Campo | Tipo | Notas |
|---|---|---|
| `name` | Char (computed/sequence) | rótulo legível (ex: `OS26-06-0007 / Dia 2 / João`) |
| `os_id` | Many2one → `afr.qualificacao.os` | required, `ondelete="cascade"` |
| `tecnico_id` | Many2one → `hr.employee` | required, **editável** (reatribuição manual de grupos paralelos); default = `os_id.tecnico_default_id` |
| `date` | Date | required — o dia da visita |
| `time_start` | Float | opcional — hora início (modo hora) |
| `time_stop` | Float | opcional — hora fim (modo hora) |
| `date_start` | Datetime | computed **store**, de `date` + `time_start` (00:00 se vazio) → fonte da calendar view |
| `date_stop` | Datetime | computed **store**, de `date` + `time_stop` (23:59 se vazio) |
| `equipment_ids` | Many2many → `engc.equipment` | equipamentos trabalhados nesse dia |
| `planned_hours` | Float | horas de trabalho previstas no dia (≤ jornada do equipamento) |
| `travel_buffer_hours` | Float | tempo de deslocamento manual (h) até esta visita |
| `partner_id` | Many2one (related `os_id.partner_id`, store) | cliente |
| `city` | Char (related `partner_id.city`, store) | localização — base do alerta cross-city |
| `sequence` | Integer | ordem dos dias dentro da OS |
| `state` | Selection: `planned`, `done` | estado simples da visita (mínimo viável) |
| `note` | Text | observações |
| `tecnico_conflict` | Boolean (computed) | técnico com outra visita sobreposta |
| `tecnico_conflict_msg` | Char (computed) | descrição do conflito de técnico |
| `travel_conflict` | Boolean (computed) | visita consecutiva do técnico em outra cidade sem gap ≥ buffer |
| `travel_conflict_msg` | Char (computed) | descrição do conflito de deslocamento |

> Os campos de conflito de **recurso** e **calibração vencida** ficam na Fase C
> (exigem prender instrumentos F10 à visita). A Fase A entrega só os conflitos
> que são pura função dos dados da visita (técnico + data + cidade).

### 4.2 Regras de conflito (Fase A)

- **Técnico em dois lugares:** existe outra `visita` com mesmo `tecnico_id` e
  sobreposição. Modo dia (sem hora): mesmo `date`. Modo hora: sobreposição de
  `[date_start, date_stop]`.
- **Deslocamento:** duas visitas consecutivas do mesmo técnico em cidades
  diferentes (`city`) sem intervalo ≥ `travel_buffer_hours`. No modo dia, visitas
  em cidades diferentes no mesmo dia já caracterizam conflito.

Todos os conflitos são **avisos não-bloqueantes**: o sistema sinaliza
(campo computado + destaque visual + aviso ao confirmar), mas permite
"confirmar mesmo assim" — coerente com o motor assistivo.

### 4.3 Mudanças em `afr.qualificacao.os` (via `_inherit` no satélite)

Todas as mudanças abaixo vivem em `afr_qualificacao_agendamento/models/qualificacao_os.py`
com `_inherit = 'afr.qualificacao.os'` — `afr_qualificacao` não é tocado.

- `visita_ids` — One2many → `afr.qualificacao.os.visita` (adição pura).
- **Opção X:** `date_planned_start` / `date_planned_end` redefinidos como
  **`computed store` rollup** (`min`/`max` de `visita_ids.date_start` / `date_stop`).
  Sem visitas: o compute retorna o valor existente/`False` (fallback definido no
  plano), e o uninstall reverte os campos à definição base do `afr_qualificacao`.
- `action_schedule`: override via `super()` — validação muda de "datas planejadas
  preenchidas" para **"≥1 visita existe"**. Interação com a state-machine
  sinalizada: `scheduled` passa a exigir pelo menos uma visita. OS legadas já em
  `scheduled` sem visitas: tratar no plano (não revalidar retroativo).
- Stat button "Visitas" (contagem) no form da OS, injetado por herança de view.

### 4.4 Views (Fase A)

- **Calendar view nativa sobre `afr.qualificacao.os.visita`**: `date_start` →
  `date_stop`, cor por `tecnico_id`, filtros por cliente/estado, drag pra
  reagendar. Reaproveita o padrão da calendar view de OS já existente.
- **Tree/form** da visita; embedding `visita_ids` como aba/linhas no form da OS.
- Destaque visual de conflito (decoração) na tree e no form.

### 4.5 Testes (TDD)

- Criação de visita; rollup de `date_planned_start/end` na OS.
- `action_schedule` exige ≥1 visita.
- Conflito de técnico (modo dia e modo hora).
- Conflito de deslocamento (cidades diferentes vs gap suficiente).
- Cascade ao deletar OS.

## 5. Fase B — Motor assistivo (resumo, plano futuro)

`action_suggest_visitas(tecnico_id, data_inicio)` na OS:

- **Fonte das horas = técnico-dias** = Σ por equipamento
  `estimated_hours ÷ work_hours_per_day` (F5.8.0 — o que foi cotado ao cliente).
  **NÃO** usar `hours_resource_usage` do F10.
- Empacota as horas em dias respeitando a jornada por equipamento; emite
  visitas sequenciais num único técnico a partir da data início.
- Insere `travel_buffer_hours` quando muda de cliente/cidade.
- Sinaliza conflitos; humano confirma, ajusta datas e reatribui técnico das
  visitas que quiser paralelizar.

> **Por que não F10 para contar dias:** `hours_resource_usage` é wall-clock do
> instrumento (um data-logger roda 24–48h sozinho, sem técnico presente).
> Técnico-dias é o esforço de campo cotado (F5.8.0). **Consequência:** o span
> do calendário da OS ≠ soma dos técnico-dias — o técnico instala sensores no
> dia 1, coleta no dia 3, e o dia 2 não tem visita. F10 fica reservado para
> ocupação/conflito de recurso (Fase C).

## 6. Fase C — Alocação recurso↔visita (resumo, plano futuro)

- Prender instrumentos do plano F10 (validador/padrão) a visitas e suas janelas
  de data → as sugestões do F10 viram compromissos datados.
- **Conflito de recurso:** mesmo instrumento alocado em duas OS no mesmo período.
- **Calibração vencida:** instrumento com calibração vencida na data da visita
  (via `engc.calibration`). Alerta de qualidade.

## 7. Fase D — Board OWL custom (resumo, plano futuro)

- Componente OWL: timeline técnico × dia, com ocupação por técnico, destaque de
  conflitos, indicação de deslocamento, e drag-reschedule.
- Substitui/complementa a calendar nativa da Fase A como tela principal de
  gestão de agenda.

## 8. Riscos e pontos de atenção

- **Rollup vs edição manual de datas na OS:** ao tornar `date_planned_*`
  computado, formulários/relatórios que escreviam nesses campos precisam ser
  auditados. Definir o fallback sem visitas no plano da Fase A.
- **State-machine:** mudar a validação de `action_schedule` pode afetar OS
  legadas já em `scheduled` sem visitas. Tratar migração/compatibilidade.
- **Modo dia vs hora no mesmo modelo:** regras de conflito híbridas; cobrir
  ambos os modos nos testes.
- **Fonte das horas (Fase B):** erro clássico seria usar F10; o design fixa
  F5.8.0. Validar empiricamente a divergência num caso de mapeamento térmico.
