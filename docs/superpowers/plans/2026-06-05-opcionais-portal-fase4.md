# Opcionais no Portal Interativo — Fase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`. Código completo na spec `docs/superpowers/specs/2026-06-05-opcionais-portal-fase4-design.md`.

**Goal:** Cliente marca opcionais no portal; um endpoint POST (token-auth) grava `optional_accepted` e recalcula o total.

**Architecture:** Lógica em `sale.order._portal_toggle_optional` (testável). Controller fino (`_document_check_access` + delega). Checkbox interativo no template (só em draft/sent). JS leve (POST JSON-RPC + reload).

**Tech Stack:** Odoo 16, Python, OWL/publicWidget (frontend). afr_qualificacao é **submodule** (branch main). Testes herdam `AfrQualificacaoTestCommon`. DB teste odoo_ecm_test.

---

## File Map

| Ficheiro | Mudança |
|---|---|
| `models/sale_order.py` | método `_portal_toggle_optional` |
| `controllers/portal.py` | **novo** — route POST token-auth |
| `controllers/__init__.py` | importar portal |
| `views/sale_order_portal_template.xml` | caixa → checkbox interativo (draft/sent) |
| `static/src/js/optional_portal.js` | **novo** — listener + POST + reload |
| `__manifest__.py` | registar JS em assets_frontend |
| `tests/test_portal_optional.py` | **novo** — 5 testes do método |

---

## Task 1: Método _portal_toggle_optional (TDD)

**Files:** `models/sale_order.py`, `tests/test_portal_optional.py` (novo)

- [ ] **Step 1: Escrever os 5 testes**

Create `tests/test_portal_optional.py`:
```python
# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestPortalOptional(AfrQualificacaoTestCommon):

    def _svc(self):
        return self.env["product.product"].create(
            {"name": "Pasta", "type": "service", "sale_ok": True,
             "list_price": 150.0})

    def _so_with_optional(self, accepted=False):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc().id, "name": "Opt",
            "is_proposal_optional": True, "optional_accepted": accepted,
            "optional_qty": 2.0, "price_unit": 150.0})
        return so, line

    def test_toggle_accepts(self):
        so, line = self._so_with_optional(accepted=False)
        res = so._portal_toggle_optional(line.id, True)
        self.assertTrue(line.optional_accepted)
        self.assertEqual(line.product_uom_qty, 2.0)
        self.assertEqual(res["accepted"], True)
        self.assertEqual(res["amount_total"], so.amount_total)

    def test_toggle_unaccepts(self):
        so, line = self._so_with_optional(accepted=True)
        line._sync_optional_qty()
        so._portal_toggle_optional(line.id, False)
        self.assertFalse(line.optional_accepted)
        self.assertEqual(line.product_uom_qty, 0.0)

    def test_toggle_confirmed_raises(self):
        so, line = self._so_with_optional(accepted=False)
        so.state = "sale"
        with self.assertRaises(UserError):
            so._portal_toggle_optional(line.id, True)
        self.assertFalse(line.optional_accepted)

    def test_toggle_non_optional_raises(self):
        so, _line = self._so_with_optional(accepted=False)
        normal = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": self._svc().id,
            "name": "Normal", "product_uom_qty": 1.0, "price_unit": 150.0})
        with self.assertRaises(UserError):
            so._portal_toggle_optional(normal.id, True)

    def test_toggle_foreign_line_raises(self):
        so1, _l1 = self._so_with_optional(accepted=False)
        so2, l2 = self._so_with_optional(accepted=False)
        with self.assertRaises(UserError):
            so1._portal_toggle_optional(l2.id, True)
```
Registar `from . import test_portal_optional` em `tests/__init__.py`.

- [ ] **Step 2: Rodar → FAIL** (método não existe). test-runner tags `/afr_qualificacao:TestPortalOptional`.

- [ ] **Step 3: Implementar o método**

Em `models/sale_order.py`, adicionar (perto de `_create_qualificacoes_from_lines` ou no fim da classe sale.order) — CÓDIGO COMPLETO na spec secção 1. `UserError`/`_` já importados.

- [ ] **Step 4: Rodar → PASS** (5 testes).

- [ ] **Step 5: NÃO commitar.**

---

## Task 2: Controller de portal

**Files:** `controllers/portal.py` (novo), `controllers/__init__.py`

- [ ] **Step 1: Criar o controller**

Create `controllers/portal.py` — CÓDIGO COMPLETO na spec secção 2.

- [ ] **Step 2: Registar import**

Em `controllers/__init__.py`, adicionar `from . import portal` (LER o ficheiro primeiro — já importa o controller de certificados; append).

- [ ] **Step 3: Verificar sintaxe**
`cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao && python3 -c "import ast; ast.parse(open('controllers/portal.py').read()); print('OK')"`

- [ ] **Step 4: NÃO commitar.**

---

## Task 3: Template checkbox interativo + JS + assets

**Files:** `views/sale_order_portal_template.xml`, `static/src/js/optional_portal.js` (novo), `__manifest__.py`

- [ ] **Step 1: Template — checkbox**

No bloco optionals, a célula da caixa (`<td class="text-center"><t t-if="ol.optional_accepted">&#9745;</t><t t-else="">&#9744;</t></td>`) passa ao bloco condicional da spec secção 3 (checkbox quando draft/sent, ☑/☐ estático caso contrário). LER a célula atual antes de editar.

- [ ] **Step 2: JS widget**

Create `static/src/js/optional_portal.js` — CÓDIGO COMPLETO na spec secção 4.
> **IMPORTANTE (verificar):** confirmar que `import { jsonrpc } from "@web/core/network/rpc_service"` resolve no bundle `web.assets_frontend` do Odoo 16. Se não resolver no frontend, usar a alternativa: `import { rpc } from "@web/core/network/rpc_service"` ou, em último caso, `fetch` com payload JSON-RPC manual (`POST` para o endpoint com `{jsonrpc:'2.0', method:'call', params:{...}}` e header `Content-Type: application/json`). Testar o carregamento do asset no browser (não há teste JS automatizado).

- [ ] **Step 3: Manifest assets**

Em `__manifest__.py` `assets.web.assets_frontend`, adicionar após o SCSS:
```python
            "afr_qualificacao/static/src/js/optional_portal.js",
```

- [ ] **Step 4: Validar**
`python3 -c "import xml.dom.minidom as m; m.parse('views/sale_order_portal_template.xml'); print('xml OK')" && node --check static/src/js/optional_portal.js && echo "js OK"`

- [ ] **Step 5: NÃO commitar.**

---

## Task 4: Bump + suite + commit

**Files:** `__manifest__.py`

- [ ] **Step 1: Version bump** `16.0.5.14.0` → `16.0.5.15.0`.

- [ ] **Step 2: Update + suite completa** (test-runner, `-u afr_qualificacao`):
- 5 testes TestPortalOptional PASS
- update sem erro (controller carrega, asset JS registado, template válido)
- 0 regressões novas (3 falhas pré-existentes conhecidas aceitáveis)

- [ ] **Step 3: Commit submodule + bump pointer**

Via git-commit-push, cwd submodule. Push origin main. Mensagem:
```
feat(qualif): portal interativo de opcionais — cliente marca e grava (Fase 4)

sale.order._portal_toggle_optional (valida estado draft/sent + pertença +
is_proposal_optional, grava optional_accepted + sync qty). Controller portal
token-auth (_document_check_access) POST /my/orders/<id>/optional/<line>/toggle.
Checkbox interativo no portal (só draft/sent) + JS publicWidget (POST + reload).
v16.0.5.15.0. 5 testes. Fase 4 de 4 — feature opcionais COMPLETA.
```
Depois bump pointer no monorepo (`git add addons/afr_qualificacao`, commit `chore: bump afr_qualificacao (opcionais portal fase 4)`, push main-monorepo).

---

## Manual Test Checklist (browser, pós-deploy)
| Cenário | Esperado |
|---|---|
| Abrir cotação draft/sent no portal | opcionais têm checkbox marcável |
| Marcar checkbox | página recarrega, total inclui o opcional |
| Desmarcar | total volta a excluir |
| Cotação confirmada (sale) | ☑/☐ estático, sem checkbox |
| POST sem token válido | rejeitado (error access) |
