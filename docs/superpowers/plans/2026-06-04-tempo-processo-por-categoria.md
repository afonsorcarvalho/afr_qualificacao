# Rótulo de Tempo por Tipo de Processo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

**Goal:** A coluna "Tempo Esterilização" da tabela de ciclos passa a refletir o tipo de processo do equipamento (Esterilização / Lavagem / Desinfecção / Monitoramento), derivado de um campo `process_type` na categoria.

**Architecture:** Campo `process_type` Selection em `engc.equipment.category` (via `_inherit` no afr_qualificacao), com helper que mapeia para o rótulo. `_qualif_cycle_specs` injeta `time_label` por equipamento. Templates PDF + portal passam a usar `cs['time_label']`. Default `esterilizacao` = zero regressão.

**Tech Stack:** Odoo 16, Python, QWeb. afr_qualificacao é **submodule** (repo github.com/afonsorcarvalho/afr_qualificacao.git, branch main).

---

## Task 1: Campo process_type + helper de rótulo (TDD)

**Files:**
- Create: `models/engc_equipment_category.py`
- Modify: `models/__init__.py`
- Test: `tests/test_process_type.py` (novo)

- [ ] **Step 1: Teste do helper de rótulo**

Create `tests/test_process_type.py`:
```python
# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProcessTypeLabel(TransactionCase):

    def _cat(self, process_type=None):
        vals = {"name": "Cat Teste"}
        if process_type:
            vals["process_type"] = process_type
        return self.env["engc.equipment.category"].create(vals)

    def test_default_esterilizacao(self):
        cat = self._cat()
        self.assertEqual(cat.process_type, "esterilizacao")
        self.assertEqual(cat._qualif_time_label(), "Tempo de Esterilização")

    def test_lavagem(self):
        cat = self._cat("lavagem")
        self.assertEqual(cat._qualif_time_label(), "Tempo de Lavagem")

    def test_desinfeccao(self):
        cat = self._cat("desinfeccao")
        self.assertEqual(cat._qualif_time_label(), "Tempo de Desinfecção")

    def test_monitoramento(self):
        cat = self._cat("monitoramento")
        self.assertEqual(cat._qualif_time_label(), "Tempo de Ciclo")
```

Garantir `from . import test_process_type` em `tests/__init__.py`.

- [ ] **Step 2: Rodar teste → FAIL** (campo/método não existem). Via test-runner, db `qualif_test_f811`? NÃO — afr_qualificacao roda em db próprio. Usar a db de teste do módulo (perguntar test-runner qual usa). Expected: FAIL.

- [ ] **Step 3: Implementar model**

Create `models/engc_equipment_category.py`:
```python
# -*- coding: utf-8 -*-
from odoo import _, fields, models


class EngcEquipmentCategory(models.Model):
    _inherit = "engc.equipment.category"

    process_type = fields.Selection(
        selection=[
            ("esterilizacao", "Esterilização"),
            ("lavagem", "Lavagem"),
            ("desinfeccao", "Desinfecção"),
            ("monitoramento", "Monitoramento"),
        ],
        string="Tipo de Processo",
        default="esterilizacao",
        required=True,
        help="Define o rótulo da coluna de tempo na tabela de ciclos da "
             "proposta (Esterilização / Lavagem / Desinfecção / Monitoramento).",
    )

    def _qualif_time_label(self):
        """Rótulo da coluna de tempo da tabela de ciclos, por tipo de processo."""
        self.ensure_one()
        labels = {
            "esterilizacao": _("Tempo de Esterilização"),
            "lavagem": _("Tempo de Lavagem"),
            "desinfeccao": _("Tempo de Desinfecção"),
            "monitoramento": _("Tempo de Ciclo"),
        }
        return labels.get(self.process_type or "esterilizacao",
                          _("Tempo de Esterilização"))
```

Add to `models/__init__.py`: `from . import engc_equipment_category` (manter ordem; pode ir ao fim).

- [ ] **Step 4: Rodar teste → PASS** (4 testes).

- [ ] **Step 5: NÃO commitar** (commit na Task 6).

---

## Task 2: time_label em _qualif_cycle_specs (TDD)

**Files:**
- Modify: `models/sale_order.py` (método `_qualif_cycle_specs`, ~linha 783-820)
- Test: `tests/test_process_type.py` (adicionar)

- [ ] **Step 1: Teste do dict**

Adicionar à classe `TestProcessTypeLabel` — mas precisa de uma SO com linha de ciclo. Se o setUp for pesado, criar classe nova `TestCycleSpecsLabel(TransactionCase)`. Implementação do teste:

```python
    def test_cycle_specs_time_label(self):
        # categoria lavagem + equipamento + SO com 1 linha de ciclo
        cat = self.env["engc.equipment.category"].create(
            {"name": "Lavadora X", "process_type": "lavagem"})
        marca = self.env["engc.equipment.marca"].create({"name": "M"})
        equip = self.env["engc.equipment"].create({
            "category_id": cat.id, "marca_id": marca.id,
            "company_id": self.env.company.id, "state": "in_use",
            "model": "M1", "serial_number": "SN1",
        })
        cycle = self.env["afr.qualificacao.cycle.type"].create({
            "name": "Ciclo Lav", "equipment_category_id": cat.id,
            "duration": "15 min",
        })
        so = self.env["sale.order"].create({"partner_id": self.env.user.partner_id.id})
        self.env["sale.order.line"].create({
            "order_id": so.id, "name": "Ciclo Lav",
            "product_id": cycle.product_id.id if cycle.product_id else self._svc().id,
            "is_qualificacao_managed": True, "equipment_id": equip.id,
            "cycle_type_id": cycle.id, "qualif_cycle_qty": 3,
            "qualification_type": "performance",
        })
        specs = so._qualif_cycle_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["time_label"], "Tempo de Lavagem")
```

> Nota: `cycle.product_id` pode ser False se o cycle_type não tiver produto. O helper `_svc()` deve devolver um product.product de serviço qualquer. Implementar `_svc` no teste: `return self.env["product.product"].create({"name": "Svc", "type": "service"})`. Usar esse produto na linha se `cycle.product_id` for vazio. Ajustar o create do cycle para gerar product_id se o modelo o exigir (verificar: cycle_type pode auto-criar product). Se cycle_type cria product automaticamente no create, usar `cycle.product_id.id` direto.

- [ ] **Step 2: Rodar → FAIL** (`time_label` ausente / KeyError).

- [ ] **Step 3: Implementar**

Em `models/sale_order.py`, no `_qualif_cycle_specs`, alterar a linha final do loop:
```python
            result.append({"equipment": equip, "rows": rows})
```
para:
```python
            result.append({
                "equipment": equip,
                "rows": rows,
                "time_label": (
                    equip.category_id._qualif_time_label()
                    if equip.category_id else _("Tempo de Esterilização")
                ),
            })
```
Garantir que `_` está importado no topo de sale_order.py (já está, é padrão Odoo — confirmar).

- [ ] **Step 4: Rodar → PASS.**

- [ ] **Step 5: NÃO commitar.**

---

## Task 3: Templates usam time_label

**Files:**
- Modify: `reports/templates_blocos/block_cycle_specs.xml` (linha ~21)
- Modify: `views/sale_order_portal_template.xml` (linha ~294)

- [ ] **Step 1: PDF**

Em `block_cycle_specs.xml`, localizar:
```xml
                            <th style="width: 15%;">Tempo Esterilização</th>
```
Substituir por:
```xml
                            <th style="width: 15%;"><t t-esc="cs['time_label']"/></th>
```
> Confirmar que a variável do loop de equipamento se chama `cs` neste template (o `<th>` está dentro do `t-foreach` que itera os specs por equipamento). Se o nome for outro (ex: `spec`), usar esse. LER o template à volta da linha 21 antes de editar.

- [ ] **Step 2: Portal**

Em `sale_order_portal_template.xml`, localizar:
```xml
                            <th>Tempo Esteril</th>
```
Substituir por:
```xml
                            <th><t t-esc="cs['time_label']"/></th>
```
> Mesma verificação do nome da variável do loop (LER à volta da linha 294).

- [ ] **Step 3: NÃO commitar.**

---

## Task 4: process_type no form da categoria

**Files:**
- Criar/Modificar: view do form `engc.equipment.category`

- [ ] **Step 1: Localizar a view do form da categoria**

Procurar no afr_qualificacao (e no engc_os) a view form de `engc.equipment.category`. Se afr_qualificacao já tiver uma view de categoria, adicionar o campo lá; senão criar herança.

Verificar: `grep -rn "engc.equipment.category" addons/afr_qualificacao/views/` e no engc_os. Se existir view base `engc.equipment.category.form`, herdar:
```xml
<record id="view_equipment_category_form_process_type" model="ir.ui.view">
    <field name="name">engc.equipment.category.form.process.type</field>
    <field name="model">engc.equipment.category</field>
    <field name="inherit_id" ref="<xmlid_da_view_base>"/>
    <field name="arch" type="xml">
        <field name="name" position="after">
            <field name="process_type"/>
        </field>
    </field>
</record>
```
Registar o XML no `__manifest__.py` (data). Se NÃO existir view base de categoria (categoria editada inline noutro sítio), criar uma view form mínima nova + ação/menu — MAS só se necessário; preferir herdar a existente. LER as views existentes antes de decidir.

- [ ] **Step 2: NÃO commitar.**

---

## Task 5: Seed das categorias + version bump

**Files:**
- Modify: `data/equipment_category_seed.xml`
- Modify: `__manifest__.py` (version bump)

- [ ] **Step 1: Setar process_type no seed**

Em `data/equipment_category_seed.xml`, adicionar `<field name="process_type">...</field>` a cada `<record>`:
- `cat_lavadora_ultrassonica` → `lavagem`
- `cat_termodesinfectora` → `desinfeccao`
- `cat_refrigerador_camara` → `monitoramento`
- `cat_autoclave_vapor`, `cat_estufa_esterilizacao`, `cat_autoclave_gas` → `esterilizacao`

> Seeds são `noupdate="1"` — só afeta instalações novas. Instâncias existentes ficam com default `esterilizacao` (ajuste manual/MCP).

- [ ] **Step 2: Version bump**

Em `__manifest__.py`, incrementar `version` (próxima minor, ex `16.0.5.10.0` → `16.0.5.11.0` — usar o próximo número conforme o valor atual).

- [ ] **Step 3: Atualizar módulo e rodar suite completa**

Via test-runner: `-u afr_qualificacao` + suite. Confirmar 0 regressões + os novos testes pass.

- [ ] **Step 4: NÃO commitar (Task 6).**

---

## Task 6: Commit (submodule) + bump pointer monorepo

- [ ] **Step 1: Commit no submodule afr_qualificacao**

Via git-commit-push, cwd = `/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao`, paths relativos ao submodule. Push origin main. Mensagem:
```
feat(qualif): rótulo de tempo por tipo de processo (esteril/lavagem/desinfec)
```

- [ ] **Step 2: Bump pointer no monorepo**

cwd = `/home/afonso/docker/odoo_engenapp`, `git add addons/afr_qualificacao`, commit `chore: bump afr_qualificacao (tempo por tipo de processo)`, push.

---

## Pós-implementação (fora do plano, via MCP)
- Ajustar `process_type` das categorias existentes no labquali: Lavadora Ultrassônica → `lavagem`, Termodesinfectora → `desinfeccao`, Refrigerador → `monitoramento`. Re-render da cotação C26-06-0001 mostra "Tempo de Lavagem" na tabela da Lavadora.
