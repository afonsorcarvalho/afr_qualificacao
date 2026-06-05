# Opcionais no Wizard — Fase 2 Design Spec
Date: 2026-06-05
Module: afr_qualificacao

## Contexto

Fase 1 (v16.0.5.12.0) entregou o núcleo: `optional_accepted`/`optional_qty` em `sale.order.line`, qty=0 até aceito, confirm gera opcional-qualificação aceito. Hoje opcionais são adicionados **manualmente** como linhas avulsas no SO. Fase 2 reintroduz a seleção de opcionais no **wizard configurador** (`afr.qualificacao.configurator`), removida na refatoração F10.2/10.3.

Decisões do utilizador:
- Wizard oferece **serviço (catálogo) + qualificação opcional** (ciclo/malha extra).
- **Step próprio "Opcionais"** entre Escopo e Revisão.
- Checkbox "Aceito" por opcional no wizard (default False = oferta; comercial pré-aceita se souber; senão cliente decide no portal na Fase 4).

## Arquitetura

Dois novos transient models (sub-linhas do wizard) + 2 O2M no header + step novo + geração no `action_apply` + carregamento no `_load_from_existing_lines`.

### 1. Novos transient models

**`afr.qualificacao.configurator.optional`** (serviço do catálogo):
```python
class AfrQualificacaoConfiguratorOptional(models.TransientModel):
    _name = "afr.qualificacao.configurator.optional"
    _description = "Serviço opcional do configurador"

    wizard_id = fields.Many2one("afr.qualificacao.configurator",
                                required=True, ondelete="cascade")
    optional_id = fields.Many2one("afr.proposal.optional",
                                  string="Serviço Opcional", required=True)
    qty = fields.Float(string="Qtd", default=1.0)
    unit_price = fields.Monetary(string="Preço Unit.")
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    accepted = fields.Boolean(string="Aceito", default=False)

    @api.onchange("optional_id")
    def _onchange_optional_id(self):
        for line in self:
            if line.optional_id:
                line.qty = line.optional_id.default_qty or 1.0
                line.unit_price = (line.optional_id.default_price
                                   or line.optional_id.product_id.list_price)
```

**`afr.qualificacao.configurator.optional.qualif`** (qualificação opcional):
```python
class AfrQualificacaoConfiguratorOptionalQualif(models.TransientModel):
    _name = "afr.qualificacao.configurator.optional.qualif"
    _description = "Qualificação opcional do configurador"

    wizard_id = fields.Many2one("afr.qualificacao.configurator",
                                required=True, ondelete="cascade")
    equipment_id = fields.Many2one("engc.equipment", string="Equipamento",
                                   required=True)
    qualification_type = fields.Selection([
        ("performance", "QD (Desempenho)"),
        ("calibration", "Calibração"),
        ("operational", "QO (Operação)"),
    ], string="Tipo", required=True, default="performance")
    cycle_type_id = fields.Many2one("afr.qualificacao.cycle.type",
                                    string="Tipo de Ciclo")
    malha_type_id = fields.Many2one("afr.qualificacao.malha.type",
                                    string="Tipo de Malha")
    qty = fields.Integer(string="Nº Ciclos/Malhas", default=1)
    estimated_hours = fields.Float(string="Horas/Ciclo")
    accepted = fields.Boolean(string="Aceito", default=False)

    @api.onchange("cycle_type_id")
    def _onchange_cycle_type_id(self):
        for line in self:
            if line.cycle_type_id:
                line.estimated_hours = line.cycle_type_id.estimated_hours

    @api.onchange("malha_type_id")
    def _onchange_malha_type_id(self):
        for line in self:
            if line.malha_type_id:
                line.estimated_hours = line.malha_type_id.estimated_hours
```

### 2. Header — campos novos

Em `afr.qualificacao.configurator`:
```python
    optional_service_ids = fields.One2many(
        "afr.qualificacao.configurator.optional", "wizard_id",
        string="Serviços Opcionais")
    optional_qualif_ids = fields.One2many(
        "afr.qualificacao.configurator.optional.qualif", "wizard_id",
        string="Qualificações Opcionais")
```

### 3. Step novo

- `_STEP_ORDER = ["escopo", "opcionais", "revisao"]`
- `step` Selection: `("escopo", "1. Escopo"), ("opcionais", "2. Opcionais"), ("revisao", "3. Revisão")`
- `action_next_step`/`action_prev_step` já operam sobre `_STEP_ORDER` (sem mudança lógica — só a lista cresce). A validação de escopo ao sair de "escopo" permanece.

### 4. `action_apply` — geração das linhas opcionais

Após o loop de equipamentos (antes de `so.write({"order_line": new_lines})`, linha ~502), acrescentar a `new_lines`:

**Serviços:**
```python
        for opt in self.optional_service_ids:
            price = opt.unit_price or opt.optional_id.product_id.list_price
            new_lines.append((0, 0, {
                "order_id": so.id,
                "product_id": opt.optional_id.product_id.id,
                "name": opt.optional_id.name,
                "is_qualificacao_managed": True,
                "is_proposal_optional": True,
                "optional_accepted": opt.accepted,
                "optional_qty": opt.qty,
                "price_unit": price,
                "product_uom_qty": opt.qty if opt.accepted else 0.0,
            }))
```

**Qualificações:**
```python
        for oq in self.optional_qualif_ids:
            ct = oq.cycle_type_id
            mt = oq.malha_type_id
            product = (ct.product_id if ct else mt.product_id if mt else False)
            if not product:
                continue
            hours = oq.estimated_hours or (
                ct.estimated_hours if ct else mt.estimated_hours if mt else 0.0)
            base_name = (ct.name if ct else mt.name if mt else _("Opcional"))
            qty_hours = (oq.qty or 1) * hours
            vals = {
                "order_id": so.id,
                "product_id": product.id,
                "name": _("%s — %d (opcional)") % (base_name, oq.qty or 1),
                "is_qualificacao_managed": True,
                "is_proposal_optional": True,
                "optional_accepted": oq.accepted,
                "optional_qty": oq.qty or 1,
                "qualification_type": oq.qualification_type,
                "equipment_id": oq.equipment_id.id,
                "qualif_cycle_qty": oq.qty or 1,
                "estimated_hours": hours,
                "product_uom_qty": qty_hours if oq.accepted else 0.0,
            }
            if ct:
                vals["cycle_type_id"] = ct.id
            if mt:
                vals["malha_type_id"] = mt.id
            if oq.qualification_type in ("operational", "calibration"):
                vals["part"] = "02"
            new_lines.append((0, 0, vals))
```

> Os opcionais são `is_qualificacao_managed=True` (apagados/recriados no re-apply) **e** `is_proposal_optional=True`. O confirm da Fase 1 já trata: aceito+qualification_type gera qualif/OS; aceito+serviço fatura; não-aceito fica qty=0.

### 5. `_load_from_existing_lines` — repopular opcionais ao reabrir

Hoje exclui opcionais (`not l.is_proposal_optional`). Adicionar, após popular `equipment_line_ids` (~linha 300), um bloco que lê as linhas opcionais existentes e popula os 2 O2M:

```python
        # Opcionais existentes → repopula as duas secções do step Opcionais.
        opt_lines = so_lines.filtered("is_proposal_optional")
        svc_cmds, qualif_cmds = [], []
        for line in opt_lines:
            if line.qualification_type:
                qualif_cmds.append((0, 0, {
                    "equipment_id": line.equipment_id.id,
                    "qualification_type": line.qualification_type,
                    "cycle_type_id": line.cycle_type_id.id or False,
                    "malha_type_id": line.malha_type_id.id or False,
                    "qty": line.qualif_cycle_qty or 1,
                    "estimated_hours": line.estimated_hours,
                    "accepted": line.optional_accepted,
                }))
            else:
                opt_catalog = self.env["afr.proposal.optional"].search(
                    [("product_id", "=", line.product_id.id)], limit=1)
                if opt_catalog:
                    svc_cmds.append((0, 0, {
                        "optional_id": opt_catalog.id,
                        "qty": line.optional_qty or line.product_uom_qty or 1.0,
                        "unit_price": line.price_unit,
                        "accepted": line.optional_accepted,
                    }))
        if svc_cmds:
            self.optional_service_ids = svc_cmds
        if qualif_cmds:
            self.optional_qualif_ids = qualif_cmds
```

> Serviço só repopula se o produto bate um `afr.proposal.optional` do catálogo (linhas de serviço avulsas sem catálogo são ignoradas no remonte — aceitável; raras). Qualificação opcional repopula sempre via metadados.

### 6. View do wizard

Em `wizards/qualificacao_configurator_views.xml`:
- Statusbar `step` já mostra os valores do Selection (passa a ter 3).
- Adicionar `<div attrs="{'invisible': [('step','!=','opcionais')]}">` entre o div de escopo e o de revisão, com:
  - `<field name="optional_service_ids">` tree editable (optional_id, qty, unit_price, accepted)
  - `<field name="optional_qualif_ids">` tree editable (equipment_id, qualification_type, cycle_type_id, malha_type_id, qty, estimated_hours, accepted)

### 7. Manifest

Os novos transient models não precisam de security CSV próprio? **Sim precisam** — TransientModel exige acesso. Adicionar 2 linhas em `security/ir.model.access.csv` (grupo user, mesmo padrão dos outros sub-models do wizard). Verificar como `.qo.line`/`.qd.line` estão no CSV e replicar.

## Fora de âmbito (Fase 2)
- PDF caixas ☐/☑ (Fase 3).
- Portal interativo (Fase 4).
- Domain de `equipment_id` restrito ao escopo (livre por agora — comercial pode ofertar equip extra).

## Testes (TDD)

`tests/test_optional_wizard.py` (herda `AfrQualificacaoTestCommon`):
1. `test_wizard_service_optional_generates_line` — wizard com 1 equip + 1 optional_service (accepted=False) → action_apply → SO tem linha is_proposal_optional, optional_accepted=False, product_uom_qty=0.
2. `test_wizard_service_optional_accepted_sums` — optional_service accepted=True qty=2 → linha product_uom_qty=2, soma ao total.
3. `test_wizard_qualif_optional_not_accepted` — optional_qualif (cycle) accepted=False → linha is_proposal_optional + qualification_type, qty=0; confirm não gera qualif.
4. `test_wizard_qualif_optional_accepted_generates` — optional_qualif accepted=True (cycle 2 ciclos × horas) → confirm gera afr.qualificacao; product_uom_qty = qty×horas.
5. `test_load_roundtrip_optionals` — aplica com 1 service optional + 1 qualif optional, cria novo wizard sobre a mesma SO, `_load_from_existing_lines` → optional_service_ids e optional_qualif_ids repopulados (len 1 cada).
6. `test_reapply_preserves_optionals` — aplica, reabre (load), re-aplica → opcionais continuam (não duplicam, não somem).
