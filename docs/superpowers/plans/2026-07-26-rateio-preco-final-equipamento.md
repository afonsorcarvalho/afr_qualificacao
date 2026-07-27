# Rateio de Preço Final por Equipamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que o vendedor digite um preço final fechado por equipamento na cotação e o sistema back-calcule os `price_unit` das linhas daquele equipamento, de forma que a soma dos subtotais bata exatamente no valor negociado.

**Architecture:** Um helper puro sem ORM (`models/price_allocation.py`) faz toda a matemática — rateio proporcional, arredondamento HALF-UP e busca de resíduo em memória. A camada ORM (`sale.order.line._apply_equipment_target`) monta a base de linhas, chama o helper, faz **um** `write` e **uma** releitura de `price_subtotal` para verificar. A UI é uma aba nova com um one2many dedicado às linhas de section (o tree padrão usa `section_and_note_one2many`, que esconde colunas em sections).

**Tech Stack:** Odoo 16.0, Python 3.9, `odoo.tests.common.TransactionCase`, `odoo.tools.float_round` / `float_compare`, XML views (QWeb form/tree).

## Global Constraints

- Módulo: `afr_qualificacao`, submodule git em `/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao`. Commits e pushes **de dentro** desse diretório.
- Odoo 16.0. Precisão decimal "Product Price" = 2 casas — **não alterar** (é global).
- Nunca usar `round()` puro em dinheiro. Sempre `float_round(x, precision_digits=2, rounding_method='HALF-UP')` ou `currency.round(x)`.
- Comparação de floats sempre via `float_compare(a, b, precision_digits=2)`, nunca `==`.
- Rodar testes: delegar ao subagente `test-runner`. Comando de referência:
  `docker exec -u root odoo-engenapp odoo -d odoo-labquali -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init` — **nunca** `odoo-bin`.
- Testes herdam `AfrQualificacaoTestCommon` (`tests/common.py`) e usam `@tagged("post_install", "-at_install")`, seguindo o padrão de `tests/test_optional_ref_subtotal.py`.
- Todo arquivo `.py` novo precisa ser registrado no `__init__.py` correspondente.
- Bump de versão no `__manifest__.py` só na última task (feat → MINOR: `16.0.6.3.5` → `16.0.6.4.0`).
- Commits em português no corpo, subject em inglês no formato Conventional Commits. Commit via subagente `git-commit-push`, sem push até o user validar.

---

### Task 1: Helper puro de rateio (`price_allocation.py`)

Toda a matemática vive aqui, sem ORM. É a parte de maior risco e a mais barata de testar.

**Files:**
- Create: `models/price_allocation.py`
- Modify: `models/__init__.py`
- Test: `tests/test_price_allocation.py` (novo), `tests/__init__.py`

**Interfaces:**
- Consumes: nada (função pura, só `odoo.tools.float_round`).
- Produces:
  - `allocate_target(target, lines, digits=2)` → `dict` com as chaves:
    - `"price_units"`: `list[float]` — o `price_unit` a gravar em cada linha, na mesma ordem de `lines`
    - `"achieved"`: `float` — soma dos subtotais previstos
    - `"exact"`: `bool` — `True` se `achieved == target`
    - `lines` é `list[tuple[float, float]]` de `(qty, subtotal_atual)`.
  - `subtotal_for(qty, price_unit, digits=2)` → `float` — subtotal previsto de uma linha.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_price_allocation.py`:

```python
# -*- coding: utf-8 -*-
"""Testes puros do helper de rateio (sem ORM — TransactionCase desnecessário)."""

from odoo.tests.common import TransactionCase, tagged

from ..models.price_allocation import allocate_target, subtotal_for


@tagged("post_install", "-at_install")
class TestPriceAllocation(TransactionCase):

    def _achieved(self, lines, price_units):
        return sum(
            subtotal_for(qty, pu)
            for (qty, _sub), pu in zip(lines, price_units)
        )

    def test_half_up_rounding(self):
        """subtotal_for usa HALF-UP, não banker's rounding do Python."""
        # round(0.075, 2) do Python dá 0.07; a moeda do Odoo dá 0.08.
        self.assertEqual(subtotal_for(7.5, 0.01), 0.08)

    def test_exact_with_unit_line(self):
        """Linha qty=1 tem grade de R$ 0,01 — fecha exato sempre."""
        lines = [(7.5, 1500.0), (12.3, 2000.0), (1.0, 1000.0)]
        res = allocate_target(10000.0, lines)
        self.assertTrue(res["exact"])
        self.assertEqual(res["achieved"], 10000.0)
        self.assertEqual(self._achieved(lines, res["price_units"]), 10000.0)

    def test_exact_only_fractional_lines(self):
        """Sem linha qty=1: a busca combinada precisa fechar."""
        lines = [(7.5, 1500.0), (12.3, 2000.0)]
        res = allocate_target(10000.0, lines)
        self.assertTrue(res["exact"])
        self.assertEqual(self._achieved(lines, res["price_units"]), 10000.0)

    def test_proportion_preserved(self):
        """Dobrar o alvo dobra cada price_unit (mix preservado)."""
        lines = [(1.0, 1000.0), (1.0, 3000.0)]
        res = allocate_target(8000.0, lines)
        self.assertEqual(res["price_units"], [2000.0, 6000.0])

    def test_degenerate_tiny_target(self):
        """Alvo minúsculo com linha longa: sem preço negativo, sem resíduo perdido."""
        lines = [(100.0, 10000.0), (1.0, 100.0)]
        res = allocate_target(10.0, lines)
        self.assertTrue(all(pu >= 0.0 for pu in res["price_units"]))
        self.assertEqual(self._achieved(lines, res["price_units"]),
                         res["achieved"])

    def test_idempotent(self):
        """Rodar sobre o resultado anterior não muda nada."""
        lines = [(7.5, 1500.0), (12.3, 2000.0), (1.0, 1000.0)]
        first = allocate_target(10000.0, lines)
        relines = [
            (qty, subtotal_for(qty, pu))
            for (qty, _s), pu in zip(lines, first["price_units"])
        ]
        second = allocate_target(10000.0, relines)
        self.assertEqual(second["price_units"], first["price_units"])

    def test_reports_inexact_without_crashing(self):
        """Alvo inatingível: devolve exact=False com a melhor aproximação."""
        # Uma única linha de 3h: grade de R$ 0,03. Alvo em 0,01 é inatingível.
        lines = [(3.0, 300.0)]
        res = allocate_target(1000.01, lines)
        self.assertFalse(res["exact"])
        self.assertLess(abs(res["achieved"] - 1000.01), 0.03)
```

Registrar em `tests/__init__.py`:

```python
from . import test_price_allocation
```

- [ ] **Step 2: Rodar e confirmar que falha**

Delegar ao subagente `test-runner` com test-tags `/afr_qualificacao:TestPriceAllocation`.
Esperado: FAIL com `ModuleNotFoundError` / `ImportError: cannot import name 'allocate_target'`.

- [ ] **Step 3: Implementar o helper**

Criar `models/price_allocation.py`:

```python
# -*- coding: utf-8 -*-
"""Rateio de um preço-alvo entre linhas de venda — matemática pura, sem ORM.

O processo é o inverso da precificação normal: em vez de somar subtotais para
achar o total, parte-se do total negociado e distribui-se proporcionalmente ao
subtotal atual de cada linha, back-calculando o `price_unit`.

Restrição central: `price_unit` tem 2 casas decimais (precisão global "Product
Price") e as quantidades são horas fracionárias. Um centavo no `price_unit` de
uma linha de 7,5h move o subtotal R$ 0,075 → nem todo alvo é alcançável mexendo
numa linha só. Daí a busca combinada em `_search_residual`.

Todo arredondamento é HALF-UP (moeda), nunca o banker's rounding do `round()`.
"""

from odoo.tools import float_round

# Quantas linhas a busca combinada pode ajustar, e em quantos centavos.
_SEARCH_MAX_LINES = 3
_SEARCH_MAX_CENTS = 20


def _round(value, digits=2):
    return float_round(value, precision_digits=digits, rounding_method="HALF-UP")


def subtotal_for(qty, price_unit, digits=2):
    """Subtotal previsto de uma linha, com o mesmo arredondamento do Odoo."""
    return _round(qty * price_unit, digits)


def allocate_target(target, lines, digits=2):
    """Distribui `target` entre `lines` proporcionalmente ao subtotal atual.

    :param target: total desejado (sem impostos)
    :param lines: list[(qty, subtotal_atual)]
    :param digits: casas decimais da moeda
    :return: dict(price_units=list[float], achieved=float, exact=bool)
    """
    if not lines:
        return {"price_units": [], "achieved": 0.0, "exact": False}

    base = sum(sub for _qty, sub in lines)
    if not base:
        return {"price_units": [], "achieved": 0.0, "exact": False}

    # 1. Shares proporcionais, arredondados; resíduo na maior linha.
    shares = [_round(target * sub / base, digits) for _qty, sub in lines]
    residual = _round(target - sum(shares), digits)
    biggest = max(range(len(lines)), key=lambda i: lines[i][1])
    shares[biggest] = _round(shares[biggest] + residual, digits)

    # 2. Back-calc do price_unit (nunca negativo).
    price_units = []
    for (qty, _sub), share in zip(lines, shares):
        pu = _round(share / qty, digits) if qty else 0.0
        price_units.append(max(pu, 0.0))

    # 3. O arredondamento do price_unit desloca o subtotal — mede o desvio.
    achieved = _round(
        sum(subtotal_for(qty, pu, digits)
            for (qty, _sub), pu in zip(lines, price_units)),
        digits,
    )
    diff = _round(target - achieved, digits)
    if diff:
        adjusted = _search_residual(lines, price_units, diff, digits)
        if adjusted is not None:
            price_units = adjusted
            achieved = _round(
                sum(subtotal_for(qty, pu, digits)
                    for (qty, _sub), pu in zip(lines, price_units)),
                digits,
            )

    return {
        "price_units": price_units,
        "achieved": achieved,
        "exact": not _round(target - achieved, digits),
    }


def _search_residual(lines, price_units, diff, digits=2):
    """Procura ajuste de n centavos no price_unit de até 3 linhas p/ zerar `diff`.

    Puro e em memória: nenhuma escrita no ORM aqui. Devolve a nova lista de
    price_units, ou None se nenhuma combinação fecha.

    As linhas são tentadas da grade mais fina para a mais grossa — a grade de uma
    linha é `qty × 0,01`, o quanto seu subtotal anda por centavo de price_unit.
    """
    step = 10 ** -digits
    order = sorted(range(len(lines)), key=lambda i: lines[i][0])
    candidates = order[:_SEARCH_MAX_LINES]

    def delta_for(idx, cents):
        qty = lines[idx][0]
        novo = _round(price_units[idx] + cents * step, digits)
        if novo < 0.0:
            return None
        return _round(
            subtotal_for(qty, novo, digits)
            - subtotal_for(qty, price_units[idx], digits),
            digits,
        )

    cents_range = [
        c for c in range(-_SEARCH_MAX_CENTS, _SEARCH_MAX_CENTS + 1) if c
    ]

    # 1 linha
    for idx in candidates:
        for cents in cents_range:
            d = delta_for(idx, cents)
            if d is not None and not _round(d - diff, digits):
                out = list(price_units)
                out[idx] = _round(out[idx] + cents * step, digits)
                return out

    # 2 linhas
    for a_pos, a in enumerate(candidates):
        for b in candidates[a_pos + 1:]:
            for ca in cents_range:
                da = delta_for(a, ca)
                if da is None:
                    continue
                for cb in cents_range:
                    db = delta_for(b, cb)
                    if db is None:
                        continue
                    if not _round(da + db - diff, digits):
                        out = list(price_units)
                        out[a] = _round(out[a] + ca * step, digits)
                        out[b] = _round(out[b] + cb * step, digits)
                        return out
    return None
```

Registrar em `models/__init__.py` (antes dos demais imports de model, é módulo puro):

```python
from . import price_allocation
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Delegar ao `test-runner`, test-tags `/afr_qualificacao:TestPriceAllocation`.
Esperado: 7 testes PASS.

- [ ] **Step 5: Commit**

Via subagente `git-commit-push`, cwd `/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao`, sem push:

```
feat(qualificacao): add pure price allocation helper
```

---

### Task 2: Campos de alvo e desvio na linha de section

**Files:**
- Modify: `models/sale_order_line.py` (campos novos após `equipment_subtotal`, linha ~229; e o `_compute_equipment_subtotal`, linhas 241-257)
- Test: `tests/test_equipment_target_price.py` (novo), `tests/__init__.py`

**Interfaces:**
- Consumes: nada da Task 1 ainda.
- Produces (usados nas Tasks 3, 4 e 5):
  - `sale.order.line.equipment_target_price` — Monetary, editável, `copy=True`
  - `sale.order.line.equipment_target_delta` — Monetary, compute `_compute_equipment_target_delta`
  - `sale.order.line.equipment_target_state` — Selection compute, valores `'none' | 'ok' | 'drift'`
  - `sale.order.line._rateio_base_lines()` → recordset das linhas elegíveis do equipamento (chamado na section line)

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_equipment_target_price.py`:

```python
# -*- coding: utf-8 -*-
"""Rateio de preço final por equipamento — camada ORM."""

from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestEquipmentTargetPrice(AfrQualificacaoTestCommon):

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _section(self, so, equip):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "display_type": "line_section",
            "name": equip.display_name,
            "is_qualificacao_managed": True,
            "equipment_id": equip.id,
        })

    def _cycle_line(self, so, equip, qty_cycles, hours, price):
        """Linha de ciclo: product_uom_qty = horas = nº ciclos × horas/ciclo."""
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo",
            "is_qualificacao_managed": True,
            "qualification_type": "performance",
            "equipment_id": equip.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": qty_cycles,
            "estimated_hours": hours,
            "product_uom_qty": qty_cycles * hours,
            "price_unit": price,
        })

    def test_base_excludes_section_and_optional(self):
        so = self._so()
        section = self._section(so, self.equip1)
        firme = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        opcional = self._cycle_line(so, self.equip1, 1, 1.0, 500.0)
        opcional.write({"is_proposal_optional": True,
                        "optional_accepted": True})
        base = section._rateio_base_lines()
        self.assertIn(firme, base)
        self.assertNotIn(opcional, base)
        self.assertNotIn(section, base)

    def test_base_excludes_declined_part01(self):
        so = self._so()
        section = self._section(so, self.equip1)
        firme = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        declinada = self._cycle_line(so, self.equip1, 1, 1.0, 900.0)
        declinada.write({"part": "01", "part01_declined": True,
                         "product_uom_qty": 0.0})
        base = section._rateio_base_lines()
        self.assertEqual(base, firme)

    def test_state_none_without_target(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        self.assertEqual(section.equipment_target_state, "none")
        self.assertEqual(section.equipment_target_delta, 0.0)

    def test_state_drift_and_delta(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)  # 7,5h × 200 = 1500
        section.equipment_target_price = 1200.0
        self.assertEqual(section.equipment_target_state, "drift")
        self.assertEqual(section.equipment_target_delta, 300.0)

    def test_state_ok_when_matching(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        section.equipment_target_price = 1500.0
        self.assertEqual(section.equipment_target_state, "ok")
        self.assertEqual(section.equipment_target_delta, 0.0)

    def test_equipment_subtotal_excludes_optionals(self):
        """equipment_subtotal alinhado com a base do rateio."""
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        opcional = self._cycle_line(so, self.equip1, 1, 1.0, 500.0)
        opcional.write({"is_proposal_optional": True,
                        "optional_accepted": True})
        self.assertEqual(section.equipment_subtotal, 1500.0)
```

Registrar em `tests/__init__.py`:

```python
from . import test_equipment_target_price
```

- [ ] **Step 2: Rodar e confirmar que falha**

`test-runner`, test-tags `/afr_qualificacao:TestEquipmentTargetPrice`.
Esperado: FAIL com `AttributeError` / `Invalid field 'equipment_target_price'`.

- [ ] **Step 3: Implementar campos e computes**

Em `models/sale_order_line.py`, substituir o bloco `equipment_subtotal` +
`_compute_equipment_subtotal` (linhas 229-257) por:

```python
    equipment_subtotal = fields.Monetary(
        compute="_compute_equipment_subtotal",
        string="Base do Rateio",
        currency_field="currency_id",
        help=(
            "Em linhas de section (display_type='line_section'), soma dos "
            "subtotais das linhas elegíveis ao rateio do mesmo equipment_id "
            "(managed, qty>0, não opcionais, não declinadas). Em demais "
            "linhas, 0."
        ),
    )
    equipment_target_price = fields.Monetary(
        string="Preço-Alvo",
        currency_field="currency_id",
        copy=True,
        help=(
            "Preço final fechado do equipamento (sem impostos). Ao ratear, "
            "os price_unit das linhas do equipamento são recalculados para "
            "que a soma dos subtotais bata neste valor."
        ),
    )
    equipment_target_delta = fields.Monetary(
        compute="_compute_equipment_target_delta",
        string="Desvio",
        currency_field="currency_id",
        help="equipment_subtotal − equipment_target_price. 0 se não há alvo.",
    )
    equipment_target_state = fields.Selection(
        selection=[
            ("none", "Sem alvo"),
            ("ok", "No alvo"),
            ("drift", "Desviado"),
        ],
        compute="_compute_equipment_target_delta",
        string="Situação do Alvo",
    )

    def _rateio_base_lines(self):
        """Linhas elegíveis ao rateio do equipamento desta section.

        Fora: sections/notas, opcionais (aceitos ou não), Parte 01 declinada,
        linhas não-managed e linhas com qty 0.
        """
        self.ensure_one()
        if not self.equipment_id:
            return self.env["sale.order.line"]
        return self.order_id.order_line.filtered(
            lambda l: l.equipment_id == self.equipment_id
            and l.is_qualificacao_managed
            and not l.display_type
            and not l.is_proposal_optional
            and not l.part01_declined
            and l.product_uom_qty > 0
        )

    # Os paths regular_line_ids.* são necessários porque as abas do form
    # editam por datapoints OWL distintos de order_line (mesmo motivo
    # documentado em _compute_qualif_subtotals_html).
    @api.depends(
        "display_type",
        "equipment_id",
        "order_id.order_line.equipment_id",
        "order_id.order_line.display_type",
        "order_id.order_line.price_subtotal",
        "order_id.order_line.is_proposal_optional",
        "order_id.order_line.part01_declined",
        "order_id.order_line.product_uom_qty",
        "order_id.regular_line_ids.price_subtotal",
    )
    def _compute_equipment_subtotal(self):
        for line in self:
            if line.display_type != "line_section" or not line.equipment_id:
                line.equipment_subtotal = 0.0
                continue
            line.equipment_subtotal = sum(
                line._rateio_base_lines().mapped("price_subtotal")
            )

    @api.depends("equipment_subtotal", "equipment_target_price",
                 "display_type", "equipment_id")
    def _compute_equipment_target_delta(self):
        for line in self:
            if line.display_type != "line_section" or not line.equipment_id \
                    or not line.equipment_target_price:
                line.equipment_target_delta = 0.0
                line.equipment_target_state = "none"
                continue
            delta = line.equipment_subtotal - line.equipment_target_price
            line.equipment_target_delta = delta
            same = float_compare(
                line.equipment_subtotal, line.equipment_target_price,
                precision_digits=2,
            ) == 0
            line.equipment_target_state = "ok" if same else "drift"
```

Adicionar o import no topo do arquivo, junto dos existentes:

```python
from odoo.tools import float_compare
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

`test-runner`, test-tags `/afr_qualificacao:TestEquipmentTargetPrice`.
Esperado: 6 testes PASS.

- [ ] **Step 5: Rodar a suíte inteira do módulo (guardar contra regressão)**

`test-runner`, suíte completa `afr_qualificacao`. Esperado: nenhuma falha nova
em relação à baseline. `equipment_subtotal` não é usado em nenhuma view nem
relatório (verificado), então a mudança de filtro não deve quebrar nada.

- [ ] **Step 6: Commit**

```
feat(qualificacao): add equipment target price fields on section lines
```

---

### Task 3: `_apply_equipment_target` — rateio no ORM

**Files:**
- Modify: `models/sale_order_line.py` (novo método após `_compute_equipment_target_delta`)
- Test: `tests/test_equipment_target_price.py` (acrescentar métodos)

**Interfaces:**
- Consumes: `allocate_target` de `models/price_allocation.py` (Task 1); `_rateio_base_lines`, `equipment_target_price`, `equipment_target_state` (Task 2).
- Produces (usados na Task 4):
  - `sale.order.line.action_apply_equipment_target()` — botão da view; devolve `ir.actions.client` de notification quando o fechamento é inexato, senão `True`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/test_equipment_target_price.py`, dentro da classe:

```python
    def test_apply_exact_with_unit_line(self):
        """Alvo redondo com linha qty=1 na base: soma bate exatamente."""
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)   # 7,5h
        self._cycle_line(so, self.equip1, 3, 4.1, 300.0)   # 12,3h
        self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self.product_qs.id,
            "name": "QS", "is_qualificacao_managed": True,
            "qualification_type": "software", "equipment_id": self.equip1.id,
            "qualif_cycle_qty": 1, "estimated_hours": 1.0,
            "product_uom_qty": 1.0, "price_unit": 800.0,
        })
        section.equipment_target_price = 10000.0
        section._apply_equipment_target()
        self.assertEqual(
            sum(section._rateio_base_lines().mapped("price_subtotal")),
            10000.0)
        self.assertEqual(section.equipment_target_state, "ok")

    def test_apply_only_fractional_lines(self):
        """Sem linha qty=1: a busca combinada precisa fechar."""
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        self._cycle_line(so, self.equip1, 3, 4.1, 300.0)
        section.equipment_target_price = 10000.0
        section._apply_equipment_target()
        self.assertEqual(
            sum(section._rateio_base_lines().mapped("price_subtotal")),
            10000.0)

    def test_apply_is_idempotent(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        self._cycle_line(so, self.equip1, 3, 4.1, 300.0)
        section.equipment_target_price = 10000.0
        section._apply_equipment_target()
        first = section._rateio_base_lines().mapped("price_unit")
        section._apply_equipment_target()
        self.assertEqual(section._rateio_base_lines().mapped("price_unit"),
                         first)

    def test_apply_preserves_mix(self):
        """Proporção entre linhas mantida: 1000 e 3000 viram 2000 e 6000."""
        so = self._so()
        section = self._section(so, self.equip1)
        a = self._cycle_line(so, self.equip1, 1, 1.0, 1000.0)
        b = self._cycle_line(so, self.equip1, 1, 1.0, 3000.0)
        section.equipment_target_price = 8000.0
        section._apply_equipment_target()
        self.assertEqual(a.price_subtotal, 2000.0)
        self.assertEqual(b.price_subtotal, 6000.0)

    def test_apply_does_not_touch_excluded_lines(self):
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        declinada = self._cycle_line(so, self.equip1, 1, 1.0, 900.0)
        declinada.write({"part": "01", "part01_declined": True,
                         "product_uom_qty": 0.0})
        opcional = self._cycle_line(so, self.equip1, 1, 1.0, 500.0)
        opcional.write({"is_proposal_optional": True,
                        "optional_accepted": True})
        section.equipment_target_price = 3000.0
        section._apply_equipment_target()
        self.assertEqual(declinada.price_unit, 900.0)
        self.assertEqual(opcional.price_unit, 500.0)
        self.assertEqual(section.price_unit, 0.0)

    def test_apply_raises_when_base_is_free(self):
        from odoo.exceptions import UserError
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 0.0)
        section.equipment_target_price = 1000.0
        with self.assertRaises(UserError):
            section._apply_equipment_target()

    def test_apply_raises_when_base_is_empty(self):
        from odoo.exceptions import UserError
        so = self._so()
        section = self._section(so, self.equip1)
        section.equipment_target_price = 1000.0
        with self.assertRaises(UserError):
            section._apply_equipment_target()

    def test_zero_target_clears_without_touching_prices(self):
        so = self._so()
        section = self._section(so, self.equip1)
        linha = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        section.equipment_target_price = 0.0
        section._apply_equipment_target()
        self.assertEqual(linha.price_unit, 200.0)
        self.assertEqual(section.equipment_target_state, "none")

    def test_drift_after_editing_cycles(self):
        so = self._so()
        section = self._section(so, self.equip1)
        linha = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        section.equipment_target_price = 3000.0
        section._apply_equipment_target()
        self.assertEqual(section.equipment_target_state, "ok")
        linha.write({"qualif_cycle_qty": 4, "product_uom_qty": 4 * 2.5})
        self.assertEqual(section.equipment_target_state, "drift")
        self.assertEqual(section.equipment_target_delta, 1000.0)

    def test_inexact_posts_message_and_stays_drift(self):
        """Alvo inatingível: grava a melhor aproximação, avisa, fica drift."""
        so = self._so()
        section = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 1, 3.0, 100.0)  # grade R$ 0,03
        section.equipment_target_price = 1000.01
        section._apply_equipment_target()
        self.assertEqual(section.equipment_target_state, "drift")
        self.assertTrue(any(
            "arredondamento" in (m.body or "")
            for m in so.message_ids))
```

- [ ] **Step 2: Rodar e confirmar que falha**

`test-runner`, test-tags `/afr_qualificacao:TestEquipmentTargetPrice`.
Esperado: FAIL com `AttributeError: '_apply_equipment_target'`.

- [ ] **Step 3: Implementar**

Em `models/sale_order_line.py`, após `_compute_equipment_target_delta`:

```python
    def _apply_equipment_target(self):
        """Ratea equipment_target_price entre as linhas do equipamento.

        Um único write, seguido de uma releitura de price_subtotal — quem
        arredonda de verdade é o compute_all do Odoo, não a aritmética local.
        Devolve dict(exact=bool, achieved=float) para a camada de UI.
        """
        self.ensure_one()
        target = self.equipment_target_price
        if not target:
            return {"exact": True, "achieved": 0.0}

        base = self._rateio_base_lines()
        if not base:
            raise UserError(_(
                "Nenhuma linha elegível ao rateio para %s. Gere as linhas de "
                "qualificação antes de definir o preço-alvo."
            ) % (self.equipment_id.display_name or _("equipamento")))
        if not sum(base.mapped("price_subtotal")):
            raise UserError(_(
                "As linhas de %s estão com preço zerado — defina os preços "
                "base antes de ratear."
            ) % (self.equipment_id.display_name or _("equipamento")))

        pairs = [(l.product_uom_qty, l.price_subtotal) for l in base]
        result = allocate_target(target, pairs)

        for line, price_unit in zip(base, result["price_units"]):
            line.price_unit = price_unit

        # Verificação sobre o que o ORM realmente computou.
        base.invalidate_recordset(["price_subtotal"])
        achieved = sum(base.mapped("price_subtotal"))
        diff = float_round(target - achieved, precision_digits=2,
                           rounding_method="HALF-UP")
        if diff:
            self.order_id.message_post(body=_(
                "Rateio de %(equip)s fechou em %(achieved)s — %(diff)s de "
                "diferença para o alvo %(target)s (limite de arredondamento: "
                "o preço unitário tem 2 casas e as horas são fracionárias)."
            ) % {
                "equip": self.equipment_id.display_name or "",
                "achieved": formatLang(self.env, achieved,
                                       currency_obj=self.currency_id),
                "diff": formatLang(self.env, diff,
                                   currency_obj=self.currency_id),
                "target": formatLang(self.env, target,
                                     currency_obj=self.currency_id),
            })
        return {"exact": not diff, "achieved": achieved}

    def action_apply_equipment_target(self):
        """Botão 'Ratear' da linha na aba Preços por Equipamento."""
        self.ensure_one()
        res = self._apply_equipment_target()
        if res["exact"]:
            return True
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning",
                "title": _("Rateio aproximado"),
                "message": _(
                    "Fechou em %s — o alvo não é atingível com 2 casas no "
                    "preço unitário. Veja o histórico do pedido."
                ) % formatLang(self.env, res["achieved"],
                               currency_obj=self.currency_id),
                "sticky": False,
            },
        }
```

Ajustar os imports no topo do arquivo:

```python
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round
from odoo.tools.misc import formatLang

from .price_allocation import allocate_target
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

`test-runner`, test-tags `/afr_qualificacao:TestEquipmentTargetPrice`.
Esperado: 16 testes PASS (6 da Task 2 + 10 novos).

- [ ] **Step 5: Commit**

```
feat(qualificacao): allocate equipment target price across lines
```

---

### Task 4: UI — aba "Preços por Equipamento" e botão no header

**Files:**
- Modify: `models/sale_order.py` (novo one2many junto de `optional_line_ids`, linha ~148; novo método de ação; rótulo do painel HTML na linha ~296)
- Modify: `views/sale_order_views.xml` (nova page depois de `qualif_opcionais`; botão no header)
- Test: `tests/test_equipment_target_price.py` (acrescentar métodos)

**Interfaces:**
- Consumes: `action_apply_equipment_target`, `equipment_target_price`, `equipment_target_delta`, `equipment_target_state`, `equipment_subtotal` (Tasks 2-3).
- Produces:
  - `sale.order.equipment_target_ids` — one2many das sections com equipamento
  - `sale.order.action_apply_all_equipment_targets()` — botão do header

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/test_equipment_target_price.py`:

```python
    def test_equipment_target_ids_lists_only_sections(self):
        so = self._so()
        section = self._section(so, self.equip1)
        linha = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        self.assertIn(section, so.equipment_target_ids)
        self.assertNotIn(linha, so.equipment_target_ids)

    def test_apply_all_processes_every_drifted_equipment(self):
        so = self._so()
        s1 = self._section(so, self.equip1)
        self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        s2 = self._section(so, self.equip2)
        self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo eq2", "is_qualificacao_managed": True,
            "qualification_type": "performance", "equipment_id": self.equip2.id,
            "cycle_type_id": self.cycle_cmax.id, "qualif_cycle_qty": 2,
            "estimated_hours": 1.0, "product_uom_qty": 2.0,
            "price_unit": 300.0,
        })
        s1.equipment_target_price = 2000.0
        s2.equipment_target_price = 900.0
        so.action_apply_all_equipment_targets()
        self.assertEqual(s1.equipment_target_state, "ok")
        self.assertEqual(s2.equipment_target_state, "ok")

    def test_apply_all_skips_sections_without_target(self):
        so = self._so()
        section = self._section(so, self.equip1)
        linha = self._cycle_line(so, self.equip1, 3, 2.5, 200.0)
        so.action_apply_all_equipment_targets()   # sem alvo: não faz nada
        self.assertEqual(linha.price_unit, 200.0)
```

- [ ] **Step 2: Rodar e confirmar que falha**

`test-runner`, test-tags `/afr_qualificacao:TestEquipmentTargetPrice`.
Esperado: FAIL com `AttributeError: 'equipment_target_ids'`.

- [ ] **Step 3: Implementar o model**

Em `models/sale_order.py`, logo após `optional_line_ids`:

```python
    equipment_target_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="order_id",
        domain=[("display_type", "=", "line_section"),
                ("equipment_id", "!=", False)],
        string="Preços por Equipamento",
        help=(
            "Linhas de section com equipamento — onde vive o preço-alvo do "
            "rateio. Datapoint próprio porque o tree de linhas usa "
            "section_and_note_one2many, que esconde colunas em sections."
        ),
    )
```

E o método de ação (junto dos demais `action_*`):

```python
    def action_apply_all_equipment_targets(self):
        """Ratea todos os equipamentos com alvo definido e fora do alvo."""
        self.ensure_one()
        inexatos = []
        for section in self.equipment_target_ids:
            if section.equipment_target_state != "drift":
                continue
            res = section._apply_equipment_target()
            if not res["exact"]:
                inexatos.append(section.equipment_id.display_name or "")
        if not inexatos:
            return True
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning",
                "title": _("Rateio aproximado"),
                "message": _(
                    "Não foi possível fechar exatamente: %s. Veja o "
                    "histórico do pedido."
                ) % ", ".join(inexatos),
                "sticky": False,
            },
        }
```

Ainda em `models/sale_order.py`, no `_compute_qualif_subtotals_html`, trocar o
cabeçalho da coluna de subtotal para distingui-lo da base do rateio:

```python
                '<th style="padding:6px 12px;text-align:right;">Subtotal (c/ opcionais)</th>'
```

- [ ] **Step 4: Implementar a view**

Em `views/sale_order_views.xml`, dentro do `<xpath expr="//page[@name='order_lines']" position="before">`, logo após a page `qualif_opcionais`:

```xml
                <page string="Preços por Equipamento" name="qualif_precos"
                      attrs="{'invisible': [('has_qualif_lines','=',False)]}">
                    <field name="equipment_target_ids">
                        <tree editable="bottom" create="false" delete="false"
                              decoration-warning="equipment_target_state == 'drift'"
                              decoration-success="equipment_target_state == 'ok'">
                            <field name="equipment_target_state" invisible="1"/>
                            <field name="currency_id" invisible="1"/>
                            <field name="name" string="Equipamento" readonly="1"/>
                            <field name="equipment_subtotal" string="Base do Rateio"
                                   widget="monetary" readonly="1"/>
                            <field name="equipment_target_price" string="Preço-Alvo"
                                   widget="monetary"/>
                            <field name="equipment_target_delta" string="Desvio"
                                   widget="monetary" readonly="1"/>
                            <button name="action_apply_equipment_target"
                                    type="object" string="Ratear"
                                    icon="fa-balance-scale"
                                    attrs="{'invisible': [('equipment_target_state','=','none')]}"/>
                        </tree>
                    </field>
                </page>
```

E o botão do header, dentro do `<xpath expr="//header/button[@name='action_quotation_send']" position="before">`, após o botão do configurador:

```xml
                <button name="action_apply_all_equipment_targets"
                        string="Ratear Preços-Alvo"
                        type="object"
                        attrs="{'invisible': ['|', ('state','not in',['draft','sent']), ('has_qualif_lines','=',False)]}"/>
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

`test-runner`, test-tags `/afr_qualificacao:TestEquipmentTargetPrice`.
Esperado: 19 testes PASS.

- [ ] **Step 6: Validar a view no browser**

A view precisa carregar sem `ParseError` e a aba precisa renderizar de fato.

```bash
docker restart odoo-engenapp
```

Depois, com `agent-browser`: login em `http://localhost:8083`, abrir uma cotação
com linhas de qualificação (ex.: `C26-07-0009`), conferir que a aba "Preços por
Equipamento" lista os equipamentos, digitar um alvo redondo, clicar Ratear e
conferir que o subtotal do equipamento passa a bater com o alvo. Tirar
screenshot.

- [ ] **Step 7: Commit**

```
feat(qualificacao): add equipment target price tab and header action
```

---

### Task 5: Preservar o alvo no re-apply do wizard + bump de versão

**Files:**
- Modify: `wizards/qualificacao_configurator.py` (método `action_apply`, linha 410; o `unlink` está na linha 438 e a criação da section na 452)
- Modify: `__manifest__.py`
- Test: `tests/test_equipment_target_price.py` (acrescentar método)

**Interfaces:**
- Consumes: `equipment_target_price` (Task 2).
- Produces: nada novo.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `tests/test_equipment_target_price.py`:

Instanciação do wizard segue o padrão de `tests/test_configurator.py:15-36`
(`afr.qualificacao.configurator`, `_load_from_existing_lines()`, `action_apply()`):

```python
    def _open_wizard(self, so):
        wiz = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": so.id,
        })
        wiz._load_from_existing_lines()
        return wiz

    def test_target_survives_wizard_reapply(self):
        """Re-apply do configurador recria as sections — o alvo tem que voltar."""
        so = self._so()
        wiz = self._open_wizard(so)
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id,
            "qd_line_ids": [
                (0, 0, {"cycle_type_id": self.cycle_cmax.id, "qty": 3}),
            ],
        })]
        wiz.action_apply()

        section = so.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id == self.equip1
        )
        self.assertTrue(section, "wizard deveria ter criado a section")
        section.equipment_target_price = 5000.0

        # Re-apply: wizard novo, recarregado das linhas existentes.
        wiz2 = self._open_wizard(so)
        wiz2.action_apply()

        nova = so.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id == self.equip1
        )
        self.assertEqual(nova.equipment_target_price, 5000.0)
```

- [ ] **Step 2: Rodar e confirmar que falha**

`test-runner`, test-tags `/afr_qualificacao:TestEquipmentTargetPrice`.
Esperado: FAIL — `equipment_target_price` volta 0.0 na section recriada.

- [ ] **Step 3: Implementar a preservação**

Em `wizards/qualificacao_configurator.py`, **antes** do `unlink` da linha 438,
capturar os alvos existentes:

```python
        # Alvos de rateio vivem nas sections managed, que o unlink abaixo
        # apaga. Capturar antes e regravar nas sections novas (mesmo padrão
        # de config_template_id, que também é lido de volta das linhas).
        alvos_por_equip = {
            line.equipment_id.id: line.equipment_target_price
            for line in so.order_line
            if line.display_type == "line_section"
            and line.equipment_id
            and line.equipment_target_price
        }
        so.order_line.filtered("is_qualificacao_managed").unlink()
```

E, no dict de vals da section (linha ~452, o `new_lines.append` com
`"display_type": "line_section"`), acrescentar a chave:

```python
                "equipment_target_price": alvos_por_equip.get(equip.id, 0.0),
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

`test-runner`, test-tags `/afr_qualificacao:TestEquipmentTargetPrice`.
Esperado: 20 testes PASS.

- [ ] **Step 5: Bump de versão**

Em `__manifest__.py`, `"version": "16.0.6.3.5"` → `"version": "16.0.6.4.0"`
(feat → bump MINOR).

- [ ] **Step 6: Rodar a suíte completa do módulo**

`test-runner`, suíte inteira de `afr_qualificacao`. Esperado: nenhuma falha nova
em relação à baseline registrada no início. Reportar explicitamente falhas
pré-existentes/ambientais separadas das novas.

- [ ] **Step 7: Commit**

```
feat(qualificacao): preserve equipment target across configurator re-apply
```

---

## Verificação final

- [ ] Suíte completa do módulo sem falhas novas.
- [ ] Validação no browser (Task 4, Step 6) com screenshot: alvo digitado, botão Ratear, subtotal batendo.
- [ ] PDF da proposta de uma cotação rateada: a soma dos itens do equipamento bate com o alvo (o template imprime `price_subtotal`, nada muda nele — é uma conferência, não uma mudança).
- [ ] Só então push dos commits (`git push origin main` de dentro do submodule) e bump do pointer no monorepo.
