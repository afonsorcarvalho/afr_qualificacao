# Procedimento por Categoria (pivot F1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unificar os procedimentos de qualificação em 1 record por categoria de equipamento, com os passos de coleta de todas as fases (QI/QO/QD/QS/Calibração) num só lugar, fase auto-setada pela aba do editor.

**Architecture:** A chave do template `afr.qualificacao.procedimento` passa de `(applicable_qualification_type, equipment_category_id, company)` para `(equipment_category_id, company)`. A fase migra do procedimento para cada `procedimento.item` (campo `phase`). `resolve_for` acha o procedimento pela categoria (categoria vazia = fallback). A explosão para `collect.item` (no SO confirm e no wizard de aplicação) filtra os itens pela fase da qualificação. O editor usa um notebook com 1 página por fase, cada página com `domain`/`context` que filtra e auto-seta a fase.

**Tech Stack:** Odoo 16.0, Python, XML views, testes `odoo.tests` (tagged). Docker entrypoint custom (porta host 8083; NÃO usar `odoo-bin` direto).

**Referência (spec):** `docs/superpowers/specs/2026-06-09-procedimento-por-categoria-design.md`

**Migração major:** versão alvo `16.0.6.0.0`. labquali está em DEV → migração limpa procs antigos.

---

## File Structure

| Arquivo | Responsabilidade | Ação |
|---|---|---|
| `models/qualificacao_procedimento.py` | Model template + item: remove `applicable_qualification_type`, add `phase` no item, constraint por categoria, `resolve_for(category)` | Modify |
| `models/sale_order.py` | Caller + `_explode_collect_items`: resolve por categoria, filtra itens por fase | Modify (~1120, 1124-1154) |
| `wizards/apply_procedimento_wizard.py` | Aplicar procedimento manual: filtra itens por fase da qualif | Modify (57, 79-106) |
| `views/qualificacao_procedimento_views.xml` | Form notebook por fase; remove campo do form/tree/search | Modify |
| `migrations/16.0.6.0.0/pre-migrate.py` | Limpa procs antigos antes da nova constraint | Create |
| `__manifest__.py` | Version bump → `16.0.6.0.0` | Modify (linha 3) |
| `tests/test_procedimento_explosion.py` | Fixtures unificadas + testes resolve/explosão por fase + teste do wizard | Modify |
| `tests/test_docx_render.py` | Ajuste de fixture (remove campo, add phase) | Modify (~177) |
| `tests/test_coverage.py` | Ajuste de fixture (remove campo, add phase) | Modify (~71) |

---

## Task 1: Model pivot — `phase` no item, constraint por categoria, `resolve_for(category)`

**Files:**
- Modify: `models/qualificacao_procedimento.py`
- Modify: `views/qualificacao_procedimento_views.xml` (remover as 4 refs ao campo removido — senão a view não carrega e `-u` falha)
- Test: `tests/test_procedimento_explosion.py` (fixtures + resolve)

> **Dependência (descoberta na execução):** remover `applicable_qualification_type` do model quebra o load da view que ainda referencia o campo → `-u` aborta antes dos testes. Por isso as deleções de view (antes na Task 4 Step 2) entram AQUI, antes do GREEN.

- [ ] **Step 1: Reescrever as fixtures do teste de explosão (setUpClass)**

Substituir TODO o bloco `setUpClass` (linhas ~11-79, das 4 criações de `Proc`) em `tests/test_procedimento_explosion.py` por uma fixture unificada: 1 proc da categoria com itens das fases QI/QD/Calib, + 1 proc fallback (sem categoria) com itens QD.

```python
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Proc = cls.env["afr.qualificacao.procedimento"]
        # 1 procedimento por categoria — itens de TODAS as fases (QI + QD + Calib)
        cls.proc_category = Proc.create({
            "name": "Procedimento Autoclave",
            "equipment_category_id": cls.category.id,
            "item_ids": [
                # QI
                (0, 0, {"name": "Foto plaqueta", "kind": "foto",
                        "phase": "installation", "target_level": "qualificacao",
                        "sequence": 10}),
                (0, 0, {"name": "NF cópia", "kind": "pdf",
                        "phase": "installation", "target_level": "qualificacao",
                        "sequence": 20}),
                # QD
                (0, 0, {"name": "Foto carga autoclave", "kind": "foto",
                        "phase": "performance", "target_level": "cycle",
                        "sequence": 30}),
                (0, 0, {"name": "Dados qualificador térmico", "kind": "qualificador_data",
                        "phase": "performance", "target_level": "qualificacao",
                        "sequence": 40}),
                (0, 0, {"name": "Indicador biológico", "kind": "foto",
                        "phase": "performance", "target_level": "cycle",
                        "sequence": 50}),
                # Calibração
                (0, 0, {"name": "Foto sensor in loco", "kind": "foto",
                        "phase": "calibration", "target_level": "malha",
                        "sequence": 60}),
            ],
        })
        # Procedimento fallback (sem categoria) — itens QD
        cls.proc_fallback = Proc.create({
            "name": "Procedimento Genérico (fallback)",
            "item_ids": [
                (0, 0, {"name": "Doc procedimento", "kind": "pdf",
                        "phase": "performance", "target_level": "qualificacao",
                        "sequence": 10}),
                (0, 0, {"name": "Foto carga", "kind": "foto",
                        "phase": "performance", "target_level": "cycle",
                        "sequence": 20}),
            ],
        })
```

- [ ] **Step 2: Reescrever os 3 testes de `resolve_for`**

Substituir os métodos `test_resolve_prefers_category_match`, `test_resolve_fallback_generic_when_no_category`, `test_resolve_returns_empty_when_no_match` por (nova assinatura `resolve_for(category)`):

```python
    # ─────────────────────────────────────────────────────────────
    # resolve_for: categoria > fallback (categoria vazia)
    # ─────────────────────────────────────────────────────────────
    def test_resolve_prefers_category_match(self):
        Proc = self.env["afr.qualificacao.procedimento"]
        rec = Proc.resolve_for(self.category)
        self.assertEqual(rec, self.proc_category)

    def test_resolve_fallback_when_category_has_no_proc(self):
        Proc = self.env["afr.qualificacao.procedimento"]
        other_cat = self.env["engc.equipment.category"].create({"name": "OutraCat"})
        rec = Proc.resolve_for(other_cat)
        self.assertEqual(rec, self.proc_fallback)

    def test_resolve_empty_when_no_category_and_no_fallback(self):
        Proc = self.env["afr.qualificacao.procedimento"]
        self.proc_fallback.active = False  # sem fallback disponível
        other_cat = self.env["engc.equipment.category"].create({"name": "SemProc"})
        rec = Proc.resolve_for(other_cat)
        self.assertFalse(rec)
        self.proc_fallback.active = True
```

- [ ] **Step 3: Run os testes de resolve — devem FALHAR**

Run (via subagente test-runner, tags da classe):
```
docker exec -i <odoo_container> odoo --test-enable --stop-after-init \
  -d <db_test> -u afr_qualificacao \
  --test-tags /afr_qualificacao:TestProcedimentoExplosion.test_resolve_prefers_category_match
```
Expected: FAIL — model ainda exige `applicable_qualification_type` (required) e `procedimento.item` não tem `phase`; criação das fixtures quebra.

- [ ] **Step 4: Editar o model — remover `applicable_qualification_type`, add `phase`, constraint, resolve_for**

Em `models/qualificacao_procedimento.py`:

(a) Adicionar constante de fase no topo do arquivo (após `KIND_SELECTION`):
```python
PHASE_SELECTION = [
    ("installation", "QI"),
    ("operational", "QO"),
    ("performance", "QD"),
    ("software", "QS"),
    ("calibration", "Calibração"),
]
```

(b) Em `AfrQualificacaoProcedimento`: **remover** o campo `applicable_qualification_type` inteiro (linhas 78-89). Atualizar a docstring do módulo (linha 8) para "Resolve por equipment_category_id (vazio = fallback)".

(c) Trocar `_sql_constraints`:
```python
    _sql_constraints = [
        (
            "uniq_category_company",
            "unique(equipment_category_id, company_id)",
            "Já existe procedimento para essa categoria + empresa.",
        ),
    ]
```

(d) Trocar `resolve_for`:
```python
    @api.model
    def resolve_for(self, equipment_category):
        """Retorna o procedimento da categoria (ou fallback de categoria vazia).

        Preferência: 1) match por categoria → 2) fallback (equipment_category_id
        vazio). Retorna recordset vazio se nenhum.
        """
        domain = [("active", "=", True)]
        cat_id = equipment_category.id if equipment_category else False
        if cat_id:
            rec = self.search(
                domain + [("equipment_category_id", "=", cat_id)], limit=1
            )
            if rec:
                return rec
        return self.search(
            domain + [("equipment_category_id", "=", False)], limit=1
        )
```

(e) Em `AfrQualificacaoProcedimentoItem`: adicionar o campo `phase` (após `procedimento_id`):
```python
    phase = fields.Selection(
        PHASE_SELECTION,
        required=True,
        default="installation",
        string="Fase",
        help="Fase de qualificação a que este item pertence. Setado "
             "automaticamente pela aba do editor.",
    )
```

- [ ] **Step 4b: Remover as 4 refs ao campo na view (pré-requisito do load)**

Em `views/qualificacao_procedimento_views.xml`, remover (deleções puras):
- Form, `<group string="Aplicabilidade">` (~linha 23): `<field name="applicable_qualification_type"/>`.
- Tree (~linha 78): `<field name="applicable_qualification_type"/>`.
- Search, campo (~linha 97): `<field name="applicable_qualification_type"/>`.
- Search, filtro group_by (~linhas 102-103): o `<filter string="Tipo" name="group_type" context="{'group_by': 'applicable_qualification_type'}"/>`.

(O rewrite do form em notebook por fase continua na Task 4 — aqui só removemos as refs ao campo morto; o `<field name="item_ids">` plano segue funcionando.)

- [ ] **Step 5: Run os testes de resolve — devem PASSAR**

Run: mesmas test-tags do Step 3 + as outras 2 de resolve.
Expected: PASS (3 testes resolve verdes).

- [ ] **Step 6: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add models/qualificacao_procedimento.py views/qualificacao_procedimento_views.xml tests/test_procedimento_explosion.py
git commit -m "feat(procedimento): pivot 1-por-categoria + campo phase no item

Remove applicable_qualification_type; constraint unique(category,company);
resolve_for(category) com fallback de categoria vazia; item ganha phase.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Explosão filtra itens pela fase da qualificação

**Files:**
- Modify: `models/sale_order.py` (caller ~1120; método `_explode_collect_items` 1124-1154)
- Test: `tests/test_procedimento_explosion.py` (testes de explosão já existentes validam)

- [ ] **Step 1: Run os testes de explosão existentes — devem FALHAR**

Run (test-runner, classe inteira):
```
--test-tags /afr_qualificacao:TestProcedimentoExplosion
```
Expected: FAIL nos `test_explosion_*` / `test_os_collect_counts_aggregated` — sem filtro de fase, a explosão cria itens de TODAS as fases do proc (ex.: QI explodiria também itens QD/Calib), contagens erradas. (`test_so_with_qs_no_proc` pode falhar pois agora há proc da categoria.)

- [ ] **Step 2: Editar o caller `resolve_for` + passar a fase**

Em `models/sale_order.py`, trocar o bloco ~1118-1122:
```python
                # F1 16.0.6.0.0: 1 proc por categoria; filtra itens pela fase (qtype)
                proc = Procedimento.sudo().resolve_for(equipment.category_id)
                if proc:
                    self._explode_collect_items(CollectItem.sudo(), qualif, proc, qtype)
```

- [ ] **Step 3: Editar `_explode_collect_items` — novo arg `phase` + filtro**

Trocar a assinatura e o loop inicial (linhas 1124-1131):
```python
    def _explode_collect_items(self, CollectItem, qualif, procedimento, phase):
        """F3/F1: Cria N collect.items por procedimento.item conforme target_level.

        Filtra os itens do procedimento pela `phase` da qualificação (F1).
        target_level=qualificacao → 1 item por qualif
        target_level=cycle → 1 item por cycle existente (qualif QD)
        target_level=malha → 1 item por malha existente (qualif Calib)
        """
        items = procedimento.item_ids.filtered(lambda pi: pi.phase == phase)
        for pi in items:
            base_vals = {
```
(O resto do método — `base_vals`, os 3 ramos `target_level` — fica idêntico.)

- [ ] **Step 3b: Atualizar comentários stale nos corpos dos testes de explosão**

Os comentários ainda citam fixtures deletadas (`proc_qi`, `proc_qd_autoclave`). Trocar para refletir `proc_category`:
- `test_explosion_qi_target_qualificacao`: `# proc_qi tem 2 items...` → `# proc_category tem 2 items QI target=qualificacao → 2 collect.items`.
- `test_explosion_qd_cycle_explodes_per_cycle`: `# proc_qd_autoclave: ...` → `# proc_category (fase QD): 2 items cycle + 1 qualificacao = 2*3 + 1 = 7`.

- [ ] **Step 4: Run os testes de explosão — devem PASSAR**

Run: `--test-tags /afr_qualificacao:TestProcedimentoExplosion`
Expected: PASS. Conferir as contagens-chave:
- `test_explosion_qi_target_qualificacao`: 2 (só itens QI da categoria).
- `test_explosion_qd_cycle_explodes_per_cycle`: 7 (2 cycle × 3 + 1 qualif, itens QD).
- `test_explosion_calib_malha_explodes_per_malha`: 4 (1 malha × 4).
- `test_os_collect_counts_aggregated`: 7 (QI 2 + QD 1 qualif + 2×2 cycle).
- `test_so_with_qs_no_proc_no_explosion`: 0 (categoria não tem itens fase `software`).

- [ ] **Step 5: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add models/sale_order.py
git commit -m "feat(procedimento): explosão filtra collect.items pela fase da qualif

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Wizard "Aplicar Procedimento" filtra por fase

**Files:**
- Modify: `wizards/apply_procedimento_wizard.py` (linha 57; método `_explode_for_qualif` 78-106)
- Test: `tests/test_procedimento_explosion.py` (adicionar método; reusa `_confirm_so_with` e a fixture `proc_category`)

> **Por que no arquivo de explosão:** qualifs/OS NÃO se criam direto nos testes (exigem campos do fluxo); cria-se via `_confirm_so_with` (configurador + SO confirm), helper que só existe nessa classe. Reusar evita criar `afr.qualificacao` na mão.

- [ ] **Step 1: Escrever o teste do wizard (falha) — adicionar método à classe `TestProcedimentoExplosion`**

Adicionar ao fim de `tests/test_procedimento_explosion.py`:
```python
    # ─────────────────────────────────────────────────────────────
    # Wizard "Aplicar Procedimento": filtra itens pela fase da qualif
    # ─────────────────────────────────────────────────────────────
    def test_wizard_apply_filters_by_phase(self):
        # confirma SO com 1 qualif QI (proc_category auto-explode os itens QI)
        so = self._confirm_so_with([
            {"equipment_id": self.equip1.id, "do_qi": True},
        ])
        qualif = so.qualificacao_ids
        os = so.qualificacao_os_ids
        # limpa coletas auto-explodidas no confirm p/ isolar o efeito do wizard
        qualif.collect_item_ids.unlink()
        wiz = self.env["afr.qualificacao.os.apply.procedimento.wizard"].create({
            "os_id": os.id,
            "procedimento_id": self.proc_category.id,
            "qualificacao_ids": [(6, 0, qualif.ids)],
        })
        wiz.action_apply()
        names = qualif.collect_item_ids.mapped("name")
        # proc_category tem QI(2) + QD(3) + Calib(1); qualif QI recebe só os 2 QI
        self.assertEqual(len(qualif.collect_item_ids), 2)
        self.assertIn("Foto plaqueta", names)
        self.assertNotIn("Dados qualificador térmico", names)  # item QD fica de fora
```

- [ ] **Step 2: Run o teste — deve FALHAR**

Run: `--test-tags /afr_qualificacao:TestProcedimentoExplosion.test_wizard_apply_filters_by_phase`
Expected: FAIL — wizard hoje referencia `self.procedimento_id.applicable_qualification_type` (campo removido → AttributeError) ou cria itens das 2 fases.

- [ ] **Step 3: Editar o wizard — remover check de tipo, filtrar itens por fase**

Em `wizards/apply_procedimento_wizard.py`:

(a) No `action_apply` (linhas ~55-57), **remover** o bloco:
```python
            # Filtra qualifs incompatíveis com o tipo aplicável do procedimento
            if qualif.qualification_type != self.procedimento_id.applicable_qualification_type:
                continue
```
(Não pular a qualif; o filtro de fase no método de explosão cuida disso.)

(b) Em `_explode_for_qualif`, trocar a linha do loop (`for pi in procedimento.item_ids:`, ~linha 79) por:
```python
        items = procedimento.item_ids.filtered(
            lambda pi: pi.phase == qualif.qualification_type
        )
        for pi in items:
```

- [ ] **Step 4: Run o teste — deve PASSAR**

Run: `--test-tags /afr_qualificacao:TestApplyProcedimentoWizard`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add wizards/apply_procedimento_wizard.py tests/test_apply_procedimento_wizard.py
git commit -m "feat(procedimento): wizard aplicar filtra itens pela fase da qualif

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: View — editor notebook por fase (auto-set da fase)

**Files:**
- Modify: `views/qualificacao_procedimento_views.xml`

- [ ] **Step 1: Trocar o form — notebook por fase no lugar do `item_ids` plano**

Em `views/qualificacao_procedimento_views.xml`, no form (`view_afr_qualificacao_procedimento_form`):

(a) No `<group string="Aplicabilidade">` (linha ~22-28), **remover** `<field name="applicable_qualification_type"/>`.

(b) Substituir o bloco `<separator string="Itens (esperados de coleta)"/>` + `<field name="item_ids">...</field>` (linhas 37-57) por um notebook. Cada página repete a mesma tree, mudando só `phase` no domain/context:
```xml
                    <notebook>
                        <page string="QI · Instalação">
                            <field name="item_ids" mode="tree"
                                   domain="[('phase', '=', 'installation')]"
                                   context="{'default_phase': 'installation'}">
                                <tree editable="bottom">
                                    <field name="phase" column_invisible="1"/>
                                    <field name="sequence" widget="handle"/>
                                    <field name="name"/>
                                    <field name="kind"/>
                                    <field name="target_level"/>
                                    <field name="required"/>
                                    <field name="requires_instrument"
                                           widget="boolean_toggle" optional="show"/>
                                    <field name="required_sensor_kind_ids"
                                           widget="many2many_tags" optional="show"
                                           options="{'no_create_edit': True}"/>
                                    <field name="docx_section" optional="show"/>
                                    <field name="mimetypes_hint" optional="hide"/>
                                    <field name="instruction" optional="hide"/>
                                </tree>
                            </field>
                        </page>
                        <page string="QO · Operacional">
                            <field name="item_ids" mode="tree"
                                   domain="[('phase', '=', 'operational')]"
                                   context="{'default_phase': 'operational'}">
                                <tree editable="bottom">
                                    <field name="phase" column_invisible="1"/>
                                    <field name="sequence" widget="handle"/>
                                    <field name="name"/>
                                    <field name="kind"/>
                                    <field name="target_level"/>
                                    <field name="required"/>
                                    <field name="requires_instrument"
                                           widget="boolean_toggle" optional="show"/>
                                    <field name="required_sensor_kind_ids"
                                           widget="many2many_tags" optional="show"
                                           options="{'no_create_edit': True}"/>
                                    <field name="docx_section" optional="show"/>
                                    <field name="mimetypes_hint" optional="hide"/>
                                    <field name="instruction" optional="hide"/>
                                </tree>
                            </field>
                        </page>
                        <page string="QD · Desempenho">
                            <field name="item_ids" mode="tree"
                                   domain="[('phase', '=', 'performance')]"
                                   context="{'default_phase': 'performance'}">
                                <tree editable="bottom">
                                    <field name="phase" column_invisible="1"/>
                                    <field name="sequence" widget="handle"/>
                                    <field name="name"/>
                                    <field name="kind"/>
                                    <field name="target_level"/>
                                    <field name="required"/>
                                    <field name="requires_instrument"
                                           widget="boolean_toggle" optional="show"/>
                                    <field name="required_sensor_kind_ids"
                                           widget="many2many_tags" optional="show"
                                           options="{'no_create_edit': True}"/>
                                    <field name="docx_section" optional="show"/>
                                    <field name="mimetypes_hint" optional="hide"/>
                                    <field name="instruction" optional="hide"/>
                                </tree>
                            </field>
                        </page>
                        <page string="QS · Software">
                            <field name="item_ids" mode="tree"
                                   domain="[('phase', '=', 'software')]"
                                   context="{'default_phase': 'software'}">
                                <tree editable="bottom">
                                    <field name="phase" column_invisible="1"/>
                                    <field name="sequence" widget="handle"/>
                                    <field name="name"/>
                                    <field name="kind"/>
                                    <field name="target_level"/>
                                    <field name="required"/>
                                    <field name="requires_instrument"
                                           widget="boolean_toggle" optional="show"/>
                                    <field name="required_sensor_kind_ids"
                                           widget="many2many_tags" optional="show"
                                           options="{'no_create_edit': True}"/>
                                    <field name="docx_section" optional="show"/>
                                    <field name="mimetypes_hint" optional="hide"/>
                                    <field name="instruction" optional="hide"/>
                                </tree>
                            </field>
                        </page>
                        <page string="Calibração">
                            <field name="item_ids" mode="tree"
                                   domain="[('phase', '=', 'calibration')]"
                                   context="{'default_phase': 'calibration'}">
                                <tree editable="bottom">
                                    <field name="phase" column_invisible="1"/>
                                    <field name="sequence" widget="handle"/>
                                    <field name="name"/>
                                    <field name="kind"/>
                                    <field name="target_level"/>
                                    <field name="required"/>
                                    <field name="requires_instrument"
                                           widget="boolean_toggle" optional="show"/>
                                    <field name="required_sensor_kind_ids"
                                           widget="many2many_tags" optional="show"
                                           options="{'no_create_edit': True}"/>
                                    <field name="docx_section" optional="show"/>
                                    <field name="mimetypes_hint" optional="hide"/>
                                    <field name="instruction" optional="hide"/>
                                </tree>
                            </field>
                        </page>
                    </notebook>
```

> **Nota técnica:** o mesmo `item_ids` aparece em 5 páginas com domains diferentes. Isso é suportado no Odoo 16 (cada `<field>` filtra a mesma relação). O `default_phase` do context garante que criar linha numa aba seta a fase certa; o `domain` garante que a linha aparece só na aba da sua fase.

- [ ] **Step 2: (FEITO na Task 1 Step 4b)** — as refs ao campo removido na tree e no search já foram apagadas na Task 1 (eram pré-requisito do load). Confirmar que não restou nenhuma: `grep -n applicable_qualification_type views/qualificacao_procedimento_views.xml` → vazio.

- [ ] **Step 3: Validar o XML carregando o módulo**

Run (test-runner ou upgrade): `-u afr_qualificacao --stop-after-init` num db de teste.
Expected: sem `ParseError`/`ValidationError`; módulo sobe. (Validação visual completa no Task 7.)

- [ ] **Step 4: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add views/qualificacao_procedimento_views.xml
git commit -m "feat(procedimento): editor notebook por fase com auto-set

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Migração + version bump

**Files:**
- Create: `migrations/16.0.6.0.0/pre-migrate.py`
- Modify: `__manifest__.py` (linha 3)

- [ ] **Step 1: Criar o pre-migrate**

Create `migrations/16.0.6.0.0/pre-migrate.py`:
```python
# -*- coding: utf-8 -*-
"""Pre-migration 16.0.6.0.0 — pivot procedimento (tipo×categoria → 1/categoria).

labquali está em DEV: limpamos os procedimentos antigos (formato
applicable_qualification_type × categoria) e seus itens, para que a nova
constraint unique(equipment_category_id, company_id) instale limpa. Re-seed
é manual pós-upgrade. NÃO usar em produção sem trocar por merge real tipo→fase.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("DELETE FROM afr_qualificacao_procedimento_item")
    cr.execute("DELETE FROM afr_qualificacao_procedimento")
```

- [ ] **Step 2: Bump da versão no manifest**

Em `__manifest__.py` linha 3, trocar:
```python
    "version": "16.0.5.20.0",
```
por:
```python
    "version": "16.0.6.0.0",
```

- [ ] **Step 3: Run upgrade num db de teste — limpa e sobe**

Run: `-u afr_qualificacao --stop-after-init` (db com procs antigos, se houver).
Expected: pre-migrate roda, sem erro de constraint; módulo na versão 16.0.6.0.0.

- [ ] **Step 4: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add migrations/16.0.6.0.0/pre-migrate.py __manifest__.py
git commit -m "chore(procedimento): migração 16.0.6.0.0 (limpa procs antigos) + bump

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Ajustar testes remanescentes + suíte completa verde

**Files:**
- Modify: `tests/test_docx_render.py` (~177)
- Modify: `tests/test_coverage.py` (~71)

- [ ] **Step 1: Ajustar `tests/test_docx_render.py`**

No `test_docx_section_propagated_from_procedimento_item` (~linha 177), a criação do proc usa `applicable_qualification_type` (removido) e o item não tem `phase`. Trocar:
```python
        proc = self.env["afr.qualificacao.procedimento"].create({
            "name": "Test Proc QI",
            "applicable_qualification_type": "installation",
        })
        proc_item = self.env["afr.qualificacao.procedimento.item"].create({
            "procedimento_id": proc.id,
            "name": "Manual de instalação",
            "kind": "pdf",
            "docx_section": "qi_documentos",
        })
```
por:
```python
        proc = self.env["afr.qualificacao.procedimento"].create({
            "name": "Test Proc QI",
        })
        proc_item = self.env["afr.qualificacao.procedimento.item"].create({
            "procedimento_id": proc.id,
            "name": "Manual de instalação",
            "kind": "pdf",
            "phase": "installation",
            "docx_section": "qi_documentos",
        })
```

- [ ] **Step 2: Ajustar `tests/test_coverage.py`**

No `setUpClass` (~linha 71), a criação `cls.proc` usa `applicable_qualification_type` e os dois `proc_item` não têm `phase`. Trocar:
```python
        cls.proc = cls.env["afr.qualificacao.procedimento"].create({
            "name": "Test Proc",
            "applicable_qualification_type": "calibration",
            "code": "TEST-PROC-001",
        })
```
por:
```python
        cls.proc = cls.env["afr.qualificacao.procedimento"].create({
            "name": "Test Proc",
            "code": "TEST-PROC-001",
        })
```
E adicionar `"phase": "calibration",` ao dict de criação de `cls.proc_item_temp` e `cls.proc_item_temp_press` (ambos `qualificador_data`, fase calibração).

- [ ] **Step 3: Run a suíte COMPLETA do módulo — toda verde**

Run (test-runner, suite inteira do módulo):
```
--test-tags /afr_qualificacao
```
Expected: PASS em tudo. Caçar qualquer outra referência a `applicable_qualification_type` se algum teste novo falhar:
```bash
grep -rn 'applicable_qualification_type' tests/
```
(deve voltar vazio após este task). Se algum aparecer, aplicar o mesmo padrão: remover o campo do proc, add `phase` no item.

- [ ] **Step 4: Commit**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git add tests/test_docx_render.py tests/test_coverage.py
git commit -m "test(procedimento): ajustar fixtures ao pivot (remove campo, add phase)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Validação de UI (agent-browser) + push

**Files:** nenhum (validação + push dos commits)

- [ ] **Step 1: Restart do container p/ assets + upgrade live**

Aplicar `-u afr_qualificacao` no db de dev (porta host 8083), restart do container para assets. (Não usar `odoo-bin` direto — entrypoint custom.)

- [ ] **Step 2: Validar o editor via agent-browser**

Login, abrir menu "Procedimentos de Qualificação", criar/abrir um procedimento. Verificar:
- As 5 abas (QI/QO/QD/QS/Calibração) aparecem.
- Adicionar item na aba QD → o item nasce e fica na aba QD; ao salvar e reabrir, continua só na aba QD (fase auto-setada, sem coluna de fase visível).
- Adicionar item na aba QI não aparece na aba QD.
- Campo `applicable_qualification_type` não existe mais no form/tree/search.

- [ ] **Step 3: Smoke E2E — SO confirma → explode por fase**

Criar/confirmar um SO com equipamento da categoria que tem procedimento, com qualifs QI+QD. Conferir que cada qualificação recebeu só os collect.items da sua fase.

- [ ] **Step 4: Push de todos os commits (submódulo) + bump do pointer**

Após validação OK e confirmação do usuário (regra do projeto: push após teste):
```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git push origin main
cd /home/afonso/docker/odoo_engenapp
git add addons/afr_qualificacao
git commit -m "chore: bump afr_qualificacao (procedimento por categoria v16.0.6.0.0)"
git push
```

---

## Notas de execução

- **Container/db:** descobrir o nome do container Odoo e o db de teste no ambiente antes de rodar (ver convenções: porta host 8083, entrypoint custom). Delegar runs de teste ao subagente `test-runner`.
- **Filestore PermError:** se `-u` falhar com PermissionError no filestore, `chown` do `/var/lib/odoo/filestore/<db>` (gotcha conhecido do projeto).
- **Ordem:** Tasks 1→6 são sequenciais (cada uma deixa a suíte mais verde). Task 7 é validação final + push (só após OK do usuário).
- **Tabelas órfãs:** `afr_qualificacao_procedimento` mantém estrutura; o pre-migrate só apaga linhas. A coluna `applicable_qualification_type` fica órfã na tabela (inerte em dev) — aceitável.
