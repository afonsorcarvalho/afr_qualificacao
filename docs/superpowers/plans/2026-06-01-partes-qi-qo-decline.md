# Partes 01/02 da QI e QO + declínio de execução — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modelar QI e QO em Parte 01 (verificações, precificada via variante de produto) + Parte 02 (calibrações/ciclos existentes), permitir declinar a Parte 01 ("não solicitado execução") sem inflar o total, e refletir tudo na proposta (agrupamento por parte + selo + box institucional).

**Architecture:** Atributo `product.attribute` "Parte" {01,02} aplicado aos produtos-serviço QI (installation) e QO (operational) → variantes; Parte=01 carrega preço das verificações. Linhas SO ganham `part` + `part01_declined` (declinada = qty=0, preço preservado p/ exibição). Configurador ganha checkboxes de declínio por equipamento + QO Parte 01. Relatório agrupa por parte, marca declinadas e adiciona box "Itens Não Solicitados".

**Tech Stack:** Odoo 16.0, Python, QWeb, product variants/attributes. Testes via `test-runner` (docker exec, tags `afr_qualificacao`). Ambiente labquali em DEV — **sem migration** (ver memória `project_labquali_dev_stage`).

**Bump:** 16.0.5.9.0

---

## Convenções de teste (todas as tasks)

Rodar suite (delegar ao subagente `test-runner`):
```
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
  --test-enable --test-tags afr_qualificacao --stop-after-init --no-http \
  --workers=0 --max-cron-threads=0 --db_host=db --db_user=odoo --db_password=odoo
```
Para uma classe só: `--test-tags afr_qualificacao:TestClassName`.
**Fails pré-existentes conhecidas (NÃO regressão):** `TestResourcePlan.test_fleet_single_logger_two_temp_standards`, `TestProposalReport.test_render_equipment_scope_omits_cronograma_footer`, `TestProposalReport.test_render_schedule_block`.

Padrão de teste: ver `tests/common.py` + `tests/test_configurator.py` (setup de SO/equip/type_config).

---

## File Structure

- **Create** `data/product_attribute_parte_seed.xml` — atributo "Parte" + valores 01/02.
- **Modify** `hooks.py` — criar produtos QI/QO como templates com atributo Parte → variantes; `price_extra` Parte 01; type_config (installation + **operational**) aponta variante Parte=01.
- **Modify** `models/sale_order_line.py` — campos `part`, `part01_declined`; excluir declinada do subtotal.
- **Modify** `wizards/qualificacao_configurator.py` — campos `qi_part01_declined`, `do_qo_part01`, `qo_part01_declined`; `action_apply` gera QI P01 (variante+decline), QO P01 (novo), tag `part='02'`, validação.
- **Modify** `wizards/qualificacao_configurator_views.xml` — checkboxes no form do equipamento.
- **Modify** `models/sale_order.py` — `_qualif_equipment_summary` adiciona `part` + flag declínio aos items; helper `_qualif_declined_items()`; `_qualif_schedule_rows` exclui declinadas.
- **Modify** `models/proposal_block.py` — `_html_equipment_scope` agrupa por parte + selo declínio; novo `block_kind`/render `declined_items` (box).
- **Modify** `views/sale_order_portal_template.xml` — paridade de render no portal.
- **Modify** `__manifest__.py` — version bump + novo data file.
- **Create** `tests/test_partes_qi_qo.py` — toda a cobertura nova.

---

### Task 1: Atributo "Parte" (seed) + variantes nos produtos QI/QO

**Files:**
- Create: `data/product_attribute_parte_seed.xml`
- Modify: `hooks.py` (função `_install_qi_qs_type_config` → renomear conceito p/ incluir QO; criar templates+variantes)
- Modify: `__manifest__.py` (adicionar data file + version `16.0.5.9.0`)
- Test: `tests/test_partes_qi_qo.py`

- [ ] **Step 1: Escrever teste falho** — `tests/test_partes_qi_qo.py`

```python
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestPartesCatalog(TransactionCase):
    def test_parte_attribute_seeded(self):
        attr = self.env.ref("afr_qualificacao.product_attribute_parte")
        self.assertEqual(attr.create_variant, "always")
        vals = attr.value_ids.mapped("name")
        self.assertIn("Parte 01", vals)
        self.assertIn("Parte 02", vals)

    def test_qi_qo_products_have_parte_variants(self):
        company = self.env.company
        TypeConfig = self.env["afr.qualificacao.type.config"]
        for qtype in ("installation", "operational"):
            cfg = TypeConfig.with_context(active_test=False).search([
                ("qualification_type", "=", qtype),
                ("company_id", "=", company.id),
            ], limit=1)
            self.assertTrue(cfg, "type_config p/ %s deve existir" % qtype)
            variant = cfg.service_product_id
            # service_product_id resolve o variante Parte 01
            part_vals = variant.product_template_variant_value_ids.mapped("name")
            self.assertIn("Parte 01", part_vals)
            # template tem 2 variantes (Parte 01 + Parte 02)
            self.assertEqual(len(variant.product_tmpl_id.product_variant_ids), 2)
```

- [ ] **Step 2: Rodar p/ ver falhar**

`--test-tags afr_qualificacao:TestPartesCatalog` → FAIL (ref `product_attribute_parte` inexistente).

- [ ] **Step 3: Criar seed do atributo** — `data/product_attribute_parte_seed.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="product_attribute_parte" model="product.attribute">
        <field name="name">Parte</field>
        <field name="create_variant">always</field>
        <field name="display_type">radio</field>
    </record>
    <record id="product_attribute_value_parte_01" model="product.attribute.value">
        <field name="name">Parte 01</field>
        <field name="attribute_id" ref="product_attribute_parte"/>
        <field name="sequence">10</field>
    </record>
    <record id="product_attribute_value_parte_02" model="product.attribute.value">
        <field name="name">Parte 02</field>
        <field name="attribute_id" ref="product_attribute_parte"/>
        <field name="sequence">20</field>
    </record>
</odoo>
```

- [ ] **Step 4: Estender o hook p/ criar templates QI/QO com o atributo**

Em `hooks.py`: adicionar constante de produtos QO e reescrever `_install_qi_qs_type_config` (renomear p/ `_install_qualif_type_configs`) para:
1. Para cada `(qtype, suffix, name)` em `installation`/`software`/`operational`, garantir um `product.template` (type service) com xmlid no `product.template`.
2. Para `installation` e `operational`, garantir a `product.template.attribute.line` com o atributo "Parte" (ambos valores) → Odoo cria 2 variantes.
3. Definir `price_extra` no `product.template.attribute.value` correspondente a "Parte 01" (default 0.0 — preço real cadastrado pelo user na labquali).
4. `type_config.service_product_id` = variante **Parte 01** (`tmpl._get_variant_for_combination` ou filtrar `product_variant_ids` cujo `product_template_variant_value_ids.name == 'Parte 01'`). Para `software` (sem atributo) usar o variante único.

Código (substitui o corpo de `_install_qi_qs_type_config`; manter assinatura chamada no post_init):

```python
QUALIF_SERVICE_PRODUCTS = {
    "installation": ("product_qi_service", "Qualificação de Instalação (QI)", True),
    "operational": ("product_qo_service", "Qualificação de Operação (QO)", True),
    "software": ("product_qs_service", "Qualificação de Software (QS)", False),
}


def _parte_variant(template, value_name):
    """Retorna o product.product do template cujo valor de atributo Parte == value_name."""
    for variant in template.product_variant_ids:
        names = variant.product_template_variant_value_ids.mapped("name")
        if value_name in names:
            return variant
    return template.product_variant_id  # fallback (sem atributo)


def _install_qualif_type_configs(env):
    Template = env["product.template"]
    TypeConfig = env["afr.qualificacao.type.config"]
    ImdData = env["ir.model.data"]
    attr = env.ref("afr_qualificacao.product_attribute_parte", raise_if_not_found=False)
    val01 = env.ref("afr_qualificacao.product_attribute_value_parte_01", raise_if_not_found=False)
    val02 = env.ref("afr_qualificacao.product_attribute_value_parte_02", raise_if_not_found=False)

    tmpl_by_type = {}
    for qtype, (suffix, name, has_parte) in QUALIF_SERVICE_PRODUCTS.items():
        tmpl = env.ref(f"afr_qualificacao.{suffix}", raise_if_not_found=False)
        if not tmpl:
            tmpl = Template.create({
                "name": name, "type": "service", "detailed_type": "service",
                "sale_ok": True, "purchase_ok": False, "list_price": 0.0,
            })
            ImdData.create({
                "name": suffix, "module": "afr_qualificacao",
                "model": "product.template", "res_id": tmpl.id, "noupdate": True,
            })
        if has_parte and attr and not tmpl.attribute_line_ids.filtered(
            lambda l: l.attribute_id == attr
        ):
            tmpl.write({"attribute_line_ids": [(0, 0, {
                "attribute_id": attr.id,
                "value_ids": [(6, 0, [val01.id, val02.id])],
            })]})
        tmpl_by_type[qtype] = tmpl

    for company in env["res.company"].search([]):
        for qtype in ("installation", "operational", "software"):
            exists = TypeConfig.with_context(active_test=False).search([
                ("qualification_type", "=", qtype),
                ("company_id", "=", company.id),
            ], limit=1)
            if exists:
                continue
            tmpl = tmpl_by_type[qtype]
            has_parte = QUALIF_SERVICE_PRODUCTS[qtype][2]
            product = _parte_variant(tmpl, "Parte 01") if has_parte else tmpl.product_variant_id
            TypeConfig.create({
                "qualification_type": qtype,
                "company_id": company.id,
                "service_product_id": product.id,
                "default_unit_price": 0.0,
                "estimated_hours": 0.0,
            })
```

Atualizar a chamada no post_init (`_install_proposal_template_seed`): `_install_qualif_type_configs(env)`.
**Nota:** `afr.qualificacao.type.config` precisa aceitar `operational` no Selection — verificar (já tem `operational`? o Selection do model lista installation/operational/performance/software → SIM). Confirmar em `models/qualificacao_type_config.py`.

- [ ] **Step 5: Registrar data file + bump** — `__manifest__.py`

Adicionar `"data/product_attribute_parte_seed.xml"` ANTES de qualquer seed que dependa do atributo (logo após os seeds de produto base, antes de templates). Version → `"16.0.5.9.0"`.

- [ ] **Step 6: Rodar teste** → PASS (`TestPartesCatalog`). Rodar suite completa, confirmar só os 3 fails pré-existentes.

- [ ] **Step 7: Commit** (delegar a `git-commit-push` haiku, do dir do submodule)

```
feat(afr_qualificacao): atributo Parte {01,02} + variantes QI/QO + type_config operational (16.0.5.9.0 wip)
```

---

### Task 2: Campos `part` e `part01_declined` na `sale.order.line`

**Files:**
- Modify: `models/sale_order_line.py`
- Test: `tests/test_partes_qi_qo.py`

- [ ] **Step 1: Teste falho**

```python
@tagged("post_install", "-at_install", "afr_qualificacao")
class TestPartFields(TransactionCase):
    def _mk_order(self):
        partner = self.env["res.partner"].create({"name": "Cli Parte"})
        return self.env["sale.order"].create({"partner_id": partner.id})

    def test_declined_line_excluded_from_total(self):
        so = self._mk_order()
        prod = self.env["product.product"].create({
            "name": "Verif QI", "type": "service", "list_price": 1000.0,
        })
        line = self.env["sale.order.line"].create({
            "order_id": so.id, "product_id": prod.id,
            "product_uom_qty": 0.0, "price_unit": 1000.0,
            "part": "01", "part01_declined": True,
            "is_qualificacao_managed": True,
        })
        self.assertEqual(line.price_subtotal, 0.0)
        self.assertEqual(so.amount_total, 0.0)
        # preço de referência preservado p/ exibição
        self.assertEqual(line.price_unit, 1000.0)
```

- [ ] **Step 2: Rodar** → FAIL (campo `part` inexistente).

- [ ] **Step 3: Adicionar campos** — em `models/sale_order_line.py`, junto aos demais campos qualif:

```python
    part = fields.Selection(
        selection=[("01", "Parte 01"), ("02", "Parte 02")],
        string="Parte",
        copy=True,
        help=(
            "Parte da qualificação (QI/QO). Parte 01 = verificações "
            "(declinável); Parte 02 = calibrações (QI) / ciclos (QO)."
        ),
    )
    part01_declined = fields.Boolean(
        string="Parte 01 Não Solicitada",
        default=False,
        copy=True,
        help=(
            "Cliente não solicitou execução da Parte 01. A linha aparece na "
            "proposta com preço de referência e selo 'NÃO SOLICITADO "
            "EXECUÇÃO', mas não soma ao total (product_uom_qty=0)."
        ),
    )
```

(A exclusão do total é garantida por `product_uom_qty=0` na geração — não precisa override de compute. O teste valida.)

- [ ] **Step 4: Rodar** → PASS.

- [ ] **Step 5: Commit** — `feat(afr_qualificacao): campos part + part01_declined na sale.order.line`

---

### Task 3: Configurador — campos de Parte 01 / declínio

**Files:**
- Modify: `wizards/qualificacao_configurator.py` (modelo `AfrQualificacaoConfiguratorEquipment`)
- Modify: `wizards/qualificacao_configurator_views.xml`
- Test: `tests/test_partes_qi_qo.py`

- [ ] **Step 1: Teste falho** (campos existem + defaults)

```python
@tagged("post_install", "-at_install", "afr_qualificacao")
class TestConfiguratorParte(TransactionCase):
    def test_equipment_line_has_parte_fields(self):
        eq_model = self.env["afr.qualificacao.configurator.equipment"]
        fields_ = eq_model.fields_get()
        for fname in ("qi_part01_declined", "do_qo_part01", "qo_part01_declined"):
            self.assertIn(fname, fields_)
```

- [ ] **Step 2: Rodar** → FAIL.

- [ ] **Step 3: Adicionar campos** — em `AfrQualificacaoConfiguratorEquipment` (após `do_qs`):

```python
    qi_part01_declined = fields.Boolean(
        string="QI Parte 01 não solicitada",
        help="Cliente não solicitou execução das verificações (Parte 01) da QI.",
    )
    do_qo_part01 = fields.Boolean(
        string="QO Parte 01 (Verificações)",
        help="Verificações da QO (Parte 01), 1 execução por equipamento.",
    )
    qo_part01_declined = fields.Boolean(
        string="QO Parte 01 não solicitada",
        help="Cliente não solicitou execução das verificações (Parte 01) da QO.",
    )
```

- [ ] **Step 4: Atualizar a view** — `wizards/qualificacao_configurator_views.xml`

Localizar o bloco do form/tree do `equipment_line_ids` onde estão `do_qi`/`do_qo`/`do_qs`. Adicionar:
- ao lado de `do_qi`: `<field name="qi_part01_declined" attrs="{'invisible': [('do_qi', '=', False)], 'readonly': [('do_qi', '=', False)]}"/>`
- novo campo `<field name="do_qo_part01"/>`
- `<field name="qo_part01_declined" attrs="{'invisible': [('do_qo_part01', '=', False)], 'readonly': [('do_qo_part01', '=', False)]}"/>`

(Ler o XML existente p/ casar a estrutura — tree inline vs form. Manter labels curtos.)

- [ ] **Step 5: Rodar** → PASS. Validar carga da view sem erro (`-u` no test run já valida XML).

- [ ] **Step 6: Commit** — `feat(afr_qualificacao): configurador ganha QO Parte 01 + flags de declínio`

---

### Task 4: `action_apply` — gerar Parte 01 (QI/QO) + tag Parte 02 + validação

**Files:**
- Modify: `wizards/qualificacao_configurator.py` (`action_apply`)
- Test: `tests/test_partes_qi_qo.py`

- [ ] **Step 1: Teste falho** — usar setup do `test_configurator.py` (criar wizard com 1 equip, type_config installation/operational seedados pelo hook).

```python
@tagged("post_install", "-at_install", "afr_qualificacao")
class TestApplyPartes(TransactionCase):
    # setup: criar SO + equip + wizard com do_qi=True, do_qo_part01=True,
    #        1 calib_line (malha) e 1 qo_line (ciclo). Ver test_configurator.py.

    def test_qi_part01_line_created(self):
        so = self._apply(do_qi=True)
        p01 = so.order_line.filtered(
            lambda l: l.qualification_type == "installation" and l.part == "01"
        )
        self.assertEqual(len(p01), 1)
        self.assertEqual(p01.product_uom_qty, 1.0)

    def test_qi_part01_declined_zero_qty(self):
        so = self._apply(do_qi=True, qi_part01_declined=True)
        p01 = so.order_line.filtered(lambda l: l.part == "01" and l.part01_declined)
        self.assertEqual(p01.product_uom_qty, 0.0)
        self.assertTrue(p01.price_unit >= 0.0)  # preço de referência do variante

    def test_qo_part01_line_created_once(self):
        so = self._apply(do_qo_part01=True, qo_cycles=1)
        p01 = so.order_line.filtered(
            lambda l: l.qualification_type == "operational" and l.part == "01"
        )
        self.assertEqual(len(p01), 1)

    def test_malha_tagged_part02(self):
        so = self._apply(do_qi=True, calib=1)
        malha = so.order_line.filtered(lambda l: l.malha_type_id)
        self.assertTrue(all(l.part == "02" for l in malha))

    def test_decline_part01_without_part02_raises(self):
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            # QI P01 declinada e nenhuma malha (Parte 02) selecionada
            self._apply(do_qi=True, qi_part01_declined=True, calib=0)
```

(Implementar `_apply(**kw)` helper no teste seguindo `test_configurator.py`: cria wizard, set flags, `action_apply`, retorna o SO.)

- [ ] **Step 2: Rodar** → FAIL.

- [ ] **Step 3: Modificar `action_apply`** — 4 mudanças no loop por `eq_line`:

(a) Bloco QI (`do_qi`, qtype `installation`): após montar `vals`, antes do append. **Preço vem do variante Parte=01** (`cfg.service_product_id` é o variante; `lst_price` = `list_price` + `price_extra`), NÃO do `default_unit_price`:
```python
                vals["part"] = "01"
                # Preço da Parte 01 = preço do variante (price_extra do atributo).
                # Sobrescreve o default_unit_price setado acima.
                vals["price_unit"] = cfg.service_product_id.lst_price
                if eq_line.qi_part01_declined:
                    vals["part01_declined"] = True
                    vals["product_uom_qty"] = 0.0  # não soma ao total
                    # price_unit preservado p/ exibição como valor de referência
```
(QS permanece sem `part`, segue usando `default_unit_price`.)

(b) Novo bloco QO Parte 01 (após o loop QI/QS, antes do loop `qo_line_ids`):
```python
            if eq_line.do_qo_part01:
                cfg = TypeConfig.get_config_for("operational", so.company_id)
                if not cfg:
                    raise UserError(_(
                        "Sem configuração de produto para QO (operational) na "
                        "empresa %s."
                    ) % so.company_id.display_name)
                qo_vals = {
                    "order_id": so.id,
                    "product_id": cfg.service_product_id.id,
                    "product_uom_qty": 1.0,
                    "qualif_cycle_qty": 1,
                    "is_qualificacao_managed": True,
                    "qualification_type": "operational",
                    "equipment_id": equip.id,
                    "part": "01",
                    # Preço da Parte 01 = preço do variante Parte=01 (price_extra).
                    "price_unit": cfg.service_product_id.lst_price,
                }
                if cfg.estimated_hours:
                    qo_vals["estimated_hours"] = cfg.estimated_hours
                if eq_line.qo_part01_declined:
                    qo_vals["part01_declined"] = True
                    qo_vals["product_uom_qty"] = 0.0
                new_lines.append((0, 0, qo_vals))
```

(c) Loop ciclos QO (`qo_line_ids`): adicionar `"part": "02"` ao `qo_vals`. Loop malhas (`calib_line_ids`): adicionar `"part": "02"` ao `c_vals`. (QD não recebe `part`.)

(d) Validação (no loop de validação inicial, linhas ~299): após validar que há qualif, adicionar:
```python
            if eq_line.qi_part01_declined and not eq_line.calib_line_ids:
                raise UserError(_(
                    "Equipamento %s: Parte 01 da QI declinada exige ao menos "
                    "uma malha (Parte 02). Não há contratação só da Parte 01."
                ) % (eq_line.equipment_id.display_name or "?"))
            if eq_line.qo_part01_declined and not eq_line.qo_line_ids:
                raise UserError(_(
                    "Equipamento %s: Parte 01 da QO declinada exige ao menos "
                    "um ciclo (Parte 02)."
                ) % (eq_line.equipment_id.display_name or "?"))
```

Também incluir `do_qo_part01` na checagem "sem qualificações selecionadas" (linha ~300): adicionar `or eq_line.do_qo_part01`.

- [ ] **Step 4: Rodar** → PASS (`TestApplyPartes`).

- [ ] **Step 5: Atualizar `_load_from_existing_lines`** — ao reabrir o wizard de um SO existente, repopular `do_qo_part01`/`qi_part01_declined`/`qo_part01_declined` a partir das linhas (`part='01'` + `part01_declined`). Ler o método (linhas ~204-291) e espelhar a lógica de detecção atual. Adicionar teste:
```python
    def test_reload_preserves_decline(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz._load_from_existing_lines()
        eq = wiz.equipment_line_ids[:1]
        self.assertTrue(eq.qi_part01_declined)
```

- [ ] **Step 6: Rodar** → PASS.

- [ ] **Step 7: Commit** — `feat(afr_qualificacao): action_apply gera Parte 01 QI/QO + declínio + tag Parte 02`

---

### Task 5: Relatório — agrupar por Parte + selo declínio + excluir do cronograma

**Files:**
- Modify: `models/sale_order.py` (`_qualif_equipment_summary`, `_qualif_schedule_rows`; novo `_qualif_declined_items`)
- Test: `tests/test_partes_qi_qo.py`

- [ ] **Step 1: Teste falho**

```python
@tagged("post_install", "-at_install", "afr_qualificacao")
class TestReportPartes(TransactionCase):
    def test_summary_items_have_part_and_declined(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        summary = so._qualif_equipment_summary()
        qi = [t for e in summary for t in e["types"] if t["code"] == "installation"][0]
        p01 = [i for i in qi["items"] if i.get("part") == "01"]
        self.assertTrue(p01)
        self.assertTrue(p01[0]["declined"])
        # valor de referência usa price_unit (não price_subtotal=0)
        self.assertGreaterEqual(p01[0]["ref_price"], 0.0)

    def test_declined_items_helper(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        declined = so._qualif_declined_items()
        self.assertEqual(len(declined), 1)
        self.assertEqual(declined[0]["qualification_type"], "installation")

    def test_declined_excluded_from_schedule(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        rows = so._qualif_schedule_rows()
        # nenhuma row da linha declinada (qty=0 / part01_declined)
        self.assertTrue(all(not r.get("declined") for r in rows))
```

- [ ] **Step 2: Rodar** → FAIL.

- [ ] **Step 3: Modificar `_qualif_equipment_summary`** — no dict de cada item (linha ~376) adicionar:
```python
                    items.append({
                        "name": item_name,
                        "qty": line.qualif_cycle_qty or line.product_uom_qty,
                        "subtype": subtype,
                        "line": line,
                        "part": line.part or "",
                        "declined": line.part01_declined,
                        # declinada: subtotal=0; usar price_unit como referência
                        "ref_price": line.price_unit if line.part01_declined else line.price_subtotal,
                        **extra,
                    })
```
(O `type_subtotal` segue somando `line.price_subtotal` → declinada contribui 0, correto.)

- [ ] **Step 4: Novo helper `_qualif_declined_items`** — em `sale_order.py`:
```python
    def _qualif_declined_items(self):
        """Linhas Parte 01 declinadas, p/ o box 'Itens Não Solicitados'."""
        self.ensure_one()
        out = []
        for line in self.order_line.sorted(key=lambda l: (
            l.equipment_id.name or "", l.sequence,
        )):
            if not (line.is_qualificacao_managed and line.part01_declined):
                continue
            out.append({
                "equipment": line.equipment_id,
                "qualification_type": line.qualification_type or "",
                "label": QUALIF_TYPE_LABELS.get(line.qualification_type, line.qualification_type or ""),
                "name": line.name or (line.product_id.display_name or ""),
                "ref_price": line.price_unit,
            })
        return out
```

- [ ] **Step 5: Excluir declinadas do cronograma** — em `_qualif_schedule_rows` (linha ~471), no filtro de linhas que viram rows, adicionar guarda `and not line.part01_declined` (ler o método p/ casar a variável de iteração). Se o método já filtra por horas>0, a declinada (qty=0) provavelmente já cai fora — confirmar e, se não, adicionar a guarda explícita.

- [ ] **Step 6: Rodar** → PASS (`TestReportPartes`).

- [ ] **Step 7: Commit** — `feat(afr_qualificacao): summary agrupa por parte + helper declinados + cronograma exclui declinada`

---

### Task 6: Render proposta — escopo por Parte + selo + box "Itens Não Solicitados"

**Files:**
- Modify: `models/proposal_block.py` (`_html_equipment_scope`; novo render `declined_items`)
- Modify: `data/proposal_section_seed.xml` (seção institucional do box) — OU bloco static; ver Step 3
- Modify: `views/sale_order_portal_template.xml`
- Test: `tests/test_partes_qi_qo.py`

- [ ] **Step 1: Teste falho** (render HTML contém os marcadores)

```python
@tagged("post_install", "-at_install", "afr_qualificacao")
class TestRenderPartes(TransactionCase):
    def test_scope_html_groups_partes_and_seal(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        block = self.env["afr.proposal.block"]  # ajustar p/ a API real do bloco
        html = so._render_equipment_scope_html()  # helper de teste; ver Step 4
        self.assertIn("PARTE 01", html)
        self.assertIn("PARTE 02", html)
        self.assertIn("NÃO SOLICITADO EXECUÇÃO", html)

    def test_declined_box_present_only_when_declined(self):
        so_decl = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        so_ok = self._apply(do_qi=True, calib=1)
        html_decl = so_decl._render_declined_box_html()
        html_ok = so_ok._render_declined_box_html()
        self.assertIn("Itens Não Solicitados", html_decl)
        self.assertEqual(html_ok.strip(), "")
```

(Ler `proposal_block.py` p/ descobrir a assinatura real dos renders — `_html_equipment_scope(self, order)` é método do bloco. Adaptar os helpers de teste `_render_*` ou chamar `block._html_equipment_scope(so)` diretamente. Ajustar nomes conforme a API encontrada.)

- [ ] **Step 2: Rodar** → FAIL.

- [ ] **Step 3: Modificar `_html_equipment_scope`** (linha ~239) — dentro do loop por tipo, subagrupar items por `part`:
- emitir cabeçalho `PARTE 01 — Verificações` / `PARTE 02 — <Calibrações|Ciclos de Operação>` conforme `qtype` e `part`;
- item com `declined=True`: renderizar nome riscado + `<span class="qq-declined">NÃO SOLICITADO EXECUÇÃO</span>` + `ref_price` (não somar);
- Parte 01 (não declinada) e Parte 02 normais.
Seguir o estilo HTML/escape já usado no método (Markup/escape). Manter labels: QI P02 = "Calibrações"; QO P02 = "Ciclos de Operação".

- [ ] **Step 4: Novo render do box** — método em `proposal_block.py` (ou em `sale_order.py` como `_render_declined_box_html`) que consome `order._qualif_declined_items()` e gera:
- vazio (`""`) se lista vazia;
- senão: título "ITENS NÃO SOLICITADOS PARA EXECUÇÃO" + parágrafo institucional + tabela (Equipamento | Tipo | Item | Valor de referência).

Texto institucional (rascunho do spec; pode virar campo editável depois):
> Os itens listados abaixo integram o escopo técnico recomendado da qualificação, conforme exigências da Vigilância Sanitária aplicáveis, porém não foram solicitados para execução pelo cliente nesta contratação. O registro é mantido para fins de rastreabilidade documental e eventual auditoria, evidenciando que a não realização decorreu de opção do contratante.

Integrar o box no fluxo do relatório: registrar um novo `block_kind` `declined_items` no dispatch dos blocos (ver dict de renders ~linha 223 `"equipment_scope": ...`) e semear o bloco no template (em `_seed_proposal_blocks` / seed do template), posicionado após o escopo. Se mais simples, anexar o box ao final do `_html_equipment_scope` (decisão do implementer; preferir bloco próprio p/ posicionamento controlável).

- [ ] **Step 5: CSS do selo** — adicionar `.qq-declined` (vermelho, bold, uppercase, pequeno) e `.qq-strike` (line-through) ao SCSS/CSS do relatório de cotação. Localizar o asset CSS já usado pelo report (grep `qq-section-cont`).

- [ ] **Step 6: Rodar** → PASS (`TestRenderPartes`).

- [ ] **Step 7: Commit** — `feat(afr_qualificacao): proposta agrupa Parte 01/02 + selo NÃO SOLICITADO + box auditoria`

---

### Task 7: Portal — paridade de render

**Files:**
- Modify: `views/sale_order_portal_template.xml`
- Test: `tests/test_partes_qi_qo.py`

- [ ] **Step 1: Teste falho** — renderizar o template do portal e checar marcadores. Seguir o padrão de `test_quotation_report.py` (usa `_render_qweb_html` ou `IrQweb._render`). Asserts: contém "PARTE 01", "PARTE 02", "NÃO SOLICITADO EXECUÇÃO" e o box quando há declínio.

```python
@tagged("post_install", "-at_install", "afr_qualificacao")
class TestPortalPartes(TransactionCase):
    def test_portal_renders_partes(self):
        so = self._apply(do_qi=True, qi_part01_declined=True, calib=1)
        html = self.env["ir.qweb"]._render(
            "afr_qualificacao.<portal_template_id>", {"sale_order": so, "doc": so}
        )
        html = str(html)
        self.assertIn("PARTE 01", html)
        self.assertIn("NÃO SOLICITADO EXECUÇÃO", html)
```
(Descobrir o id real do template do portal lendo `sale_order_portal_template.xml`; ajustar contexto conforme o template espera.)

- [ ] **Step 2: Rodar** → FAIL.

- [ ] **Step 3: Editar o portal template** — espelhar o agrupamento por parte + selo + box. Reusar os helpers `_qualif_equipment_summary` (agora com `part`/`declined`/`ref_price`) e `_qualif_declined_items`. Iterar items agrupando por `part`; render do selo p/ `declined`; box ao final condicionado a `_qualif_declined_items()`.

- [ ] **Step 4: Rodar** → PASS.

- [ ] **Step 5: Commit** — `feat(afr_qualificacao): portal reflete Parte 01/02 + selo + box`

---

### Task 8: Suite completa + regressão + bump final

**Files:**
- Modify: `__manifest__.py` (confirmar version `16.0.5.9.0`)
- Test: suite inteira

- [ ] **Step 1: Rodar suite completa** (via `test-runner`). Esperado: todas verdes EXCETO os 3 fails pré-existentes conhecidos. Qualquer fail novo → investigar (systematic-debugging).

- [ ] **Step 2: Smoke manual via odoo-mcp (local)** — confirmar: atributo "Parte" existe; produtos QI/QO têm 2 variantes; type_config installation/operational apontam variante Parte 01. (Ver memória `feedback_test_with_local_odoo`.)

- [ ] **Step 3: Atualizar TODO.md** (raiz monorepo) — mover esta feature p/ "Feito" com sumário + commits.

- [ ] **Step 4: NÃO commitar/push final ainda** — aguardar teste do user no ambiente (`-u afr_qualificacao` na labquali). Regra `feedback_commit_after_test`. Quando user aprovar → `git-commit-push` (haiku) do dir do submodule + bump pointer no monorepo.

---

## Self-Review (preenchido)

- **Cobertura do spec:** Bloco 1 → Task 1. Bloco 2 → Task 2. Bloco 3 (configurador) → Tasks 3-4. Bloco 4 (relatório a+c) → Tasks 5-7. Cronograma exclui declinada → Task 5. ✔
- **Constraint total não inflado:** Task 2 (qty=0) + teste explícito. ✔
- **Sem migration:** explícito (dev). ✔
- **Pontos a confirmar pelo implementer (ler código):** estrutura exata da view do configurador (Task 3), API dos renders em `proposal_block.py` e ids de template (Tasks 6-7), filtro real de `_qualif_schedule_rows` (Task 5), `_load_from_existing_lines` (Task 4 Step 5). Marcados nos steps.
- **Consistência de nomes:** `part` (Selection 01/02), `part01_declined` (bool), `qi_part01_declined`/`do_qo_part01`/`qo_part01_declined` (configurador), `_qualif_declined_items` — usados consistentemente entre tasks. ✔
- **Decisão fechada (user):** preço da Parte 01 vem do **variante Parte=01** (`cfg.service_product_id.lst_price` = `list_price` + `price_extra` do valor do atributo), NÃO do `default_unit_price`. Cabeado em Task 4 Step 3 (a)+(b). User cadastra o preço no variante/`price_extra` na labquali. QS/QD/ciclos/malhas mantêm suas fontes atuais.
```
