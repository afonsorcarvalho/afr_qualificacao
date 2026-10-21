# Template de cotação por cliente + tempo-alvo + reajuste — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Per-client, per-category quotation templates auto-applied in the configurator, with agreed price and time targets (rateio), "Gravar como padrão deste cliente", and anniversary price readjustment (BCB index / % / absolute).

**Architecture:** Extend `afr.qualificacao.config.template` with `partner_id`; resolver mirrors procedimento's `_resolve_for_equipment`; time rateio mirrors `price_allocation.allocate_target`; readjust = wizard + history model + daily cron; BCB SGS via `urllib.request`.

**Tech Stack:** Odoo 16, Python, QWeb XML views, TransactionCase.

**Spec:** `addons/afr_qualificacao/docs/superpowers/specs/2026-10-21-template-cotacao-por-cliente-design.md` (binding; §6 lists controller calls).

## Global Constraints
- Repo `addons/afr_qualificacao`, branch `main`; commit + push per task; never stage untracked junk (`*.png`, `.superpowers/`, `migrations/16.0.8.9.4/`, `__pycache__`). Never bare `git stash`.
- Manifest version → `16.0.9.0.0` (Task 1); later tasks bump PATCH (`16.0.9.0.N`).
- Tests: `docker exec odoo_engenapp-web-qualificacao-1 /entrypoint.sh -d levantamento_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Class> --stop-after-init --no-http`; full module suite once before each commit (baseline 1434 green).
- UI copy pt-BR, user language: "Preço combinado", "Tempo combinado (dias)", "Padrão deste cliente", "Reajustar preços combinados". Spec §4.7 usability rules apply to every view.
- No `sudo()` except where existing code already does; BCB HTTP timeout 10 s, mocked in tests.
- Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus
- Re-apply of the configurator on an existing quote keeps user-typed price/time targets and does not re-inject template targets the user zeroed.
- Applying time target with an agreed price keeps the equipment total exactly equal to the target (cent-exact).
- Client template uniqueness ignores archived templates; contact (child) partner on the SO resolves to the commercial partner's templates.
- BCB down/timeout → wizard still usable via manual %; no exception to the user.
- Readjust never touches existing sale orders, only templates of that client.

---

### Task 1: Client template model, resolver, partner tab
**Files:** `models/config_template.py`, `models/res_partner.py`, `views/config_template_views.xml` (or existing view file), `views/res_partner_views.xml`, `__manifest__.py`, `tests/test_client_config_template.py`.
**Interfaces (produces):**
- `afr.qualificacao.config.template.partner_id` (M2o res.partner, domain commercial partners, index).
- `res.partner.afr_config_template_ids` (O2m inverse).
- `config.template._resolve_for_equipment(equipment, partner, company) -> (template_or_empty, origin)` with origin ∈ `{'cliente','categoria','none'}`; partner normalized to `commercial_partner_id`; category template = lowest `sequence` with `partner_id=False`.
- Python constraint: ≤1 active template per (partner_id, equipment_category_id, company_id) when partner_id set; `company_id` required.
- [ ] Failing tests: resolver order (client > category > none), child contact → commercial partner, other company ignored, archived client template doesn't block a new one, constraint raises on duplicate active.
- [ ] Implement + partner tab "Templates de cotação" (only commercial partners; list: categoria, preço combinado, tempo combinado, ativo; opening the template form). Template form shows "Cliente" field only when set or in a dedicated group.
- [ ] Suite green; commit + push.

### Task 2: Time target rateio on the quotation
**Files:** `models/time_allocation.py` (new, pure function like price_allocation), `models/sale_order_line.py`, `models/sale_order.py`, views of SO lines/section, `tests/test_time_target.py`.
**Interfaces:**
- `time_allocation.allocate_hours(target_hours: float, weights: list[float], step: float = 0.25) -> list[float]` — proportional; line totals multiples of `step`; residual on largest; all-zero weights → equal split; exact sum.
- Section line fields: `equipment_target_days` (Float), `equipment_target_hours` (computed = days × work_hours_per_day), `equipment_time_state` ∈ none/ok/drift (like `equipment_target_state`).
- `sale.order.line._apply_equipment_time_target()`: base lines = `_rateio_base_lines()`; weight = `qualif_cycle_qty × estimated_hours`; set `estimated_hours = line_hours / qualif_cycle_qty`; then if `equipment_target_price` → `_apply_equipment_target()`.
- Buttons `action_apply_equipment_time_target` (section) and `sale.order.action_apply_all_equipment_time_targets`.
- [ ] Failing tests: allocate_hours cases (proportional, 0.25 steps, exact sum, zero weights, qty>1 per-cycle derived); with price target the equipment total stays equal to target after time change; without price target price follows hours.
- [ ] Implement + UI next to price target ("Tempo combinado (dias)" + button), drift badge.
- [ ] Suite green; commit + push.

### Task 3: Configurator auto-apply + targets from template + re-apply safety
**Files:** `wizards/qualificacao_configurator.py` (equipment line `afr.qualificacao.configurator.equipment`, `action_apply`, bulk `AfrQualificacaoConfiguratorBulk`), configurator views, `tests/test_configurator_client_template.py`.
**Interfaces:**
- Equipment line: `@api.onchange('equipment_id')` → if no `config_template_id`, use `_resolve_for_equipment(equipment, wizard.sale_order partner, company)`; field `template_origin` (Selection cliente/categoria/none, shown as badge "Padrão do cliente"/"Padrão da categoria").
- `action_apply`: capture `equipment_target_days` like `alvos_por_equip`; for equipment **new to the SO** with template `price_base>0`/`estimated_days>0`, set targets; after recreating lines, apply time then price targets where set.
- Bulk wizard: boolean `use_partner_template` (default True when any equipment resolves a template) — per equipment, resolved template overrides bulk scope; else bulk scope as today.
- Lines loaded from an existing SO without template stay without template.
- [ ] Failing tests: onchange picks client then category template; manual choice not overwritten; new equipment gets template targets; re-apply keeps user targets and doesn't restore zeroed ones; bulk with/without option.
- [ ] Implement; suite green; commit + push.

### Task 4: "Gravar como padrão deste cliente"
**Files:** `wizards/qualificacao_configurator.py` (reuse `action_save_as_template` internals), views, `tests/test_save_client_template.py`.
**Interfaces:** equipment-line button `action_save_as_client_default()` → create or update the client template for (commercial partner, equipment category, company) from the line scope (QI/QO/QS, qo/qd/calib/qd_point lines, hours, work_hours_per_day) + `price_base` = price target or current equipment total + `estimated_days` = time target or total hours / work_hours_per_day; when one exists, confirmation dialog "Substituir o padrão de <categoria> de <cliente>?" (small confirm wizard). Returns notification.
- [ ] Failing tests: creates; updates existing (no duplicate); price_base/estimated_days rules; requires equipment category (UserError in pt-BR otherwise).
- [ ] Implement; suite green; commit + push.

### Task 5: Readjustment (index / % / absolute) + history + anniversary activity
**Files:** `models/res_partner.py`, `models/reajuste.py` (`afr.qualificacao.reajuste` + `.line`), `models/bcb_index.py` (fetch helper), `wizards/reajuste_wizard.py` + view, `data/ir_cron_reajuste.xml`, security ACL, `tests/test_reajuste.py`.
**Interfaces:**
- Partner: `afr_reajuste_data` (Date), `afr_reajuste_indice` (Selection ipca/igpm/inpc, default ipca), O2m history, button "Reajustar preços combinados".
- `bcb_index.accumulated_12m(serie: int, ref_month: date) -> float` (percent) — SGS `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa`, 12 months ending the month before ref; Π(1+v/100)−1; series IPCA 433, IGP-M 189, INPC 188; raises `UserError` on failure (wizard catches → manual mode).
- Wizard: tipo (indice/percentual/valor), indice, percentual (computed from BCB or typed), valor; preview O2m (template, categoria, antes, depois); `action_confirm` writes `price_base` rounded to cents, creates history + lines, posts chatter on partner.
- Cron daily: partners with day/month of `afr_reajuste_data` == today and client templates with price_base>0 → `mail.activity` "Reajustar preços combinados" for partner `user_id` or admin (no duplicate open activity).
- [ ] Failing tests (mock HTTP): accumulated math; failure → manual mode; % / value / index application; preview == applied; history rows; only that client's templates; SOs untouched; cron creates one activity, no duplicates.
- [ ] Implement; suite green; commit + push.

### Task 6: Usability pass + browser validation
- [ ] Review every new/changed view against spec §4.7 (hide advanced fields, labels, badges, top buttons, help text); fix.
- [ ] Upgrade `qualificacao-dev` (`-u afr_qualificacao`), restart, validate with agent-browser: client tab, configurator auto-apply badge, time/price targets, save as client default, readjust wizard (with BCB live + forced failure). Screenshots to scratchpad.
- [ ] Commit + push; bump monorepo pointer (agent from monorepo root, only the gitlink).

---
## Fase 2 (pedidos do user após teste, 2026-10-21)

### Task 7: "Gravar como padrão deste cliente" na linha de seção da cotação
- Botão na linha de seção do equipamento (sale.order.line seção), qualquer estado do SO, só `group_afr_qualificacao_manager` (groups= + checagem servidor). Escopo reconstruído das linhas managed da seção (mesma lógica de `_load_from_existing_lines`, extrair helper compartilhado), preço = `equipment_target_price` ou total atual da seção; dias = `equipment_target_days` ou horas/jornada. Reusa `_write_client_default` / confirm wizard (substituir com antes/depois). Testes: SO confirmado grava; não-gestor bloqueado; escopo igual ao gravado pelo configurador.

### Task 8: "Copiar padrões de outro cliente"
- Wizard a partir da aba "Templates de cotação" (só gestor): cliente de origem (parceiro comercial, ≠ destino), lista de categorias da origem com checkbox; para categorias já existentes no destino mostra antes/depois e pede confirmação de substituição. Copia escopo completo + `price_base` + `estimated_days` para templates com `partner_id` = destino, mesma empresa. Testes: copia; substitui; não toca origem; não-gestor bloqueado; outra empresa ignorada.

### Task 9: Equipamentos do cliente — lista editável + regras relaxadas
- Smart button "Equipamentos" do cliente (views/engc_equipment_views.xml F10.6) abre lista **editável inline** (`editable="bottom"`) com TAG, Categoria, Marca, Modelo, Nº de série, Local, Apelido; criação já com `client_id` do cliente; link para ficha completa.
- Herança em afr_qualificacao (não alterar engc_os): `marca_id`, `model`, `serial_number` `required=False`; remover `_sql_constraints` `serial_marca_company_id_no_uniq` (override `_sql_constraints` + pre/post-migrate dropando a constraint, guarda se existe); `_compute_name` robusto: junta partes não vazias (categoria, modelo, série, marca); fallback TAG, depois "Equipamento <id>". Bump 16.0.9.1.0. Testes: criar só com categoria; série repetida mesma marca permitida; nome com partes faltando.

### Task 10: Levantamento acompanha (repos afr_qualificacao_levantamento + pwa)
- Backend `survey_api_push.EQUIPMENT_CREATE_REQUIRED = ("category_id",)`; testes ajustados; bump 16.0.1.0.1.
- PWA `missingRequired` → só categoria; aviso "Preencha a categoria para enviar"; testes.
