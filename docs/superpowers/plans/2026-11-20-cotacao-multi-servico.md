# Cotação Multi-serviço com Proposta Única — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cotar serviços por unidade (calibração avulsa, NR-13, vazão de exaustores) na mesma cotação das qualificações e emitir uma proposta única com capítulo por serviço e resumo financeiro somando tudo.

**Architecture:** Catálogo novo (`afr.servico.grupo` → `afr.servico`) alimenta linhas `sale.order.line` marcadas `is_service_managed`, criadas por um passo novo do configurador existente. Cada linha tem unidades numeradas (`afr.servico.unidade`). A proposta ganha blocos condicionais (`applies_when`), um bloco `service_group` e o bloco `financial` revivido como emissor de totais; um template novo `TPL-MULTI` junta tudo.

**Tech Stack:** Odoo 16.0, Python 3.9, QWeb (PDF wkhtmltopdf + portal), `TransactionCase`.

**Spec:** `docs/superpowers/specs/2026-11-20-cotacao-multi-servico-design.md` (ler antes de qualquer tarefa).

## Global Constraints

- Todos os caminhos são relativos a `addons/afr_qualificacao/` (git submodule). Rodar `git` **de dentro** desse diretório, nunca da raiz do monorepo.
- Branch de trabalho: `feat/cotacao-multi-servico` (criar a partir de `main` do submodule).
- Commits **somente via subagente `git-commit-push` (haiku)** com `cwd` = diretório do submodule. Não fazer push nem bump de pointer no monorepo até o user testar e aprovar.
- Não editar o módulo `engc_os`; só `_inherit`.
- Versão final do manifest: `16.0.9.3.0` (bump só na Task 10).
- Linha de serviço **nunca** é `is_qualificacao_managed`, nunca tem `equipment_id` nem `qualification_type`.
- Linha de qualificação: `product_uom_qty` = horas. Linha de serviço: `product_uom_qty` = número de unidades, `price_unit` = preço por unidade, `estimated_hours` = horas por unidade.
- Cada tipo de bloco de proposta tem **três** implementações que andam juntas: `reports/templates_blocos/block_*.xml` (PDF), `views/sale_order_portal_template.xml` (portal, cópia inline) e `models/proposal_block.py::_snapshot_html` (editável).
- Arquivo novo de teste precisa de import em `tests/__init__.py`; modelo novo precisa de import em `models/__init__.py`, ACL em `security/ir.model.access.csv` e XML novo listado em `__manifest__.py` (`data`).
- Comando de teste (substituir `<Classe>`):
  `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init --no-http`
  O orquestrador delega runs ao subagente `test-runner`.
- Falhas pré-existentes conhecidas (não são regressão): `TestResourcePlan.test_fleet_single_logger_two_temp_standards`, `TestProposalReport.test_render_equipment_scope_omits_cronograma_footer`, `TestProposalReport.test_render_schedule_block`.
- TDD: teste falhando antes do código, em toda tarefa.

## Review Focus

1. **Cotação só de serviços com template antigo (`TPL-LABQUALI`):** não há bloco `financial` e `equipment_scope` fica oculto. Esperado: a tabela de totais imprime uma vez, no fim. (Task 6)
2. **Mudar a quantidade de uma linha de serviço depois de editar o preço unitário:** o core recalcula `price_unit` pela pricelist. Esperado: preço digitado permanece. (Task 2)
3. **Duplicar uma cotação confirmada:** esperado que a cópia não herde unidades nem números de item. (Task 3)
4. **Reaplicar o configurador sem mexer nos serviços:** esperado que as unidades já identificadas e seus dados sobrevivam intactos. (Task 4)
5. **Bloco filho cujo pai está oculto pela condição** (ex.: QI/QO/QD filhos de "Qualificação Térmica"): esperado que o filho também suma e a numeração dos demais não pule. (Task 5)

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `models/servico.py` (novo) | `afr.servico.grupo`, `afr.servico` |
| `models/servico_unidade.py` (novo) | `afr.servico.unidade` |
| `models/sale_order_line.py` | campos de serviço, guarda de preço, regra de quantidade × unidades |
| `models/sale_order_servico.py` (novo, `_inherit sale.order`) | helpers de serviço da cotação: flags, unidades, tabela por grupo, títulos |
| `models/sale_order.py` | totais, normas, horas, blocos visíveis, gates `is_managed_quote` |
| `models/proposal_template.py`, `models/proposal_block.py` | `applies_when`, `service_group_id`, tipo `service_group`, snapshot |
| `wizards/qualificacao_configurator.py` + `_views.xml` | passo "Outros serviços" |
| `reports/templates_blocos/block_service_group.xml` (novo), `block_financial.xml` (novo), `block_totals.xml`, `block_equipment_scope.xml`, `reports/quotation_template.xml` | PDF |
| `views/sale_order_portal_template.xml` | portal |
| `views/servico_views.xml` (novo), `views/qualificacao_menus.xml`, `views/sale_order_views.xml`, `views/proposal_template_views.xml`, `views/proposal_block_views.xml` | UI |
| `data/servico_seed.xml` (novo), `data/proposal_multi_servico_seed.xml` (novo), `hooks.py`, `migrations/16.0.9.3.0/post-migrate.py` (novo) | seeds e template `TPL-MULTI` |
| `tests/common_servico.py` (novo) + `tests/test_servico_*.py`, `tests/test_proposal_multi_*.py` (novos) | testes |

---

### Task 1: Catálogo de serviços

**Files:**
- Create: `models/servico.py`, `views/servico_views.xml`, `data/servico_seed.xml`, `tests/common_servico.py`, `tests/test_servico_catalog.py`
- Modify: `models/__init__.py`, `security/ir.model.access.csv`, `views/qualificacao_menus.xml`, `__manifest__.py`, `tests/__init__.py`

**Interfaces:**
- Produces:
  - `afr.servico.grupo`: `name` (Char, required, translate), `code` (Char), `sequence` (Integer, default 10), `active`, `company_id`, `chapter_title` (Char, translate; vazio = usa `name`), `unit_label` (Char, default `"unidade"`), `service_ids` (O2M). `_order = "sequence, name"`. Método `_chapter_title() -> str` (`chapter_title or name`).
  - `afr.servico` (`_inherit = "afr.product.service.mixin"`): `name` (required, translate), `code`, `sequence`, `active`, `company_id`, `group_id` (M2O grupo, required, `ondelete="restrict"`), `product_id` (M2O `product.product`, required, domínio serviço vendável), `estimated_hours` (Float, horas por unidade), `scope_description` (Text, translate), `procedure_code` (Char), `procedure_revision` (Char), `standard_ids` (M2M `afr.qualificacao.standard`), `equipment_category_id` (M2O `engc.equipment.category`), `currency_id` (related company). `_order = "group_id, sequence, name"`. Método `_default_unit_price() -> float` (`product_id.list_price`).
  - `tests/common_servico.py::AfrServicoTestCommon(AfrQualificacaoTestCommon)` com: `group_calib` ("Calibração de Instrumentos", sequence 10, unit_label "instrumento"), `group_nr13` ("NR-13", sequence 20), `svc_seladora` (list_price 120, hours 0.5, procedure_code "QPC-008"), `svc_incubadora` (180, 1.0), `svc_nr13` (2400, 8.0, grupo nr13), e `cls._make_order(partner=None)` devolvendo `sale.order` em rascunho para `cls.partner` da base.
- ACL: `group_afr_qualificacao_user` e `sales_team.group_sale_salesman` leitura; `group_afr_qualificacao_manager` CRUD; `group_afr_qualificacao_technician` leitura. Para os dois modelos.
- Seeds (`noupdate="1"`, produtos de serviço com `list_price` 0):

| xmlid do grupo | nome | seq | unit_label |
|---|---|---|---|
| `servico_grupo_calibracao` | Calibração de Instrumentos | 10 | instrumento |
| `servico_grupo_nr13` | NR-13 | 20 | equipamento |
| `servico_grupo_vazao` | Vazão de Exaustores e Trocas de Ar | 30 | exaustor |

| xmlid do serviço | nome | grupo | procedure_code |
|---|---|---|---|
| `servico_calib_sensor_ambiente` | Calibração de sensor de ambiente (termo-higrômetro) | calibracao | QPC-011 |
| `servico_calib_camara_fria` | Calibração de câmara frigorífica | calibracao | — |
| `servico_calib_estufa` | Calibração de estufa | calibracao | — |
| `servico_calib_incubadora_ib` | Calibração de incubadora de indicador biológico | calibracao | — |
| `servico_calib_seladora` | Calibração de seladora de papel grau cirúrgico | calibracao | QPC-008 |
| `servico_nr13_inspecao` | Inspeção NR-13 | nr13 | — |
| `servico_vazao_exaustor` | Verificação de vazão de exaustor e trocas de ar | vazao | — |

- [ ] **Step 1: Teste falhando** em `tests/test_servico_catalog.py`, classe `TestServicoCatalog(AfrServicoTestCommon)`:
  - `test_default_unit_price_from_product`: `self.svc_seladora._default_unit_price() == 120`.
  - `test_chapter_title_falls_back_to_name`: grupo sem `chapter_title` devolve `name`; com valor devolve o valor.
  - `test_product_must_be_service`: criar `afr.servico` com produto `type="consu"` levanta `ValidationError`.
  - `test_seed_loaded`: `env.ref("afr_qualificacao.servico_calib_seladora").group_id == env.ref("afr_qualificacao.servico_grupo_calibracao")` e os 7 serviços existem.
  - `test_salesman_reads_but_cannot_write`: usuário só com `sales_team.group_sale_salesman` lê serviço; `write` levanta `AccessError`.
- [ ] **Step 2:** Rodar `TestServicoCatalog` — falha (modelo inexistente).
- [ ] **Step 3:** Implementar modelos, ACL, seeds, views (tree+form para os dois, form do serviço com abas "Proposta" e "Execução") e menus em Configuração ao lado de "Tipos de Malha".
- [ ] **Step 4:** Rodar `TestServicoCatalog` — passa.
- [ ] **Step 5:** Commit `feat(afr_qualificacao): service catalog (afr.servico, afr.servico.grupo)`.

---

### Task 2: Linha de cotação de serviço

**Files:**
- Create: `models/sale_order_servico.py`, `tests/test_servico_lines.py`
- Modify: `models/sale_order_line.py`, `models/__init__.py`, `tests/__init__.py`, `tests/common_servico.py`

**Interfaces:**
- Consumes: Task 1.
- Produces em `sale.order.line`:
  - `service_id` (M2O `afr.servico`, `ondelete="restrict"`, `copy=True`), `is_service_managed` (Boolean, `copy=True`), `service_group_id` (related `service_id.group_id`, `store=True`).
  - `_service_line_vals(service, qty, unit_price=None, estimated_hours=None) -> dict` (`@api.model`): `product_id`, `name` = `service.name`, `service_id`, `is_service_managed=True`, `product_uom_qty=qty`, `price_unit` (default `service._default_unit_price()`), `estimated_hours` (default `service.estimated_hours`).
  - `_service_hours() -> float`: `product_uom_qty * estimated_hours` (0 para não-serviço).
  - `_compute_price_unit`: acrescentar linhas `is_service_managed` existentes (`l._origin.id`) ao conjunto `frozen` já existente.
  - `@api.constrains`: `is_service_managed` exige `service_id`, e proíbe `is_qualificacao_managed`, `equipment_id` e `qualification_type`.
- Produces em `sale.order` (`models/sale_order_servico.py`):
  - `has_service_lines` (Boolean, compute não-armazenado, depende de `order_line.is_service_managed`, `order_line.display_type`).
  - `is_managed_quote` (Boolean, compute: `has_qualif_lines or has_service_lines`).
  - `_service_lines(group=None) -> sale.order.line` ordenado por (`service_group_id.sequence`, `service_id.sequence`, `id`), filtrando por grupo quando dado.
  - `_service_groups() -> afr.servico.grupo` (grupos presentes, ordenados por `sequence`).
- `tests/common_servico.py`: `cls._add_service(order, service, qty, unit_price=None) -> sale.order.line` (cria via `_service_line_vals`).

- [ ] **Step 1: Teste falhando**, classe `TestServicoLines(AfrServicoTestCommon)`:
  - `test_line_vals_defaults`: linha de `svc_seladora` qty 8 → `price_unit == 120`, `price_subtotal == 960`, `estimated_hours == 0.5`, `_service_hours() == 4.0`.
  - `test_price_survives_qty_change` (Review Focus 2): criar linha com `unit_price=100`, `line.write({"product_uom_qty": 10})` → `price_unit == 100`.
  - `test_flags`: cotação só com serviço → `has_service_lines`, `not has_qualif_lines`, `is_managed_quote`.
  - `test_service_line_cannot_be_qualif`: `write({"is_qualificacao_managed": True})` levanta `ValidationError`; idem `equipment_id`.
  - `test_groups_ordered`: cotação com nr13 + seladora → `_service_groups()` == calib, nr13 nessa ordem.
  - `test_not_pending_qualif`: `order._pending_qualif_lines()` vazio para cotação só de serviço.
- [ ] **Step 2:** Rodar `TestServicoLines` — falha.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar `TestServicoLines` e `TestEquipmentTargetPrice` (regressão do `frozen`) — passam.
- [ ] **Step 5:** Commit `feat(afr_qualificacao): service-managed quotation lines`.

---

### Task 3: Unidades numeradas

**Files:**
- Create: `models/servico_unidade.py`, `tests/test_servico_unidades.py`
- Modify: `models/sale_order_line.py`, `models/sale_order_servico.py`, `models/sale_order.py` (`action_confirm`), `models/__init__.py`, `security/ir.model.access.csv`, `tests/__init__.py`

**Interfaces:**
- Consumes: Task 2.
- Produces `afr.servico.unidade` (`_order = "item_number, sequence, id"`): `line_id` (M2O `sale.order.line`, required, `ondelete="cascade"`), `order_id` (related `line_id.order_id`, store), `service_id` (related, store), `sequence`, `item_number` (Integer, readonly, `copy=False`, 0 = ainda sem número), `equipment_id` (M2O `engc.equipment`), `tag`, `description`, `marca`, `model`, `serial_number`, `location`, `range_spec` (todos Char), `is_identified` (Boolean compute armazenado: `bool(tag or serial_number)`). Onchange de `equipment_id` preenche descrição, marca, modelo, série e local a partir do equipamento (TAG só se o equipamento tiver campo equivalente; conferir em `engc.equipment`).
- ACL de `afr.servico.unidade`: user, manager e salesman CRUD; technician leitura.
- Em `sale.order.line`: `service_unit_ids` (O2M, `copy=False`), `service_unit_count`, `service_unit_identified_count` (computes).
- Em `sale.order`: `service_units_summary` (Char compute, ex.: `"3 de 11 unidades identificadas"`, vazio sem serviço); `_service_sync_units()`; chamada em `action_confirm` antes do `super()`.
- Regras (spec 6.3), implementadas em `_service_sync_units()` e em `sale.order.line.write`/`create` quando `product_uom_qty` muda em linha `is_service_managed`:
  - **Completar:** só em cotação confirmada (`state in ("sale","done")`) ou no `action_confirm`: cria unidades vazias até `int(product_uom_qty)`.
  - **Numerar:** unidades com `item_number == 0` recebem `max(item_number da cotação) + 1`, percorrendo `_service_lines()` e, dentro da linha, (`sequence`, `id`). Número atribuído nunca é alterado nem reaproveitado.
  - **Reduzir** (qualquer estado): apaga unidades não identificadas, da maior para a menor (`item_number`, depois `id`), até caber. Se `service_unit_identified_count > nova qty`, `UserError`: `"A linha %s tem %d unidade(s) identificada(s). Remova as unidades que não serão atendidas antes de reduzir a quantidade para %d."`
  - **Constraint:** `len(service_unit_ids) <= int(product_uom_qty)`.
  - Apagar linha de serviço com unidade identificada: mesmo `UserError` (via `unlink`).

- [ ] **Step 1: Teste falhando**, classe `TestServicoUnidades(AfrServicoTestCommon)`:
  - `test_draft_units_optional`: linha qty 8 em rascunho, 0 unidades, sem erro; `service_units_summary == "0 de 8 unidades identificadas"`.
  - `test_confirm_fills_and_numbers`: seladora qty 3 + nr13 qty 1, confirmar → 4 unidades, `item_number` 1..3 na seladora (grupo calib vem antes) e 4 no nr13.
  - `test_identified_flag`: unidade com `tag="TAG-001"` → `is_identified`; summary conta 1.
  - `test_increase_after_confirm_appends`: após confirmar (1..4), qty da seladora 3→5 → novos números 5 e 6; os antigos intactos.
  - `test_reduce_removes_pending_highest_first`: seladora qty 3 confirmada, identificar a nº 1, reduzir para 1 → sobra só a nº 1.
  - `test_reduce_below_identified_blocks`: 2 identificadas, reduzir para 1 → `UserError`.
  - `test_cancel_draft_reconfirm_keeps_numbers`: `action_cancel`, `action_draft`, `action_confirm` → mesmos ids e números.
  - `test_copy_does_not_carry_units` (Review Focus 3): `order.copy()` → linhas de serviço copiadas, `service_unit_ids` vazio.
  - `test_more_units_than_qty_blocked`: criar 2 unidades em linha qty 1 → `ValidationError`.
  - `test_equipment_onchange_fills`: `unit.equipment_id = equip` + onchange → `serial_number` e `model` do equipamento.
- [ ] **Step 2:** Rodar `TestServicoUnidades` — falha.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar `TestServicoUnidades`, `TestServicoLines`, `TestOptionalAccepted` (regressão do `action_confirm`) — passam.
- [ ] **Step 5:** Commit `feat(afr_qualificacao): numbered service units per quotation line`.

---

### Task 4: Passo "Outros serviços" no configurador

**Files:**
- Create: `tests/test_servico_configurator.py`
- Modify: `wizards/qualificacao_configurator.py`, `wizards/qualificacao_configurator_views.xml`, `security/ir.model.access.csv`, `models/sale_order.py` (`action_open_configurator`), `views/sale_order_views.xml`, `tests/__init__.py`, `tests/test_configurator_steps.py` (ajustar à nova ordem)

**Interfaces:**
- Consumes: `_service_line_vals`, `_service_lines`, regras de unidade da Task 3.
- Produces:
  - `_STEP_ORDER = ["escopo", "servicos", "opcionais", "revisao"]`; selection `step` com rótulos `"1. Escopo"`, `"2. Outros serviços"`, `"3. Opcionais"`, `"4. Revisão"`.
  - `afr.qualificacao.configurator.service` (TransientModel): `wizard_id` (required, cascade), `service_id` (required), `group_id` (related), `qty` (Integer, default 1), `unit_price` (Monetary), `estimated_hours` (Float), `subtotal` (Monetary compute `qty * unit_price`), `currency_id` (related wizard). Onchange de `service_id` preenche `unit_price` e `estimated_hours` do catálogo. ACL igual à de `afr.qualificacao.configurator.optional`.
  - No wizard: `service_line_ids` (O2M), `service_subtotal` (Monetary compute).
  - `_load_from_existing_lines`: carregar `service_line_ids` a partir de `sale_order_id._service_lines()` **antes** do `if not managed: return` existente.
  - `action_next_step`: remover a exigência de equipamento ao sair de "escopo".
  - `action_apply`: validar `"Adicione ao menos 1 equipamento ou 1 serviço."` quando os dois estão vazios; pular todo o trecho de equipamentos quando não há equipamento; `qty < 1` → `UserError`; serviço repetido → `UserError("O serviço %s aparece mais de uma vez.")`. Depois de gravar as linhas de qualificação, chamar `_apply_service_lines()`.
  - `_apply_service_lines()`: upsert por `service_id` nas linhas `is_service_managed` da cotação — cria as novas (`_service_line_vals`), faz `write` de `product_uom_qty`/`price_unit`/`estimated_hours` nas existentes só quando mudou, `unlink` das que saíram. Nunca apaga e recria linha existente. `sequence` das linhas de serviço depois de todas as de qualificação, por grupo e serviço.
  - Rótulo do botão no form e nome da ação: `"Configurar Serviços"`.

- [ ] **Step 1: Teste falhando**, classe `TestServicoConfigurator(AfrServicoTestCommon)` (abrir o wizard como os testes de `test_configurator.py` fazem):
  - `test_services_only_quote`: wizard sem equipamento, 1 linha seladora qty 8 → `action_apply()` cria 1 linha de serviço, `amount_untaxed == 960`, nenhum `UserError`.
  - `test_empty_wizard_blocks`: sem equipamento e sem serviço → `UserError`.
  - `test_next_step_without_equipment`: `action_next_step()` em "escopo" sem equipamento leva a `step == "servicos"`.
  - `test_onchange_fills_price_and_hours`.
  - `test_duplicate_service_blocks`.
  - `test_reapply_preserves_units` (Review Focus 4): aplicar seladora qty 3; criar unidade com `tag="TAG-001"`; reabrir wizard (carrega 1 linha qty 3), aplicar de novo → mesma `sale.order.line` (mesmo id) e a unidade continua lá.
  - `test_reapply_updates_qty_and_price`: reabrir, mudar qty 3→5 e preço 120→100, aplicar → mesmo id de linha, `product_uom_qty == 5`, `price_unit == 100`.
  - `test_remove_service_with_identified_unit_blocks`: tirar do wizard o serviço com unidade identificada → `UserError`.
  - `test_mixed_quote_keeps_qualif_behavior`: 1 equipamento com QI + 1 serviço → linhas de qualificação criadas como antes e linha de serviço presente; reaplicar recria as de qualificação e mantém o id da de serviço.
- [ ] **Step 2:** Rodar `TestServicoConfigurator` — falha.
- [ ] **Step 3:** Implementar; na view, novo `<div attrs="{'invisible': [('step','!=','servicos')]}">` com lista editável (Serviço | Grupo | Qtd | Unitário | Horas/un. | Total) e subtotal; no passo "revisao", bloco com as linhas de serviço e o subtotal.
- [ ] **Step 4:** Rodar `TestServicoConfigurator`, `TestConfiguratorSteps`, `TestConfigurator`, `TestWizardSoParity` — passam.
- [ ] **Step 5:** Commit `feat(afr_qualificacao): "Outros serviços" step in the configurator`.

---

### Task 5: Blocos condicionais

**Files:**
- Create: `tests/test_proposal_multi_conditions.py`
- Modify: `models/proposal_template.py`, `models/proposal_block.py`, `models/sale_order.py` (`_seed_proposal_blocks`, `_proposal_block_numbering`), `reports/quotation_template.xml`, `views/sale_order_portal_template.xml`, `views/proposal_template_views.xml`, `views/proposal_block_views.xml`, `views/sale_order_views.xml`, `tests/__init__.py`

**Interfaces:**
- Consumes: `has_service_lines`, `_service_groups()` (Task 2).
- Produces:
  - Constante em `models/proposal_template.py`: `PROPOSAL_APPLIES_WHEN = [("always","Sempre"),("qualification","Quando há qualificação"),("service_group","Quando há serviço do grupo")]`.
  - Em `afr.proposal.template.line` e `afr.proposal.block`: `applies_when` (Selection, default `"always"`, required), `service_group_id` (M2O `afr.servico.grupo`, `ondelete="restrict"`). Constraint: `applies_when == "service_group"` exige `service_group_id`.
  - `afr.proposal.block._is_applicable() -> bool`: `always` → True; `qualification` → `sale_order_id.has_qualif_lines`; `service_group` → grupo em `sale_order_id._service_groups()`. Se tem `parent_id`, exige também `parent_id._is_applicable()`.
  - `afr.proposal.block.is_applicable` (Boolean compute não-armazenado) para a view.
  - `sale.order._proposal_visible_blocks() -> afr.proposal.block`: `included` e `_is_applicable()`, na ordem do modelo.
  - `_proposal_block_numbering()` passa a numerar `_proposal_visible_blocks()`.
  - `_seed_proposal_blocks` copia `applies_when` e `service_group_id`.
  - PDF e portal passam a iterar `doc._proposal_visible_blocks()` no lugar de `proposal_block_ids.filtered('included')` (todas as ocorrências, inclusive as condições `t-if` do layout e o sumário/TOC se houver).
  - Views: colunas `applies_when` e `service_group_id` (este `invisible` quando não `service_group`) nas listas de linhas de template e de blocos; na lista de blocos do form da cotação, `decoration-muted="not is_applicable"`.

- [ ] **Step 1: Teste falhando**, classe `TestProposalMultiConditions(AfrServicoTestCommon)` — montar um template de teste com: A static always; B static qualification com filho B1; C static service_group=calib; D static service_group=nr13:
  - `test_services_only_hides_qualification`: cotação com seladora → visíveis A e C.
  - `test_child_follows_parent` (Review Focus 5): B oculto ⇒ B1 oculto mesmo com `applies_when="always"`.
  - `test_numbering_skips_hidden`: números de A e C são `"1"` e `"2"`.
  - `test_qualification_only`: cotação só com qualificação (fixture da base) → A, B, B1.
  - `test_included_false_still_hidden`: C com `included=False` não aparece.
  - `test_service_group_requires_group`: `ValidationError`.
  - `test_seed_copies_condition`: bloco criado por `_seed_proposal_blocks` tem o mesmo `applies_when`/`service_group_id` da linha.
  - `test_pdf_omits_hidden_block`: renderizar o HTML do relatório de cotação (mesmo helper de `tests/test_proposal_report.py`) e afirmar que o título de B não está e o de C está.
- [ ] **Step 2:** Rodar — falha.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar `TestProposalMultiConditions`, `TestProposalReport`, `TestProposalBuilder`, `TestPortalOptional` — passam (salvo as pré-existentes).
- [ ] **Step 5:** Commit `feat(afr_qualificacao): conditional proposal blocks (applies_when)`.

---

### Task 6: Resumo financeiro multi-serviço e emissor único de totais

**Files:**
- Create: `reports/templates_blocos/block_financial.xml`, `tests/test_proposal_multi_totals.py`
- Modify: `models/sale_order.py` (`_qualif_additional_lines`, `_qualif_proposal_totals`, `_qualif_grand_total_html`, `_compute_qualif_subtotals_html` e gates), `models/sale_order_form_panels.py`, `reports/templates_blocos/block_totals.xml`, `reports/templates_blocos/block_equipment_scope.xml`, `reports/quotation_template.xml`, `views/sale_order_portal_template.xml`, `views/sale_order_views.xml`, `__manifest__.py`, `tests/__init__.py`

**Interfaces:**
- Consumes: `_service_lines`, `_service_groups`, `is_managed_quote`, `_proposal_visible_blocks`.
- Produces:
  - `_qualif_additional_lines`: pular linhas `is_service_managed`.
  - `_qualif_proposal_totals()` ganha a chave `"service_groups": [{"group": rec, "name": group._chapter_title(), "amount": float}]` (só grupos com valor ≠ 0) e o `residual` desconta a soma delas.
  - `_qualif_total_rows() -> list[tuple[str, float]]` — **fonte única das linhas do resumo**, nesta ordem: `("Valor total dos Serviços de Qualificação", equip_total)` só se `has_qualif_lines`; uma por grupo de serviço; adicionais; `("Outros", residual)` se ≠ 0; `("Descontos", -discount_amount)` se ≠ 0. Devolve `[]` quando o resultado teria uma única linha (aí só o total geral imprime).
  - `_qualif_grand_total_html` e `qq_totals_table` passam a iterar `_qualif_total_rows()`; a linha final continua `"Valor Geral da Proposta"` = `amount_untaxed`.
  - `_proposal_totals_emitter() -> afr.proposal.block` (vazio ou 1 registro): primeiro bloco visível `financial`; senão o primeiro visível `equipment_scope`; senão vazio.
  - `block_financial.xml`, template `qq_block_financial`: seção com título do bloco + `t-call qq_totals_table`, só quando `block == doc._proposal_totals_emitter()`.
  - `block_equipment_scope.xml`: o `t-call qq_totals_table` só quando `block == doc._proposal_totals_emitter()`.
  - `quotation_template.xml` e portal: ramo `financial`; e, depois do laço de blocos, `t-call qq_totals_table` quando `not doc._proposal_totals_emitter()` e `doc.is_managed_quote`.
  - Trocar `has_qualif_lines` por `is_managed_quote` em: portal (as 3 condições do inherit), `_find_mail_template`, as 2 condições de `quotation_template.xml`, `_compute_qualif_subtotals_html`, e no form os elementos de totais/resumo e a aba de blocos. Painéis que são de alvo por equipamento (`sale_order_form_panels.py` e os `attrs` ligados a alvo de preço/tempo) continuam em `has_qualif_lines`.
  - `action_edit_block` continua recusando `financial` (não mexer).

- [ ] **Step 1: Teste falhando**, classe `TestProposalMultiTotals(AfrServicoTestCommon)`:
  - `test_rows_multi_front`: 1 equipamento com QI (valor conhecido da fixture) + seladora 8×120 + nr13 1×2400 + linha manual "Despesas de viagem" 500 → `_qualif_total_rows()` == `[("Valor total dos Serviços de Qualificação", X), ("Calibração de Instrumentos", 960), ("NR-13", 2400), ("Despesas de viagem", 500)]` e a soma == `amount_untaxed`.
  - `test_service_lines_not_double_counted`: nenhuma linha de serviço aparece em `totals["adicionais"]`; `totals["residual"] == 0`.
  - `test_single_front_prints_only_grand_total`: só seladora → `_qualif_total_rows() == []`.
  - `test_qualification_only_unchanged`: cotação só de qualificação com 1 adicional → mesmas linhas de antes (rótulo de qualificação + adicional).
  - `test_optional_not_accepted_excluded`: opcional com `optional_accepted=False` não aparece nem soma; aceito aparece.
  - `test_emitter_prefers_financial`: template com `equipment_scope` + `financial` em cotação mista → emissor é o `financial`.
  - `test_emitter_falls_back_to_scope`: template sem `financial`, cotação com qualificação → emissor é `equipment_scope`.
  - `test_totals_printed_exactly_once` (Review Focus 1), três cenários, contando ocorrências de `"Valor Geral da Proposta"` no HTML do PDF: (a) `TPL-LABQUALI` + só qualificação → 1; (b) `TPL-LABQUALI` + só serviços → 1; (c) template com `financial` + cotação mista → 1.
  - `test_portal_and_mail_gate`: cotação só de serviço → `_find_mail_template()` devolve `afr_qualificacao.email_template_proposal_labquali`.
- [ ] **Step 2:** Rodar — falha.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar `TestProposalMultiTotals`, `TestProposalReport`, `TestQuotationReport`, `TestQualifDiscount`, `TestScopeTable`, `TestCotacaoFormRefactor`, `TestPortalOptional` — passam.
- [ ] **Step 5:** Commit `feat(afr_qualificacao): multi-service financial summary with single totals emitter`.

---

### Task 7: Bloco `service_group`, normas, horas e títulos

**Files:**
- Create: `reports/templates_blocos/block_service_group.xml`, `tests/test_proposal_multi_service_group.py`
- Modify: `models/proposal_template.py` (`PROPOSAL_BLOCK_KINDS`), `models/proposal_block.py` (`_snapshot_html`, `_html_service_group`), `models/sale_order_servico.py`, `models/sale_order.py` (`_compute_qualif_standard_ids`, `_qualif_estimated_hours`, `_qualif_schedule_rows`), `reports/quotation_template.xml`, `reports/templates_blocos/block_schedule.xml`, `views/sale_order_portal_template.xml`, `__manifest__.py`, `tests/__init__.py`

**Interfaces:**
- Consumes: Tasks 2, 3, 5.
- Produces:
  - `PROPOSAL_BLOCK_KINDS` += `("service_group", "Serviços do Grupo")`. Constraint: bloco/linha `service_group` exige `service_group_id`.
  - `sale.order._service_group_table(group) -> dict`:
    `{"group": group, "rows": [{"item": int (1..n na tabela), "line": sol, "name": str, "description": service.scope_description or "", "procedure": "QPC-008 rev. 00" ou "", "qty": float, "price_unit": float, "subtotal": float}], "subtotal": float, "hours": float, "days_label": str ou "", "units": afr.servico.unidade identificadas do grupo, por item_number}`.
    `days_label` = `_qualif_days_label(_qualif_days_from_hours(hours, self.env["engc.equipment"]))` quando `hours > 0` (conferir que `_qualif_work_hours_per_day` tolera equipamento vazio; senão 8 h/dia).
  - `qq_block_service_group` (PDF): título do bloco; tabela `qq-table` Item | Serviço (nome + descrição + procedimento em linha menor) | Qtd | Valor Unitário | Valor Total; rodapé `qq-total-table` com `Subtotal <título do grupo>` e, se houver, `Previsão de <days_label> de serviço`; se `units`: subtítulo "Relação de <unit_label>s" e tabela Item (`item_number` ou "—") | Identificação | Descrição | Marca / Modelo | Série | Local. Não renderiza nada se o grupo não tem linhas.
  - Mesmo conteúdo no portal e em `_html_service_group(order)` (registrado no dicionário de `_snapshot_html`).
  - `_compute_qualif_standard_ids`: incluir `service_id.standard_ids` das linhas `is_service_managed` (e a dependência).
  - `_qualif_estimated_hours(equipment=None)`: quando `equipment` é `None`, somar `_service_hours()` das linhas de serviço.
  - `_qualif_schedule_rows()`: acrescentar uma linha por grupo de serviço `{"equipment": False, "label": group._chapter_title(), "hours": h, "work_hours_per_day": 8.0, "days": h / 8.0}`; os três renderizadores do bloco `schedule` usam `row.get("label") or row["equipment"].display_name`.
  - `sale.order._proposal_service_titles() -> str`: `"Qualificação Térmica"` se `has_qualif_lines`, mais `_chapter_title()` de cada grupo presente, unidos por `", "` e `" e "` antes do último. Vazio se nada.

- [ ] **Step 1: Teste falhando**, classe `TestProposalMultiServiceGroup(AfrServicoTestCommon)`:
  - `test_table_rows_and_subtotal`: seladora 8×120 + incubadora 3×180 → 2 rows, itens 1 e 2, `subtotal == 1500`, `hours == 7.0`, `days_label` não vazio; row da seladora com `procedure` contendo `"QPC-008"`.
  - `test_units_only_identified`: confirmar, identificar 1 unidade → `len(table["units"]) == 1`.
  - `test_render_pdf`: bloco `service_group` do grupo calib no HTML contém "Calibração de seladora", o subtotal formatado e **não** contém "Relação de" sem unidade identificada; com unidade `tag="TAG-001"` contém "TAG-001".
  - `test_render_absent_group_empty`: bloco do grupo nr13 em cotação sem nr13 (forçando `applies_when="always"`) não imprime tabela.
  - `test_snapshot_html`: `block._snapshot_html()` contém "Calibração de seladora".
  - `test_standards_include_services`: serviço com `standard_ids` → norma em `order.qualif_standard_ids`.
  - `test_estimated_hours_include_services`: `_qualif_estimated_hours()` == horas de qualificação + 7.0.
  - `test_service_titles`: mista → `"Qualificação Térmica, Calibração de Instrumentos e NR-13"`; só seladora → `"Calibração de Instrumentos"`.
  - `test_title_expression_renders`: `order._render_proposal_block_body("<p>{{ doc._proposal_service_titles() }}</p>")` contém "Calibração de Instrumentos".
- [ ] **Step 2:** Rodar — falha.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar `TestProposalMultiServiceGroup`, `TestProposalReport`, `TestProposalBlockEdit`, `TestEstimatedHours` — passam.
- [ ] **Step 5:** Commit `feat(afr_qualificacao): service_group proposal block`.

---

### Task 8: Template `TPL-MULTI` e textos

**Files:**
- Create: `data/proposal_multi_servico_seed.xml`, `migrations/16.0.9.3.0/post-migrate.py`, `tests/test_proposal_multi_template.py`
- Modify: `hooks.py`, `__manifest__.py` (data), `tests/__init__.py`

**Interfaces:**
- Consumes: Tasks 1, 5, 6, 7.
- Produces:
  - Seções novas (`afr.proposal.section`, `document_type="proposal"`, `noupdate="1"`):
    - `proposal_section_objetivo_multi` (SEC-OBJETIVO-MULTI, categoria `objetivo`): `Esta proposta tem por objetivo o fornecimento de serviços de {{ doc._proposal_service_titles() }}.`
    - `proposal_section_grp_calibracao` (SEC-GRP-CALIB, `tecnico`): texto de calibração a partir de `sec_vc_procedimento` + `sec_vc_metodologia` (definição de calibração, certificado com incerteza 95 % e fator K, padrões rastreados à RBC/INMETRO, entrega do certificado de calibração por instrumento).
    - `proposal_section_grp_nr13` (SEC-GRP-NR13, `tecnico`) e `proposal_section_grp_vazao` (SEC-GRP-VAZAO, `tecnico`): rascunho de um parágrafo cada, começando por `[REVISAR — texto provisório]`.
  - `hooks.py`: `PROPOSAL_MULTI_TEMPLATE_LINES` e `_install_proposal_multi_template(env)`, idempotente pelo xmlid `afr_qualificacao.proposal_template_multi` (cria template `name="Proposta Multi-serviço"`, `code="TPL-MULTI"`, `sequence=1`, linhas com xmlid `proposal_template_multi_<sufixo>`, `noupdate=True`, mesmo padrão de `_install_proposal_template_seed`). Chamado de `_install_proposal_template_seed` **antes** do `return` antecipado e de `migrations/16.0.9.3.0/post-migrate.py`.
  - Linhas (sufixo, seq, tipo, seção, page_break, pai, applies_when, grupo, título):

| suf | seq | tipo | seção | pb | pai | aparece | grupo | título |
|---|---|---|---|---|---|---|---|---|
| m01 | 10 | static | proposal_section_objetivo_multi | T | — | always | — | — |
| m02 | 20 | static | proposal_section_metodologia | F | — | always | — | — |
| m03 | 30 | standards_table | — | F | — | always | — | — |
| m04 | 40 | static | proposal_section_normas | F | — | always | — | — |
| m05 | 50 | static | proposal_section_qualif_termica | F | — | qualification | — | — |
| m06 | 60 | static | proposal_section_qi | F | m05 | qualification | — | — |
| m07 | 70 | static | proposal_section_qo | F | m05 | qualification | — | — |
| m08 | 80 | static | proposal_section_qd | F | m05 | qualification | — | — |
| m09 | 90 | static | proposal_section_validadores | F | — | qualification | — | — |
| m10 | 100 | static | proposal_section_entregaveis | F | — | qualification | — | — |
| m11 | 110 | equipment_scope | — | T | — | qualification | — | — |
| m12 | 120 | static | proposal_section_grp_calibracao | T | — | service_group | calibracao | Calibração de Instrumentos |
| m13 | 130 | service_group | — | F | m12 | service_group | calibracao | Serviços |
| m14 | 140 | static | proposal_section_grp_nr13 | T | — | service_group | nr13 | NR-13 |
| m15 | 150 | service_group | — | F | m14 | service_group | nr13 | Serviços |
| m16 | 160 | static | proposal_section_grp_vazao | T | — | service_group | vazao | Vazão de Exaustores e Trocas de Ar |
| m17 | 170 | service_group | — | F | m16 | service_group | vazao | Serviços |
| m18 | 180 | financial | — | T | — | always | — | Resumo Financeiro |
| m19 | 190 | static | proposal_section_condicoes | F | — | always | — | — |
| m20 | 200 | static | proposal_section_responsabilidades | T | — | always | — | — |
| m21 | 210 | static | proposal_section_credenciais | F | — | always | — | — |
| m22 | 220 | static | sec_dados_cadastrais | F | — | always | — | — |
| m23 | 230 | acceptance | — | T | — | always | — | — |
| m24 | 240 | static | proposal_section_aceite | F | — | always | — | — |

  - `TPL-LABQUALI` e `TPL-VENDA-CALIB` não são alterados.

- [ ] **Step 1: Teste falhando**, classe `TestProposalMultiTemplate(AfrServicoTestCommon)`:
  - `test_template_installed`: `env.ref("afr_qualificacao.proposal_template_multi")` existe, 24 linhas, `sequence == 1`.
  - `test_is_default_for_new_quotes`: `env["sale.order"]._default_proposal_template()` é o `TPL-MULTI`.
  - `test_old_template_untouched`: `proposal_template_labquali` mantém o número de linhas e nenhuma tem `applies_when != "always"`.
  - `test_idempotent`: chamar `_install_proposal_multi_template(env)` de novo não cria linhas.
  - `test_services_only_document`: cotação com seladora + nr13 via `TPL-MULTI` → títulos visíveis incluem "Calibração de Instrumentos" e "NR-13", não incluem "Qualificação Térmica" nem "Vazão de Exaustores"; HTML contém "Valor Geral da Proposta" 1 vez.
  - `test_mixed_document_order`: cotação mista → no HTML, "Qualificação Térmica" vem antes de "Calibração de Instrumentos", que vem antes de "Resumo Financeiro".
  - `test_objective_cites_services`: HTML contém `"serviços de Calibração de Instrumentos e NR-13"`.
  - `test_existing_quote_keeps_template`: cotação criada com `proposal_template_labquali` e blocos semeados não muda de template depois da instalação.
- [ ] **Step 2:** Rodar — falha.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar `TestProposalMultiTemplate`, `TestProposalCatalog`, `TestProposalBuilder`, `TestProposalVendaCalibracao` — passam. Testes antigos que assumiam `TPL-LABQUALI` como default devem passar a setar o template explicitamente no setup (não mudar a regra de default).
- [ ] **Step 5:** Commit `feat(afr_qualificacao): multi-service proposal template (TPL-MULTI)`.

---

### Task 9: Aba de unidades e acabamento do form

**Files:**
- Modify: `views/sale_order_views.xml`, `views/servico_views.xml`, `tests/test_servico_unidades.py`

**Interfaces:**
- Consumes: Tasks 2, 3, 4.
- Produces:
  - Aba `<page string="Unidades" name="service_units">` no form da cotação, visível só com `has_service_lines`: `service_units_summary` no topo e lista editável de `afr.servico.unidade` da cotação (campo O2M novo em `sale.order`: `service_unit_ids`, `inverse_name="order_id"`), colunas Item | Serviço (linha, obrigatório, domínio linhas `is_service_managed` da cotação) | Identificação | Descrição | Marca | Modelo | Série | Local | Faixa | Equipamento. `decoration-success="is_identified"`.
  - Na aba "Linhas (Comercial)", as linhas de serviço aparecem com serviço, quantidade, unitário e subtotal editáveis (quantidade e unitário), sem os campos de equipamento/alvo.
  - Como o `order_id` da unidade é related de `line_id`, criar pela aba exige escolher a linha; o related preenche a cotação.

- [ ] **Step 1: Teste falhando** em `TestServicoUnidades`:
  - `test_order_unit_o2m`: `order.service_unit_ids` devolve as unidades de todas as linhas, ordenadas por `item_number`.
  - `test_view_loads`: `env["sale.order"].get_view(view_id=env.ref("afr_qualificacao.<id da view de form herdada>").id)` não levanta e o `arch` contém `name="service_units"`.
- [ ] **Step 2:** Rodar — falha.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar `TestServicoUnidades`, `TestCotacaoFormRefactor` — passam.
- [ ] **Step 5:** Commit `feat(afr_qualificacao): service units tab on the quotation form`.

---

### Task 10: Versão, suíte completa e validação no navegador

**Files:**
- Modify: `__manifest__.py` (`"version": "16.0.9.3.0"` + linha de roadmap na `description`)

- [ ] **Step 1:** Bump de versão.
- [ ] **Step 2:** Suíte completa do módulo via `test-runner` (`--test-tags /afr_qualificacao`). Esperado: só as 3 falhas pré-existentes listadas em Global Constraints.
- [ ] **Step 3:** Atualizar o db de desenvolvimento (`odoo-labquali`, `-u afr_qualificacao`) e reiniciar o container para assets.
- [ ] **Step 4:** Validar com `agent-browser` em `http://localhost:8083` (logout antes do login):
  1. Configuração → Serviços: os 7 serviços e 3 grupos aparecem; pôr preço em seladora (120), incubadora (180) e NR-13 (2400).
  2. Cotação nova → "Configurar Serviços" → pular Escopo sem equipamento → Outros serviços: seladora 8, incubadora 3, NR-13 1 → aplicar. Total R$ 3.900,00.
  3. Aba Unidades: identificar 1 seladora (TAG TAG-001). Contador "1 de 12 unidades identificadas".
  4. Imprimir a proposta: capítulos Calibração e NR-13 presentes, sem capítulo de Qualificação nem de Vazão; "Relação de instrumentos" com TAG-001; resumo com 2 linhas + Valor Geral, uma única vez.
  5. Reabrir o configurador, adicionar 1 equipamento com QI + opcional de viagem aceito, aplicar: capítulo de Qualificação aparece, resumo com qualificação, calibração, NR-13 e viagem; unidade TAG-001 continua lá.
  6. Confirmar: unidades numeradas 1..12.
  7. Portal do cliente da mesma cotação: mesmos capítulos e mesmo resumo.
  8. Cotação antiga com `TPL-LABQUALI` só de qualificação: PDF igual ao de antes (totais no fim do escopo, uma vez).
- [ ] **Step 5:** Commit `chore(afr_qualificacao): bump to 16.0.9.3.0`. **Sem push**: entregar ao user para teste; push, merge em `main` e bump do pointer no monorepo só depois do OK dele.
