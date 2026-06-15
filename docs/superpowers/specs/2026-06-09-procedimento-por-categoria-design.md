# Design — Procedimento de Qualificação por Categoria (pivot + editor unificado)

Data: 2026-06-09
Módulo: afr_qualificacao
Versão alvo: 16.0.6.0.0 (mudança estrutural — major bump)
Fase: **F1** (core + minimizadores grátis). Biblioteca de passos + Seed = F2 (spec futuro).

## ⚠️ ATUALIZAÇÃO DE EXECUÇÃO (2026-06-10) — editor NÃO é notebook

O **pivot core foi entregue como especificado** (1 proc/categoria, `phase` por
item, `resolve_for(category)` + fallback, explosão/wizard filtram por fase,
migração 16.0.6.0.0). **MAS o editor notebook-por-fase com auto-set NÃO funciona
no Odoo 16 OWL** e foi abandonado:

- Renderizar o mesmo comodel (`procedimento.item`) em 5 abas faz o web client
  **colapsar o `default_phase` do context por comodel** (a última aba, Calibração,
  vence em todas). Campos One2many distintos por fase (faceta) **não resolvem** —
  o colapso é por comodel, não por campo.
- `@api.onchange` por faceta **não dispara no "add line" puro**, e o `domain` da
  faceta faz a linha nova **sumir da aba** quando a fase não bate.
- `column_invisible="1"` na coluna phase **vaza** pelo mesmo motivo (multi-render).

**Decisão (validada via agent-browser):** editor = **tree flat único** sobre
`item_ids` com coluna **`phase` editável + visível + required** (`default_order=
"phase, sequence"`). O usuário escolhe a fase por item; sem abas, sem domain, sem
context. Round-trip validado (salva `phase` correto). Seções 2.1 e "View" abaixo
(notebook/auto-set) ficam **OBSOLETAS** — ver commit `8b2fc94`.

Implicação p/ F2: a "biblioteca de passos" + seed continuam o caminho p/ config
mínima; a organização visual por fase (se desejada) precisaria de outra técnica
(ex.: grupos read-only + um editor à parte), não o multi-render de abas.

## Problema

Hoje o template `afr.qualificacao.procedimento` tem chave
`unique(applicable_qualification_type, equipment_category_id, company_id)`.
Para qualificar uma categoria de equipamento por completo (QI + QO + QD + QS +
Calibração) o usuário mantém **5 records desconexos** para a mesma categoria —
cada um com seu próprio `item_ids`. É confuso, repetitivo e espalha a
configuração de um mesmo equipamento por vários registros.

## Objetivo

**Um procedimento por categoria de equipamento**, contemplando todas as fases
de coleta (QI/QO/QD/QS/Calibração) organizadas num só lugar, com configuração
mínima e usabilidade máxima.

## Decisões travadas (brainstorm)

1. **Granularidade:** 1 procedimento por categoria. Chave passa a
   `unique(equipment_category_id, company_id)`. Cada `procedimento.item` ganha
   campo `phase` (mesmas opções do antigo `applicable_qualification_type`).
2. **Layout do editor:** Notebook com 1 página por fase (QI/QO/QD/QS/Calib).
   Cada página é uma tree editável de itens daquela fase, com contador no título.
3. **Auto-set da fase:** o usuário NUNCA escolhe a fase manualmente. Cada página
   renderiza `item_ids` com `domain=[('phase','=','<fase>')]` +
   `context={'default_phase':'<fase>'}`. Adicionar item na aba QD → nasce com
   `phase='performance'`.
4. **Escopo F1:** pivot + auto-set + resolve/explode por categoria + migração +
   Duplicar (quase grátis) + Fallback genérico (~1 linha).

## Arquitetura

### Modelo `afr.qualificacao.procedimento`

**Remover** o campo `applicable_qualification_type` (a aplicabilidade agora é
só por categoria; a fase migra para o item).

**Alterar** a SQL constraint:
```python
_sql_constraints = [
    ("uniq_category_company",
     "unique(equipment_category_id, company_id)",
     "Já existe procedimento para essa categoria + empresa."),
]
```
- `equipment_category_id` vazio = **fallback genérico** (vale quando a categoria
  do equipamento não tem procedimento próprio). Um único fallback por empresa.

**Ajustar** `resolve_for(qualification_type, equipment_category)` → assinatura
passa a `resolve_for(equipment_category)` (não filtra mais por tipo aqui; a fase
é filtrada na explosão):
```python
@api.model
def resolve_for(self, equipment_category):
    domain = [("active", "=", True)]
    cat_id = equipment_category.id if equipment_category else False
    if cat_id:
        rec = self.search(domain + [("equipment_category_id", "=", cat_id)], limit=1)
        if rec:
            return rec
    # fallback genérico (categoria vazia)
    return self.search(domain + [("equipment_category_id", "=", False)], limit=1)
```

`item_count` permanece. Pode-se adicionar contadores por fase
(`qi_count`/`qo_count`/...) para exibir nos títulos das abas — computed simples.

### Modelo `afr.qualificacao.procedimento.item`

**Adicionar** campo `phase`:
```python
phase = fields.Selection(
    [
        ("installation", "QI"),
        ("operational", "QO"),
        ("performance", "QD"),
        ("software", "QS"),
        ("calibration", "Calibração"),
    ],
    required=True,
    default="installation",
    string="Fase",
)
```
(Mesmos valores técnicos do antigo `applicable_qualification_type`, agora no
item.) Demais campos (`kind`, `target_level`, `requires_instrument`,
`required_sensor_kind_ids`, `docx_section`, `instruction`, etc.) inalterados.

### Explosão — `sale_order._explode_collect_items()` e o caller

O caller (`sale_order.py:~1118`) hoje faz:
```python
proc = Procedimento.sudo().resolve_for(qtype, equipment.category_id)
if proc:
    self._explode_collect_items(CollectItem.sudo(), qualif, proc)
```
Passa a:
```python
proc = Procedimento.sudo().resolve_for(equipment.category_id)
if proc:
    self._explode_collect_items(CollectItem.sudo(), qualif, proc, qtype)
```
E `_explode_collect_items(self, CollectItem, qualif, procedimento, qtype)` filtra
os itens pela fase:
```python
items = procedimento.item_ids.filtered(lambda pi: pi.phase == qtype)
for pi in items:
    ...  # resto idêntico (target_level qualificacao/cycle/malha)
```
Resultado: cada qualificação (que já tem seu `qualification_type`) recebe só os
itens da fase correspondente. Comportamento de coleta final inalterado.

### View `qualificacao_procedimento_views.xml`

Form passa a usar notebook por fase no lugar do `item_ids` plano:
```xml
<notebook>
  <page string="QI · Instalação">
    <field name="item_ids" domain="[('phase','=','installation')]"
           context="{'default_phase':'installation'}">
      <tree editable="bottom">
        <field name="sequence" widget="handle"/>
        <field name="name"/>
        <field name="kind"/>
        <field name="target_level"/>
        <field name="required"/>
        <field name="requires_instrument" widget="boolean_toggle" optional="show"/>
        <field name="required_sensor_kind_ids" widget="many2many_tags"
               optional="show" options="{'no_create_edit': True}"/>
        <field name="docx_section" optional="show"/>
        <field name="phase" column_invisible="1"/>
      </tree>
    </field>
  </page>
  <!-- páginas QO/QD/QS/Calibração idênticas, trocando phase -->
</notebook>
```
- `phase` fica `column_invisible="1"` (setado pelo context, não editável na tree).
- Remover `applicable_qualification_type` do form e do search; trocar agrupamento
  do search "por tipo" → some (não existe mais); manter "por categoria".
- Tree principal: remover coluna `applicable_qualification_type`.

### Wizard "Aplicar Procedimento" (`apply_procedimento_wizard.py`)

Consumidor que também muda (aplica procedimento manualmente a qualifs de uma OS):

- **Linha 57** — hoje pula qualifs cujo `qualification_type !=
  procedimento.applicable_qualification_type`. Esse campo some. Trocar a lógica:
  não pular a qualif inteira; em vez disso, filtrar os **itens** pela fase da
  qualif dentro da explosão.
- **`_explode_for_qualif`** — hoje itera `procedimento.item_ids` inteiro. Passa a
  iterar `procedimento.item_ids.filtered(lambda pi: pi.phase == qualif.qualification_type)`.
- A checagem de compatibilidade vira: se o procedimento não tem nenhum item da
  fase da qualif, ela contribui 0 (já coberto pelo filtro vazio). Remover o
  `continue` baseado em `applicable_qualification_type`.

(Refatorar `_explode_for_qualif` e o `_explode_collect_items` do sale_order pode
compartilhar o filtro de fase — opcional; manter dois se for mais simples.)

### Duplicar (minimizador — quase grátis)

`item_ids` já tem `copy=True`. Expor botão "Duplicar" no form
(`%(action)` ou `copy()` padrão do Odoo já disponível no menu Ação). Sem código
novo além de, opcionalmente, um botão header chamando `copy()`. Mantém YAGNI:
usar o "Duplicar" nativo do menu Ação; só documentar. **Sem código extra em F1.**

### Fallback genérico (minimizador — ~1 linha)

Já contemplado no `resolve_for` acima: categoria vazia = fallback. Sem campo novo.

## Migração

A troca de constraint quebra `-u` se houver 2+ procedimentos na mesma categoria
(estado normal hoje: QI+QO+QD por categoria). Como **labquali está em DEV**
(sem produção), a estratégia segura é limpar + re-seed manual:

**Passo nomeado (pre-migration `migrations/16.0.6.0.0/pre-migrate.py`):**
```python
def migrate(cr, version):
    # Remove procedimentos antigos (formato tipo×categoria) e seus itens.
    # labquali DEV: aceitável apagar; re-seed manual pós-upgrade.
    cr.execute("DELETE FROM afr_qualificacao_procedimento_item")
    cr.execute("DELETE FROM afr_qualificacao_procedimento")
```
Assim a nova constraint instala limpa. (Em produção futura, trocaríamos por um
merge real tipo→fase; fora de escopo agora — labquali DEV.)

## Fluxo de dados (depois)

1. Usuário cria 1 procedimento, escolhe a categoria, preenche itens nas abas das
   fases (fase auto-setada pela aba).
2. SO confirma → `resolve_for(category)` acha o procedimento (ou fallback).
3. Por qualificação criada, `_explode_collect_items(..., qtype)` explode só os
   itens daquela fase em `collect.item`. Rastreio `qualif_id` inalterado.

## Casos de borda

- Categoria sem procedimento próprio → usa fallback genérico (se existir); senão
  nenhuma coleta explodida (igual a hoje quando `resolve_for` retorna vazio).
- Item sem `phase` → impossível: `required=True` + default + auto-set por aba.
- Procedimento com itens de fases que a qualificação não tem → filtrados fora na
  explosão (ex.: itens QS num equipamento sem QS).
- Tabela órfã `afr_qualificacao_procedimento` herda dados antigos → limpos no
  pre-migrate.

## Testes

1. **test_constraint_one_per_category** — criar 2 procedimentos mesma categoria
   → `IntegrityError`.
2. **test_resolve_by_category** — `resolve_for(cat)` acha o da categoria;
   sem match → acha o fallback (categoria vazia); sem fallback → vazio.
3. **test_item_phase_field** — `procedimento.item` tem `phase`; default e
   required corretos.
4. **test_explode_filters_by_phase** — procedimento com itens QI+QD; explodir
   para qualif QD cria só os collect.items dos itens QD (count + nomes).
5. **test_explode_cycle_malha_still_works** — target_level cycle/malha continua
   explodindo N por ciclo/malha, agora dentro do filtro de fase.
6. **test_wizard_apply_filters_by_phase** — wizard aplica procedimento e cria só
   collect.items da fase de cada qualif alvo (não pula mais a qualif inteira por
   `applicable_qualification_type`).
7. Suíte completa verde. Testes a ajustar (referenciam o campo/assinatura
   removidos): `tests/test_procedimento_explosion.py` (cria proc com
   `applicable_qualification_type` + chama `resolve_for(type, cat)`),
   `tests/test_docx_render.py:179`, `tests/test_coverage.py:73`. Trocar criação
   do proc para sem o campo e os itens com `phase`; `resolve_for(cat)`.

## DECISÃO 2026-06-10 — F2 ARQUIVADA (não construir)

F2 avaliada empiricamente via agent-browser (DB `qualif_fresh_811`, editor F1 do
zero). Conclusão: **não construir F2** — nem biblioteca de passos, nem seed.

- **Editor F1 não é gargalo.** Linha nova já nasce com defaults (Fase=QI,
  Tipo=Foto, Target=Qualificação, Required✓). Item simples = só digitar Name.
  Item metrológico = +3 campos, `requires_instrument` auto via onchange.
- **Reuso já resolvido** pelo "Duplicate" nativo (menu Ação): clonar 1
  procedimento canônico p/ categoria similar = 1 clique + trocar categoria.
- **Biblioteca de passos (`step.catalog`): YAGNI.** Modelo+tela+onchange = muito
  código + risco OWL multi-render/onchange em tree (já queimado no pivot F1) p/
  ganho marginal sobre per-linha-barato + Duplicate.
- **Seed embarcado: descartado também.** A dor real é "página em branco"
  (conhecimento de domínio do que coletar), não fricção de UI. Categorias serão
  configuradas à mão a partir do canônico existente + Duplicate. (labquali já tem
  "Protocolo Autoclave Vapor" como referência viva, se precisar.)

Reabrir só se o volume de categorias crescer a ponto de o Duplicate+ajuste manual
virar gargalo medido — não por antecipação.

## Fora de escopo (F2 / YAGNI)

- **Biblioteca de passos** (`afr.qualificacao.step.catalog`) — modelo novo +
  tela + onchange. Spec futuro.
- **Seed pré-pronto** por categoria comum (autoclave, termodesinfectora) — dados
  embarcados. Spec futuro. (Lever mais direto p/ "config mínima"; vem em F2.)
- Merge real tipo→fase na migração (só relevante em produção; labquali DEV).
- Contadores por fase nas abas são opcionais (nice-to-have; incluir só se barato).
- Botão "Duplicar" custom — usar o nativo do menu Ação.
