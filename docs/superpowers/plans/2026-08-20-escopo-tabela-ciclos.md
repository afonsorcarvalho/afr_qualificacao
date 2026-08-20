# Escopo por Equipamento como Tabela Única — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o escopo da proposta numa tabela única por equipamento contendo etapas, tabelas de ciclos, previsão de dias, subtotal por etapa, valor unitário do equipamento e, ao fim, o total geral com adicionais.

**Architecture:** Um helper novo em `sale.order` (`_qualif_scope_table`) vira a fonte única de verdade da agregação; os três renders (PDF QWeb, portal QWeb, HTML Python para DOCX/bloco editável) só formatam o que ele devolve. O conjunto de linhas do escopo passa a ser idêntico ao de `_rateio_base_lines()`, o que faz Σ subtotais dos grupos bater com `equipment_subtotal` por construção. `_qualif_proposal_totals()` deixa de calcular "resto" e passa a enumerar adicionais, com uma linha residual de guarda para nunca perder dinheiro do `amount_untaxed`.

**Tech Stack:** Odoo 16.0, QWeb, Python 3.9, `odoo.tests.common.TransactionCase`, Docker (`odoo_engenapp-web-1`, db de teste `odoo_ecm_test`).

**Spec:** `docs/superpowers/specs/2026-08-20-escopo-tabela-ciclos-design.md`

## Global Constraints

- Módulo: `addons/afr_qualificacao` — **é git submodule**. Commit e `git push origin main` de dentro de `addons/afr_qualificacao/`, nunca pelo monorepo. Bump do pointer no monorepo só depois do push.
- Commits via subagente `git-commit-push` (model haiku), nunca `git commit` direto.
- Versão em `__manifest__.py`: subir de `16.0.6.13.5` para `16.0.7.0.0` na Task 8 (uma única vez, no fim).
- Testes rodam via subagente `test-runner`. Comando de referência:
  `docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags <TAGS> --stop-after-init`
- Nunca usar `odoo-bin`. Porta host do Odoo local: 8083.
- Todos os testes novos herdam de `AfrQualificacaoTestCommon` (`tests/common.py`) e usam `@tagged("post_install", "-at_install")`.
- Todo teste novo precisa ser registrado em `tests/__init__.py`.
- Rótulos em português, com travessão `—` (em dash) entre tipo e parte, exatamente como nas constantes deste plano.

---

## Estrutura de Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `models/sale_order.py` | Constantes de grupo, `_qualif_scope_lines`, `_qualif_group_hours`, `_qualif_days_from_hours`, `_qualif_scope_ref`, `_qualif_scope_row`, `_qualif_scope_table`, `_qualif_scope_tables`, `_qualif_additional_lines`, `_qualif_proposal_totals`, `_qualif_grand_total_html` |
| `reports/templates_blocos/block_totals.xml` (novo) | Sub-template `qq_totals_table` — bloco de totais compartilhado pelo escopo e pelo bloco `financial` |
| `reports/templates_blocos/block_equipment_scope.xml` | Tabela nova do escopo (PDF) + chamada do `qq_totals_table` |
| `reports/templates_blocos/block_financial.xml` | Passa a chamar `qq_totals_table` (mantém o tipo funcionando) |
| `reports/templates_blocos/styles.xml` | Estilos da tabela nova |
| `views/sale_order_portal_template.xml` | Mesma tabela no portal + totais no formato novo |
| `models/proposal_block.py` | `_html_equipment_scope` e `_html_financial` reescritos sobre os helpers novos |
| `data/proposal_template_seed.xml` | Remove linhas `l12` (financial) e `l13` (optionals) |
| `data/proposal_template_cleanup.xml` (novo) | `<delete>` dos blocos financial/optionals do template em bases existentes |
| `__manifest__.py` | Registra o data file novo + bump de versão |
| `tests/test_scope_table.py` (novo) | Cobertura dos helpers novos |
| `tests/test_scope_render.py` (novo) | Cobertura dos três renders |

---

### Task 1: Helpers de linhas, horas e dias

**Files:**
- Modify: `models/sale_order.py` (adicionar após `_qualif_work_hours_per_day`, ~linha 644)
- Create: `tests/test_scope_table.py`
- Modify: `tests/__init__.py`

**Interfaces:**
- Produces:
  - `_qualif_scope_lines(equipment, qtype=None, part=None) -> sale.order.line recordset`
  - `_qualif_group_hours(lines) -> float`
  - `_qualif_days_from_hours(hours, equipment) -> float`

- [ ] **Step 1: Registrar o arquivo de teste novo**

Em `tests/__init__.py`, adicionar na ordem alfabética junto dos demais:

```python
from . import test_scope_table
```

- [ ] **Step 2: Escrever os testes que falham**

Criar `tests/test_scope_table.py`:

```python
# -*- coding: utf-8 -*-
"""Escopo por equipamento como tabela única — camada de agregação."""

from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestScopeLinesAndHours(AfrQualificacaoTestCommon):

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _section(self, so, equip, work_hours=8.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "display_type": "line_section",
            "name": equip.display_name,
            "is_qualificacao_managed": True,
            "equipment_id": equip.id,
            "work_hours_per_day": work_hours,
        })

    def _cycle_line(self, so, equip, qtype, part, qty, hours, price):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo",
            "is_qualificacao_managed": True,
            "qualification_type": qtype,
            "part": part,
            "equipment_id": equip.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": qty,
            "estimated_hours": hours,
            "product_uom_qty": qty * hours,
            "price_unit": price,
        })

    def test_scope_lines_match_rateio_base(self):
        """O conjunto do escopo é exatamente o do rateio."""
        so = self._so()
        section = self._section(so, self.equip1)
        firme = self._cycle_line(so, self.equip1, "performance", False, 3, 2.0, 200.0)
        opcional = self._cycle_line(so, self.equip1, "performance", False, 1, 1.0, 500.0)
        opcional.write({"is_proposal_optional": True, "optional_accepted": True})
        declinada = self._cycle_line(so, self.equip1, "installation", "01", 1, 1.0, 900.0)
        declinada.write({"part01_declined": True, "product_uom_qty": 0.0})

        scope = so._qualif_scope_lines(self.equip1)
        self.assertEqual(scope, section._rateio_base_lines())
        self.assertIn(firme, scope)
        self.assertNotIn(opcional, scope)
        self.assertNotIn(declinada, scope)
        self.assertNotIn(section, scope)

    def test_scope_lines_filter_by_type_and_part(self):
        so = self._so()
        self._section(so, self.equip1)
        qo2 = self._cycle_line(so, self.equip1, "operational", "02", 2, 1.0, 100.0)
        qd = self._cycle_line(so, self.equip1, "performance", False, 3, 1.0, 200.0)

        self.assertEqual(so._qualif_scope_lines(self.equip1, "operational", "02"), qo2)
        self.assertEqual(so._qualif_scope_lines(self.equip1, "performance", None), qd)
        self.assertFalse(so._qualif_scope_lines(self.equip1, "operational", "01"))

    def test_group_hours_uses_qualif_cycle_qty(self):
        so = self._so()
        self._section(so, self.equip1)
        lines = self._cycle_line(so, self.equip1, "performance", False, 3, 2.5, 200.0)
        self.assertEqual(so._qualif_group_hours(lines), 7.5)

    def test_days_round_up_to_next_half(self):
        so = self._so()
        self._section(so, self.equip1, work_hours=8.0)
        self.assertEqual(so._qualif_days_from_hours(4.0, self.equip1), 0.5)
        self.assertEqual(so._qualif_days_from_hours(4.1, self.equip1), 1.0)
        self.assertEqual(so._qualif_days_from_hours(8.0, self.equip1), 1.0)
        self.assertEqual(so._qualif_days_from_hours(25.6, self.equip1), 3.5)
        self.assertEqual(so._qualif_days_from_hours(0.0, self.equip1), 0.0)

    def test_days_respect_work_hours_per_day(self):
        so = self._so()
        self._section(so, self.equip1, work_hours=4.0)
        self.assertEqual(so._qualif_days_from_hours(4.0, self.equip1), 1.0)
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

Delegar ao subagente `test-runner`:

```
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
  --test-enable --test-tags /afr_qualificacao:TestScopeLinesAndHours --stop-after-init
```

Esperado: FAIL com `AttributeError: 'sale.order' object has no attribute '_qualif_scope_lines'`.

- [ ] **Step 4: Implementar os helpers**

No topo de `models/sale_order.py`, junto dos demais imports:

```python
import math
```

Em `models/sale_order.py`, logo depois de `_qualif_work_hours_per_day` (~linha 644):

```python
    def _qualif_scope_lines(self, equipment, qtype=None, part=None):
        """Linhas que compõem o escopo impresso de um equipamento.

        Conjunto IDÊNTICO ao de `sale.order.line._rateio_base_lines()` —
        managed, sem display_type, não opcional, não declinada, qty > 0.
        Manter os dois em sincronia é o que garante que a soma dos
        subtotais dos grupos bata com `equipment_subtotal` (e portanto
        com o Valor Unitário impresso).

        `qtype` filtra por qualification_type; `part` filtra por parte
        ('01'/'02'). `part=None` = qualquer parte.
        """
        self.ensure_one()
        lines = self.order_line.filtered(
            lambda l: l.equipment_id == equipment
            and l.is_qualificacao_managed
            and not l.display_type
            and not l.is_proposal_optional
            and not l.part01_declined
            and l.product_uom_qty > 0
        )
        if qtype:
            lines = lines.filtered(lambda l: l.qualification_type == qtype)
        if part is not None:
            lines = lines.filtered(lambda l: (l.part or "") == part)
        return lines

    def _qualif_group_hours(self, lines):
        """Horas estimadas de um conjunto de linhas do escopo.

        Hierarquia da hora unitária: override na linha → cycle_type →
        malha_type → afr.qualificacao.type.config (QI/QS). Multiplicada
        por `qualif_cycle_qty` (fallback `product_uom_qty`).
        """
        self.ensure_one()
        TypeConfig = self.env["afr.qualificacao.type.config"]
        total = 0.0
        for line in lines:
            hours = line.estimated_hours
            if not hours:
                if line.cycle_type_id:
                    hours = line.cycle_type_id.estimated_hours
                elif line.malha_type_id:
                    hours = line.malha_type_id.estimated_hours
                elif line.qualification_type in ("installation", "software"):
                    cfg = TypeConfig.get_config_for(
                        line.qualification_type, self.company_id,
                    )
                    if cfg:
                        hours = cfg.estimated_hours
            qty = line.qualif_cycle_qty or int(line.product_uom_qty or 0)
            total += (hours or 0.0) * qty
        return total

    def _qualif_days_from_hours(self, hours, equipment):
        """Horas → dias de serviço, arredondado PARA CIMA ao próximo 0,5.

        3,2 dias → 3,5; 3,6 → 4,0. `round(..., 6)` antes do ceil evita
        que 3.0000000001 (ruído de float) vire 3,5.
        """
        self.ensure_one()
        wh = self._qualif_work_hours_per_day(equipment) or 8.0
        return math.ceil(round((hours / wh) * 2, 6)) / 2.0
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Mesmo comando do Step 3. Esperado: PASS, 6 testes.

- [ ] **Step 6: Commit**

Delegar ao subagente `git-commit-push`, com `cwd` em `addons/afr_qualificacao`:

```
feat(qualificacao): scope line set, group hours and day rounding helpers
```
Arquivos: `models/sale_order.py`, `tests/test_scope_table.py`, `tests/__init__.py`.
Push `origin main`; **não** bumpar o pointer do monorepo ainda (fica para a Task 8).

---

### Task 2: Remissiva ao tópico (`_qualif_scope_ref`)

**Files:**
- Modify: `models/sale_order.py` (constante nova no topo + método após `_qualif_days_from_hours`)
- Modify: `tests/test_scope_table.py`

**Interfaces:**
- Consumes: nada da Task 1.
- Produces: `_qualif_scope_ref(qtype) -> str`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_scope_table.py`:

```python
@tagged("post_install", "-at_install")
class TestScopeRef(AfrQualificacaoTestCommon):

    def _so_with_blocks(self):
        """SO com 2 blocos numerados: SEC-QI (nº 1) e SEC-QO (nº 2)."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        Block = self.env["afr.proposal.block"]
        self.sec_qi = self.env.ref("afr_qualificacao.proposal_section_qi")
        self.sec_qo = self.env.ref("afr_qualificacao.proposal_section_qo")
        self.blk_qi = Block.create({
            "sale_order_id": so.id, "block_kind": "static",
            "section_id": self.sec_qi.id, "sequence": 10, "included": True,
        })
        self.blk_qo = Block.create({
            "sale_order_id": so.id, "block_kind": "static",
            "section_id": self.sec_qo.id, "sequence": 20, "included": True,
        })
        return so

    def test_ref_cites_block_number(self):
        so = self._so_with_blocks()
        ref = so._qualif_scope_ref("installation")
        self.assertIn("Conforme item 1", ref)
        self.assertIn(self.sec_qi.name, ref)

    def test_ref_second_block_gets_number_two(self):
        so = self._so_with_blocks()
        self.assertIn("Conforme item 2", so._qualif_scope_ref("operational"))

    def test_ref_without_block_degrades_to_topic_name(self):
        so = self._so_with_blocks()
        ref = so._qualif_scope_ref("performance")
        self.assertNotIn("Conforme item", ref)
        self.assertIn("Qualificação de Desempenho", ref)

    def test_ref_without_number_degrades(self):
        """show_number=False → numbering devolve '' → sem 'Conforme item'."""
        so = self._so_with_blocks()
        self.blk_qi.show_number = False
        ref = so._qualif_scope_ref("installation")
        self.assertNotIn("Conforme item", ref)
        self.assertIn(self.sec_qi.name, ref)

    def test_ref_unknown_type_never_returns_falsy(self):
        so = self._so_with_blocks()
        self.assertTrue(so._qualif_scope_ref(False))
        self.assertTrue(so._qualif_scope_ref("inexistente"))
```

- [ ] **Step 2: Rodar e confirmar falha**

```
--test-tags /afr_qualificacao:TestScopeRef
```
Esperado: FAIL com `AttributeError: ... '_qualif_scope_ref'`.

- [ ] **Step 3: Implementar**

Em `models/sale_order.py`, logo abaixo de `QUALIF_TYPE_LABELS` (~linha 37):

```python
# Tipo de qualificação → code da seção da biblioteca que o descreve.
# Usado pela remissiva do escopo ("Conforme item 5.1 — ...").
SCOPE_REF_SECTION_CODES = {
    "installation": "SEC-QI",
    "operational": "SEC-QO",
    "performance": "SEC-QD",
    "software": "SEC-QS",
    "calibration": "SEC-CALIB",
}
```

E o método, depois de `_qualif_days_from_hours`:

```python
    def _qualif_scope_ref(self, qtype):
        """Remissiva ao tópico da proposta que descreve o tipo.

        Com bloco incluído e numerado:
            "Conforme item 5.1 — Qualificação de Instalação (QI)"
        Sem bloco (cliente removeu) ou sem número (show_number=False):
            "Conforme descrito no tópico Qualificação de Instalação (QI)"

        NUNCA devolve vazio/None — o QWeb interpola direto.
        """
        self.ensure_one()
        label = QUALIF_TYPE_LABELS.get(qtype) or _("este escopo")
        code = SCOPE_REF_SECTION_CODES.get(qtype)
        block = self.env["afr.proposal.block"]
        if code:
            block = self.proposal_block_ids.filtered(
                lambda b: b.included and b.section_id
                and b.section_id.code == code
            )[:1]
        if not block:
            return _("Conforme descrito no tópico %s") % label
        name = block.section_id.name or block.title or label
        num = self._proposal_block_numbering().get(block.id) or ""
        if not num:
            return _("Conforme descrito no tópico %s") % name
        return _("Conforme item %s — %s") % (num, name)
```

- [ ] **Step 4: Rodar e confirmar que passam**

Mesmo comando do Step 2. Esperado: PASS, 5 testes.

- [ ] **Step 5: Commit**

```
feat(qualificacao): topic cross-reference helper for the scope table
```
Arquivos: `models/sale_order.py`, `tests/test_scope_table.py`. Push `origin main`.

---

### Task 3: Agregação da tabela (`_qualif_scope_table`)

**Files:**
- Modify: `models/sale_order.py` (constantes + métodos após `_qualif_scope_ref`)
- Modify: `tests/test_scope_table.py`

**Interfaces:**
- Consumes: `_qualif_scope_lines`, `_qualif_group_hours`, `_qualif_days_from_hours` (Task 1); `_qualif_scope_ref` (Task 2).
- Produces:
  - `_qualif_scope_table(equipment) -> dict` com chaves `equipment`, `groups`, `footer`
  - `_qualif_scope_tables() -> list[dict]`
  - Cada grupo: `{"key", "rows", "days", "subtotal", "subtotal_label"}`
  - Cada row: `{"kind": "ref"|"list"|"cycles", "label", "title", + "ref"|"items"|("cycles","time_label")}`
  - Cada ciclo: `{"qty", "name", "temperature", "duration"}`
  - Footer: `{"days": float, "unit_price": float}`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_scope_table.py`:

```python
@tagged("post_install", "-at_install")
class TestScopeTable(AfrQualificacaoTestCommon):

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _section(self, so, equip, target=0.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "display_type": "line_section",
            "name": equip.display_name,
            "is_qualificacao_managed": True,
            "equipment_id": equip.id,
            "work_hours_per_day": 8.0,
            "equipment_target_price": target,
        })

    def _line(self, so, equip, qtype, part, price, hours=1.0, qty=1,
              cycle=None, malha=None, name="Item"):
        vals = {
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "name": name,
            "is_qualificacao_managed": True,
            "qualification_type": qtype,
            "part": part,
            "equipment_id": equip.id,
            "qualif_cycle_qty": qty,
            "estimated_hours": hours,
            "product_uom_qty": qty * hours,
            "price_unit": price / (qty * hours) if qty * hours else price,
        }
        if cycle:
            vals.update({
                "cycle_type_id": cycle.id,
                "product_id": cycle.product_id.id,
                "temperature": "134°C",
                "duration": "7 minutos",
            })
        if malha:
            vals.update({
                "malha_type_id": malha.id,
                "product_id": malha.product_id.id,
            })
        return self.env["sale.order.line"].create(vals)

    def _full_so(self):
        """SO no formato da proposta alvo: QI-1, QO-1, calib, QO-2, QD."""
        so = self._so()
        self.section = self._section(so, self.equip1)
        self._line(so, self.equip1, "installation", "01", 1500.0, hours=4.0,
                   name="Verificações QI")
        self._line(so, self.equip1, "operational", "01", 1700.0, hours=4.0,
                   name="Verificações QO")
        self._line(so, self.equip1, "calibration", "02", 400.0, hours=1.0,
                   malha=self.malha_temp, name="Calibração de Malha de Temperatura")
        self._line(so, self.equip1, "operational", "02", 500.0, hours=1.0, qty=3,
                   cycle=self.cycle_qo_test, name="Bowie Dick")
        self._line(so, self.equip1, "performance", False, 948.0, hours=1.0, qty=3,
                   cycle=self.cycle_cmax, name="Carga Mista")
        return so

    def test_three_groups_in_order(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        self.assertEqual([g["key"] for g in table["groups"]],
                         ["qi1", "qo1", "parte2"])

    def test_group_subtotal_labels(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        self.assertEqual(
            [g["subtotal_label"] for g in table["groups"]],
            ["Subtotal QI", "Subtotal QO", "Subtotal QD"],
        )

    def test_parte2_rows_order_and_kinds(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        parte2 = table["groups"][2]
        self.assertEqual([r["kind"] for r in parte2["rows"]],
                         ["list", "cycles", "cycles"])
        self.assertEqual(parte2["rows"][0]["title"],
                         "Calibração dos equipamentos de controle:")
        self.assertEqual(parte2["rows"][1]["title"],
                         "Execução dos ciclos sem carga")
        self.assertEqual(parte2["rows"][2]["title"],
                         "Execução dos ciclos com carga")

    def test_qi1_and_qo1_are_refs(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        self.assertEqual(table["groups"][0]["rows"][0]["kind"], "ref")
        self.assertTrue(table["groups"][0]["rows"][0]["ref"])
        self.assertEqual(table["groups"][1]["rows"][0]["kind"], "ref")

    def test_cycle_row_fields(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        cycles = table["groups"][2]["rows"][2]["cycles"]
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0]["qty"], 3)
        self.assertEqual(cycles[0]["name"], self.cycle_cmax.name)
        self.assertEqual(cycles[0]["temperature"], "134°C")
        self.assertEqual(cycles[0]["duration"], "7 minutos")
        self.assertTrue(table["groups"][2]["rows"][2]["time_label"])

    def test_group_subtotals_sum_to_equipment_subtotal(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        soma = sum(g["subtotal"] for g in table["groups"])
        self.assertAlmostEqual(soma, self.section.equipment_subtotal, places=2)

    def test_footer_days_is_sum_of_rounded_group_days(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        self.assertAlmostEqual(
            table["footer"]["days"],
            sum(g["days"] for g in table["groups"]),
            places=2,
        )
        # QI 4h → 0,5 | QO 4h → 0,5 | parte2 (1+3+3=7h) → 1,0
        self.assertAlmostEqual(table["footer"]["days"], 2.0, places=2)

    def test_unit_price_uses_target_when_state_ok(self):
        so = self._full_so()
        self.section.equipment_target_price = self.section.equipment_subtotal
        table = so._qualif_scope_table(self.equip1)
        self.assertAlmostEqual(table["footer"]["unit_price"],
                               self.section.equipment_target_price, places=2)

    def test_unit_price_falls_back_when_target_drifts(self):
        so = self._full_so()
        self.section.equipment_target_price = 1.0  # desviado de propósito
        self.assertEqual(self.section.equipment_target_state, "drift")
        table = so._qualif_scope_table(self.equip1)
        self.assertAlmostEqual(table["footer"]["unit_price"],
                               self.section.equipment_subtotal, places=2)

    def test_unknown_type_becomes_its_own_group(self):
        so = self._full_so()
        self._line(so, self.equip1, "software", False, 800.0, hours=2.0,
                   name="Validação de software")
        table = so._qualif_scope_table(self.equip1)
        keys = [g["key"] for g in table["groups"]]
        self.assertIn("extra-software", keys)
        extra = table["groups"][keys.index("extra-software")]
        self.assertEqual(extra["rows"][0]["kind"], "list")
        self.assertIn("Validação de software", extra["rows"][0]["items"])

    def test_optional_and_declined_never_reach_the_table(self):
        so = self._full_so()
        opt = self._line(so, self.equip1, "performance", False, 999.0,
                         cycle=self.cycle_cmin, name="Ciclo opcional")
        opt.write({"is_proposal_optional": True, "optional_accepted": True})
        table = so._qualif_scope_table(self.equip1)
        nomes = [c["name"] for r in table["groups"][2]["rows"]
                 if r["kind"] == "cycles" for c in r["cycles"]]
        self.assertNotIn(self.cycle_cmin.name, nomes)

    def test_scope_tables_lists_every_equipment_with_scope(self):
        so = self._full_so()
        self._section(so, self.equip2)
        self._line(so, self.equip2, "performance", False, 300.0,
                   cycle=self.cycle_cmax, name="Ciclo eq2")
        tables = so._qualif_scope_tables()
        self.assertEqual([t["equipment"] for t in tables],
                         [self.equip1, self.equip2])
```

- [ ] **Step 2: Rodar e confirmar falha**

```
--test-tags /afr_qualificacao:TestScopeTable
```
Esperado: FAIL com `AttributeError: ... '_qualif_scope_table'`.

- [ ] **Step 3: Implementar as constantes**

Em `models/sale_order.py`, logo abaixo de `SCOPE_REF_SECTION_CODES`:

```python
# Agrupamento das linhas "Previsão de dias / Subtotal" no escopo impresso.
# Fiel à proposta antiga do cliente: QI parte 01 e QO parte 01 fecham
# sozinhos; parte 02 (calibrações + ciclos sem carga) e QD fecham juntos
# sob o rótulo "Subtotal QD". `part=None` = qualquer parte.
SCOPE_GROUPS = (
    {
        "key": "qi1",
        "subtotal_label": "Subtotal QI",
        "members": (("installation", "01"),),
    },
    {
        "key": "qo1",
        "subtotal_label": "Subtotal QO",
        "members": (("operational", "01"),),
    },
    {
        "key": "parte2",
        "subtotal_label": "Subtotal QD",
        "members": (
            ("installation", "02"),
            ("calibration", None),
            ("operational", "02"),
            ("performance", None),
        ),
    },
)

# Como cada (tipo, parte) se apresenta na coluna direita da tabela.
SCOPE_ROW_SPECS = {
    ("installation", "01"): {
        "label": "Qualificação da Instalação — QI (primeira parte)",
        "kind": "ref", "title": "",
    },
    ("operational", "01"): {
        "label": "Qualificação de Operação — QO (primeira parte)",
        "kind": "ref", "title": "",
    },
    ("installation", "02"): {
        "label": "Qualificação da Instalação — QI (segunda parte)",
        "kind": "list", "title": "Itens a serem avaliados:",
    },
    ("calibration", None): {
        "label": "Qualificação da Instalação — QI (segunda parte)",
        "kind": "list", "title": "Calibração dos equipamentos de controle:",
    },
    ("operational", "02"): {
        "label": "Qualificação de Operação — QO (segunda parte)",
        "kind": "cycles", "title": "Execução dos ciclos sem carga",
    },
    ("performance", None): {
        "label": "Qualificação de Desempenho — QD",
        "kind": "cycles", "title": "Execução dos ciclos com carga",
    },
}
```

- [ ] **Step 4: Implementar os métodos**

Em `models/sale_order.py`, depois de `_qualif_scope_ref`:

```python
    def _qualif_scope_row(self, equipment, qtype, row_spec, lines):
        """Monta uma linha da coluna direita da tabela de escopo."""
        self.ensure_one()
        row = {
            "kind": row_spec["kind"],
            "label": row_spec["label"],
            "title": row_spec["title"],
        }
        if row_spec["kind"] == "ref":
            row["ref"] = self._qualif_scope_ref(qtype)
        elif row_spec["kind"] == "cycles":
            row["time_label"] = (
                equipment.category_id._qualif_time_label()
                if equipment.category_id else _("Tempo de Esterilização")
            )
            row["cycles"] = [{
                "qty": line.qualif_cycle_qty or int(line.product_uom_qty or 0),
                "name": line.cycle_type_id.name or line.name or "",
                "temperature": (
                    line.temperature
                    or line.cycle_type_id.temperature or ""
                ),
                "duration": (
                    line.duration or line.cycle_type_id.duration or ""
                ),
            } for line in lines]
        else:
            row["items"] = [
                line.name or line.product_id.display_name or ""
                for line in lines
            ]
        return row

    def _qualif_scope_table(self, equipment):
        """Tabela de escopo completa de um equipamento.

        Fonte ÚNICA dos três renders (PDF, portal, HTML do bloco). Nenhum
        deles refaz agregação nem aritmética. Ver spec
        docs/superpowers/specs/2026-08-20-escopo-tabela-ciclos-design.md.
        """
        self.ensure_one()
        all_lines = self._qualif_scope_lines(equipment)
        used = self.env["sale.order.line"]
        groups = []
        for spec in SCOPE_GROUPS:
            rows = []
            group_lines = self.env["sale.order.line"]
            for qtype, part in spec["members"]:
                lines = self._qualif_scope_lines(equipment, qtype, part)
                if not lines:
                    continue
                group_lines |= lines
                rows.append(self._qualif_scope_row(
                    equipment, qtype, SCOPE_ROW_SPECS[(qtype, part)], lines,
                ))
            if not group_lines:
                continue
            used |= group_lines
            groups.append({
                "key": spec["key"],
                "rows": rows,
                "days": self._qualif_days_from_hours(
                    self._qualif_group_hours(group_lines), equipment),
                "subtotal": sum(group_lines.mapped("price_subtotal")),
                "subtotal_label": spec["subtotal_label"],
            })

        # Sobras: tipo/parte fora da matriz (ex.: QS). Cada tipo vira um
        # grupo próprio — nada some silenciosamente do escopo impresso.
        leftovers = all_lines - used
        for qtype in OrderedDict.fromkeys(
                leftovers.mapped("qualification_type")):
            lines = leftovers.filtered(
                lambda l: l.qualification_type == qtype)
            label = QUALIF_TYPE_LABELS.get(qtype) or _("Outros serviços")
            groups.append({
                "key": "extra-%s" % (qtype or "other"),
                "rows": [{
                    "kind": "list", "label": label, "title": "",
                    "items": [
                        line.name or line.product_id.display_name or ""
                        for line in lines
                    ],
                }],
                "days": self._qualif_days_from_hours(
                    self._qualif_group_hours(lines), equipment),
                "subtotal": sum(lines.mapped("price_subtotal")),
                "subtotal_label": _("Subtotal %s") % label,
            })

        # Valor Unitário: o preço-alvo quando ele bate com a soma real;
        # senão a soma real, para o impresso sempre fechar com o
        # amount_untaxed do SO. Drift continua sinalizado no form.
        section = self.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id == equipment
        )[:1]
        if section and section.equipment_target_state == "ok":
            unit_price = section.equipment_target_price
        else:
            unit_price = sum(all_lines.mapped("price_subtotal"))

        return {
            "equipment": equipment,
            "groups": groups,
            "footer": {
                "days": sum(g["days"] for g in groups),
                "unit_price": unit_price,
            },
        }

    def _qualif_scope_tables(self):
        """Tabelas de escopo de todos os equipamentos, na ordem do resumo.

        Equipamento cujas linhas foram todas declinadas/optadas fora não
        gera tabela (grupos vazios) e é omitido — os itens declinados
        continuam aparecendo no box de auditoria.
        """
        self.ensure_one()
        out = []
        for summary in self._qualif_equipment_summary():
            table = self._qualif_scope_table(summary["equipment"])
            if table["groups"]:
                out.append(table)
        return out
```

- [ ] **Step 5: Rodar e confirmar que passam**

Mesmo comando do Step 2. Esperado: PASS, 12 testes.

- [ ] **Step 6: Commit**

```
feat(qualificacao): aggregate the per-equipment scope table
```
Arquivos: `models/sale_order.py`, `tests/test_scope_table.py`. Push `origin main`.

---

### Task 4: Totais com adicionais enumerados

**Files:**
- Modify: `models/sale_order.py:357-440` (`_qualif_proposal_totals`, `_qualif_grand_total_html`)
- Modify: `tests/test_scope_table.py`

**Interfaces:**
- Consumes: `_qualif_scope_tables`, `_qualif_scope_lines` (Tasks 1 e 3).
- Produces:
  - `_qualif_additional_lines() -> list[{"name": str, "amount": float}]`
  - `_qualif_proposal_totals() -> {"equip_total", "adicionais", "residual", "grand_total"}` — chaves `optional_total` e `outros_total` **deixam de existir**.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_scope_table.py`:

```python
@tagged("post_install", "-at_install")
class TestProposalTotals(TestScopeTable):
    """Herda os fixtures de TestScopeTable (_full_so, _line, _section)."""

    def _extra(self, so, name, price):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "name": name,
            "product_uom_qty": 1.0,
            "price_unit": price,
        })

    def test_additional_lines_are_enumerated_by_name(self):
        so = self._full_so()
        self._extra(so, "Despesas de viagem, hospedagem e alimentação", 1000.0)
        self._extra(so, "Pasta impressa e envio correio", 400.0)
        adicionais = so._qualif_additional_lines()
        self.assertEqual(
            [a["name"] for a in adicionais],
            ["Despesas de viagem, hospedagem e alimentação",
             "Pasta impressa e envio correio"],
        )
        self.assertAlmostEqual(adicionais[0]["amount"], 1000.0, places=2)

    def test_accepted_optional_with_equipment_is_an_additional(self):
        """Rateio exclui opcional; se ele não virasse adicional, sumia."""
        so = self._full_so()
        opt = self._line(so, self.equip1, "performance", False, 700.0,
                         cycle=self.cycle_cmin, name="Ciclo extra opcional")
        opt.write({"is_proposal_optional": True, "optional_accepted": True})
        nomes = [a["name"] for a in so._qualif_additional_lines()]
        self.assertIn("Ciclo extra opcional", nomes)

    def test_declined_optional_is_not_listed(self):
        so = self._full_so()
        opt = self._line(so, self.equip1, "performance", False, 700.0,
                         cycle=self.cycle_cmin, name="Ciclo recusado")
        opt.write({"is_proposal_optional": True, "optional_accepted": False,
                   "product_uom_qty": 0.0})
        nomes = [a["name"] for a in so._qualif_additional_lines()]
        self.assertNotIn("Ciclo recusado", nomes)

    def test_sections_are_not_additionals(self):
        so = self._full_so()
        nomes = [a["name"] for a in so._qualif_additional_lines()]
        self.assertNotIn(self.equip1.display_name, nomes)

    def test_totals_reconcile_with_amount_untaxed(self):
        so = self._full_so()
        self._extra(so, "Despesas de viagem", 1000.0)
        totals = so._qualif_proposal_totals()
        self.assertAlmostEqual(totals["residual"], 0.0, places=2)
        self.assertAlmostEqual(
            totals["equip_total"] + sum(a["amount"] for a in totals["adicionais"]),
            totals["grand_total"], places=2,
        )

    def test_residual_absorbs_unaccounted_money(self):
        """Alvo desviado não pode fazer dinheiro sumir do total impresso."""
        so = self._full_so()
        self.section.equipment_target_price = self.section.equipment_subtotal
        # força drift artificial mexendo no alvo depois de 'ok'
        self.section.equipment_target_price = self.section.equipment_subtotal + 50.0
        totals = so._qualif_proposal_totals()
        self.assertAlmostEqual(
            totals["equip_total"]
            + sum(a["amount"] for a in totals["adicionais"])
            + totals["residual"],
            totals["grand_total"], places=2,
        )

    def test_no_additionals_yields_empty_list(self):
        so = self._full_so()
        self.assertEqual(so._qualif_proposal_totals()["adicionais"], [])

    def test_grand_total_html_lists_additionals(self):
        so = self._full_so()
        self._extra(so, "Pasta impressa e envio correio", 400.0)
        html = str(so._qualif_grand_total_html())
        self.assertIn("Total dos Serviços de Qualificação", html)
        self.assertIn("Pasta impressa e envio correio", html)
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)

    def test_grand_total_html_omits_breakdown_without_additionals(self):
        so = self._full_so()
        html = str(so._qualif_grand_total_html())
        self.assertNotIn("Total dos Serviços de Qualificação", html)
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)
```

- [ ] **Step 2: Rodar e confirmar falha**

```
--test-tags /afr_qualificacao:TestProposalTotals
```
Esperado: FAIL com `AttributeError: ... '_qualif_additional_lines'`.

- [ ] **Step 3: Implementar `_qualif_additional_lines` e reescrever `_qualif_proposal_totals`**

Substituir o corpo de `_qualif_proposal_totals` (`models/sale_order.py:357`) e acrescentar o helper novo logo antes dele:

```python
    def _qualif_additional_lines(self):
        """Adicionais: tudo que não entra no escopo de nenhum equipamento.

        Ex.: despesas de viagem, pasta impressa, e também opcionais
        ACEITOS (o rateio os exclui do escopo; sem esta regra o valor
        sumiria do impresso sem sumir do amount_untaxed).
        Opcional recusado tem product_uom_qty=0 → subtotal 0 → fora,
        sem precisar de regra especial.
        """
        self.ensure_one()
        in_scope = self.env["sale.order.line"]
        for table in self._qualif_scope_tables():
            in_scope |= self._qualif_scope_lines(table["equipment"])
        out = []
        for line in self.order_line.sorted(key=lambda l: (l.sequence, l.id)):
            if line.display_type or line in in_scope:
                continue
            if self.currency_id.is_zero(line.price_subtotal):
                continue
            out.append({
                "name": line.name or line.product_id.display_name or "",
                "amount": line.price_subtotal,
            })
        return out

    def _qualif_proposal_totals(self):
        """Totais da proposta — fonte única do form, do PDF e do portal.

        `grand_total` continua sendo `amount_untaxed` (o total real). Ele
        é decomposto em:

        - `equip_total`: soma dos Valores Unitários IMPRESSOS nas tabelas
          de escopo (preço-alvo quando bate, soma real quando desviado).
        - `adicionais`: lista enumerada `[{"name", "amount"}]`.
        - `residual`: o que sobra. Deve ser zero; quando não for (alvo
          desviado, arredondamento), é impresso como linha "Outros" para
          que nenhum valor do amount_untaxed fique invisível — foi
          exatamente esse o bug C26-06-0005.
        """
        self.ensure_one()
        equip_total = sum(
            t["footer"]["unit_price"] for t in self._qualif_scope_tables())
        adicionais = self._qualif_additional_lines()
        grand_total = self.amount_untaxed
        residual = self.currency_id.round(
            grand_total - equip_total - sum(a["amount"] for a in adicionais))
        return {
            "equip_total": equip_total,
            "adicionais": adicionais,
            "residual": residual,
            "grand_total": grand_total,
        }
```

- [ ] **Step 4: Reescrever `_qualif_grand_total_html`**

Substituir o método inteiro (`models/sale_order.py:388` até o fim do método) por:

```python
    def _qualif_grand_total_html(self):
        """Banner de totais do form + base do bloco de totais do PDF.

        Sem adicionais nem residual, imprime só a linha do total geral.
        """
        self.ensure_one()
        totals = self._qualif_proposal_totals()
        rows = []
        breakdown = bool(totals["adicionais"]) or not self.currency_id.is_zero(
            totals["residual"])
        if breakdown:
            rows.append((
                _("Total dos Serviços de Qualificação"), totals["equip_total"]))
            for adicional in totals["adicionais"]:
                rows.append((adicional["name"], adicional["amount"]))
            if not self.currency_id.is_zero(totals["residual"]):
                rows.append((_("Outros"), totals["residual"]))
        body = "".join(
            '<tr><td style="padding:4px 12px;">%s</td>'
            '<td style="padding:4px 12px;text-align:right;">%s</td></tr>'
            % (escape(name), escape(formatLang(
                self.env, value, currency_obj=self.currency_id)))
            for name, value in rows
        )
        grand_str = formatLang(
            self.env, totals["grand_total"], currency_obj=self.currency_id)
        return Markup(
            '<div style="margin-top:12px;width:100%%;">'
            '<table style="border-collapse:collapse;width:100%%;'
            'font-size:12px;">%s'
            '<tr style="border-top:2px solid #333;">'
            '<td style="padding:6px 12px;font-weight:bold;">'
            'TOTAL GERAL DA PROPOSTA</td>'
            '<td style="padding:6px 12px;text-align:right;font-weight:bold;'
            'font-size:14px;">%s</td></tr>'
            '</table></div>'
        ) % (Markup(body), escape(grand_str))
```

`escape`, `Markup` e `formatLang` já estão importados no topo do arquivo
(`models/sale_order.py:19-21`) — não duplicar imports.

- [ ] **Step 5: Tirar a tabela de opcionais do banner do form**

Com os adicionais enumerados, um opcional aceito apareceria duas vezes no
painel: na tabela "Subtotais de Opcionais (aceitos)" e na linha de adicional
do total. No compute `_compute_qualif_subtotals_html` (`models/sale_order.py:~300`),
remover a concatenação do bloco de opcionais, deixando só o total:

```python
            html += str(order._qualif_grand_total_html())
```

isto é, apagar a linha `html = order._qualif_optionals_subtotals_html()`
e passar a inicializar `html` com o HTML de subtotais por equipamento que já
existia antes dela (conferir o corpo real do compute antes de editar — a
variável `html` é montada acima no mesmo método).

Apagar também o método `_qualif_optionals_subtotals_html`
(`models/sale_order.py:308-356`), que fica sem chamador. Se algum teste ainda
o referenciar, ele é ajustado na Task 8, Step 7.

- [ ] **Step 6: Rodar e confirmar que passam**

Mesmo comando do Step 2. Esperado: PASS, 9 testes.

- [ ] **Step 7: Rodar a suíte inteira e anotar o que quebrou**

```
--test-tags /afr_qualificacao
```
Esperado: falhas em `block_financial.xml`, `_html_financial`, portal e testes de opcionais que ainda usam `optional_total`/`outros_total`. **Não** corrigir agora — as Tasks 5-7 fazem isso. Anotar a lista no relatório da task.

- [ ] **Step 8: Commit**

```
feat(qualificacao): enumerate additionals in the proposal totals
```
Arquivos: `models/sale_order.py`, `tests/test_scope_table.py`. Push `origin main`.

---

### Task 5: Render PDF — tabela nova + bloco de totais

**Files:**
- Create: `reports/templates_blocos/block_totals.xml`
- Modify: `reports/templates_blocos/block_equipment_scope.xml`
- Modify: `reports/templates_blocos/block_financial.xml`
- Modify: `reports/templates_blocos/styles.xml`
- Modify: `__manifest__.py` (registrar o template novo)
- Create: `tests/test_scope_render.py`
- Modify: `tests/__init__.py`
- Modify: `tests/test_partes_qi_qo.py` (classe `TestPdfReportPartes`)

**Interfaces:**
- Consumes: `_qualif_scope_tables()`, `_qualif_proposal_totals()` (Tasks 3 e 4).
- Produces: template `afr_qualificacao.qq_totals_table`, consumido pelo escopo e pelo bloco financeiro.

- [ ] **Step 1: Registrar o teste novo**

Em `tests/__init__.py`:

```python
from . import test_scope_render
```

- [ ] **Step 2: Escrever os testes que falham**

Criar `tests/test_scope_render.py`:

```python
# -*- coding: utf-8 -*-
"""Renders da tabela de escopo — PDF, portal e HTML do bloco."""

from odoo.tests.common import tagged
from .test_scope_table import TestScopeTable


@tagged("post_install", "-at_install")
class TestScopePdfRender(TestScopeTable):

    def _render_pdf(self, so):
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "equipment_scope",
            "included": True,
        })
        report = self.env.ref("sale.action_report_saleorder")
        html, _ct = report._render_qweb_html(report.report_name, so.ids)
        return html.decode("utf-8") if isinstance(html, bytes) else html

    def _extra(self, so, name, price):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "name": name,
            "product_uom_qty": 1.0,
            "price_unit": price,
        })

    def test_pdf_has_group_labels(self):
        html = self._render_pdf(self._full_so())
        self.assertIn("QI (primeira parte)", html)
        self.assertIn("QO (primeira parte)", html)
        self.assertIn("QO (segunda parte)", html)

    def test_pdf_has_day_forecast_and_subtotal_rows(self):
        html = self._render_pdf(self._full_so())
        self.assertIn("Previsão de", html)
        self.assertIn("dia(s) de serviço", html)
        self.assertIn("Subtotal QI", html)
        self.assertIn("Subtotal QO", html)
        self.assertIn("Subtotal QD", html)

    def test_pdf_has_cycle_table_headers(self):
        html = self._render_pdf(self._full_so())
        self.assertIn("Execução dos ciclos com carga", html)
        self.assertIn("Quantidade", html)
        self.assertIn(self.cycle_cmax.name, html)

    def test_pdf_has_unit_price_footer(self):
        html = self._render_pdf(self._full_so())
        self.assertIn("Valor Unitário", html)

    def test_pdf_lists_additionals_in_totals(self):
        so = self._full_so()
        self._extra(so, "Despesas de viagem", 1000.0)
        html = self._render_pdf(so)
        self.assertIn("Total dos Serviços de Qualificação", html)
        self.assertIn("Despesas de viagem", html)
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)

    def test_pdf_totals_without_additionals_is_single_line(self):
        html = self._render_pdf(self._full_so())
        self.assertNotIn("Total dos Serviços de Qualificação", html)
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)
```

- [ ] **Step 3: Rodar e confirmar falha**

```
--test-tags /afr_qualificacao:TestScopePdfRender
```
Esperado: FAIL — o HTML ainda traz os bullets antigos, sem "Previsão de".

- [ ] **Step 4: Criar o sub-template de totais**

Criar `reports/templates_blocos/block_totals.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Bloco de totais compartilhado: usado no fim do Escopo por
         Equipamento e pelo bloco `financial` (que segue disponível como
         tipo, mesmo fora do template default). -->
    <template id="qq_totals_table">
        <t t-set="totals" t-value="doc._qualif_proposal_totals()"/>
        <t t-set="tot_breakdown"
           t-value="bool(totals['adicionais']) or not doc.currency_id.is_zero(totals['residual'])"/>
        <table class="qq-total-table">
            <t t-if="tot_breakdown">
                <tr>
                    <td class="qq-tot-label">Total dos Serviços de Qualificação</td>
                    <td class="qq-tot-value">
                        <span t-esc="totals['equip_total']"
                              t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                    </td>
                </tr>
                <t t-foreach="totals['adicionais']" t-as="adic">
                    <tr>
                        <td class="qq-tot-label" t-esc="adic['name']"/>
                        <td class="qq-tot-value">
                            <span t-esc="adic['amount']"
                                  t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                        </td>
                    </tr>
                </t>
                <tr t-if="not doc.currency_id.is_zero(totals['residual'])">
                    <td class="qq-tot-label">Outros</td>
                    <td class="qq-tot-value">
                        <span t-esc="totals['residual']"
                              t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                    </td>
                </tr>
            </t>
            <tr class="qq-total-grand">
                <td class="qq-tot-label">TOTAL GERAL DA PROPOSTA</td>
                <td class="qq-tot-value">
                    <span t-esc="totals['grand_total']"
                          t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                </td>
            </tr>
        </table>
    </template>
</odoo>
```

Registrar em `__manifest__.py`, na lista `data`, imediatamente antes de
`"reports/templates_blocos/block_equipment_scope.xml"`:

```python
        "reports/templates_blocos/block_totals.xml",
```

(Se a ordem exata dos `templates_blocos` no manifest divergir, inserir o
arquivo novo antes de qualquer template que o chame.)

- [ ] **Step 5: Reescrever o bloco de escopo do PDF**

Substituir, em `reports/templates_blocos/block_equipment_scope.xml`, todo o
conteúdo entre `<div t-att-class="sec_class">` e o comentário
`<!-- Box de auditoria ... -->` (ou seja: o título continua, o `t-foreach`
sobre `summary` sai inteiro e o box de declinados permanece intocado):

```xml
                                <t t-set="scope_tables" t-value="doc._qualif_scope_tables()"/>
                                <t t-foreach="scope_tables" t-as="st">
                                    <t t-set="equip_letter" t-value="chr(ord('a') + st_index)"/>
                                    <div class="qq-equip-card">
                                        <table class="qq-scope-table">
                                            <thead>
                                                <tr class="qq-scope-equip-header">
                                                    <td colspan="2">
                                                        <span class="qq-scope-equip-num"><t t-esc="equip_letter"/>.</span>
                                                        <span t-esc="st['equipment'].name"/>
                                                        <span class="qq-equip-meta">
                                                            <t t-if="st['equipment'].serial_number">
                                                                · S/N: <span t-esc="st['equipment'].serial_number"/>
                                                            </t>
                                                        </span>
                                                    </td>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <t t-foreach="st['groups']" t-as="grp">
                                                    <t t-foreach="grp['rows']" t-as="row">
                                                        <tr class="qq-scope-group-row">
                                                            <td class="qq-scope-stage" t-esc="row['label']"/>
                                                            <td class="qq-scope-description">
                                                                <t t-if="row['kind'] == 'ref'">
                                                                    <span t-esc="row['ref']"/>
                                                                </t>
                                                                <t t-elif="row['kind'] == 'cycles'">
                                                                    <div class="qq-scope-subtitle" t-esc="row['title']"/>
                                                                    <table class="qq-cycle-table">
                                                                        <thead>
                                                                            <tr>
                                                                                <th style="width: 22%;">Quantidade</th>
                                                                                <th>Ciclo</th>
                                                                                <th style="width: 22%;">Temperatura</th>
                                                                                <th style="width: 22%;"><t t-esc="row['time_label']"/></th>
                                                                            </tr>
                                                                        </thead>
                                                                        <tbody>
                                                                            <t t-foreach="row['cycles']" t-as="cyc">
                                                                                <tr>
                                                                                    <td t-esc="'%02d' % cyc['qty']"/>
                                                                                    <td t-esc="cyc['name']"/>
                                                                                    <td t-esc="cyc['temperature']"/>
                                                                                    <td t-esc="cyc['duration']"/>
                                                                                </tr>
                                                                            </t>
                                                                        </tbody>
                                                                    </table>
                                                                </t>
                                                                <t t-else="">
                                                                    <div class="qq-scope-subtitle" t-if="row['title']" t-esc="row['title']"/>
                                                                    <ul class="qq-scope-list">
                                                                        <li t-foreach="row['items']" t-as="it" t-esc="it"/>
                                                                    </ul>
                                                                </t>
                                                            </td>
                                                        </tr>
                                                    </t>
                                                    <tr class="qq-scope-subtotal-row">
                                                        <td t-esc="'Previsão de %.1f dia(s) de serviço' % grp['days']"/>
                                                        <td>
                                                            <t t-esc="grp['subtotal_label']"/>:
                                                            <span t-esc="grp['subtotal']"
                                                                  t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                                                        </td>
                                                    </tr>
                                                </t>
                                                <tr class="qq-scope-footer-row">
                                                    <td t-esc="'Previsão de %.1f dia(s) de serviço' % st['footer']['days']"/>
                                                    <td>
                                                        Valor Unitário:
                                                        <span t-esc="st['footer']['unit_price']"
                                                              t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </t>
                                <t t-call="afr_qualificacao.qq_totals_table"/>
```

O `<t t-set="declined_items" .../>` e todo o `<div t-if="declined_items" class="qq-declined-box">` continuam depois, inalterados.

- [ ] **Step 6: Apontar o bloco financeiro para o sub-template**

Em `reports/templates_blocos/block_financial.xml`, substituir as duas tabelas
(`qq-table` por equipamento e `qq-total-table`) por:

```xml
                                <t t-call="afr_qualificacao.qq_totals_table"/>
```

O título do bloco (`<div t-attf-class="qq-section-title...">`) fica.

- [ ] **Step 7: Adicionar os estilos**

Em `reports/templates_blocos/styles.xml`, depois do bloco `.qq-scope-declined`
(~linha 232):

```css
                    .qq-scope-group-row td { vertical-align: top; page-break-inside: avoid; }
                    .qq-scope-stage {
                        width: 32%;
                        font-weight: bold;
                        text-align: center;
                        vertical-align: middle;
                        background: var(--lq-gray-lighter, #f7f7f7);
                    }
                    .qq-scope-subtitle { font-weight: bold; margin-bottom: 4px; }
                    .qq-scope-list { margin: 0; padding-left: 18px; }
                    .qq-cycle-table {
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 4px;
                        page-break-inside: avoid;
                    }
                    .qq-cycle-table th, .qq-cycle-table td {
                        border: 1px solid var(--lq-gray-light);
                        padding: 3px 6px;
                        text-align: center;
                        font-size: 11px;
                    }
                    .qq-scope-subtotal-row td {
                        font-weight: bold;
                        background: var(--lq-gray-lighter, #f2f2f2);
                        text-align: center;
                    }
                    .qq-scope-footer-row td {
                        font-weight: bold;
                        background: var(--lq-brand-light, #e8eef5);
                        text-align: center;
                        font-size: 13px;
                    }
```

Se `--lq-gray-lighter` / `--lq-brand-light` não existirem no `:root` do
`styles.xml`, os fallbacks entre parênteses já cobrem; não inventar variáveis novas.

- [ ] **Step 8: Ajustar as assertions legadas do PDF**

Em `tests/test_partes_qi_qo.py`, classe `TestPdfReportPartes`, método
`test_pdf_report_groups_partes_seal_and_box`: trocar

```python
        self.assertIn("qq-scope-type-row", html)
```

por

```python
        self.assertIn("qq-scope-stage", html)
```

O resto do método fica (título do bloco, selo de declinado e box de auditoria
continuam válidos).

- [ ] **Step 9: Rodar os testes de render e os legados do PDF**

```
--test-tags /afr_qualificacao:TestScopePdfRender,/afr_qualificacao:TestPdfReportPartes
```
Esperado: PASS nos dois.

- [ ] **Step 10: Commit**

```
feat(qualificacao): render the scope table and totals block in the PDF
```
Arquivos: `reports/templates_blocos/block_totals.xml`,
`reports/templates_blocos/block_equipment_scope.xml`,
`reports/templates_blocos/block_financial.xml`,
`reports/templates_blocos/styles.xml`, `__manifest__.py`,
`tests/test_scope_render.py`, `tests/__init__.py`, `tests/test_partes_qi_qo.py`.
Push `origin main`.

---

### Task 6: Render do portal

**Files:**
- Modify: `views/sale_order_portal_template.xml` (escopo `:143`+, totais `:440`+)
- Modify: `tests/test_scope_render.py`
- Modify: `tests/test_partes_qi_qo.py` (classe `TestPortalPartes`)

**Interfaces:**
- Consumes: `_qualif_scope_tables()`, `_qualif_proposal_totals()`.
- Produces: nada novo — o portal só formata.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/test_scope_render.py`:

```python
@tagged("post_install", "-at_install")
class TestScopePortalRender(TestScopeTable):

    def _render_portal(self, so):
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "block_kind": "equipment_scope",
            "included": True,
        })
        html = self.env["ir.qweb"]._render(
            "afr_qualificacao.sale_order_online_qualif_content",
            {"sale_order": so},
        )
        return str(html)

    def test_portal_has_stage_column_and_forecast(self):
        html = self._render_portal(self._full_so())
        self.assertIn("lq-scope-stage", html)
        self.assertIn("Previsão de", html)
        self.assertIn("Subtotal QD", html)

    def test_portal_has_cycle_table(self):
        html = self._render_portal(self._full_so())
        self.assertIn("Execução dos ciclos com carga", html)
        self.assertIn(self.cycle_cmax.name, html)

    def test_portal_has_unit_price_and_grand_total(self):
        html = self._render_portal(self._full_so())
        self.assertIn("Valor Unitário", html)
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)

    def test_portal_lists_additionals(self):
        so = self._full_so()
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "name": "Pasta impressa e envio correio",
            "product_uom_qty": 1.0,
            "price_unit": 400.0,
        })
        html = self._render_portal(so)
        self.assertIn("Pasta impressa e envio correio", html)
        self.assertIn("Total dos Serviços de Qualificação", html)
```

- [ ] **Step 2: Rodar e confirmar falha**

```
--test-tags /afr_qualificacao:TestScopePortalRender
```
Esperado: FAIL — portal ainda traz `lq-scope-type-row`.

- [ ] **Step 3: Reescrever o escopo do portal**

Em `views/sale_order_portal_template.xml`, dentro de
`<t t-if="block.block_kind == 'equipment_scope'">`, substituir o
`<t t-foreach="summary" t-as="eq">` inteiro (até o fechamento do
`</t>` correspondente, antes do box de declinados) por:

```xml
                        <t t-set="scope_tables" t-value="sale_order._qualif_scope_tables()"/>
                        <t t-foreach="scope_tables" t-as="st">
                            <t t-set="equip_letter" t-value="chr(ord('a') + st_index)"/>
                            <div class="lq-equip-card">
                                <table class="lq-scope-table">
                                    <thead>
                                        <tr class="lq-scope-equip-header">
                                            <td colspan="2">
                                                <span class="lq-scope-equip-num"><t t-esc="equip_letter"/>.</span>
                                                <span t-esc="st['equipment'].name"/>
                                                <span class="lq-equip-meta">
                                                    <t t-if="st['equipment'].serial_number">
                                                        · S/N: <span t-esc="st['equipment'].serial_number"/>
                                                    </t>
                                                </span>
                                            </td>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <t t-foreach="st['groups']" t-as="grp">
                                            <t t-foreach="grp['rows']" t-as="row">
                                                <tr class="lq-scope-group-row">
                                                    <td class="lq-scope-stage" t-esc="row['label']"/>
                                                    <td class="lq-scope-description">
                                                        <t t-if="row['kind'] == 'ref'">
                                                            <span t-esc="row['ref']"/>
                                                        </t>
                                                        <t t-elif="row['kind'] == 'cycles'">
                                                            <div class="lq-scope-subtitle" t-esc="row['title']"/>
                                                            <div class="table-responsive">
                                                                <table class="table table-sm lq-cycle-table">
                                                                    <thead>
                                                                        <tr>
                                                                            <th>Quantidade</th>
                                                                            <th>Ciclo</th>
                                                                            <th>Temperatura</th>
                                                                            <th><t t-esc="row['time_label']"/></th>
                                                                        </tr>
                                                                    </thead>
                                                                    <tbody>
                                                                        <t t-foreach="row['cycles']" t-as="cyc">
                                                                            <tr>
                                                                                <td t-esc="'%02d' % cyc['qty']"/>
                                                                                <td t-esc="cyc['name']"/>
                                                                                <td t-esc="cyc['temperature']"/>
                                                                                <td t-esc="cyc['duration']"/>
                                                                            </tr>
                                                                        </t>
                                                                    </tbody>
                                                                </table>
                                                            </div>
                                                        </t>
                                                        <t t-else="">
                                                            <div class="lq-scope-subtitle" t-if="row['title']" t-esc="row['title']"/>
                                                            <ul class="lq-scope-list">
                                                                <li t-foreach="row['items']" t-as="it" t-esc="it"/>
                                                            </ul>
                                                        </t>
                                                    </td>
                                                </tr>
                                            </t>
                                            <tr class="lq-scope-subtotal-row">
                                                <td t-esc="'Previsão de %.1f dia(s) de serviço' % grp['days']"/>
                                                <td>
                                                    <t t-esc="grp['subtotal_label']"/>:
                                                    <span t-esc="grp['subtotal']"
                                                          t-options="{'widget': 'monetary', 'display_currency': sale_order.currency_id}"/>
                                                </td>
                                            </tr>
                                        </t>
                                        <tr class="lq-scope-footer-row">
                                            <td t-esc="'Previsão de %.1f dia(s) de serviço' % st['footer']['days']"/>
                                            <td>
                                                Valor Unitário:
                                                <span t-esc="st['footer']['unit_price']"
                                                      t-options="{'widget': 'monetary', 'display_currency': sale_order.currency_id}"/>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </t>
                        <table class="lq-total-table">
                            <t t-set="totals" t-value="sale_order._qualif_proposal_totals()"/>
                            <t t-set="tot_breakdown"
                               t-value="bool(totals['adicionais']) or not sale_order.currency_id.is_zero(totals['residual'])"/>
                            <t t-if="tot_breakdown">
                                <tr>
                                    <td class="lq-tot-label">Total dos Serviços de Qualificação</td>
                                    <td class="lq-tot-value">
                                        <span t-esc="totals['equip_total']"
                                              t-options="{'widget': 'monetary', 'display_currency': sale_order.currency_id}"/>
                                    </td>
                                </tr>
                                <t t-foreach="totals['adicionais']" t-as="adic">
                                    <tr>
                                        <td class="lq-tot-label" t-esc="adic['name']"/>
                                        <td class="lq-tot-value">
                                            <span t-esc="adic['amount']"
                                                  t-options="{'widget': 'monetary', 'display_currency': sale_order.currency_id}"/>
                                        </td>
                                    </tr>
                                </t>
                                <tr t-if="not sale_order.currency_id.is_zero(totals['residual'])">
                                    <td class="lq-tot-label">Outros</td>
                                    <td class="lq-tot-value">
                                        <span t-esc="totals['residual']"
                                              t-options="{'widget': 'monetary', 'display_currency': sale_order.currency_id}"/>
                                    </td>
                                </tr>
                            </t>
                            <tr class="lq-total-grand">
                                <td class="lq-tot-label">TOTAL GERAL DA PROPOSTA</td>
                                <td class="lq-tot-value">
                                    <span t-esc="totals['grand_total']"
                                          t-options="{'widget': 'monetary', 'display_currency': sale_order.currency_id}"/>
                                </td>
                            </tr>
                        </table>
```

- [ ] **Step 4: Atualizar o bloco de totais antigo do portal**

O `financial` do portal (`:440`-`:470`) ainda usa `totals['outros_total']` e
`totals['optional_total']`, chaves que não existem mais. Substituir o corpo
daquela `<table class="lq-total-table">` pelo mesmo markup da tabela de totais
do Step 3 (o `<t t-set="totals" .../>` até o `</table>`).

- [ ] **Step 5: Estilos do portal**

No `<style>` do portal (mesma folha onde vivem `.lq-scope-table` e
`.lq-tot-label`), acrescentar:

```css
.lq-scope-group-row td { vertical-align: top; }
.lq-scope-stage { width: 32%; font-weight: 600; text-align: center; vertical-align: middle; background: #f7f7f7; }
.lq-scope-subtitle { font-weight: 600; margin-bottom: 4px; }
.lq-scope-list { margin: 0; padding-left: 18px; }
.lq-cycle-table th, .lq-cycle-table td { text-align: center; font-size: 0.85rem; }
.lq-scope-subtotal-row td { font-weight: 600; background: #f2f2f2; text-align: center; }
.lq-scope-footer-row td { font-weight: 700; background: #e8eef5; text-align: center; }
```

- [ ] **Step 6: Ajustar a assertion legada do portal**

Em `tests/test_partes_qi_qo.py`, `TestPortalPartes.test_portal_groups_partes_and_seal`:
trocar `self.assertIn("lq-scope-type-row", html)` por
`self.assertIn("lq-scope-stage", html)`.

- [ ] **Step 7: Rodar**

```
--test-tags /afr_qualificacao:TestScopePortalRender,/afr_qualificacao:TestPortalPartes
```
Esperado: PASS.

- [ ] **Step 8: Commit**

```
feat(qualificacao): mirror the scope table and totals in the portal
```
Arquivos: `views/sale_order_portal_template.xml`, `tests/test_scope_render.py`,
`tests/test_partes_qi_qo.py`. Push `origin main`.

---

### Task 7: Render HTML Python (DOCX / bloco editável)

**Files:**
- Modify: `models/proposal_block.py:239` (`_html_equipment_scope`) e `_html_financial`
- Modify: `tests/test_scope_render.py`
- Modify: `tests/test_partes_qi_qo.py` (classe `TestRenderPartes`)

**Interfaces:**
- Consumes: `_qualif_scope_tables()`, `_qualif_grand_total_html()`.
- Produces: nada novo.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/test_scope_render.py`:

```python
@tagged("post_install", "-at_install")
class TestScopeHtmlBlock(TestScopeTable):

    def _block(self, so, kind="equipment_scope"):
        return self.env["afr.proposal.block"].create({
            "sale_order_id": so.id, "block_kind": kind,
        })

    def test_html_scope_has_table_and_forecast(self):
        so = self._full_so()
        html = str(self._block(so)._html_equipment_scope(so))
        self.assertIn("<table", html)
        self.assertIn("Previsão de", html)
        self.assertIn("Subtotal QI", html)
        self.assertIn("Valor Unitário", html)

    def test_html_scope_has_cycle_rows(self):
        so = self._full_so()
        html = str(self._block(so)._html_equipment_scope(so))
        self.assertIn("Execução dos ciclos com carga", html)
        self.assertIn(self.cycle_cmax.name, html)

    def test_html_scope_keeps_declined_box(self):
        so = self._full_so()
        decl = self._line(so, self.equip1, "installation", "01", 900.0,
                          name="Verificação recusada")
        decl.write({"part01_declined": True, "product_uom_qty": 0.0})
        html = str(self._block(so)._html_equipment_scope(so))
        self.assertIn("Itens Não Solicitados", html)

    def test_html_financial_uses_new_totals(self):
        so = self._full_so()
        html = str(self._block(so, "financial")._html_financial(so))
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)

    def test_snapshot_to_static_preserves_table(self):
        so = self._full_so()
        block = self._block(so)
        block.action_edit_block()
        self.assertEqual(block.block_kind, "static")
        self.assertIn("Previsão de", str(block.body))
```

- [ ] **Step 2: Rodar e confirmar falha**

```
--test-tags /afr_qualificacao:TestScopeHtmlBlock
```
Esperado: FAIL — HTML atual não tem "Previsão de".

- [ ] **Step 3: Reescrever `_html_equipment_scope`**

Substituir o método inteiro (`models/proposal_block.py:239`-`~290`) por:

```python
    def _html_equipment_scope(self, order):
        """Snapshot HTML da tabela de escopo (DOCX + bloco editável).

        Espelha o QWeb `qq_block_equipment_scope`: uma tabela por
        equipamento, com etapa à esquerda e conteúdo à direita, linhas de
        previsão/subtotal por grupo e rodapé com Valor Unitário.
        """
        parts = []
        for index, table in enumerate(order._qualif_scope_tables()):
            equip = table["equipment"]
            letter = chr(ord("a") + index)
            head = escape("%s. %s" % (letter, equip.name or ""))
            if equip.serial_number:
                head += Markup(" — S/N: ") + escape(equip.serial_number)
            rows = [Markup(
                "<tr><td colspan='2'><strong>%s</strong></td></tr>") % head]
            for group in table["groups"]:
                for row in group["rows"]:
                    rows.append(Markup(
                        "<tr><td class='qq-scope-stage'>%s</td><td>%s</td></tr>"
                    ) % (escape(row["label"]), self._html_scope_cell(row)))
                rows.append(Markup(
                    "<tr class='qq-scope-subtotal-row'><td>%s</td>"
                    "<td>%s: %s</td></tr>"
                ) % (
                    escape("Previsão de %.1f dia(s) de serviço" % group["days"]),
                    escape(group["subtotal_label"]),
                    escape(self._money(order, group["subtotal"])),
                ))
            rows.append(Markup(
                "<tr class='qq-scope-footer-row'><td>%s</td>"
                "<td>Valor Unitário: %s</td></tr>"
            ) % (
                escape("Previsão de %.1f dia(s) de serviço"
                       % table["footer"]["days"]),
                escape(self._money(order, table["footer"]["unit_price"])),
            ))
            parts.append(Markup("<table class='qq-scope-table'>%s</table>")
                         % Markup("").join(rows))
        parts.append(order._qualif_grand_total_html())
        parts.append(self._html_declined_items(order))
        return Markup("").join(parts) or Markup("<p></p>")

    def _html_scope_cell(self, row):
        """Conteúdo da coluna direita de uma linha do escopo."""
        if row["kind"] == "ref":
            return escape(row["ref"])
        if row["kind"] == "cycles":
            body = Markup("").join(
                Markup("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>")
                % (
                    escape("%02d" % cyc["qty"]), escape(cyc["name"]),
                    escape(cyc["temperature"]), escape(cyc["duration"]),
                )
                for cyc in row["cycles"]
            )
            return Markup(
                "<div class='qq-scope-subtitle'><strong>%s</strong></div>"
                "<table class='qq-cycle-table'><thead><tr>"
                "<th>Quantidade</th><th>Ciclo</th><th>Temperatura</th>"
                "<th>%s</th></tr></thead><tbody>%s</tbody></table>"
            ) % (escape(row["title"]), escape(row["time_label"]), body)
        items = Markup("").join(
            Markup("<li>%s</li>") % escape(it) for it in row["items"])
        title = (
            Markup("<div class='qq-scope-subtitle'><strong>%s</strong></div>")
            % escape(row["title"]) if row["title"] else Markup("")
        )
        return title + Markup("<ul>%s</ul>") % items
```

- [ ] **Step 4: Apontar `_html_financial` para os totais novos**

Substituir o corpo de `_html_financial` (`models/proposal_block.py:~390`) por:

```python
    def _html_financial(self, order):
        """Bloco financeiro = bloco de totais (mesmo conteúdo do escopo)."""
        return order._qualif_grand_total_html()
```

- [ ] **Step 5: Ajustar as assertions legadas**

Em `tests/test_partes_qi_qo.py`, `TestRenderPartes.test_scope_html_groups_partes_and_seal`:
o HTML novo não emite mais os rótulos "PARTE 01"/"PARTE 02". Substituir o teste por:

```python
    def test_scope_html_groups_partes_and_seal(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        block = self._scope_block(so)
        html = str(block._html_equipment_scope(so))
        self.assertIn("QI (segunda parte)", html)
        self.assertIn("Calibração dos equipamentos de controle:", html)
        self.assertIn("NÃO SOLICITADO EXECUÇÃO", html)
```

`test_declined_box_present_only_when_declined` não muda.

- [ ] **Step 6: Rodar**

```
--test-tags /afr_qualificacao:TestScopeHtmlBlock,/afr_qualificacao:TestRenderPartes
```
Esperado: PASS.

- [ ] **Step 7: Commit**

```
feat(qualificacao): rebuild the scope block HTML snapshot on the new table
```
Arquivos: `models/proposal_block.py`, `tests/test_scope_render.py`,
`tests/test_partes_qi_qo.py`. Push `origin main`.

---

### Task 8: Template default, limpeza em bases existentes e suíte verde

**Files:**
- Modify: `data/proposal_template_seed.xml` (remover `l12` e `l13`)
- Create: `data/proposal_template_cleanup.xml`
- Modify: `__manifest__.py` (data file novo + versão `16.0.7.0.0`)
- Modify: testes remanescentes que quebrarem

**Interfaces:**
- Consumes: tudo das Tasks 1-7.
- Produces: template default sem `financial` nem `optionals`.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `tests/test_scope_render.py`:

```python
@tagged("post_install", "-at_install")
class TestTemplateCleanup(AfrQualificacaoTestCommon):

    def test_default_template_has_no_financial_or_optionals(self):
        tpl = self.env.ref(
            "afr_qualificacao.proposal_template_labquali",
            raise_if_not_found=False,
        )
        if not tpl:
            self.skipTest("template default não instalado nesta base")
        kinds = tpl.line_ids.mapped("block_kind")
        self.assertNotIn("financial", kinds)
        self.assertNotIn("optionals", kinds)
        self.assertIn("equipment_scope", kinds)
```

Adicionar o import no topo do arquivo:

```python
from .common import AfrQualificacaoTestCommon
```

Confirmar o nome do campo one2many do template (`line_ids`) lendo
`models/proposal_template.py`; se for outro, usar o nome real.

- [ ] **Step 2: Rodar e confirmar falha**

```
--test-tags /afr_qualificacao:TestTemplateCleanup
```
Esperado: FAIL — `financial` ainda está no template.

- [ ] **Step 3: Remover as linhas do seed**

Em `data/proposal_template_seed.xml`, apagar os dois `<record>` inteiros:
`proposal_template_labquali_l12` (block_kind `financial`) e
`proposal_template_labquali_l13` (block_kind `optionals`). No lugar, deixar o
comentário:

```xml
    <!-- Escopo tabela de ciclos (2026-08-20) — l12 (financial) e l13
         (optionals) removidos do template default: os totais passaram para
         o fim do bloco equipment_scope e os opcionais aceitos aparecem lá
         como adicionais. Os dois tipos de bloco continuam disponíveis para
         quem montar template manualmente. -->
```

Ajustar `page_break` da primeira linha seguinte (`l14`, seção
Responsabilidades) para `eval="True"`, já que a quebra de página vinha do `l12`.

- [ ] **Step 4: Criar o data file de limpeza**

Criar `data/proposal_template_cleanup.xml` — **sem** `noupdate`, para rodar em
todo `-u`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!--
        Escopo tabela de ciclos (2026-08-20).

        `proposal_template_seed.xml` é carregado apenas pelo post_init_hook,
        então remover os <record> de lá só afeta instalações novas. Este
        arquivo (sem noupdate) remove os blocos `financial` e `optionals` do
        template default em bases já instaladas, no próximo -u.

        Busca por template_id.code + block_kind em vez de ref() ao xmlid,
        porque os xmlids foram removidos do seed no mesmo commit.

        Só mexe no TEMPLATE. Blocos já materializados em cotações
        (afr.proposal.block) não são tocados de propósito — cotação antiga
        continua renderizando como foi montada.
    -->
    <delete model="afr.proposal.template.line"
            search="[('template_id.code', '=', 'TPL-LABQUALI'),
                     ('block_kind', 'in', ['financial', 'optionals'])]"/>
</odoo>
```

Registrar em `__manifest__.py`, na lista `data`, logo após
`"data/proposal_venda_calibracao_seed.xml"`:

```python
        # Escopo tabela de ciclos — remove financial/optionals do template
        # default em bases já instaladas (seed só roda no post_init_hook).
        "data/proposal_template_cleanup.xml",
```

- [ ] **Step 5: Bump de versão**

Em `__manifest__.py`, trocar `"version": "16.0.6.13.5"` por
`"version": "16.0.7.0.0"`.

- [ ] **Step 6: Rodar o teste do template**

```
--test-tags /afr_qualificacao:TestTemplateCleanup
```
Esperado: PASS.

- [ ] **Step 7: Rodar a suíte completa e zerar as falhas**

```
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
  --test-enable --test-tags /afr_qualificacao --stop-after-init
```

Suítes com maior chance de ainda quebrar e o que fazer em cada uma:

- `test_proposal_report.py::test_scope_bullet_process_word_follows_category` —
  o bullet com sufixo de processo não existe mais. Reescrever a assertion para
  conferir que o `time_label` da categoria aparece no cabeçalho da tabela de
  ciclos (`row['time_label']` via `_qualif_scope_table`), mantendo a troca de
  categoria no meio do teste.
- `test_proposal_report.py::test_render_equipment_scope_omits_cronograma_footer` —
  conferir que o texto que ele proíbe continua fora; se a nova linha "Previsão
  de ..." colidir com a assertion, ajustar o texto proibido para o do bloco
  Cronograma (`_qualif_schedule_rows`), não o do escopo.
- `test_optional_accepted.py` / `test_optional_wizard.py` — se assertarem
  `totals['optional_total']`, trocar por
  `[a['name'] for a in totals['adicionais']]`. O aceite em si não muda.
- `test_proposal_builder.py`, `test_docx_render.py`,
  `test_proposal_block_edit.py`, `test_quotation_report.py`,
  `test_hours_vs_cycles.py` — ajustar assertions de markup antigo
  (`qq-scope-type-row`, `PARTE 01`, `TOTAL OPCIONAIS`) para os marcadores
  novos (`qq-scope-stage`, `Previsão de`, `TOTAL GERAL DA PROPOSTA`).

Não relaxar assertion nenhuma para "passar": se o valor impresso estiver
errado, corrigir o código, não o teste.

- [ ] **Step 8: Validação manual no Odoo local**

1. `docker exec odoo_engenapp-web-1 odoo -d <db_dev> -u afr_qualificacao --stop-after-init`
2. `docker restart odoo_engenapp-web-1` (assets).
3. Via `agent-browser`, em `http://localhost:8083`: criar cotação com autoclave
   (QI parte 01, QO parte 01, 1 calibração, 3 ciclos QO sem carga, 3 ciclos QD
   com carga), preço-alvo rateado, uma linha avulsa "Despesas de viagem" e um
   opcional recusado.
4. Conferir nos três: PDF da proposta, página do portal e DOCX/bloco editável —
   Σ Valores Unitários + Σ adicionais == `amount_untaxed` do SO, e as previsões
   de dias por grupo somam a do rodapé.
5. Anexar/descrever no relatório da task o que foi visto em cada render.

- [ ] **Step 9: Commit e bump do pointer**

Commit no submodule:

```
feat(qualificacao)!: scope table with embedded cycles, days and totals

BREAKING CHANGE: blocos `financial` e `optionals` saem do template
default; totais passam para o fim do bloco `equipment_scope`.
```
Arquivos: `data/proposal_template_seed.xml`, `data/proposal_template_cleanup.xml`,
`__manifest__.py`, testes ajustados. Push `origin main`.

Depois, no monorepo `/home/afonso/docker/odoo_engenapp`:

```
chore: bump submodule afr_qualificacao (escopo tabela de ciclos v16.0.7.0.0)
```

---

## Self-Review

**Cobertura da spec:**

| Spec | Task |
|---|---|
| D1 agrupamento | T3 (`SCOPE_GROUPS`) |
| D2 rótulo "Subtotal QD" | T3 |
| D3 dias = soma dos arredondados | T1 + T3 |
| D4 Valor Unitário / drift | T3 |
| D5 conjunto = `_rateio_base_lines` | T1 |
| D6 remissiva QI-1/QO-1 | T2 + T3 |
| D7 numeração automática | T2 |
| D8 letras no cabeçalho | T5/T6/T7 |
| D9 colunas dos ciclos | T5/T6/T7 |
| D10 três renders | T5, T6, T7 |
| D11 financial fora do default | T8 |
| D12 cycle_specs intocado | — (nenhuma task o toca, por desenho) |
| D13 optionals fora do default | T8 |
| D14 adicionais | T4 |
| D15 total geral + residual | T4 + T5 |

**Consistência de tipos:** `_qualif_scope_table` devolve `groups[].rows[]` com
`kind` ∈ {`ref`, `list`, `cycles`}; os três renders fazem o mesmo despacho
sobre esse campo. `_qualif_proposal_totals` devolve `adicionais` (lista) e
`residual` (float) em T4, e é lido com esses nomes em T5, T6 e T7.

**Riscos anotados no plano:** quebra de página do wkhtmltopdf (mitigada com
`page-break-inside: avoid` em T5, Step 7) e equipamentos cujo escopo fica
vazio saírem da numeração por letra (documentado no docstring de
`_qualif_scope_tables`, T3).
