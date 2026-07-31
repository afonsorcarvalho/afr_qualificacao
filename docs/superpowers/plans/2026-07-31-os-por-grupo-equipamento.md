# OS de Qualificação por grupo de equipamentos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que uma cotação confirmada gere N OS de qualificação, cada uma com um subconjunto de equipamentos, garantindo que nenhum equipamento apareça em duas OS da mesma cotação.

**Architecture:** A materialização (qualificações + ciclos/malhas + itens de coleta) é extraída de `sale.order._create_qualificacoes_from_lines()` para `_materialize_qualificacoes(lines, os)`, que recebe a OS de destino em vez de resolvê-la. A geração automática no `action_confirm()` é removida; um wizard pós-confirmação (`afr.qualificacao.os.generate.wizard`) cria uma OS por clique com os equipamentos selecionados. Uma `@api.constrains` em `afr.qualificacao` sustenta a invariante independentemente do caminho de criação.

**Tech Stack:** Odoo 16.0, Python 3.9, PostgreSQL, testes `odoo.tests.TransactionCase` via docker.

## Global Constraints

- Módulo: `afr_qualificacao` (git submodule com `.git` próprio — commits e `git push origin main` de dentro de `/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao`).
- Commits sempre via subagente `git-commit-push` (model haiku), nunca `git commit` direto.
- Versão alvo no `__manifest__.py`: `16.0.6.13.0` (bump na última task).
- Spec de referência: `docs/superpowers/specs/2026-07-31-os-por-grupo-equipamento-design.md`.
- Comando de teste (delegar ao subagente `test-runner`; abaixo o comando cru para referência):
  ```bash
  docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
    --test-enable --test-tags <TAGS> --stop-after-init \
    --no-http --workers=0 --max-cron-threads=0 \
    --db_host=db --db_user=odoo --db_password=odoo 2>&1
  ```
  Formas de `<TAGS>`: suite `afr_qualificacao`; classe `/afr_qualificacao:TestClasse`; método `/afr_qualificacao:TestClasse.test_metodo`.
- Falhas pré-existentes conhecidas (NÃO são regressão): `TestResourcePlan.test_fleet_single_logger_two_temp_standards` e as outras listadas no agente `test-runner`. Classifique-as como pré-existentes.
- Idioma: código, docstrings e mensagens de UI em português (padrão do módulo). Mensagens de commit em inglês.
- Item do spec que **não** vira task: o spec previa ajustar o stat button para abrir tree com N OS. Verificado — `action_view_qualificacao_os` já retorna `"view_mode": "tree,form"`, então não há mudança a fazer.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `models/sale_order.py` (modificar) | Extração de `_materialize_qualificacoes`, helper `_pending_qualif_lines`, regra de nome, computes `equipamentos_sem_os_ids`/`pode_gerar_os`, action que abre o wizard, remoção da geração no confirm |
| `models/qualificacao.py` (modificar) | `@api.constrains` da invariante equipamento↔OS por cotação |
| `wizards/qualificacao_os_generate_wizard.py` (criar) | TransientModel do wizard de geração |
| `wizards/qualificacao_os_generate_wizard_views.xml` (criar) | Form do wizard |
| `wizards/__init__.py` (modificar) | Import do novo wizard |
| `views/sale_order_views.xml` (modificar) | Botão de header + campo invisível `pode_gerar_os` |
| `security/ir.model.access.csv` (modificar) | ACL do wizard |
| `__manifest__.py` (modificar) | Registro da view do wizard + bump de versão |
| `tests/common.py` (modificar) | Helper `_confirm_and_generate_os(so)` para os testes existentes |
| `tests/test_os_por_grupo.py` (criar) | Testes do fluxo N-OS |
| 13 arquivos de teste existentes (modificar) | Trocar `so.action_confirm()` pelo helper |

---

### Task 1: Extrair `_materialize_qualificacoes` e `_pending_qualif_lines`

Refatoração pura, sem mudança de comportamento. A suíte inteira deve continuar
verde no fim (é o teste desta task).

**Files:**
- Modify: `models/sale_order.py:1180-1300` (`_create_qualificacoes_from_lines`)

**Interfaces:**
- Consumes: nada
- Produces:
  - `sale.order._pending_qualif_lines() -> sale.order.line` (recordset das linhas
    managed elegíveis ainda sem `afr_qualificacao_id`)
  - `sale.order._materialize_qualificacoes(lines, os) -> None` (cria
    `afr.qualificacao` + sub-records de `lines` dentro de `os`)

- [ ] **Step 1: Rodar a suíte antes de mexer (baseline)**

Delegue ao subagente `test-runner` com tags `afr_qualificacao`.
Anote o número de testes e as falhas pré-existentes — este é o baseline que a
task tem de preservar.

- [ ] **Step 2: Adicionar `_pending_qualif_lines()`**

Em `models/sale_order.py`, logo antes de `_create_qualificacoes_from_lines`:

```python
    def _pending_qualif_lines(self):
        """Linhas managed elegíveis que ainda não têm afr.qualificacao.

        Elegível = gerada pelo configurador, não é seção/nota, não teve a
        Parte 01 recusada, e — se for opcional — foi aceita e tem tipo.
        """
        self.ensure_one()
        managed = self.order_line.filtered(
            lambda l: l.is_qualificacao_managed
            and not l.display_type
            and not l.part01_declined
            and not (l.is_proposal_optional and not l.optional_accepted)
            and not (l.is_proposal_optional and not l.qualification_type)
        )
        return managed.filtered(lambda l: not l.afr_qualificacao_id)
```

- [ ] **Step 3: Reescrever `_create_qualificacoes_from_lines` usando os dois helpers**

Substitua o corpo de `_create_qualificacoes_from_lines` (mantendo a docstring
existente, que segue válida nesta task) por:

```python
        self.ensure_one()
        managed = self._pending_qualif_lines()
        if not managed:
            return

        QualifOs = self.env["afr.qualificacao.os"]

        # 1 OS por SO (reusa se já existe — re-confirmação parcial)
        # Fallback: busca por nome derivado caso OS tenha sido desvinculada
        os = self.qualificacao_os_ids[:1]
        if not os:
            so_name = self.name or ""
            os_name = ("OS" + so_name[1:]) if so_name.startswith("C") else None
            if os_name:
                os = QualifOs.search([
                    ("name", "=", os_name),
                    ("company_id", "=", self.company_id.id),
                ], limit=1)
                if os and os not in self.qualificacao_os_ids:
                    self.write({"qualificacao_os_ids": [(4, os.id)]})
            if not os:
                os = QualifOs.create(self._prepare_qualificacao_os_values())

        self._materialize_qualificacoes(managed, os)
```

- [ ] **Step 4: Criar `_materialize_qualificacoes(lines, os)` com o corpo antigo**

Adicione logo depois de `_create_qualificacoes_from_lines`. O corpo é o trecho
que hoje vai de `# Agrupa linhas por equipamento` até o fim do método, com
`managed` renomeado para `lines`:

```python
    def _materialize_qualificacoes(self, lines, os):
        """Cria afr.qualificacao + sub-records de `lines`, dentro de `os`.

        - 1 afr.qualificacao por (equipamento, qualification_type)
        - QD/QO com cycle_type: N afr.qualificacao.cycle por linha (qty=N)
        - Calibração: N afr.qualificacao.malha por linha
        - QI/QS e QO booleano: sem sub-records
        - Snapshot dos pontos QD + explosão de collect.items do procedimento

        Não resolve OS — o chamador escolhe o destino. É o que permite
        1 cotação → N OS.
        """
        self.ensure_one()
        Qualif = self.env["afr.qualificacao"]
        Cycle = self.env["afr.qualificacao.cycle"]
        Malha = self.env["afr.qualificacao.malha"]
        Procedimento = self.env["afr.qualificacao.procedimento"]
        CollectItem = self.env["afr.qualificacao.collect.item"]

        by_equipment = defaultdict(lambda: self.env["sale.order.line"])
        for line in lines:
            by_equipment[line.equipment_id] |= line

        for equipment, equip_lines in by_equipment.items():
            by_type = defaultdict(lambda: self.env["sale.order.line"])
            for line in equip_lines:
                by_type[line.qualification_type] |= line

            for qtype, type_lines in by_type.items():
                qualif = Qualif.create(
                    self._prepare_qualificacao_values(equipment, qtype, os)
                )
                type_lines.write({"afr_qualificacao_id": qualif.id})

                # F10 — snapshot dos pontos QD (cópia própria do template),
                # p/ o plano de recursos não depender do template depois.
                if qtype == "performance":
                    tpl = self._qd_template_for(equipment)
                    if tpl and tpl.qd_point_ids:
                        qualif.sudo().write({
                            "qd_point_snapshot_ids": [
                                (0, 0, {
                                    "sensor_kind_id": p.sensor_kind_id.id,
                                    "points": p.points,
                                })
                                for p in tpl.qd_point_ids
                            ]
                        })

                # F8.8 — QO cycle-based explode igual ao QD.
                if qtype in ("performance", "operational"):
                    for line in type_lines:
                        if not line.cycle_type_id:
                            continue
                        qty = line.qualif_cycle_qty or int(line.product_uom_qty or 0)
                        for seq in range(1, qty + 1):
                            Cycle.create({
                                "qualificacao_id": qualif.id,
                                "cycle_type_id": line.cycle_type_id.id,
                                "sale_order_line_id": line.id,
                                "sequence": seq * 10,
                            })
                elif qtype == "calibration":
                    for line in type_lines:
                        qty = line.qualif_cycle_qty or int(line.product_uom_qty or 0)
                        for seq in range(1, qty + 1):
                            Malha.create({
                                "qualificacao_id": qualif.id,
                                "malha_type_id": line.malha_type_id.id,
                                "sale_order_line_id": line.id,
                                "sequence": seq * 10,
                            })

                # F3/F1: explode procedimento default em collect.items.
                # sudo: quem confirma a SO pode não ter grupos de qualificação.
                proc = Procedimento.sudo().resolve_for(equipment.category_id)
                if proc:
                    self._explode_collect_items(CollectItem.sudo(), qualif, proc, qtype)
```

- [ ] **Step 5: Rodar a suíte completa e comparar com o baseline**

Delegue ao `test-runner` com tags `afr_qualificacao`.
Esperado: mesmo total de testes, mesmas falhas do baseline, nenhuma nova.
Se aparecer falha nova, a extração alterou comportamento — corrija antes de commitar.

- [ ] **Step 6: Commit**

Delegue ao subagente `git-commit-push` com `cwd` em
`/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao`, staged apenas
`models/sale_order.py`, mensagem:

```
refactor(sale_order): extract _materialize_qualificacoes from confirm flow
```

---

### Task 2: Regra de nome das OS (sufixo `-1`, `-2`, `-3`)

**Files:**
- Modify: `models/sale_order.py:1335` (`_prepare_qualificacao_os_values`)
- Test: `tests/test_os_por_grupo.py` (criar)

**Interfaces:**
- Consumes: `sale.order._pending_qualif_lines()` (Task 1)
- Produces: `sale.order._prepare_qualificacao_os_values(equipments=None, pending_equipments=None) -> dict`
  - `equipments`: recordset `engc.equipment` que vai nesta OS
  - `pending_equipments`: recordset dos equipamentos ainda sem OS antes desta criação
  - Ambos `None` → caminho legado (nome sem sufixo, comportamento pré-feature)

- [ ] **Step 1: Escrever os testes de nome que falham**

Crie `tests/test_os_por_grupo.py`:

```python
"""Fluxo 1 cotação : N OS de qualificação por grupo de equipamentos."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestOsPorGrupo(AfrQualificacaoTestCommon):

    def _build_so(self, equipment_lines_spec):
        """Cria SO com linhas managed via configurador."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [(0, 0, spec) for spec in equipment_lines_spec]
        wiz.action_apply()
        return so

    def _so_dois_equipamentos(self):
        return self._build_so([
            {"equipment_id": self.equip1.id, "do_qi": True},
            {"equipment_id": self.equip2.id, "do_qi": True},
        ])

    def test_nome_sem_sufixo_quando_cobre_todos_equipamentos(self):
        so = self._so_dois_equipamentos()
        so.write({"name": "C26-06-0001"})
        pending = so._pending_qualif_lines().mapped("equipment_id")
        vals = so._prepare_qualificacao_os_values(pending, pending)
        self.assertEqual(vals["name"], "OS26-06-0001")

    def test_nome_com_sufixo_1_quando_parcial(self):
        so = self._so_dois_equipamentos()
        so.write({"name": "C26-06-0002"})
        pending = so._pending_qualif_lines().mapped("equipment_id")
        vals = so._prepare_qualificacao_os_values(pending[:1], pending)
        self.assertEqual(vals["name"], "OS26-06-0002-1")

    def test_nome_legado_sem_argumentos(self):
        """Chamada sem seleção (caminho antigo) segue sem sufixo."""
        so = self._so_dois_equipamentos()
        so.write({"name": "C26-06-0003"})
        vals = so._prepare_qualificacao_os_values()
        self.assertEqual(vals["name"], "OS26-06-0003")
```

- [ ] **Step 2: Rodar os testes e ver falhar**

Tags: `/afr_qualificacao:TestOsPorGrupo`
Esperado: FAIL — `_prepare_qualificacao_os_values() takes 1 positional argument but 3 were given`.

- [ ] **Step 3: Implementar a regra de nome**

Substitua `_prepare_qualificacao_os_values` inteiro por:

```python
    def _prepare_qualificacao_os_values(self, equipments=None, pending_equipments=None):
        """Hook: valores para criar afr.qualificacao.os a partir do SO.

        Nome derivado: substitui 'C' inicial pelo prefixo 'OS'.
        Ex: C26-06-0001 → OS26-06-0001

        Com N OS por cotação o nome precisa de sufixo — `unique(name,
        company_id)` no modelo. A decisão é tomada na criação, sem rename
        retroativo:

        - 1ª OS cobrindo TODOS os equipamentos pendentes → sem sufixo
          (a cotação nunca terá uma segunda OS).
        - Qualquer outro caso → `-1`, `-2`, `-3`… Um primeiro clique parcial
          já nasce `-1` porque virá pelo menos a `-2`.

        `equipments`/`pending_equipments` a None = caminho legado (sem sufixo).

        Fallback: se a SO não tem formato esperado, o nome é gerado por
        sequência no create() do modelo.
        """
        self.ensure_one()
        vals = {
            "sale_order_id": self.id,
            "company_id": self.company_id.id,
        }
        so_name = self.name or ""
        if so_name.startswith("C") and len(so_name) > 1:
            base = "OS" + so_name[1:]
            existentes = len(self.qualificacao_os_ids)
            cobre_tudo = (
                equipments is not None
                and pending_equipments is not None
                and set(equipments.ids) == set(pending_equipments.ids)
            )
            if existentes == 0 and (equipments is None or cobre_tudo):
                vals["name"] = base
            else:
                vals["name"] = "%s-%d" % (base, existentes + 1)
        return vals
```

- [ ] **Step 4: Rodar os testes e ver passar**

Tags: `/afr_qualificacao:TestOsPorGrupo`
Esperado: PASS (3 testes).

- [ ] **Step 5: Rodar a suíte completa**

Tags: `afr_qualificacao`. Esperado: mesmas falhas do baseline da Task 1.

- [ ] **Step 6: Commit**

Via `git-commit-push`, staged `models/sale_order.py` e `tests/test_os_por_grupo.py`:

```
feat(sale_order): suffix OS names when a quotation yields multiple OS
```

---

### Task 3: Constraint — um equipamento em uma só OS por cotação

**Files:**
- Modify: `models/qualificacao.py` (adicionar constrains junto às demais do modelo)
- Test: `tests/test_os_por_grupo.py` (adicionar teste)

**Interfaces:**
- Consumes: nada
- Produces: `afr.qualificacao._check_equipamento_unico_por_os_da_so()` (constrains)

- [ ] **Step 1: Escrever o teste que falha**

Adicione a `tests/test_os_por_grupo.py`, dentro de `TestOsPorGrupo`:

```python
    def test_constraint_equipamento_em_duas_os_da_mesma_so(self):
        so = self._so_dois_equipamentos()
        os_a = self.env["afr.qualificacao.os"].create({
            "company_id": so.company_id.id, "sale_order_id": so.id,
        })
        os_b = self.env["afr.qualificacao.os"].create({
            "company_id": so.company_id.id, "sale_order_id": so.id,
        })
        Qualif = self.env["afr.qualificacao"]
        Qualif.create({
            "name": "Q-A", "equipment_id": self.equip1.id,
            "partner_id": self.partner.id, "qualification_type": "installation",
            "company_id": so.company_id.id, "sale_order_id": so.id,
            "os_id": os_a.id,
        })
        with self.assertRaises(ValidationError):
            Qualif.create({
                "name": "Q-B", "equipment_id": self.equip1.id,
                "partner_id": self.partner.id, "qualification_type": "operational",
                "company_id": so.company_id.id, "sale_order_id": so.id,
                "os_id": os_b.id,
            })

    def test_constraint_permite_tipos_diferentes_na_mesma_os(self):
        """QI e QO do mesmo equipamento na MESMA OS é o caso normal."""
        so = self._so_dois_equipamentos()
        os_a = self.env["afr.qualificacao.os"].create({
            "company_id": so.company_id.id, "sale_order_id": so.id,
        })
        Qualif = self.env["afr.qualificacao"]
        for qtype in ("installation", "operational"):
            Qualif.create({
                "name": "Q-%s" % qtype, "equipment_id": self.equip1.id,
                "partner_id": self.partner.id, "qualification_type": qtype,
                "company_id": so.company_id.id, "sale_order_id": so.id,
                "os_id": os_a.id,
            })
        self.assertEqual(len(os_a.qualificacao_ids), 2)
```

- [ ] **Step 2: Rodar e ver falhar**

Tags: `/afr_qualificacao:TestOsPorGrupo.test_constraint_equipamento_em_duas_os_da_mesma_so`
Esperado: FAIL — nenhum `ValidationError` é levantado.

- [ ] **Step 3: Implementar a constraint**

Em `models/qualificacao.py`, junto aos outros `@api.constrains` da classe
`AfrQualificacao`. Confirme que `ValidationError` está importado de
`odoo.exceptions` no topo do arquivo; se não estiver, adicione ao import.

```python
    @api.constrains("os_id", "equipment_id", "sale_order_id")
    def _check_equipamento_unico_por_os_da_so(self):
        """Um equipamento não pode estar em duas OS da mesma cotação.

        Invariante: para cada (sale_order_id, equipment_id) o conjunto de
        `os_id` tem no máximo um elemento. Vale para qualquer caminho de
        criação — wizard, import ou script.

        sudo() na busca: sem ele, uma record rule que esconda a qualificação
        irmã faria a validação passar em falso.
        """
        for qualif in self:
            if not qualif.sale_order_id or not qualif.equipment_id:
                continue
            irmas = self.sudo().search([
                ("sale_order_id", "=", qualif.sale_order_id.id),
                ("equipment_id", "=", qualif.equipment_id.id),
                ("os_id", "!=", False),
            ])
            outras_os = irmas.mapped("os_id") - qualif.os_id
            if qualif.os_id and outras_os:
                raise ValidationError(_(
                    "O equipamento '%s' já está na OS '%s' desta cotação. "
                    "Um equipamento não pode estar em duas OS da mesma "
                    "cotação."
                ) % (
                    qualif.equipment_id.display_name,
                    outras_os[0].display_name,
                ))
```

- [ ] **Step 4: Rodar os testes e ver passar**

Tags: `/afr_qualificacao:TestOsPorGrupo`
Esperado: PASS (5 testes).

- [ ] **Step 5: Rodar a suíte completa**

Tags: `afr_qualificacao`. Esperado: mesmas falhas do baseline.
Atenção especial: a constraint roda em toda criação de qualificação — se algum
teste existente criar duas OS na mesma SO, ele vai falhar aqui e o problema é
real, não da task.

- [ ] **Step 6: Commit**

Via `git-commit-push`, staged `models/qualificacao.py` e `tests/test_os_por_grupo.py`:

```
feat(qualificacao): constrain one equipment to a single OS per quotation
```

---

### Task 4: Remover geração automática no confirm + migrar testes existentes

Task grande em número de arquivos, mas um só deliverable: depois dela,
`action_confirm()` não materializa nada e a suíte continua verde porque os
testes passam a gerar a OS explicitamente.

**Files:**
- Modify: `models/sale_order.py:1171-1178` (`action_confirm`) e a docstring do módulo (linha 5)
- Modify: `tests/common.py` (helper)
- Modify: `tests/test_so_confirm_generation.py` (inverte de propósito)
- Modify: `tests/test_qo_cycles.py`, `tests/test_procedimento_explosion.py`,
  `tests/test_hours_vs_cycles.py`, `tests/test_partes_qi_qo.py`,
  `tests/test_resource_plan.py`, `tests/test_certificate.py`,
  `tests/test_quote_first_os.py`, `tests/test_optional_accepted.py`,
  `tests/test_sequence_naming.py`, `tests/test_qty_delivered_propagation.py`,
  `tests/test_optional_wizard.py`, `tests/test_proposal_builder.py`

**Interfaces:**
- Consumes: `_pending_qualif_lines()`, `_materialize_qualificacoes()` (Task 1),
  `_prepare_qualificacao_os_values(equipments, pending)` (Task 2)
- Produces: `AfrQualificacaoTestCommon._confirm_and_generate_os(so) -> afr.qualificacao.os`

- [ ] **Step 1: Escrever o teste de que o confirm não gera nada**

Substitua o conteúdo de `tests/test_so_confirm_generation.py` por:

```python
"""Confirm da SO NÃO materializa mais nada — geração é manual via wizard.

Cutover 16.0.6.13.0: a OS de qualificação passou a ser gerada por grupo de
equipamentos, depois da confirmação, pelo wizard
`afr.qualificacao.os.generate.wizard`.
"""

from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestSoConfirmGeneration(AfrQualificacaoTestCommon):

    def _build_so_with_lines(self, equipment_lines_spec):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [(0, 0, spec) for spec in equipment_lines_spec]
        wiz.action_apply()
        return so

    def test_confirm_nao_cria_os_nem_qualificacao(self):
        so = self._build_so_with_lines([
            {"equipment_id": self.equip1.id, "do_qi": True},
            {"equipment_id": self.equip2.id, "do_qi": True},
        ])
        so.action_confirm()
        self.assertEqual(so.qualificacao_os_count, 0)
        self.assertEqual(so.qualificacao_count, 0)
        self.assertEqual(so.engc_os_count, 0)

    def test_confirm_deixa_equipamentos_pendentes(self):
        so = self._build_so_with_lines([
            {"equipment_id": self.equip1.id, "do_qi": True},
            {"equipment_id": self.equip2.id, "do_qi": True},
        ])
        so.action_confirm()
        self.assertEqual(
            set(so._pending_qualif_lines().mapped("equipment_id").ids),
            {self.equip1.id, self.equip2.id},
        )

    def test_geracao_explicita_produz_estrutura_completa(self):
        """O que o confirm fazia antes, agora o helper faz."""
        so = self._build_so_with_lines([
            {"equipment_id": self.equip1.id, "do_qi": True},
            {"equipment_id": self.equip2.id, "do_qi": True},
        ])
        os = self._confirm_and_generate_os(so)
        self.assertEqual(so.qualificacao_os_count, 1)
        self.assertEqual(set(os.equipment_ids.ids), {self.equip1.id, self.equip2.id})
        self.assertEqual(so.engc_os_count, 0)
```

- [ ] **Step 2: Rodar e ver falhar**

Tags: `/afr_qualificacao:TestSoConfirmGeneration`
Esperado: FAIL — o confirm ainda cria a OS, e `_confirm_and_generate_os` não existe.

- [ ] **Step 3: Adicionar o helper em `tests/common.py`**

Dentro da classe `AfrQualificacaoTestCommon`:

```python
    def _confirm_and_generate_os(self, so):
        """Confirma a SO e gera UMA OS com todos os equipamentos pendentes.

        Reproduz o comportamento que o `action_confirm()` tinha até
        16.0.6.12.0, para os testes que dependem da estrutura materializada.
        O fluxo real de produção é o wizard
        `afr.qualificacao.os.generate.wizard`, coberto em test_os_por_grupo.py.
        """
        so.action_confirm()
        lines = so._pending_qualif_lines()
        if not lines:
            return self.env["afr.qualificacao.os"]
        pending = lines.mapped("equipment_id")
        os = self.env["afr.qualificacao.os"].create(
            so._prepare_qualificacao_os_values(pending, pending)
        )
        so._materialize_qualificacoes(lines, os)
        return os
```

- [ ] **Step 4: Remover a geração do `action_confirm`**

Em `models/sale_order.py`, substitua `action_confirm` por:

```python
    def action_confirm(self):
        """Override: sincroniza qty de opcionais antes de confirmar.

        16.0.6.13.0 — o confirm NÃO materializa mais qualificações/OS. A
        geração passou a ser manual e incremental, por grupo de equipamentos,
        via `action_open_generate_os_wizard()` na SO confirmada.
        """
        for order in self:
            order.order_line._sync_optional_qty()
        return super().action_confirm()
```

Ajuste também a docstring do módulo (topo de `models/sale_order.py`), trocando
a linha:

```
- `action_confirm()` override dispara `_create_qualificacoes_from_lines()`
  que materializa engc.os (1/equipamento) + afr.qualificacao (1/equip×tipo)
  + sub-records (cycles/malhas explodidos por qty).
```

por:

```
- Botão `Gerar OS de Qualificação` (SO confirmada) abre wizard que cria 1
  OS por grupo de equipamentos selecionados, materializando
  afr.qualificacao (1/equip×tipo) + sub-records (cycles/malhas por qty).
  1 cotação → N OS, sem equipamento repetido entre elas.
```

Mantenha `_create_qualificacoes_from_lines` no arquivo por ora — a Task 6 a remove
depois que o wizard estiver no lugar.

- [ ] **Step 5: Rodar os testes do confirm e ver passar**

Tags: `/afr_qualificacao:TestSoConfirmGeneration`
Esperado: PASS (3 testes).

- [ ] **Step 6: Rodar a suíte completa e listar as falhas novas**

Tags: `afr_qualificacao`.
Esperado: muitas falhas nos 12 arquivos restantes (a estrutura não existe mais).
Anote a lista — ela é o roteiro do próximo step.

- [ ] **Step 7: Migrar os 12 arquivos de teste restantes**

Em cada arquivo da lista de **Files** (exceto `test_so_confirm_generation.py`,
já feito), troque cada `<so>.action_confirm()` que é seguido de asserções sobre
qualificações / OS / ciclos / malhas / itens de coleta por:

```python
        self._confirm_and_generate_os(so)
```

Quando o teste precisar da OS, capture o retorno:

```python
        os = self._confirm_and_generate_os(so)
```

Regra para decidir: se depois do confirm o teste toca em
`qualificacao_ids`, `qualificacao_os_ids`, `cycle_ids`, `malha_ids`,
`collect_item_ids`, `afr_qualificacao_id` ou em `relatorio`, use o helper. Se o
teste só verifica estado/valores da própria SO (preço, qty, opcionais), deixe
`action_confirm()` como está.

Se algum teste buscar a OS por `so.qualificacao_os_ids[0]` logo depois, prefira
o retorno do helper.

- [ ] **Step 8: Rodar a suíte completa até voltar ao baseline**

Tags: `afr_qualificacao`.
Esperado: mesmas falhas do baseline da Task 1, nenhuma nova. Itere no Step 7 até
chegar lá.

- [ ] **Step 9: Commit**

Via `git-commit-push`, staged `models/sale_order.py`, `tests/common.py` e os 13
arquivos de teste:

```
feat(sale_order): stop auto-generating OS on confirm

Generation moves to an explicit, incremental wizard run after
confirmation. Existing tests materialize through the new
_confirm_and_generate_os helper.
```

---

### Task 5: Computes `equipamentos_sem_os_ids` / `pode_gerar_os` + action

**Files:**
- Modify: `models/sale_order.py` (campos junto aos demais, ~linha 105; action junto a `action_view_qualificacao_os`, ~linha 1041)
- Test: `tests/test_os_por_grupo.py`

**Interfaces:**
- Consumes: `_pending_qualif_lines()` (Task 1)
- Produces:
  - `sale.order.equipamentos_sem_os_ids` (Many2many `engc.equipment`, compute)
  - `sale.order.pode_gerar_os` (Boolean, compute)
  - `sale.order.action_open_generate_os_wizard() -> dict` (act_window para o wizard)

- [ ] **Step 1: Escrever os testes que falham**

Adicione a `TestOsPorGrupo` em `tests/test_os_por_grupo.py`:

```python
    def test_pendentes_e_pode_gerar_os(self):
        so = self._so_dois_equipamentos()
        # Em rascunho: há pendentes, mas não pode gerar
        self.assertEqual(
            set(so.equipamentos_sem_os_ids.ids), {self.equip1.id, self.equip2.id}
        )
        self.assertFalse(so.pode_gerar_os)
        so.action_confirm()
        self.assertTrue(so.pode_gerar_os)

    def test_pendentes_esvaziam_apos_gerar_tudo(self):
        so = self._so_dois_equipamentos()
        self._confirm_and_generate_os(so)
        self.assertFalse(so.equipamentos_sem_os_ids)
        self.assertFalse(so.pode_gerar_os)

    def test_action_wizard_exige_so_confirmada(self):
        so = self._so_dois_equipamentos()
        with self.assertRaises(UserError):
            so.action_open_generate_os_wizard()

    def test_action_wizard_erra_se_nada_pendente(self):
        so = self._so_dois_equipamentos()
        self._confirm_and_generate_os(so)
        with self.assertRaises(UserError):
            so.action_open_generate_os_wizard()
```

- [ ] **Step 2: Rodar e ver falhar**

Tags: `/afr_qualificacao:TestOsPorGrupo`
Esperado: FAIL — `equipamentos_sem_os_ids` não existe.

- [ ] **Step 3: Adicionar os campos**

Em `models/sale_order.py`, logo depois de `qualificacao_os_count`:

```python
    equipamentos_sem_os_ids = fields.Many2many(
        comodel_name="engc.equipment",
        string="Equipamentos sem OS",
        compute="_compute_equipamentos_sem_os",
        help=(
            "Equipamentos das linhas de qualificação que ainda não foram "
            "materializados em nenhuma OS desta cotação."
        ),
    )
    pode_gerar_os = fields.Boolean(
        string="Pode Gerar OS",
        compute="_compute_equipamentos_sem_os",
        help="True se a cotação está confirmada e ainda há equipamento sem OS.",
    )
```

E o compute, junto aos demais computes do modelo:

```python
    @api.depends(
        "state",
        "order_line.equipment_id",
        "order_line.afr_qualificacao_id",
        "order_line.is_qualificacao_managed",
    )
    def _compute_equipamentos_sem_os(self):
        for order in self:
            pendentes = order._pending_qualif_lines().mapped("equipment_id")
            order.equipamentos_sem_os_ids = pendentes
            order.pode_gerar_os = bool(pendentes) and order.state == "sale"
```

- [ ] **Step 4: Adicionar a action**

Depois de `action_view_qualificacao_os`:

```python
    def action_open_generate_os_wizard(self):
        """Abre o wizard de geração de OS por grupo de equipamentos."""
        self.ensure_one()
        if self.state != "sale":
            raise UserError(_(
                "Confirme a cotação antes de gerar OS de Qualificação."
            ))
        if not self.equipamentos_sem_os_ids:
            raise UserError(_(
                "Todos os equipamentos desta cotação já têm OS gerada."
            ))
        return {
            "type": "ir.actions.act_window",
            "name": _("Gerar OS de Qualificação"),
            "res_model": "afr.qualificacao.os.generate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_sale_order_id": self.id},
        }
```

- [ ] **Step 5: Rodar os testes e ver passar**

Tags: `/afr_qualificacao:TestOsPorGrupo`
Esperado: PASS. `test_action_wizard_exige_so_confirmada` e
`test_action_wizard_erra_se_nada_pendente` passam porque os `UserError` são
levantados antes de o modelo do wizard ser resolvido.

- [ ] **Step 6: Rodar a suíte completa**

Tags: `afr_qualificacao`. Esperado: baseline.

- [ ] **Step 7: Commit**

Via `git-commit-push`, staged `models/sale_order.py` e `tests/test_os_por_grupo.py`:

```
feat(sale_order): expose pending equipments and generate-OS action
```

---

### Task 6: Wizard de geração + botão na cotação

**Files:**
- Create: `wizards/qualificacao_os_generate_wizard.py`
- Create: `wizards/qualificacao_os_generate_wizard_views.xml`
- Modify: `wizards/__init__.py`
- Modify: `views/sale_order_views.xml:10-21` (header) e `:51-53` (campo invisível)
- Modify: `security/ir.model.access.csv`
- Modify: `__manifest__.py:198` (data) e `:3` (versão)
- Modify: `models/sale_order.py` (remover `_create_qualificacoes_from_lines`)
- Test: `tests/test_os_por_grupo.py`

**Interfaces:**
- Consumes: `_pending_qualif_lines()`, `_materialize_qualificacoes(lines, os)`,
  `_prepare_qualificacao_os_values(equipments, pending)`, `equipamentos_sem_os_ids`
- Produces: `afr.qualificacao.os.generate.wizard.action_generate() -> dict`

- [ ] **Step 1: Escrever os testes do fluxo N-OS**

Adicione a `TestOsPorGrupo` em `tests/test_os_por_grupo.py`:

```python
    def _so_tres_equipamentos(self):
        return self._build_so([
            {"equipment_id": self.equip1.id, "do_qi": True},
            {"equipment_id": self.equip2.id, "do_qi": True},
            {"equipment_id": self.equip3.id, "do_qi": True},
        ])

    def _gerar(self, so, equipments):
        wiz = self.env["afr.qualificacao.os.generate.wizard"].create({
            "sale_order_id": so.id,
            "equipment_ids": [(6, 0, equipments.ids)],
        })
        action = wiz.action_generate()
        return self.env["afr.qualificacao.os"].browse(action["res_id"])

    def test_dois_cliques_geram_duas_os_disjuntas(self):
        so = self._so_tres_equipamentos()
        so.write({"name": "C26-06-0010"})
        so.action_confirm()
        equips = so.equipamentos_sem_os_ids
        os1 = self._gerar(so, equips[:2])
        self.assertEqual(so.qualificacao_os_count, 1)
        os2 = self._gerar(so, so.equipamentos_sem_os_ids)
        self.assertEqual(so.qualificacao_os_count, 2)
        self.assertEqual(len(os1.equipment_ids), 2)
        self.assertEqual(len(os2.equipment_ids), 1)
        self.assertFalse(os1.equipment_ids & os2.equipment_ids)
        self.assertEqual(os1.name, "OS26-06-0010-1")
        self.assertEqual(os2.name, "OS26-06-0010-2")
        self.assertFalse(so.pode_gerar_os)

    def test_clique_unico_cobrindo_tudo_gera_nome_sem_sufixo(self):
        so = self._so_tres_equipamentos()
        so.write({"name": "C26-06-0011"})
        so.action_confirm()
        os1 = self._gerar(so, so.equipamentos_sem_os_ids)
        self.assertEqual(os1.name, "OS26-06-0011")
        self.assertEqual(len(os1.equipment_ids), 3)

    def test_tres_cliques_geram_sufixos_1_2_3(self):
        so = self._so_tres_equipamentos()
        so.write({"name": "C26-06-0012"})
        so.action_confirm()
        nomes = []
        for _i in range(3):
            nomes.append(self._gerar(so, so.equipamentos_sem_os_ids[:1]).name)
        self.assertEqual(
            nomes,
            ["OS26-06-0012-1", "OS26-06-0012-2", "OS26-06-0012-3"],
        )

    def test_wizard_rejeita_equipamento_ja_gerado(self):
        so = self._so_tres_equipamentos()
        so.action_confirm()
        ja = so.equipamentos_sem_os_ids[:1]
        self._gerar(so, ja)
        with self.assertRaises(UserError):
            self._gerar(so, ja)

    def test_wizard_rejeita_selecao_vazia(self):
        so = self._so_tres_equipamentos()
        so.action_confirm()
        wiz = self.env["afr.qualificacao.os.generate.wizard"].create({
            "sale_order_id": so.id,
        })
        with self.assertRaises(UserError):
            wiz.action_generate()

    def test_wizard_rejeita_so_nao_confirmada(self):
        so = self._so_tres_equipamentos()
        wiz = self.env["afr.qualificacao.os.generate.wizard"].create({
            "sale_order_id": so.id,
            "equipment_ids": [(6, 0, so.equipamentos_sem_os_ids.ids)],
        })
        with self.assertRaises(UserError):
            wiz.action_generate()

    def test_subrecords_ficam_no_grupo_certo(self):
        """Ciclos QD e itens de coleta só do equipamento daquele grupo."""
        so = self._build_so([
            {
                "equipment_id": self.equip1.id,
                "qd_line_ids": [(0, 0, {
                    "cycle_type_id": self.cycle_qd_test.id, "qty": 2,
                })],
            },
            {"equipment_id": self.equip2.id, "do_qi": True},
        ])
        so.action_confirm()
        os1 = self._gerar(so, self.equip1)
        os2 = self._gerar(so, self.equip2)
        self.assertEqual(len(os1.qualificacao_ids.mapped("cycle_ids")), 2)
        self.assertFalse(os2.qualificacao_ids.mapped("cycle_ids"))
        self.assertEqual(os1.equipment_ids, self.equip1)
        self.assertEqual(os2.equipment_ids, self.equip2)
```

Antes de rodar, confirme em `tests/common.py` que existem `self.equip3` e
`self.cycle_qd_test`. Se não existirem, use os nomes reais do `setUpClass`
(há `self.equip1`, `self.equip2` e ciclos de teste) e, se faltar um terceiro
equipamento, crie-o no próprio `_so_tres_equipamentos` com
`self.env["engc.equipment"].create({...})` seguindo o padrão do `setUpClass`.

- [ ] **Step 2: Rodar e ver falhar**

Tags: `/afr_qualificacao:TestOsPorGrupo`
Esperado: FAIL — modelo `afr.qualificacao.os.generate.wizard` não existe.

- [ ] **Step 3: Criar o wizard**

`wizards/qualificacao_os_generate_wizard.py`:

```python
# -*- coding: utf-8 -*-
"""Wizard: gerar OS de Qualificação por grupo de equipamentos.

Uma cotação confirmada pode render N OS — tipicamente uma por visita de campo
(setor, andar, disponibilidade do cliente). Cada execução cria UMA OS com o
subconjunto de equipamentos escolhido; repete-se até não sobrar pendente.

Invariante: um equipamento nunca entra em duas OS da mesma cotação. Garantida
aqui (domínio + revalidação) e no modelo (`afr.qualificacao`
`_check_equipamento_unico_por_os_da_so`).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AfrQualificacaoOsGenerateWizard(models.TransientModel):
    _name = "afr.qualificacao.os.generate.wizard"
    _description = "Wizard: gerar OS de Qualificação por grupo de equipamentos"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Cotação",
        required=True,
        readonly=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    equipamento_disponivel_ids = fields.Many2many(
        "engc.equipment",
        relation="afr_qualif_gen_os_wizard_disp_rel",
        column1="wizard_id",
        column2="equipment_id",
        string="Disponíveis",
        compute="_compute_equipamento_disponivel_ids",
        help="Equipamentos da cotação que ainda não têm OS. Alimenta o domínio.",
    )
    equipment_ids = fields.Many2many(
        "engc.equipment",
        relation="afr_qualif_gen_os_wizard_equip_rel",
        column1="wizard_id",
        column2="equipment_id",
        string="Equipamentos desta OS",
        required=True,
    )

    @api.depends("sale_order_id")
    def _compute_equipamento_disponivel_ids(self):
        for wiz in self:
            wiz.equipamento_disponivel_ids = wiz.sale_order_id.equipamentos_sem_os_ids

    @api.onchange("sale_order_id")
    def _onchange_sale_order_default_equipments(self):
        """Default = todos os pendentes; o usuário desmarca o que não vai agora."""
        if self.sale_order_id:
            self.equipment_ids = [
                (6, 0, self.sale_order_id.equipamentos_sem_os_ids.ids)
            ]

    def action_generate(self):
        self.ensure_one()
        so = self.sale_order_id
        if so.state != "sale":
            raise UserError(_(
                "Confirme a cotação antes de gerar OS de Qualificação."
            ))
        if not self.equipment_ids:
            raise UserError(_("Selecione ao menos um equipamento."))

        # Revalidação no momento da execução: outra aba/sessão pode ter gerado
        # OS para parte da seleção depois que este wizard foi aberto.
        pendentes = so.equipamentos_sem_os_ids
        ja_gerados = self.equipment_ids - pendentes
        if ja_gerados:
            raise UserError(_(
                "Estes equipamentos já têm OS nesta cotação: %s"
            ) % ", ".join(ja_gerados.mapped("display_name")))

        lines = so._pending_qualif_lines().filtered(
            lambda l: l.equipment_id in self.equipment_ids
        )
        if not lines:
            raise UserError(_(
                "Nenhuma linha de qualificação pendente para os equipamentos "
                "selecionados."
            ))

        os = self.env["afr.qualificacao.os"].create(
            so._prepare_qualificacao_os_values(self.equipment_ids, pendentes)
        )
        so._materialize_qualificacoes(lines, os)
        return {
            "type": "ir.actions.act_window",
            "name": os.display_name,
            "res_model": "afr.qualificacao.os",
            "res_id": os.id,
            "view_mode": "form",
            "target": "current",
        }
```

- [ ] **Step 4: Registrar o import**

Em `wizards/__init__.py`, acrescente ao fim:

```python
from . import qualificacao_os_generate_wizard  # 16.0.6.13.0 — OS por grupo
```

- [ ] **Step 5: Criar a view do wizard**

`wizards/qualificacao_os_generate_wizard_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="view_afr_qualificacao_os_generate_wizard_form" model="ir.ui.view">
        <field name="name">afr.qualificacao.os.generate.wizard.form</field>
        <field name="model">afr.qualificacao.os.generate.wizard</field>
        <field name="arch" type="xml">
            <form string="Gerar OS de Qualificação">
                <sheet>
                    <group>
                        <field name="sale_order_id" readonly="1"/>
                        <field name="equipamento_disponivel_ids" invisible="1"/>
                    </group>
                    <separator string="Equipamentos desta OS"/>
                    <p class="text-muted">
                        Marque os equipamentos que serão atendidos nesta OS.
                        Os que ficarem de fora continuam disponíveis para uma
                        próxima OS desta mesma cotação.
                    </p>
                    <field name="equipment_ids" nolabel="1"
                           domain="[('id', 'in', equipamento_disponivel_ids)]"
                           widget="many2many">
                        <tree>
                            <field name="name"/>
                            <field name="category_id"/>
                        </tree>
                    </field>
                </sheet>
                <footer>
                    <button name="action_generate" type="object"
                            string="Gerar OS" class="btn-primary"/>
                    <button special="cancel" string="Cancelar"
                            class="btn-secondary"/>
                </footer>
            </form>
        </field>
    </record>

</odoo>
```

Se `engc.equipment` não tiver o campo `category_id`, remova essa coluna da
`<tree>` (confirme com `grep -n "category_id" models/engc_equipment.py`).

- [ ] **Step 6: ACL do wizard**

Em `security/ir.model.access.csv`, acrescente uma linha ao final, no mesmo
formato das existentes:

```csv
access_qualificacao_os_generate_wizard_user,qualificacao_os_generate_wizard_user,model_afr_qualificacao_os_generate_wizard,afr_qualificacao.group_afr_qualificacao_user,1,1,1,1
```

- [ ] **Step 7: Registrar a view no manifest**

Em `__manifest__.py`, depois de `"wizards/apply_procedimento_wizard_views.xml",`:

```python
        "wizards/qualificacao_os_generate_wizard_views.xml",
```

- [ ] **Step 8: Botão na cotação**

Em `views/sale_order_views.xml`, dentro do primeiro `<xpath>` (o que insere
antes de `action_quotation_send`), depois do botão `action_apply_all_equipment_targets`:

```xml
                <button name="action_open_generate_os_wizard"
                        string="Gerar OS de Qualificação"
                        type="object"
                        class="oe_highlight"
                        attrs="{'invisible': [('pode_gerar_os','=',False)]}"/>
```

E no xpath que já injeta `has_qualif_lines` (depois de `//field[@name='order_line']`),
acrescente o campo invisível de que o `attrs` depende:

```xml
                <field name="pode_gerar_os" invisible="1"/>
```

- [ ] **Step 9: Remover `_create_qualificacoes_from_lines`**

Em `models/sale_order.py`, apague o método `_create_qualificacoes_from_lines`
inteiro — não tem mais chamador (a Task 4 removeu o do `action_confirm`; o wizard
usa `_materialize_qualificacoes` direto). Confirme com:

```bash
grep -rn "_create_qualificacoes_from_lines" /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
```

Esperado: nenhum hit fora de comentários/docs. Se houver hit em código, o método fica.

- [ ] **Step 10: Rodar os testes do grupo e ver passar**

Tags: `/afr_qualificacao:TestOsPorGrupo`
Esperado: PASS em todos.

- [ ] **Step 11: Rodar a suíte completa**

Tags: `afr_qualificacao`. Esperado: baseline, nenhuma falha nova.

- [ ] **Step 12: Commit**

Via `git-commit-push`, staged os arquivos do wizard, views, security, manifest,
`models/sale_order.py` e `tests/test_os_por_grupo.py`:

```
feat(qualificacao): generate one OS per equipment group from a quotation
```

---

### Task 7: Bump de versão e validação na UI

**Files:**
- Modify: `__manifest__.py:3`

- [ ] **Step 1: Bump da versão**

Em `__manifest__.py`, `"version": "16.0.6.12.0"` → `"version": "16.0.6.13.0"`.

- [ ] **Step 2: Atualizar o módulo no ambiente de desenvolvimento**

Descubra o nome do banco de desenvolvimento (o que responde em
`http://localhost:8083`):

```bash
docker exec odoo_engenapp-db-1 psql -U odoo -l | grep -v test
```

Depois atualize o módulo nesse banco:

```bash
docker exec odoo_engenapp-web-1 odoo -d <DB_DEV> -u afr_qualificacao \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 \
  --db_host=db --db_user=odoo --db_password=odoo 2>&1 | tail -20
```

Depois reinicie o container para recarregar assets:
`docker restart odoo_engenapp-web-1`

- [ ] **Step 3: Validar o fluxo na UI via `agent-browser`**

Regra do projeto: testar a interface antes de declarar pronto, não delegar o
clique ao usuário.

1. `agent-browser open http://localhost:8083` e faça login (logout antes de
   re-login, para evitar bounce de sessão stale).
2. Abra uma cotação de qualificação com 3+ equipamentos (ou monte uma pelo
   configurador).
3. Confirme a cotação. Verifique: **nenhuma** OS é criada e o botão
   **Gerar OS de Qualificação** aparece no header.
4. Clique no botão. O wizard abre com todos os equipamentos pré-marcados.
   Desmarque um e gere. Verifique que abre a OS criada e que o nome tem
   sufixo `-1`.
5. Volte à cotação. O botão continua visível. Gere a segunda OS — nome `-2`,
   com só o equipamento restante.
6. O botão some. O stat button "OS Qualif" mostra 2 e abre a lista.
7. Tire screenshot de cada passo relevante com `agent-browser`.

Se o wizard não abrir ou o botão não aparecer, investigue antes de commitar —
causa mais provável: campo `pode_gerar_os` faltando na arch ou XML do wizard
não registrado no manifest.

- [ ] **Step 4: Rodar a suíte completa uma última vez**

Tags: `afr_qualificacao`. Esperado: baseline.

- [ ] **Step 5: Commit e push do submodule**

Via `git-commit-push`, `cwd` em `addons/afr_qualificacao`, staged `__manifest__.py`:

```
chore: bump afr_qualificacao to 16.0.6.13.0
```

Depois `git push origin main` **de dentro do submodule** — obrigatório antes do
pointer.

- [ ] **Step 6: Bump do pointer no monorepo**

Via `git-commit-push`, `cwd` em `/home/afonso/docker/odoo_engenapp`, staged
`addons/afr_qualificacao`:

```
chore: bump submodule afr_qualificacao (OS por grupo de equipamentos, v16.0.6.13.0)
```
