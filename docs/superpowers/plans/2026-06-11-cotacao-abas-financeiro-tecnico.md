# Abas Cotação — Resumo Financeiro + Detalhes Técnicos Ricos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar "TOTAL GERAL DA PROPOSTA" ao resumo financeiro e exibi-lo no rodapé das abas Comercial/Opcionais; enriquecer a aba Detalhes Técnicos com Escopo + Tabela de Ciclos + Tempo de Execução (read-only, reusando métodos de dados do relatório).

**Architecture:** Parte financeira: novo helper `_qualif_grand_total_html()` anexado ao `qualif_subtotals_html` existente; campo exibido em 3 lugares na view. Parte técnica: mover `qualif_tecnico_html` para arquivo focado novo `models/sale_order_form_panels.py` e reescrever o compute para montar, por equipamento, header + escopo + tabela de ciclos + tempo, via `Markup`/`escape`, reusando `_qualif_equipment_summary()`, `_qualif_cycle_specs()`, `_qualif_estimated_hours/days()`.

**Tech Stack:** Odoo 16.0, Python (markupsafe), XML. Testes via docker (container `odoo_engenapp-web-1`, db `odoo_ecm_test`; entrypoint custom — NÃO usar `odoo-bin` direto).

⚠️ **NOTA DE COMMIT (Tasks 1 e 2):** o working tree de `models/sale_order.py` contém uma mudança pré-existente NÃO relacionada (`extra["process_word"] = ...`). Tasks que editam `sale_order.py` devem ser implementadas SEM commit pelo subagente — o orquestrador faz o commit cirúrgico excluindo o `process_word`. Tasks 3 e 4 não tocam `sale_order.py` e podem commitar normalmente (staging do arquivo específico, nunca `-A`).

---

## File Structure

- **Modify** `models/sale_order.py` — `_qualif_grand_total_html()` + chamada no `_compute_qualif_subtotals_html`; REMOVER field+compute `qualif_tecnico_html` (movidos p/ novo arquivo).
- **Create** `models/sale_order_form_panels.py` — field `qualif_tecnico_html` + compute enriquecido + helpers de render.
- **Modify** `models/__init__.py` — importar `sale_order_form_panels`.
- **Modify** `views/sale_order_views.xml` — `qualif_subtotals_html` nos rodapés Comercial/Opcionais.
- **Modify** `__manifest__.py` — bump `16.0.6.2.0` → `16.0.6.3.0`.
- **Modify** `tests/test_cotacao_form_refactor.py` — novos testes (arquivo limpo, sem process_word).

---

## Task 1: Total Geral da Proposta (financeiro)

**Files:**
- Modify: `models/sale_order.py`
- Test: `tests/test_cotacao_form_refactor.py`

**NÃO COMMITAR** (orquestrador faz commit cirúrgico).

- [ ] **Step 1: Escrever os testes que falham**

Adicionar à classe `TestCotacaoFormRefactor` em `tests/test_cotacao_form_refactor.py`. Garantir no topo do arquivo o import:
```python
from odoo.tools.misc import formatLang
```
E os métodos:
```python
    def _equip_line(self, so, price=700.0, qty=1.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo CMax",
            "is_qualificacao_managed": True,
            "qualification_type": "performance",
            "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": int(qty),
            "price_unit": price,
            "product_uom_qty": qty,
        })

    def test_grand_total_present_equip_only(self):
        so = self._so()
        self._equip_line(so, price=700.0, qty=1.0)
        equip_total = sum(s["subtotal"] for s in so._qualif_equipment_summary())
        expected = formatLang(self.env, equip_total, currency_obj=so.currency_id)
        html = so.qualif_subtotals_html
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)
        self.assertIn(expected, html)

    def test_grand_total_includes_accepted_optional(self):
        so = self._so()
        self._equip_line(so, price=700.0, qty=1.0)
        self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc(50.0).id,
            "name": "Opc Aceito", "is_proposal_optional": True,
            "optional_accepted": True, "optional_qty": 1.0, "price_unit": 50.0,
        })
        equip_total = sum(s["subtotal"] for s in so._qualif_equipment_summary())
        opt_total = sum(so.order_line.filtered(
            lambda l: l.is_proposal_optional and l.optional_accepted
        ).mapped("price_subtotal"))
        expected = formatLang(self.env, equip_total + opt_total,
                              currency_obj=so.currency_id)
        self.assertIn(expected, so.qualif_subtotals_html)
```

- [ ] **Step 2: Rodar e verificar que falham**

```
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestCotacaoFormRefactor --stop-after-init 2>&1 | tail -40
```
Esperado: FAIL — o HTML não contém "TOTAL GERAL DA PROPOSTA" ainda.

- [ ] **Step 3: Implementar `_qualif_grand_total_html` + hook**

Em `models/sale_order.py`, adicionar o método LOGO APÓS `_qualif_optionals_subtotals_html` (que termina por volta da linha 360, com `) % "".join(rows)`):

```python
    def _qualif_grand_total_html(self):
        """Banner 'TOTAL GERAL DA PROPOSTA' = subtotais de equipamento +
        opcionais aceitos. Anexado ao fim de qualif_subtotals_html."""
        self.ensure_one()
        equip_total = sum(
            s["subtotal"] for s in self._qualif_equipment_summary())
        accepted = self.order_line.filtered(
            lambda l: l.is_proposal_optional and l.optional_accepted)
        opt_total = sum(accepted.mapped("price_subtotal"))
        grand = equip_total + opt_total
        grand_str = formatLang(
            self.env, grand, currency_obj=self.currency_id)
        note = Markup("")
        if accepted:
            equip_str = formatLang(
                self.env, equip_total, currency_obj=self.currency_id)
            opt_str = formatLang(
                self.env, opt_total, currency_obj=self.currency_id)
            note = (
                Markup('<div style="font-size:11px;color:#888;'
                       'margin-top:4px;">(equipamentos ')
                + escape(equip_str) + Markup(' + opcionais aceitos ')
                + escape(opt_str) + Markup(')</div>')
            )
        return (
            Markup('<div style="margin-top:16px;padding:10px 14px;'
                   'background:#1f7a3d;color:#fff;border-radius:6px;'
                   'display:flex;justify-content:space-between;'
                   'align-items:center;">'
                   '<span style="font-weight:bold;font-size:14px;">'
                   'TOTAL GERAL DA PROPOSTA</span>'
                   '<span style="font-weight:bold;font-size:18px;">')
            + escape(grand_str) + Markup('</span></div>') + note
        )
```

Em `_compute_qualif_subtotals_html`, localizar a linha:
```python
            html += order._qualif_optionals_subtotals_html()
            order.qualif_subtotals_html = html
```
e inserir a chamada do grand total ANTES da atribuição:
```python
            html += order._qualif_optionals_subtotals_html()
            html += order._qualif_grand_total_html()
            order.qualif_subtotals_html = html
```

Nota: `html` é `str`; concatenar `+= Markup(...)` resulta em `str` (Markup é subclasse de str), preservando o conteúdo já escapado dos valores dinâmicos. `Markup`, `escape` e `formatLang` já estão importados no topo de `sale_order.py`.

- [ ] **Step 4: Rodar e verificar que passam**

Mesmo comando do Step 2. Esperado: os 2 novos testes PASS.

- [ ] **Step 5: Reportar (SEM commitar)**

Reportar ao orquestrador os arquivos modificados (`models/sale_order.py`, `tests/test_cotacao_form_refactor.py`) e o resultado dos testes. NÃO rodar `git commit`.

---

## Task 2: Aba Detalhes Técnicos rica (mover + enriquecer)

**Files:**
- Modify: `models/sale_order.py` (REMOVER field+compute `qualif_tecnico_html`)
- Create: `models/sale_order_form_panels.py`
- Modify: `models/__init__.py`
- Test: `tests/test_cotacao_form_refactor.py`

**NÃO COMMITAR** (orquestrador faz commit cirúrgico).

- [ ] **Step 1: Escrever os testes que falham**

Adicionar à classe `TestCotacaoFormRefactor`:
```python
    def _cycle_line(self, so, name, qtype, cycle, qty, hours,
                    temp="80ºC", dur="10 min", load="com_carga"):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": cycle.product_id.id,
            "name": name,
            "is_qualificacao_managed": True,
            "qualification_type": qtype,
            "equipment_id": self.equip1.id,
            "cycle_type_id": cycle.id,
            "qualif_cycle_qty": qty,
            "estimated_hours": hours,
            "temperature": temp,
            "duration": dur,
            "load_type": load,
            "product_uom_qty": qty * hours,
            "price_unit": 100.0,
        })

    def test_tecnico_html_has_scope_and_cycle_table(self):
        so = self._so()
        self._cycle_line(so, "Carga Mista 134", "performance",
                         self.cycle_cmax, qty=3, hours=2.0)
        html = so.qualif_tecnico_html
        self.assertIn("ESCOPO", html)
        self.assertIn("TABELA DE CICLOS", html)
        self.assertIn("Temperatura", html)
        self.assertIn("Carga", html)
        self.assertIn("80ºC", html)
        self.assertIn("TEMPO DE EXECUÇÃO", html)
        self.assertIn("TEMPO TOTAL DE EXECUÇÃO DA PROPOSTA", html)

    def test_tecnico_html_empty_without_qualif_v2(self):
        so = self._so()
        self._line(so, optional=False)
        self.assertFalse(so.qualif_tecnico_html)
```

- [ ] **Step 2: Rodar e verificar que falham**

```
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestCotacaoFormRefactor --stop-after-init 2>&1 | tail -40
```
Esperado: FAIL — `test_tecnico_html_has_scope_and_cycle_table` não encontra "ESCOPO"/"TABELA DE CICLOS" (compute atual só faz cards simples).

- [ ] **Step 3: Remover o field+compute antigos de `sale_order.py`**

Em `models/sale_order.py`, DELETAR o field `qualif_tecnico_html` (bloco):
```python
    qualif_tecnico_html = fields.Html(
        compute="_compute_qualif_tecnico_html",
        string="Detalhes Técnicos",
        sanitize=False,
        help=(
            "Cards read-only por equipamento (equipamento → tipo qualif → "
            "itens), gerados do agregado das linhas managed. Aba de conferência."
        ),
    )
```
E DELETAR o método `_compute_qualif_tecnico_html` inteiro (o `@api.depends(...)` + `def _compute_qualif_tecnico_html(self): ...` até o fim do método, antes do próximo `@api.depends` de `_compute_qualif_standard_ids`).

- [ ] **Step 4: Criar `models/sale_order_form_panels.py`**

```python
# -*- coding: utf-8 -*-
"""Painéis HTML read-only do form de cotação (aba Detalhes Técnicos).

Mantido separado de sale_order.py (já grande) por coesão: só renderização
HTML de conferência reusando os métodos de dados do relatório
(_qualif_equipment_summary, _qualif_cycle_specs, _qualif_estimated_hours/days).
"""
from markupsafe import Markup, escape

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    qualif_tecnico_html = fields.Html(
        compute="_compute_qualif_tecnico_html",
        string="Detalhes Técnicos",
        sanitize=False,
        help=(
            "Render read-only por equipamento: escopo + tabela de ciclos "
            "(temperatura/tempo/carga/tempo estimado) + tempo de execução. "
            "Reusa os métodos de dados do relatório de cotação."
        ),
    )

    @api.depends(
        "order_line.equipment_id",
        "order_line.qualification_type",
        "order_line.is_qualificacao_managed",
        "order_line.cycle_type_id",
        "order_line.malha_type_id",
        "order_line.name",
        "order_line.product_id",
        "order_line.qualif_cycle_qty",
        "order_line.product_uom_qty",
        "order_line.display_type",
        "order_line.temperature",
        "order_line.duration",
        "order_line.load_type",
        "order_line.estimated_hours",
    )
    def _compute_qualif_tecnico_html(self):
        for order in self:
            if not order.has_qualif_lines:
                order.qualif_tecnico_html = False
                continue
            summary = order._qualif_equipment_summary()
            if not summary:
                order.qualif_tecnico_html = False
                continue
            specs_by_equip = {
                s["equipment"].id: s for s in order._qualif_cycle_specs()
            }
            cards = Markup("")
            for s in summary:
                equip = s["equipment"]
                cards += order._qualif_tecnico_card(
                    equip, s, specs_by_equip.get(equip.id))
            total_h = order._qualif_estimated_hours()
            total_d = order._qualif_estimated_days()
            footer = (
                Markup('<div style="margin-top:10px;padding:8px 14px;'
                       'background:#714B67;color:#fff;border-radius:6px;'
                       'font-size:13px;font-weight:bold;">'
                       'TEMPO TOTAL DE EXECUÇÃO DA PROPOSTA: ')
                + escape('%.1f horas · %.1f dias úteis' % (total_h, total_d))
                + Markup('</div>')
            )
            order.qualif_tecnico_html = (
                Markup('<div style="width:100%;">') + cards + footer
                + Markup('</div>')
            )

    def _qualif_tecnico_card(self, equip, summary_entry, cycle_spec):
        """Card HTML de um equipamento: header + escopo + ciclos + tempo."""
        self.ensure_one()
        header = escape(equip.display_name or _("Equipamento"))
        if equip.serial_number:
            header = header + Markup(" — S/N: ") + escape(equip.serial_number)
        if equip.category_id:
            header = (header + Markup(" · Categoria: ")
                      + escape(equip.category_id.name))
        escopo = self._qualif_tecnico_escopo(summary_entry)
        ciclos = (self._qualif_tecnico_ciclos(cycle_spec)
                  if cycle_spec and cycle_spec.get("rows") else Markup(""))
        h = self._qualif_estimated_hours(equip)
        d = self._qualif_estimated_days(equip)
        tempo = (
            Markup('<div style="margin-top:12px;font-size:12px;">'
                   '<span style="font-weight:bold;color:#714B67;">'
                   'TEMPO DE EXECUÇÃO (equipamento):</span> ')
            + escape('%.1f horas · %.1f dias úteis' % (h, d))
            + Markup('</div>')
        )
        return (
            Markup('<div style="border:1px solid #ddd;border-radius:6px;'
                   'margin:8px 0;padding:10px 14px;background:#fafafa;">'
                   '<div style="font-weight:bold;font-size:14px;color:#222;'
                   'border-bottom:1px solid #eee;padding-bottom:5px;'
                   'margin-bottom:8px;">')
            + header + Markup('</div>') + escopo + ciclos + tempo
            + Markup('</div>')
        )

    def _qualif_tecnico_escopo(self, summary_entry):
        """Tabela ESCOPO: Tipo (cabeçalho) → itens agrupados por parte."""
        rows = Markup("")
        for tp in summary_entry["types"]:
            rows += (
                Markup('<tr style="background:#f0eef0;">'
                       '<td style="padding:4px 10px;font-weight:bold;" '
                       'colspan="2">')
                + escape(tp["label"]) + Markup('</td></tr>')
            )
            for pcode, plabel in (("01", "Parte 01"), ("02", "Parte 02"),
                                  ("", "")):
                part_items = [
                    i for i in tp["items"] if (i.get("part") or "") == pcode]
                if not part_items:
                    continue
                names = Markup(" · ").join(
                    ((Markup('<span style="text-decoration:line-through;'
                             'color:#999;">') + escape(i["name"])
                      + Markup('</span>'))
                     if i.get("declined") else escape(i["name"]))
                    + (Markup(" &times; %s") % int(i["qty"])
                       if i.get("qty") else Markup(""))
                    for i in part_items
                )
                rows += (
                    Markup('<tr><td style="padding:3px 10px;width:70px;'
                           'color:#888;">') + escape(plabel)
                    + Markup('</td><td style="padding:3px 10px;">')
                    + names + Markup('</td></tr>')
                )
        return (
            Markup('<div style="font-weight:bold;color:#714B67;'
                   'font-size:12px;margin:10px 0 4px;">ESCOPO</div>'
                   '<table style="border-collapse:collapse;width:100%;'
                   'font-size:12px;border:1px solid #e0e0e0;"><tbody>')
            + rows + Markup('</tbody></table>')
        )

    def _qualif_tecnico_ciclos(self, cycle_spec):
        """Tabela de Ciclos (cycle_spec de _qualif_cycle_specs)."""
        rows = Markup("")
        total_qty = 0
        total_hours = 0.0
        for idx, row in enumerate(cycle_spec["rows"]):
            bg = "background:#fafafa;" if idx % 2 else ""
            total_qty += row["qty"] or 0
            total_hours += row["estimated_hours_total"] or 0.0
            rows += (
                Markup('<tr style="%s">' % bg)
                + Markup('<td style="padding:4px 10px;">')
                + escape(row["name"]) + Markup('</td>')
                + Markup('<td style="padding:4px 8px;text-align:center;">')
                + escape(str(row["qty"])) + Markup('</td>')
                + Markup('<td style="padding:4px 8px;text-align:center;">')
                + escape(row["temperature"] or "") + Markup('</td>')
                + Markup('<td style="padding:4px 8px;text-align:center;">')
                + escape(row["duration"] or "") + Markup('</td>')
                + Markup('<td style="padding:4px 8px;text-align:center;">')
                + escape(row["load_type"] or "") + Markup('</td>')
                + Markup('<td style="padding:4px 10px;text-align:right;">')
                + escape('%.1f h' % (row["estimated_hours_total"] or 0.0))
                + Markup('</td></tr>')
            )
        head = (
            Markup('<thead><tr style="background:#714B67;color:#fff;">'
                   '<th style="padding:5px 10px;text-align:left;">Ciclo</th>'
                   '<th style="padding:5px 8px;text-align:center;">Qtd</th>'
                   '<th style="padding:5px 8px;text-align:center;">'
                   'Temperatura</th>'
                   '<th style="padding:5px 8px;text-align:center;">')
            + escape(cycle_spec.get("time_label") or "Tempo")
            + Markup('</th>'
                     '<th style="padding:5px 8px;text-align:center;">Carga</th>'
                     '<th style="padding:5px 10px;text-align:right;">'
                     'Tempo Estimado</th></tr></thead>')
        )
        foot = (
            Markup('<tfoot><tr style="border-top:2px solid #333;'
                   'font-weight:bold;"><td style="padding:5px 10px;" '
                   'colspan="5">Total: ')
            + escape('%d ciclo(s)' % total_qty)
            + Markup('</td><td style="padding:5px 10px;text-align:right;">')
            + escape('%.1f h · %.1f dias' % (total_hours, total_hours / 8.0))
            + Markup('</td></tr></tfoot>')
        )
        return (
            Markup('<div style="font-weight:bold;color:#714B67;'
                   'font-size:12px;margin:14px 0 4px;">TABELA DE CICLOS</div>'
                   '<table style="border-collapse:collapse;width:100%;'
                   'font-size:12px;border:1px solid #e0e0e0;">')
            + head + Markup('<tbody>') + rows + Markup('</tbody>') + foot
            + Markup('</table>')
        )
```

- [ ] **Step 5: Registrar o arquivo em `models/__init__.py`**

Após a linha `from . import sale_order`, adicionar:
```python
from . import sale_order_form_panels
```

- [ ] **Step 6: Rodar e verificar que passam**

Mesmo comando do Step 2. Esperado: `test_tecnico_html_has_scope_and_cycle_table` e `test_tecnico_html_empty_without_qualif_v2` PASS, e todos os testes pré-existentes da classe seguem PASS.

- [ ] **Step 7: Reportar (SEM commitar)**

Reportar arquivos modificados/criados (`models/sale_order.py`, `models/sale_order_form_panels.py`, `models/__init__.py`, `tests/test_cotacao_form_refactor.py`) + resultado dos testes. NÃO commitar.

---

## Task 3: View — resumo financeiro nos rodapés das abas

**Files:**
- Modify: `views/sale_order_views.xml`

(Esta task NÃO toca `sale_order.py` — pode commitar normalmente, staging só do arquivo de view.)

- [ ] **Step 1: Adicionar `qualif_subtotals_html` no rodapé da aba Comercial**

Em `views/sale_order_views.xml`, na page `qualif_comercial`, LOGO APÓS o fechamento `</field>` do `regular_line_ids` (antes de `</page>`), inserir:
```xml
                    <field name="qualif_subtotals_html" nolabel="1" readonly="1"
                           attrs="{'invisible': [('has_qualif_lines','=',False)]}"/>
```

- [ ] **Step 2: Adicionar `qualif_subtotals_html` no rodapé da aba Opcionais**

Na page `qualif_opcionais`, LOGO APÓS o `</field>` do `optional_line_ids` (antes de `</page>`), inserir o MESMO bloco:
```xml
                    <field name="qualif_subtotals_html" nolabel="1" readonly="1"
                           attrs="{'invisible': [('has_qualif_lines','=',False)]}"/>
```

- [ ] **Step 3: Upgrade + validar arch**

```
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --stop-after-init 2>&1 | tail -20
```
Esperado: upgrade SEM ParseError.

Validar via shell que `qualif_subtotals_html` aparece 3× na arch (painel direito + 2 abas):
```
docker exec -i odoo_engenapp-web-1 odoo shell -d odoo_ecm_test --no-http 2>/dev/null <<'EOF'
v = env.ref('afr_qualificacao.view_sale_order_form_inherit_qualificacao')
arch = env['sale.order'].fields_view_get(view_id=v.id, view_type='form')['arch']
print('ocorrencias qualif_subtotals_html:', arch.count('qualif_subtotals_html'))
assert arch.count('qualif_subtotals_html') >= 3
print('OK')
EOF
```
Esperado: >= 3 ocorrências.

- [ ] **Step 4: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add views/sale_order_views.xml
git commit -m "feat: resumo financeiro no rodape das abas Comercial e Opcionais"
```

---

## Task 4: Bump versão + suíte completa

**Files:**
- Modify: `__manifest__.py`

- [ ] **Step 1: Bump da versão**

Em `__manifest__.py`, alterar:
```python
    "version": "16.0.6.2.0",
```
para:
```python
    "version": "16.0.6.3.0",
```

- [ ] **Step 2: Rodar a suíte completa**

```
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao --stop-after-init 2>&1 | tail -30
```
Esperado: baseline conhecido = 3 falhas pré-existentes/ambientais
(`TestResourcePlan.test_fleet_single_logger_two_temp_standards`;
`TestProposalReport.test_render_equipment_scope_omits_cronograma_footer`;
`TestProposalReport.test_render_schedule_block`). Confirmar SEM regressão nova,
e `TestCotacaoFormRefactor` (todos) PASS.

- [ ] **Step 3: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add __manifest__.py
git commit -m "chore: bump afr_qualificacao 16.0.6.3.0 (financeiro + tecnico nas abas)"
```

---

## Self-Review (orquestrador, antes do handoff)

- Spec coverage: Parte 1 (grand total + view footers) = Tasks 1, 3 ✓. Parte 2 (técnico rico em arquivo novo) = Task 2 ✓. Bump/testes = Task 4 ✓.
- Métodos reusados confirmados existentes: `_qualif_equipment_summary`, `_qualif_cycle_specs` (retorna {equipment, rows[name/qty/temperature/duration/load_type/estimated_hours_total], time_label}), `_qualif_estimated_hours/days` (agregam todos quando `equipment=None`).
- Escaping: todo valor dinâmico via `escape()`; literais via `Markup()`.
