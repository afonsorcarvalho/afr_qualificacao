# Design — Qualificações: remover Etapas/Desvios/Mensagens + aba Coletas

Data: 2026-06-09
Módulo: afr_qualificacao
Versão alvo: 16.0.5.20.0

## Objetivo

Simplificar o form de `afr.qualificacao`:
1. Remover funcionalidade de **Etapas** (model `afr.qualificacao.step`) — não usada.
2. Remover funcionalidade de **Desvios** (model `afr.qualificacao.deviation`) — não usada.
3. Esconder a aba **Mensagens** (chatter dentro de page de notebook) — não mostrar.
4. Adicionar aba **Coletas** mostrando as coletas (`collect.item`) ligadas à qualificação — rastreio que os dados já têm (`qualif_id`) mas a UI não expõe.

## Contexto / descobertas

- `afr.qualificacao.collect.item` já tem `qualif_id` (Many2one) e `afr.qualificacao`
  já tem o inverso `collect_item_ids` (One2many, inverse `qualif_id`, string "Coletas").
- Ambos caminhos de criação setam `qualif_id`:
  - `sale_order._explode_collect_items()` na confirmação do SO (sale_order.py:1139).
  - wizard "Aplicar Procedimento" (apply_procedimento_wizard.py).
- Logo o rastreio coleta→qualificação **já existe nos dados**; falta só a aba.
- O "step" do configurador (`qualificacao_configurator.py`) é um `Selection` de
  navegação do wizard — NÃO é o model `afr.qualificacao.step`. Não é afetado.
- `tests/test_configurator_steps.py` testa a navegação do wizard, não os models
  removidos.
- labquali está em DEV (sem produção) — migração não necessária. Ao remover os
  models do código e rodar `-u`, o registry remove os models; as tabelas órfãs
  `afr_qualificacao_step` / `afr_qualificacao_deviation` permanecem inertes no
  DB (aceitável em dev). Sem `ir.model` cleanup manual nesta fase.

## Parte 1 — Remoções

### 1.1 Models (`models/qualificacao.py`)
- Remover classe `AfrQualificacaoStep` (`_name = "afr.qualificacao.step"`).
- Remover classe `AfrQualificacaoDeviation` (`_name = "afr.qualificacao.deviation"`).
- Em `AfrQualificacao` remover os campos e computes:
  - `step_ids`, `step_count`, `_compute_step_count`
  - `deviation_ids`, `deviation_count`, `_compute_deviation_count`

### 1.2 Views (`views/qualificacao_views.xml`)
- Remover `<page string="Etapas">` (com `step_ids`).
- Remover `<page string="Desvios">` (com `deviation_ids`).
- Remover smart button de Desvios (`name="deviation_count"`, ~linha 110).
- Remover `<page string="Mensagens">` (~linha 330) — esconde a aba; o chatter
  (followers/activities/messages) vive dentro dessa page e sai junto, conforme
  pedido.
- Remover os records de deviation: search (`view_afr_qualificacao_deviation_search`),
  action (`action_afr_qualificacao_deviation`), tree (`view_afr_qualificacao_deviation_tree`),
  form (`view_afr_qualificacao_deviation_form`).

### 1.3 Menu (`views/qualificacao_menus.xml`)
- Remover `menu_afr_qualificacao_deviation` (referencia a action removida).

### 1.4 Security (`security/ir.model.access.csv`)
- Remover as 4 linhas:
  `access_afr_qualificacao_step_user`, `access_afr_qualificacao_step_manager`,
  `access_afr_qualificacao_deviation_user`, `access_afr_qualificacao_deviation_manager`.

### 1.5 Report certificate (`reports/qualificacao_certificate_template.xml`)
- Remover a seção/tabela que itera `o.step_ids` (incl. fallback "Sem etapas registradas").
- Remover a seção que itera `o.deviation_ids`.

### 1.6 Tests
- Verificar e ajustar qualquer teste que referencie os models/campos removidos.
  Conhecidos seguros: `test_configurator_steps.py` (nav do wizard).
  No plano: rodar a suíte e corrigir falhas residuais (ex.: testes que criavam
  step/deviation ou checavam `step_count`/`deviation_count`).

## Parte 2 — Aba Coletas (editável)

### 2.1 View (`views/qualificacao_views.xml`)
Adicionar uma `<page string="Coletas">` no notebook, **na posição onde estavam
Etapas/Desvios** (antes da page "Comercial"):

```xml
<page string="Coletas">
    <field name="collect_item_ids">
        <tree editable="bottom">
            <field name="sequence" widget="handle"/>
            <field name="name"/>
            <field name="kind"/>
            <field name="cycle_id" optional="show"/>
            <field name="malha_id" optional="hide"/>
            <field name="required"/>
            <field name="state" widget="badge"
                   decoration-success="state == 'collected'"
                   decoration-warning="state == 'pending'"
                   decoration-muted="state == 'skipped'"/>
            <field name="relatorio_id" optional="show"/>
            <field name="captured_by" optional="hide"/>
            <field name="filename" optional="hide"/>
        </tree>
    </field>
</page>
```

Notas:
- **Editável** (decisão do user): `editable="bottom"` permite criar/editar coletas
  na própria aba. `qualif_id` é preenchido automaticamente pelo one2many (contexto
  do pai), mantendo o rastreio.
- Não exibe coluna `qualif_id` (redundante — todas as linhas são desta qualif).
- Sem mudança no model; reusa `collect_item_ids` existente.

## Fluxo de dados

- Aba Coletas lê/escreve `collect_item_ids` (One2many inverse `qualif_id`).
  Criar linha aqui → `qualif_id` = a qualificação atual (automático).
- Remoções não alteram dados de coletas; só retiram models/UI não usados.

## Casos de borda

- Coletas criadas na aba sem `os_id`/`relatorio_id` ficam com esses campos
  vazios (aceitável — `collected_without_relatorio` já sinaliza). Não bloquear.
- Remoção dos models pode deixar `ir.model.data`/tabelas órfãs — inerte em dev.

## Testes

1. **test_remove_models** — `afr.qualificacao.step` e `afr.qualificacao.deviation`
   não existem mais em `self.env` (assert KeyError/`not in self.env`).
2. **test_qualif_no_step_deviation_fields** — `afr.qualificacao` não tem mais
   `step_ids`/`deviation_ids`/`step_count`/`deviation_count` em `_fields`.
3. **test_collect_tab_field_present** — `collect_item_ids` continua em `_fields`
   e lista as coletas com `qualif_id` correto (criar qualif + collect.item com
   `qualif_id` → aparece em `qualif.collect_item_ids`).
4. Suíte completa verde (corrigir testes que referenciavam os models removidos).

## Fora de escopo (YAGNI)

- Cleanup de tabelas/`ir.model.data` órfãs no DB (dev; fazer só se/quando produção).
- Backfill de `qualif_id` (já setado nos caminhos de criação).
- Mudança no fluxo de explosão de coletas.
- Reescrita do report além de remover as 2 seções.
