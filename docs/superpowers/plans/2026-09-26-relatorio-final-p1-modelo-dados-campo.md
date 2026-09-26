# Relatório Final — P1: Modelo do relatório + dados de campo + ciclos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar o modelo `afr.qualificacao.relatorio` (um por OS × equipamento) com os dados de campo (checklist, indicadores, leituras de IB), a extensão dos ciclos (janela, posição de sensores, `extracted_json`), a geração idempotente a partir da OS e as telas (form com abas *Dados de campo* e *Ciclos*, smart button na OS, menu).

**Architecture:** Arquivos novos em `models/` com `_inherit` para estender OS e ciclo, sem editar `qualificacao_os.py` nem `qualificacao_cycle.py`. `relatorio.py` guarda o modelo principal; `relatorio_dados_campo.py` guarda os três filhos de dados de campo; `relatorio_cycle.py` guarda a extensão do ciclo + `afr.relatorio.sensor.pos`; `relatorio_os.py` guarda a extensão da OS. As views ficam em `views/relatorio_views.xml` (relatório + herança do form da OS + menu) e `views/relatorio_cycle_views.xml` (herança do form do ciclo). O form do relatório expõe `<header>` só com statusbar e `<notebook>` com `page_dados_campo`/`page_ciclos`, que P2–P5 estendem por xpath.

**Tech Stack:** Odoo 16.0, Python 3.9 (container), `dateutil.relativedelta`, testes `odoo.tests.common.TransactionCase` via `tests/common.py::AfrQualificacaoTestCommon`.

**Spec:** `docs/superpowers/specs/2026-09-26-relatorio-final-qualificacao-design.md` (§4.1, §4.2, §4.3, §9 parcial). **Índice + contrato:** `docs/superpowers/plans/2026-09-26-relatorio-final-00-indice.md`. Os nomes da seção "P1 produz" são obrigatórios.

## Global Constraints

- Odoo **16.0**. `afr_qualificacao` é **git submodule** em `addons/afr_qualificacao/`. Trabalhar na branch `feat/relatorio-final` criada **dentro do submodule** a partir de `main` (Task 1, Step 0).
- Commits: sempre de dentro de `addons/afr_qualificacao/`, via agente `git-commit-push` (haiku), com paths relativos ao submodule. **Não** fazer push nem bump do pointer no monorepo sem o usuário pedir. Mensagens em inglês, Conventional Commits. **Não** incluir no commit arquivos alheios que já estão sujos no submodule (`.gitignore`, `pwa/README.md`, `pwa/package.json`, `.superpowers/`, planos de `pwa/docs/`).
- Testes (comando base do índice, **verbatim**):
  `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init --no-http`
  (`-u` obrigatório quando tocar XML; `--no-http` obrigatório). **Fallback:** em 2026-09-26 o container de pé era `odoo_engenapp-web-qualificacao-1`, não `odoo_engenapp-web-1`. Conferir com `docker ps --format '{{.Names}}'` e trocar só o nome do container. Se o banco `odoo_ecm_test` não existir nesse container, **parar e perguntar**; não inventar nome de banco.
  Falhas pré-existentes conhecidas (ignorar): `TestResourcePlan.test_fleet_single_logger_two_temp_standards`, `TestProposalReport.test_render_equipment_scope_omits_cronograma_footer`, `TestProposalReport.test_render_schedule_block`.
- Novos testes herdam de `tests/common.py::AfrQualificacaoTestCommon`; registrar o arquivo novo em `tests/__init__.py`.
- Todo model novo: entrada em `models/__init__.py` e ACL em `security/ir.model.access.csv`. No modelo principal: technician read; user read/write/create; manager full. **Exceção justificada:** nas linhas-filhas (`afr.relatorio.checklist`, `afr.relatorio.indicador`, `afr.relatorio.leitura.ib`, `afr.relatorio.sensor.pos`) o grupo `user` recebe **unlink**. Sem isso o Usuário não remove linha no O2M inline, e "copiar do ciclo anterior" (que troca as linhas) dá `AccessError`. Há precedente em `access_qualificacao_collect_item_user` (`1,1,1,1`).
- **Sem `ir.rule` de leitura.** Todas as regras do técnico em `security/qualificacao_groups.xml` são só de escrita (`perm_read=False`), então o técnico já lê todas as OSs. O espelho fiel é a ACL read-only do técnico, sem regra nova. O revisor **não** deve "corrigir" isso adicionando regra.
- Grupos: `afr_qualificacao.group_afr_qualificacao_technician`, `..._user`, `..._manager` (user implica technician; manager implica user).
- **Nunca** usar nomes reais de clientes, pessoas ou certificados de `dados_sensiveis/`. Usar "Cliente Teste", "Eng. Responsável".
- `engc_os` está **congelado**: nada em `engenapp/engc_os/`.
- PWA (`pwa/`) **não muda**.
- Manifest ao final do P1: `"version": "16.0.8.0.0"`. **P1 não cria dado seed**, portanto **não** cria `migrations/16.0.8.0.0/`. Não criar pasta vazia.
- Textos de UI em pt-BR. Docstrings e comentários em pt-BR, com a densidade dos arquivos vizinhos (`models/qualificacao_os.py`).

## Review Focus

1. **Equipamento entra na OS depois da geração.** A próxima "Gerar relatórios" cria só o relatório faltante, com `index = max + 1`, e os índices (e portanto os números `ReQT-…`) existentes não mudam. Teste: Task 1, `test_generate_new_equipment_gets_next_index`.
2. **Qualificação adicionada ou movida de OS depois da geração.** `qualificacao_ids` (stored) e `cycle_ids` refletem a mudança sem regerar. Teste: Task 1, `test_qualificacao_ids_recompute_on_late_qualif`.
3. **Leitura de IB apontando para ciclo de outro equipamento ou indicador de outro relatório.** Deve ser rejeitada com `ValidationError`; o domain da view não basta (import/RPC passam por fora). Teste: Task 2, `test_leitura_ib_rejects_foreign_cycle` e `test_leitura_ib_rejects_foreign_indicador`.
4. **Janela de esterilização invertida** (`janela_fim < janela_inicio`). Deve dar `ValidationError`. Teste: Task 3, `test_janela_fim_before_inicio_rejected`.
5. **Usuário (não Gestor) copiando posições de sensor sobre linhas já existentes.** Deve funcionar e substituir as linhas, não somar nem dar `AccessError`. Técnico só lê relatórios e não cria. Testes: Task 3, `test_copy_sensor_pos_as_usuario_replaces`, e Task 1, `test_technician_reads_but_cannot_create`.

Fora de teste, mas documentado no código: um equipamento que **sai** da OS depois da geração **não** tem o relatório apagado. O relatório fica e o escritório decide.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `models/relatorio.py` | Create | `afr.qualificacao.relatorio` (campos P1, nome, `_doc_number`, índice automático, `proxima_qualificacao`, `_seed_checklist`) |
| `models/relatorio_os.py` | Create | `_inherit afr.qualificacao.os`: `relatorio_final_ids`, `relatorio_final_count`, `action_generate_relatorios`, wrappers de UI |
| `models/relatorio_dados_campo.py` | Create | `afr.relatorio.checklist`, `afr.relatorio.indicador`, `afr.relatorio.leitura.ib` |
| `models/relatorio_cycle.py` | Create | `_inherit afr.qualificacao.cycle` + `afr.relatorio.sensor.pos` + `action_copy_sensor_pos_from_previous` |
| `models/__init__.py` | Modify | imports novos no fim |
| `security/ir.model.access.csv` | Modify | ACLs dos 5 models novos |
| `views/relatorio_views.xml` | Create | form/tree/search/action do relatório, herança do form da OS, menu |
| `views/relatorio_cycle_views.xml` | Create | herança do form do ciclo (janela, sensores, arquivos, botão copiar) |
| `__manifest__.py` | Modify | versão 16.0.8.0.0 + 2 views no `data` |
| `tests/test_relatorio_model.py` | Create | `TestRelatorioModel` |
| `tests/__init__.py` | Modify | registra o arquivo de teste |

### Nomes adicionados fora do contrato (P2–P5 podem usar; não renomear)

- `afr.qualificacao.os._relatorio_final_equipments()` retorna recordset `engc.equipment` na ordem canônica `(name, id)`.
- `afr.qualificacao.os._relatorio_final_default_dates()` retorna `(date|False, date|False)`.
- `afr.qualificacao.os.action_generate_relatorios_open()` retorna `dict` act_window. É o wrapper do botão, porque o contrato manda `action_generate_relatorios()` retornar recordset, e recordset não serializa para o web client.
- `afr.qualificacao.os.action_view_relatorios_finais()` retorna `dict` act_window (smart button).
- `afr.qualificacao.relatorio.os_collect_item_ids`: M2M computado, os itens de coleta das `qualificacao_ids` (coluna lateral de consulta).
- `afr.qualificacao.cycle.sensor_pos_count` (Integer compute), `afr.qualificacao.cycle.action_open_relatorio_cycle()` retorna `dict` e `afr.qualificacao.cycle._previous_cycle_with_sensor_pos()` retorna record (0 ou 1).
- XML ids: `afr_qualificacao.view_afr_qualificacao_relatorio_form`, `..._tree`, `..._search`, `afr_qualificacao.action_afr_qualificacao_relatorio`, `afr_qualificacao.view_afr_qualificacao_os_form_relatorio_final`, `afr_qualificacao.view_afr_qualificacao_cycle_form_relatorio_final`, `afr_qualificacao.menu_afr_relatorio_final`.

---

### Task 1: Modelo `afr.qualificacao.relatorio` + geração a partir da OS

**Files:**
- Create: `models/relatorio.py`
- Create: `models/relatorio_os.py`
- Modify: `models/__init__.py` (append no fim)
- Modify: `security/ir.model.access.csv` (append no fim)
- Create: `tests/test_relatorio_model.py`
- Modify: `tests/__init__.py` (append no fim)

**Interfaces:**
- Consumes: `afr.qualificacao.os` (`name`, `company_id`, `partner_id`, `equipment_ids`, `qualificacao_ids`, `date_actual_start/end`, `date_planned_start/end`), `afr.qualificacao` (`os_id`, `equipment_id`, `cycle_ids`).
- Produces:
  - Model `afr.qualificacao.relatorio` com os campos `name, index, os_id, equipment_id, partner_id, company_id, qualificacao_ids, cycle_ids, state, revision, revision_label, data_inicio_ensaios, data_fim_ensaios, amb_temperatura, amb_umidade, tolerancia_acima, criterio_f0_fator, proxima_qualificacao`. `checklist_ids/indicador_ids/leitura_ib_ids` entram na Task 2.
  - `relatorio._doc_number(prefix: str) -> str`.
  - `os.action_generate_relatorios() -> afr.qualificacao.relatorio recordset`, `os.relatorio_final_ids` (O2M), `os.relatorio_final_count` (Integer).
  - `os._relatorio_final_equipments() -> engc.equipment recordset`, `os._relatorio_final_default_dates() -> tuple`.

- [ ] **Step 0: Criar a branch dentro do submodule**

```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git checkout main
git checkout -b feat/relatorio-final
```

Expected: `Switched to a new branch 'feat/relatorio-final'`. Os arquivos sujos alheios (`.gitignore`, `pwa/…`) vêm junto e não devem ser tocados.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_relatorio_model.py`:

```python
# -*- coding: utf-8 -*-
"""Testes do Relatório Final de Qualificação — P1 (16.0.8.0.0).

Cobre: geração a partir da OS (um por equipamento, índice estável,
idempotência), unicidade (OS, equipamento), agregação de qualificações e
ciclos do mesmo equipamento, numeração ReQT/PrQT/ReQM, rótulo de revisão,
próxima qualificação e ACL do técnico.
"""
from datetime import date, datetime

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "relatorio_final", "post_install", "-at_install")
class TestRelatorioModel(AfrQualificacaoTestCommon):
    """Fixture: 1 OS com equip1 (QI + QO c/ 1 ciclo + QD c/ 3 ciclos) e
    equip2 (QI + QD c/ 1 ciclo). Qualificações criadas direto com `os_id`
    (sem SO), no mesmo padrão de `test_os_workflow._attach_dummy_qualif`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Relatorio = cls.env["afr.qualificacao.relatorio"]
        cls.Cycle = cls.env["afr.qualificacao.cycle"]
        cls.tecnico = cls.env["hr.employee"].create({"name": "Técnico Relatório"})
        cls.os = cls._make_os()

        cls.q1_qi = cls._make_qualif(cls.os, cls.equip1, "installation")
        cls.q1_qo = cls._make_qualif(cls.os, cls.equip1, "operational")
        cls.q1_qd = cls._make_qualif(cls.os, cls.equip1, "performance")
        cls.q2_qi = cls._make_qualif(cls.os, cls.equip2, "installation")
        cls.q2_qd = cls._make_qualif(cls.os, cls.equip2, "performance")

        cls.cycle_qo = cls._make_cycle(cls.q1_qo, cls.cycle_qo_test, 10)
        cls.cycle_qd1 = cls._make_cycle(cls.q1_qd, cls.cycle_cmax, 10)
        cls.cycle_qd2 = cls._make_cycle(cls.q1_qd, cls.cycle_cmax, 20)
        cls.cycle_qd3 = cls._make_cycle(cls.q1_qd, cls.cycle_cmax, 30)
        cls.cycle_other = cls._make_cycle(cls.q2_qd, cls.cycle_cmax, 10)

    # ─────────────────────────────────────────────────────────────
    # Helpers de fixture
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def _make_os(cls):
        return cls.env["afr.qualificacao.os"].create({
            "tecnico_default_id": cls.tecnico.id,
            "date_planned_start": datetime(2026, 9, 1, 12, 0),
            "date_planned_end": datetime(2026, 9, 3, 18, 0),
        })

    @classmethod
    def _make_qualif(cls, os, equip, qtype):
        return cls.env["afr.qualificacao"].create({
            "name": "RF-%s-%s-%s" % (os.id, equip.serial_number, qtype),
            "equipment_id": equip.id,
            "qualification_type": qtype,
            "os_id": os.id,
            "company_id": os.company_id.id,
        })

    @classmethod
    def _make_cycle(cls, qualif, cycle_type, sequence):
        return cls.Cycle.create({
            "qualificacao_id": qualif.id,
            "cycle_type_id": cycle_type.id,
            "sequence": sequence,
        })

    def _make_equip(self, serial):
        return self.env["engc.equipment"].create({
            "client_id": self.partner.id,
            "category_id": self.category.id,
            "model": "TestModel-%s" % serial, "serial_number": serial,
            "means_of_aquisition_id": self.means.id,
            "location_id": self.location.id,
            "marca_id": self.marca.id,
        })

    @staticmethod
    def _canonical(equipments):
        """Mesma chave de ordenação de `_relatorio_final_equipments()`."""
        return sorted(equipments, key=lambda e: (e.name or "", e.id))

    def _rel_for(self, os, equip):
        return os.relatorio_final_ids.filtered(lambda r: r.equipment_id == equip)

    # ─────────────────────────────────────────────────────────────
    # GERAÇÃO
    # ─────────────────────────────────────────────────────────────
    def test_generate_one_per_equipment_in_index_order(self):
        rels = self.os.action_generate_relatorios()
        self.assertEqual(len(rels), 2)
        self.assertEqual(self.os.relatorio_final_count, 2)
        expected = self._canonical(self.os.equipment_ids)
        for position, equip in enumerate(expected, start=1):
            rel = self._rel_for(self.os, equip)
            self.assertEqual(len(rel), 1)
            self.assertEqual(rel.index, position)
            self.assertEqual(rel.name, "ReQT-%s-%d" % (self.os.name, position))
            self.assertEqual(rel.state, "draft")
            self.assertEqual(rel.partner_id, self.os.partner_id)
            self.assertEqual(rel.company_id, self.os.company_id)

    def test_generate_is_idempotent(self):
        first = self.os.action_generate_relatorios()
        second = self.os.action_generate_relatorios()
        self.assertEqual(first, second)
        self.assertEqual(
            self.Relatorio.search_count([("os_id", "=", self.os.id)]), 2
        )

    def test_generate_new_equipment_gets_next_index(self):
        """Review Focus 1: equipamento que entra depois não renumera os
        relatórios existentes."""
        self.os.action_generate_relatorios()
        before = {r.equipment_id.id: (r.index, r.name) for r in self.os.relatorio_final_ids}
        equip3 = self._make_equip("TSN-000")
        self._make_qualif(self.os, equip3, "installation")
        self.os.action_generate_relatorios()
        self.assertEqual(len(self.os.relatorio_final_ids), 3)
        for rel in self.os.relatorio_final_ids - self._rel_for(self.os, equip3):
            self.assertEqual((rel.index, rel.name), before[rel.equipment_id.id])
        self.assertEqual(self._rel_for(self.os, equip3).index, 3)

    def test_generate_os_without_qualifs_creates_nothing(self):
        empty_os = self._make_os()
        rels = empty_os.action_generate_relatorios()
        self.assertFalse(rels)
        self.assertEqual(empty_os.relatorio_final_count, 0)

    def test_generate_sets_default_test_dates_from_os(self):
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        # Sem relatório diário, cai no planejado (12:00/18:00 UTC não troca de
        # dia em nenhum fuso do Brasil).
        self.assertEqual(rel.data_inicio_ensaios, date(2026, 9, 1))
        self.assertEqual(rel.data_fim_ensaios, date(2026, 9, 3))

    def test_create_without_index_takes_next(self):
        """Criação direta sem `index`, em lote com 2 equipamentos da mesma OS:
        pega max+1 sequencial, sem repetir índice dentro do lote."""
        self.os.action_generate_relatorios()
        eq_a = self._make_equip("TSN-A01")
        eq_b = self._make_equip("TSN-B01")
        for eq in (eq_a, eq_b):
            self._make_qualif(self.os, eq, "installation")
        new = self.Relatorio.create([
            {"os_id": self.os.id, "equipment_id": eq_a.id},
            {"os_id": self.os.id, "equipment_id": eq_b.id},
        ])
        self.assertEqual(new.mapped("index"), [3, 4])

    # ─────────────────────────────────────────────────────────────
    # CONSTRAINTS
    # ─────────────────────────────────────────────────────────────
    def test_unique_os_equipment(self):
        self.os.action_generate_relatorios()
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.Relatorio.create({
                    "os_id": self.os.id,
                    "equipment_id": self.equip1.id,
                    "index": 99,
                })

    def test_equipment_must_belong_to_os(self):
        other_os = self._make_os()
        self._make_qualif(other_os, self.equip2, "installation")
        with self.assertRaises(ValidationError):
            self.Relatorio.create({
                "os_id": other_os.id, "equipment_id": self.equip1.id,
            })

    # ─────────────────────────────────────────────────────────────
    # AGREGAÇÃO
    # ─────────────────────────────────────────────────────────────
    def test_qualificacao_and_cycle_ids_same_equipment_only(self):
        self.os.action_generate_relatorios()
        rel1 = self._rel_for(self.os, self.equip1)
        rel2 = self._rel_for(self.os, self.equip2)
        self.assertEqual(
            set(rel1.qualificacao_ids.ids),
            {self.q1_qi.id, self.q1_qo.id, self.q1_qd.id},
        )
        self.assertEqual(
            set(rel1.cycle_ids.ids),
            {self.cycle_qo.id, self.cycle_qd1.id, self.cycle_qd2.id, self.cycle_qd3.id},
        )
        self.assertEqual(set(rel2.qualificacao_ids.ids), {self.q2_qi.id, self.q2_qd.id})
        self.assertEqual(rel2.cycle_ids, self.cycle_other)

    def test_qualificacao_ids_excludes_cancelled(self):
        """Qualificação cancelada sai do relatório (e seus ciclos também)."""
        self.os.action_generate_relatorios()
        rel1 = self._rel_for(self.os, self.equip1)
        self.assertIn(self.q1_qo, rel1.qualificacao_ids)
        # env de teste é superusuário: o guard manager-only não se aplica.
        self.q1_qo.write({"state": "cancelled"})
        self.assertNotIn(self.q1_qo, rel1.qualificacao_ids)
        self.assertNotIn(self.cycle_qo, rel1.cycle_ids)
        self.assertEqual(
            set(rel1.qualificacao_ids.ids), {self.q1_qi.id, self.q1_qd.id}
        )

    def test_qualificacao_ids_exclude_other_os(self):
        other_os = self._make_os()
        q_elsewhere = self._make_qualif(other_os, self.equip1, "installation")
        self.os.action_generate_relatorios()
        rel1 = self._rel_for(self.os, self.equip1)
        self.assertNotIn(q_elsewhere, rel1.qualificacao_ids)

    def test_qualificacao_ids_recompute_on_late_qualif(self):
        """Review Focus 2: qualificação que entra (ou sai) da OS depois da
        geração reflete no stored compute sem regerar."""
        self.os.action_generate_relatorios()
        rel1 = self._rel_for(self.os, self.equip1)
        q_late = self._make_qualif(self.os, self.equip1, "software")
        cycle_late = self._make_cycle(self.q1_qd, self.cycle_cmin, 10)
        self.assertIn(q_late, rel1.qualificacao_ids)
        self.assertIn(cycle_late, rel1.cycle_ids)
        other_os = self._make_os()
        q_late.os_id = other_os
        self.assertNotIn(q_late, rel1.qualificacao_ids)

    # ─────────────────────────────────────────────────────────────
    # NUMERAÇÃO / REVISÃO / PRÓXIMA
    # ─────────────────────────────────────────────────────────────
    def test_doc_number_prefixes(self):
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        suffix = "%s-%d" % (self.os.name, rel.index)
        self.assertEqual(rel._doc_number("ReQT"), "ReQT-" + suffix)
        self.assertEqual(rel._doc_number("PrQT"), "PrQT-" + suffix)
        self.assertEqual(rel._doc_number("ReQM"), "ReQM-" + suffix)
        self.assertEqual(rel.name, rel._doc_number("ReQT"))

    def test_revision_label(self):
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        self.assertEqual(rel.revision, 0)
        self.assertEqual(rel.revision_label, "Rev.00")
        rel.revision = 3
        self.assertEqual(rel.revision_label, "Rev.03")
        rel.revision = 12
        self.assertEqual(rel.revision_label, "Rev.12")

    def test_proxima_qualificacao(self):
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        rel.data_fim_ensaios = date(2026, 9, 3)
        self.assertEqual(rel.proxima_qualificacao, date(2027, 9, 3))
        rel.data_fim_ensaios = date(2028, 2, 29)
        self.assertEqual(rel.proxima_qualificacao, date(2029, 2, 28))
        rel.data_fim_ensaios = False
        self.assertFalse(rel.proxima_qualificacao)

    def test_criterio_defaults(self):
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        self.assertEqual(rel.tolerancia_acima, 3.0)
        self.assertEqual(rel.criterio_f0_fator, 12.0)

    # ─────────────────────────────────────────────────────────────
    # ACL
    # ─────────────────────────────────────────────────────────────
    def test_technician_reads_but_cannot_create(self):
        """Review Focus 5: técnico só lê (ACL read-only, sem ir.rule de
        leitura — espelha as regras existentes, que só restringem escrita)."""
        self.os.action_generate_relatorios()
        tech_user = self.env["res.users"].create({
            "name": "Técnico ACL Relatório",
            "login": "tecnico.acl.relatorio.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("afr_qualificacao.group_afr_qualificacao_technician").id,
            ])],
        })
        rel = self._rel_for(self.os, self.equip1)
        data = rel.with_user(tech_user).read(["name", "state"])
        self.assertEqual(data[0]["name"], rel.name)
        with self.assertRaises(AccessError):
            self.Relatorio.with_user(tech_user).create({
                "os_id": self.os.id, "equipment_id": self.equip2.id, "index": 50,
            })
```

Anexar em `tests/__init__.py` (no fim):

```python

# Relatório Final de Qualificação — P1 (16.0.8.0.0): modelo + dados de campo + ciclos
from . import test_relatorio_model
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioModel --stop-after-init --no-http` (ver fallback de container nas Global Constraints)
Expected: FAIL/ERROR em `setUpClass` ou nos testes com `KeyError: 'afr.qualificacao.relatorio'` (o model ainda não existe).

- [ ] **Step 3: Implementar o model**

Criar `models/relatorio.py`:

```python
# -*- coding: utf-8 -*-
"""Relatório Final de Qualificação Térmica (afr.qualificacao.relatorio).

Um registro por (OS, equipamento). Agrega as qualificações QI/QO/QD daquele
equipamento na OS e guarda os dados de campo que o escritório digita no
backend: datas dos ensaios, ambiente, critérios, checklist, indicadores e
leituras de IB.

P1 (16.0.8.0.0): modelo + dados de campo + ciclos. Os planos seguintes
estendem por herança: certificados (P2), template/blocos/anexos (P3),
montagem/emissão (P4) e varredura (P5).
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AfrQualificacaoRelatorio(models.Model):
    _name = "afr.qualificacao.relatorio"
    _description = "Relatório Final de Qualificação"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "os_id desc, index, id"

    _sql_constraints = [
        (
            "os_equipment_uniq",
            "unique(os_id, equipment_id)",
            "Já existe um relatório final para este equipamento nesta OS.",
        ),
    ]

    STATE_SELECTION = [
        ("draft", "Rascunho"),
        ("issued", "Emitido"),
        ("client_approved", "Aprovado pelo cliente"),
    ]

    # ───────── Identificação ─────────
    name = fields.Char(
        string="Número",
        compute="_compute_name",
        store=True,
        readonly=True,
        copy=False,
        help="ReQT-<OS>-<posição do equipamento na OS>.",
    )
    index = fields.Integer(
        string="Posição na OS",
        readonly=True,
        copy=False,
        help=(
            "Posição do equipamento na OS (1..n). Atribuída na criação e "
            "nunca renumerada: é ela que fixa o número do relatório."
        ),
    )
    os_id = fields.Many2one(
        "afr.qualificacao.os",
        string="OS de Qualificação",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    equipment_id = fields.Many2one(
        "engc.equipment",
        string="Equipamento",
        required=True,
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        related="os_id.partner_id",
        store=True,
        string="Cliente",
    )
    company_id = fields.Many2one(
        related="os_id.company_id",
        store=True,
        string="Empresa",
    )

    # ───────── Escopo agregado ─────────
    qualificacao_ids = fields.Many2many(
        "afr.qualificacao",
        relation="afr_relatorio_final_qualificacao_rel",
        column1="relatorio_id",
        column2="qualificacao_id",
        compute="_compute_qualificacao_ids",
        store=True,
        string="Qualificações",
        help="Qualificações da OS (QI/QO/QD…) do mesmo equipamento, exceto canceladas.",
    )
    cycle_ids = fields.Many2many(
        "afr.qualificacao.cycle",
        compute="_compute_cycle_ids",
        string="Ciclos",
    )

    # ───────── Estado e revisão ─────────
    state = fields.Selection(
        STATE_SELECTION,
        string="Status",
        default="draft",
        required=True,
        copy=False,
        tracking=True,
    )
    revision = fields.Integer(
        string="Revisão",
        default=0,
        copy=False,
        readonly=True,
        tracking=True,
    )
    revision_label = fields.Char(
        string="Rev.",
        compute="_compute_revision_label",
    )

    # ───────── Dados de campo ─────────
    data_inicio_ensaios = fields.Date(string="Início dos ensaios", tracking=True)
    data_fim_ensaios = fields.Date(string="Fim dos ensaios", tracking=True)
    amb_temperatura = fields.Char(
        string="Temperatura ambiente",
        help='Texto livre, ex.: "22 a 25 °C".',
    )
    amb_umidade = fields.Char(
        string="Umidade relativa",
        help='Texto livre, ex.: "41 %UR".',
    )
    tolerancia_acima = fields.Float(
        string="Tolerância acima da nominal (°C)",
        default=3.0,
    )
    criterio_f0_fator = fields.Float(
        string="Fator do critério F0 (× D)",
        default=12.0,
        help="12 = SAL 10⁻⁶ (sobre-morte); 7 = líquidos.",
    )
    proxima_qualificacao = fields.Date(
        string="Próxima qualificação",
        compute="_compute_proxima_qualificacao",
        store=True,
        help=(
            "P1: fim dos ensaios + 12 meses. P4 acrescenta current_emissao_id "
            "ao depends e recomputa (spec §4.1: emissão + 12 meses)."
        ),
    )

    # ═════════════════════════════════════════════════════════════
    # CREATE — índice automático
    # ═════════════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        """Atribui `index = max + 1` por OS quando não vier no vals.

        O contador por OS é mantido em memória durante o lote, para que um
        `create([...])` com vários equipamentos da mesma OS não repita índice.
        sudo() na busca: o índice é da OS inteira, não do que o usuário enxerga.
        """
        next_by_os = {}
        for vals in vals_list:
            os_id = vals.get("os_id")
            if vals.get("index") or not os_id:
                continue
            if os_id not in next_by_os:
                last = self.sudo().search(
                    [("os_id", "=", os_id)], order="index desc", limit=1
                )
                next_by_os[os_id] = (last.index or 0) + 1
            vals["index"] = next_by_os[os_id]
            next_by_os[os_id] += 1
        return super().create(vals_list)

    # ═════════════════════════════════════════════════════════════
    # COMPUTES
    # ═════════════════════════════════════════════════════════════
    @api.depends("os_id.name", "index")
    def _compute_name(self):
        for rel in self:
            rel.name = rel._doc_number("ReQT") if rel.os_id else _("Novo")

    @api.depends(
        "os_id.qualificacao_ids.equipment_id",
        "os_id.qualificacao_ids.state",
        "equipment_id",
    )
    def _compute_qualificacao_ids(self):
        """Qualificações da OS do mesmo equipamento, exceto as canceladas."""
        for rel in self:
            rel.qualificacao_ids = rel.os_id.qualificacao_ids.filtered(
                lambda q: q.equipment_id == rel.equipment_id
                and q.state != "cancelled"
            )

    @api.depends("qualificacao_ids.cycle_ids")
    def _compute_cycle_ids(self):
        for rel in self:
            rel.cycle_ids = rel.qualificacao_ids.cycle_ids

    @api.depends("revision")
    def _compute_revision_label(self):
        for rel in self:
            rel.revision_label = "Rev.%02d" % (rel.revision or 0)

    @api.depends("data_fim_ensaios")
    def _compute_proxima_qualificacao(self):
        for rel in self:
            rel.proxima_qualificacao = (
                rel.data_fim_ensaios + relativedelta(months=12)
                if rel.data_fim_ensaios
                else False
            )

    # ═════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ═════════════════════════════════════════════════════════════
    @api.constrains("os_id", "equipment_id")
    def _check_equipment_in_os(self):
        """O equipamento precisa ter ao menos uma qualificação na OS.

        Só roda na criação/troca de OS ou equipamento. Se o equipamento
        sair da OS depois, o relatório não é apagado (decisão do escritório).
        """
        for rel in self:
            if rel.equipment_id not in rel.os_id.sudo().equipment_ids:
                raise ValidationError(_(
                    "O equipamento '%s' não tem qualificação na OS '%s'."
                ) % (rel.equipment_id.display_name, rel.os_id.display_name))

    # ═════════════════════════════════════════════════════════════
    # HELPERS
    # ═════════════════════════════════════════════════════════════
    def _doc_number(self, prefix):
        """Número de documento derivado da OS: `<prefix>-<OS>-<index>`.

        prefix ∈ {"ReQT" (relatório), "PrQT" (protocolo), "ReQM" (laudo micro)}.
        """
        self.ensure_one()
        return "%s-%s-%d" % (prefix, self.os_id.name, self.index or 0)
```

Criar `models/relatorio_os.py`:

```python
# -*- coding: utf-8 -*-
"""Extensão da OS de Qualificação para o Relatório Final (P1, 16.0.8.0.0).

Mantida fora de `qualificacao_os.py` de propósito: o relatório final é um
subsistema próprio e evolui em P2–P5 sem tocar o arquivo da OS.
"""
from odoo import _, api, fields, models


class AfrQualificacaoOsRelatorioFinal(models.Model):
    _inherit = "afr.qualificacao.os"

    relatorio_final_ids = fields.One2many(
        "afr.qualificacao.relatorio",
        "os_id",
        string="Relatórios finais",
    )
    relatorio_final_count = fields.Integer(
        string="Relatórios finais",
        compute="_compute_relatorio_final_count",
    )

    @api.depends("relatorio_final_ids")
    def _compute_relatorio_final_count(self):
        for os in self:
            os.relatorio_final_count = len(os.relatorio_final_ids)

    def _relatorio_final_equipments(self):
        """Equipamentos da OS na ordem canônica `(name, id)`.

        `equipment_ids` é M2M computado stored: o valor em cache segue a
        ordem das qualificações (`planned_date desc, name`), e uma leitura
        fresca do banco segue `engc.equipment._order`. Ordenar aqui deixa o
        índice independente do estado do cache.
        """
        self.ensure_one()
        return self.sudo().equipment_ids.sorted(
            key=lambda e: (e.name or "", e.id)
        ).with_env(self.env)

    def _relatorio_final_default_dates(self):
        """(início, fim) dos ensaios: datas reais da OS, senão as planejadas.

        Converte o Datetime (UTC) para a data local do usuário.
        """
        self.ensure_one()
        start = self.date_actual_start or self.date_planned_start
        end = self.date_actual_end or self.date_planned_end

        def to_date(dt):
            return fields.Datetime.context_timestamp(self, dt).date() if dt else False

        return to_date(start), to_date(end)

    def action_generate_relatorios(self):
        """Cria os relatórios finais faltantes (um por equipamento). Idempotente.

        Relatórios existentes nunca são renumerados nem apagados. Equipamento
        novo recebe `index = max + 1` (via `create()` do relatório).

        Retorna o recordset com TODOS os relatórios finais das OSs em `self`.
        """
        Relatorio = self.env["afr.qualificacao.relatorio"]
        for os in self:
            existing = os.relatorio_final_ids.mapped("equipment_id")
            date_start, date_end = os._relatorio_final_default_dates()
            vals_list = [
                {
                    "os_id": os.id,
                    "equipment_id": equip.id,
                    "data_inicio_ensaios": date_start,
                    "data_fim_ensaios": date_end,
                }
                for equip in os._relatorio_final_equipments()
                if equip not in existing
            ]
            if vals_list:
                Relatorio.create(vals_list)
        return self.mapped("relatorio_final_ids").sorted(
            key=lambda r: (r.os_id.id, r.index, r.id)
        )
```

Anexar em `models/__init__.py` (no fim):

```python
from . import relatorio                  # Relatório Final P1 (16.0.8.0.0)
from . import relatorio_os               # Relatório Final P1 — extensão da OS
```

Anexar em `security/ir.model.access.csv` (no fim, sem linha em branco no meio):

```csv
access_afr_qualificacao_relatorio_technician,afr_qualificacao_relatorio_technician,model_afr_qualificacao_relatorio,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_afr_qualificacao_relatorio_user,afr_qualificacao_relatorio_user,model_afr_qualificacao_relatorio,afr_qualificacao.group_afr_qualificacao_user,1,1,1,0
access_afr_qualificacao_relatorio_manager,afr_qualificacao_relatorio_manager,model_afr_qualificacao_relatorio,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
```

Antes de colar, confirmar que o CSV termina com `\n` (`tail -c1 security/ir.model.access.csv | xxd`). Se não terminar, a primeira linha nova gruda na última existente.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: o mesmo comando do Step 2.
Expected: `TestRelatorioModel`, 17 testes, 0 failures, 0 errors.

- [ ] **Step 5: Commit**

Commit via agente `git-commit-push`, cwd `addons/afr_qualificacao`, arquivos:
`models/relatorio.py models/relatorio_os.py models/__init__.py security/ir.model.access.csv tests/test_relatorio_model.py tests/__init__.py`
Mensagem:

```
feat(relatorio): add final report model generated per OS equipment

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 2: Dados de campo — checklist, indicadores, leituras de IB

**Files:**
- Create: `models/relatorio_dados_campo.py`
- Modify: `models/relatorio.py` (O2Ms + `_seed_checklist`)
- Modify: `models/__init__.py` (append)
- Modify: `security/ir.model.access.csv` (append)
- Modify: `tests/test_relatorio_model.py` (append métodos na classe)

**Interfaces:**
- Consumes: `afr.qualificacao.relatorio` (Task 1: `cycle_ids`, `os_id`), `afr.qualificacao.cycle`, `afr.qualificacao.collect.item`.
- Produces:
  - `afr.relatorio.checklist(relatorio_id, sequence, grupo, descricao, status, comentario)`, com `status` ∈ `aprovado/reprovado/na` (vazio = não avaliado).
  - `afr.relatorio.indicador(relatorio_id, tipo, marca, modelo_tipo, lote, validade, valor_d, populacao, evidencia_collect_item_id)`, com `tipo` ∈ `biologico/quimico`.
  - `afr.relatorio.leitura.ib(relatorio_id, cycle_id, indicador_id, data_incubacao, data_leitura, leitor, resultado, controle_positivo_ok)`, com `resultado` ∈ `negativo/positivo`.
  - Em `afr.qualificacao.relatorio`: `checklist_ids`, `indicador_ids`, `leitura_ib_ids` e `_seed_checklist(lines: list[dict]) -> afr.relatorio.checklist recordset` (linhas criadas; vazio se já havia linhas).

- [ ] **Step 1: Escrever os testes que falham**

Anexar ao fim da classe `TestRelatorioModel` em `tests/test_relatorio_model.py`:

```python
    # ─────────────────────────────────────────────────────────────
    # DADOS DE CAMPO (Task 2)
    # ─────────────────────────────────────────────────────────────
    CHECKLIST_LINES = [
        {"grupo": "Instalações elétricas", "descricao": "Tensão conforme placa", "sequence": 10},
        {"grupo": "Instalações elétricas", "descricao": "Aterramento presente", "sequence": 20},
        {"grupo": "Utilidades", "descricao": "Água de alimentação disponível", "sequence": 30},
    ]

    def test_seed_checklist_creates_lines_in_order(self):
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        created = rel._seed_checklist(self.CHECKLIST_LINES)
        self.assertEqual(len(created), 3)
        self.assertEqual(
            rel.checklist_ids.mapped("descricao"),
            ["Tensão conforme placa", "Aterramento presente",
             "Água de alimentação disponível"],
        )
        self.assertEqual(rel.checklist_ids[0].grupo, "Instalações elétricas")
        self.assertFalse(rel.checklist_ids[0].status)

    def test_seed_checklist_is_idempotent(self):
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        rel._seed_checklist(self.CHECKLIST_LINES)
        rel.checklist_ids[0].status = "aprovado"
        again = rel._seed_checklist(self.CHECKLIST_LINES)
        self.assertFalse(again)
        self.assertEqual(len(rel.checklist_ids), 3)
        self.assertEqual(rel.checklist_ids[0].status, "aprovado")

    def test_seed_checklist_empty_lines_is_noop(self):
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        self.assertFalse(rel._seed_checklist([]))
        self.assertFalse(rel.checklist_ids)

    def _make_indicador(self, rel, **extra):
        vals = {
            "relatorio_id": rel.id,
            "tipo": "biologico",
            "marca": "Marca Teste",
            "modelo_tipo": "Geobacillus stearothermophilus",
            "lote": "L-TESTE-01",
            "validade": date(2027, 1, 31),
            "valor_d": 1.5,
            "populacao": "1,0 x 10^6",
        }
        vals.update(extra)
        return self.env["afr.relatorio.indicador"].create(vals)

    def test_leitura_ib_valid(self):
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        ind = self._make_indicador(rel)
        leitura = self.env["afr.relatorio.leitura.ib"].create({
            "relatorio_id": rel.id,
            "cycle_id": self.cycle_qd1.id,
            "indicador_id": ind.id,
            "data_incubacao": date(2026, 9, 2),
            "data_leitura": date(2026, 9, 3),
            "leitor": "Eng. Responsável",
            "resultado": "negativo",
            "controle_positivo_ok": True,
        })
        self.assertIn(leitura, rel.leitura_ib_ids)
        self.assertIn(ind, rel.indicador_ids)

    def test_leitura_ib_rejects_foreign_cycle(self):
        """Review Focus 3: ciclo de outro equipamento."""
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        with self.assertRaises(ValidationError):
            self.env["afr.relatorio.leitura.ib"].create({
                "relatorio_id": rel.id,
                "cycle_id": self.cycle_other.id,
                "resultado": "negativo",
            })

    def test_leitura_ib_rejects_foreign_indicador(self):
        """Review Focus 3: indicador de outro relatório."""
        self.os.action_generate_relatorios()
        rel1 = self._rel_for(self.os, self.equip1)
        rel2 = self._rel_for(self.os, self.equip2)
        ind2 = self._make_indicador(rel2)
        with self.assertRaises(ValidationError):
            self.env["afr.relatorio.leitura.ib"].create({
                "relatorio_id": rel1.id,
                "cycle_id": self.cycle_qd1.id,
                "indicador_id": ind2.id,
                "resultado": "negativo",
            })

    def test_indicador_evidencia_collect_item(self):
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        item = self.env["afr.qualificacao.collect.item"].create({
            "name": "Foto da bula do IB",
            "qualif_id": self.q1_qd.id,
        })
        ind = self._make_indicador(rel, evidencia_collect_item_id=item.id)
        self.assertEqual(ind.evidencia_collect_item_id, item)

    def test_relatorio_unlink_cascades_children(self):
        self.os.action_generate_relatorios()
        rel = self._rel_for(self.os, self.equip1)
        rel._seed_checklist(self.CHECKLIST_LINES)
        ind = self._make_indicador(rel)
        checklist = rel.checklist_ids
        rel.unlink()
        self.assertFalse(checklist.exists())
        self.assertFalse(ind.exists())
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioModel --stop-after-init --no-http`
Expected: os 8 testes novos dão ERROR (`KeyError: 'afr.relatorio.indicador'` / `AttributeError: ... '_seed_checklist'`); os 17 da Task 1 continuam passando.

- [ ] **Step 3: Implementar**

Criar `models/relatorio_dados_campo.py`:

```python
# -*- coding: utf-8 -*-
"""Dados de campo do Relatório Final (P1, 16.0.8.0.0).

Filhos de `afr.qualificacao.relatorio` digitados pelo escritório a partir do
que o técnico trouxe de campo (fase 1 não altera o PWA — spec D6):
checklist de instalação (QI), indicadores biológicos/químicos usados e as
leituras de IB por ciclo.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AfrRelatorioChecklist(models.Model):
    """Item do checklist de instalação (QI) do relatório."""

    _name = "afr.relatorio.checklist"
    _description = "Checklist do Relatório Final"
    _order = "relatorio_id, sequence, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio",
        string="Relatório",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    grupo = fields.Char(help='Agrupador, ex.: "Instalações elétricas".')
    descricao = fields.Char(string="Descrição", required=True)
    status = fields.Selection(
        [
            ("aprovado", "Aprovado"),
            ("reprovado", "Reprovado"),
            ("na", "N/A"),
        ],
        help="Vazio = ainda não avaliado.",
    )
    comentario = fields.Char(string="Comentário")


class AfrRelatorioIndicador(models.Model):
    """Indicador biológico ou químico usado nos ensaios."""

    _name = "afr.relatorio.indicador"
    _description = "Indicador do Relatório Final"
    _order = "relatorio_id, tipo, id"
    _rec_name = "lote"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio",
        string="Relatório",
        required=True,
        ondelete="cascade",
        index=True,
    )
    tipo = fields.Selection(
        [("biologico", "Biológico"), ("quimico", "Químico")],
        required=True,
        default="biologico",
    )
    marca = fields.Char()
    modelo_tipo = fields.Char(
        string="Modelo / tipo",
        help='Ex.: "Geobacillus stearothermophilus", "Type 5".',
    )
    lote = fields.Char()
    validade = fields.Date()
    valor_d = fields.Float(string="Valor D (min)")
    populacao = fields.Char(
        string="População",
        help='Texto livre, ex.: "1,7 x 10^6".',
    )
    evidencia_collect_item_id = fields.Many2one(
        "afr.qualificacao.collect.item",
        string="Evidência (foto da bula)",
        ondelete="set null",
    )

    def name_get(self):
        tipos = dict(self._fields["tipo"].selection)
        return [
            (r.id, "%s — lote %s" % (tipos.get(r.tipo, ""), r.lote or "?"))
            for r in self
        ]


class AfrRelatorioLeituraIb(models.Model):
    """Leitura de indicador biológico incubado após um ciclo."""

    _name = "afr.relatorio.leitura.ib"
    _description = "Leitura de IB do Relatório Final"
    _order = "relatorio_id, cycle_id, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio",
        string="Relatório",
        required=True,
        ondelete="cascade",
        index=True,
    )
    cycle_id = fields.Many2one(
        "afr.qualificacao.cycle",
        string="Ciclo",
        ondelete="cascade",
        index=True,
    )
    indicador_id = fields.Many2one(
        "afr.relatorio.indicador",
        string="Indicador",
        ondelete="set null",
    )
    data_incubacao = fields.Date(string="Data de incubação")
    data_leitura = fields.Date(string="Data de leitura")
    leitor = fields.Char(help="Quem fez a leitura.")
    resultado = fields.Selection(
        [("negativo", "Negativo"), ("positivo", "Positivo")],
    )
    controle_positivo_ok = fields.Boolean(string="Controle positivo OK")

    @api.constrains("relatorio_id", "cycle_id", "indicador_id")
    def _check_same_relatorio(self):
        """Ciclo e indicador precisam ser do próprio relatório.

        O domain da view não basta: import e RPC passam por fora dele.
        """
        for leitura in self:
            rel = leitura.relatorio_id
            if leitura.cycle_id and leitura.cycle_id not in rel.cycle_ids:
                raise ValidationError(_(
                    "O ciclo '%s' não pertence às qualificações do relatório %s."
                ) % (leitura.cycle_id.display_name, rel.name))
            if leitura.indicador_id and leitura.indicador_id.relatorio_id != rel:
                raise ValidationError(_(
                    "O indicador '%s' é de outro relatório."
                ) % leitura.indicador_id.display_name)
```

Em `models/relatorio.py`, logo **depois** do campo `proxima_qualificacao` (antes do bloco `CREATE`), adicionar:

```python
    # ───────── Dados de campo (filhos) ─────────
    checklist_ids = fields.One2many(
        "afr.relatorio.checklist",
        "relatorio_id",
        string="Checklist",
        copy=True,
    )
    indicador_ids = fields.One2many(
        "afr.relatorio.indicador",
        "relatorio_id",
        string="Indicadores",
        copy=True,
    )
    leitura_ib_ids = fields.One2many(
        "afr.relatorio.leitura.ib",
        "relatorio_id",
        string="Leituras de IB",
    )
```

E, no fim do arquivo (dentro da classe, depois de `_doc_number`), adicionar:

```python
    def _seed_checklist(self, lines):
        """Semeia o checklist a partir de `lines` (list de dict
        `{grupo, descricao, sequence}`). Idempotente: relatório que já tem
        qualquer linha não é tocado (não duplica nem sobrescreve status).

        Retorna as linhas criadas (vazio quando nada foi semeado).
        """
        Checklist = self.env["afr.relatorio.checklist"]
        created = Checklist
        if not lines:
            return created
        for rel in self:
            if rel.checklist_ids:
                continue
            created |= Checklist.create([
                {
                    "relatorio_id": rel.id,
                    "sequence": line.get("sequence", (i + 1) * 10),
                    "grupo": line.get("grupo") or False,
                    "descricao": line["descricao"],
                }
                for i, line in enumerate(lines)
            ])
        return created
```

Anexar em `models/__init__.py`:

```python
from . import relatorio_dados_campo      # Relatório Final P1 — checklist/indicador/leitura IB
```

Anexar em `security/ir.model.access.csv` (o `user` tem unlink nas linhas-filhas; ver Global Constraints):

```csv
access_afr_relatorio_checklist_technician,afr_relatorio_checklist_technician,model_afr_relatorio_checklist,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_afr_relatorio_checklist_user,afr_relatorio_checklist_user,model_afr_relatorio_checklist,afr_qualificacao.group_afr_qualificacao_user,1,1,1,1
access_afr_relatorio_checklist_manager,afr_relatorio_checklist_manager,model_afr_relatorio_checklist,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
access_afr_relatorio_indicador_technician,afr_relatorio_indicador_technician,model_afr_relatorio_indicador,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_afr_relatorio_indicador_user,afr_relatorio_indicador_user,model_afr_relatorio_indicador,afr_qualificacao.group_afr_qualificacao_user,1,1,1,1
access_afr_relatorio_indicador_manager,afr_relatorio_indicador_manager,model_afr_relatorio_indicador,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
access_afr_relatorio_leitura_ib_technician,afr_relatorio_leitura_ib_technician,model_afr_relatorio_leitura_ib,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_afr_relatorio_leitura_ib_user,afr_relatorio_leitura_ib_user,model_afr_relatorio_leitura_ib,afr_qualificacao.group_afr_qualificacao_user,1,1,1,1
access_afr_relatorio_leitura_ib_manager,afr_relatorio_leitura_ib_manager,model_afr_relatorio_leitura_ib,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: o mesmo comando do Step 2.
Expected: `TestRelatorioModel`, 25 testes, 0 failures, 0 errors.

- [ ] **Step 5: Commit**

Commit via agente `git-commit-push`, cwd `addons/afr_qualificacao`, arquivos:
`models/relatorio_dados_campo.py models/relatorio.py models/__init__.py security/ir.model.access.csv tests/test_relatorio_model.py`
Mensagem:

```
feat(relatorio): add field data models (checklist, indicators, IB readings)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 3: Extensão do ciclo — janela, posições de sensor, `extracted_json`

**Files:**
- Create: `models/relatorio_cycle.py`
- Modify: `models/__init__.py` (append)
- Modify: `security/ir.model.access.csv` (append)
- Modify: `tests/test_relatorio_model.py` (append métodos na classe)

**Interfaces:**
- Consumes: `afr.qualificacao.cycle` (`qualificacao_id`, `cycle_type_id`, `sequence`, `_order = "qualificacao_id, cycle_type_id, sequence, id"`).
- Produces:
  - `afr.relatorio.sensor.pos(cycle_id, sequence, canal, posicao, ib_label)`.
  - Em `afr.qualificacao.cycle`: `janela_inicio`, `janela_fim` (Datetime), `sensor_pos_ids` (O2M), `sensor_pos_count` (Integer), `extracted_json` (Text).
  - `cycle.action_copy_sensor_pos_from_previous() -> bool`. Retorna `True` quando copiou e `False` quando não há ciclo anterior com posições (sem exceção). **Substitui** as linhas existentes do ciclo.
  - `cycle._previous_cycle_with_sensor_pos() -> afr.qualificacao.cycle` (0 ou 1): o ciclo mais próximo antes deste, **entre todos os ciclos das qualificações não canceladas da mesma OS + equipamento**, na ordem `_relatorio_cycle_sort_key()` = (tipo de qualificação QI<QO<QD, cycle_type `sequence, name, id`, `sequence`, `id`), que tenha posições. O 1º ciclo de QD copia do último ciclo de QO.
  - `cycle._relatorio_cycle_sort_key() -> tuple` (nome fora do contrato).
  - `cycle.action_open_relatorio_cycle() -> dict`: act_window do form do ciclo (usado pela aba Ciclos na Task 4).

- [ ] **Step 1: Escrever os testes que falham**

Anexar ao fim da classe `TestRelatorioModel`:

```python
    # ─────────────────────────────────────────────────────────────
    # CICLOS (Task 3)
    # ─────────────────────────────────────────────────────────────
    def _set_positions(self, cycle, rows):
        self.env["afr.relatorio.sensor.pos"].create([
            {
                "cycle_id": cycle.id,
                "sequence": (i + 1) * 10,
                "canal": canal,
                "posicao": posicao,
                "ib_label": ib_label,
            }
            for i, (canal, posicao, ib_label) in enumerate(rows)
        ])

    @staticmethod
    def _rows(cycle):
        return [
            (p.sequence, p.canal, p.posicao, p.ib_label)
            for p in cycle.sensor_pos_ids
        ]

    POSITIONS = [
        ("CH001", "Dreno", "IB1"),
        ("CH002", "Centro geométrico", "IB2"),
        ("CH003", "Porta", False),
    ]

    def test_janela_fim_before_inicio_rejected(self):
        """Review Focus 4."""
        with self.assertRaises(ValidationError):
            self.cycle_qd1.write({
                "janela_inicio": datetime(2026, 9, 2, 10, 30),
                "janela_fim": datetime(2026, 9, 2, 10, 0),
            })

    def test_janela_valid_and_extracted_json(self):
        self.cycle_qd1.write({
            "janela_inicio": datetime(2026, 9, 2, 10, 0),
            "janela_fim": datetime(2026, 9, 2, 10, 15),
            "extracted_json": "{}",
        })
        self.assertEqual(self.cycle_qd1.janela_fim, datetime(2026, 9, 2, 10, 15))
        self.assertEqual(self.cycle_qd1.extracted_json, "{}")

    def test_copy_sensor_pos_from_previous(self):
        self._set_positions(self.cycle_qd1, self.POSITIONS)
        self.assertTrue(self.cycle_qd2.action_copy_sensor_pos_from_previous())
        self.assertEqual(self._rows(self.cycle_qd2), self._rows(self.cycle_qd1))
        self.assertEqual(self.cycle_qd2.sensor_pos_count, 3)
        # As linhas são cópias, não as mesmas.
        self.assertFalse(self.cycle_qd2.sensor_pos_ids & self.cycle_qd1.sensor_pos_ids)

    def test_copy_sensor_pos_first_cycle_is_noop(self):
        # cycle_qo é o 1º ciclo do relatório do equip1 (QI não tem ciclo):
        # não há anterior → False, sem exceção.
        self._set_positions(self.cycle_qd1, self.POSITIONS)
        self.assertFalse(self.cycle_qo.action_copy_sensor_pos_from_previous())
        self.assertFalse(self.cycle_qo.sensor_pos_ids)

    def test_copy_sensor_pos_first_qd_copies_from_last_qo(self):
        """1º ciclo de QD copia do último ciclo de QO do mesmo equipamento
        (ordem QI < QO < QD, atravessando qualificações)."""
        self._set_positions(self.cycle_qo, self.POSITIONS)
        self.assertTrue(self.cycle_qd1.action_copy_sensor_pos_from_previous())
        self.assertEqual(self._rows(self.cycle_qd1), self._rows(self.cycle_qo))

    def test_copy_sensor_pos_ignores_other_equipment(self):
        # cycle_other (equip2) é o único ciclo do relatório do equip2: os
        # ciclos do equip1 com posições não contam.
        self._set_positions(self.cycle_qo, self.POSITIONS)
        self._set_positions(self.cycle_qd1, self.POSITIONS)
        self.assertFalse(self.cycle_other.action_copy_sensor_pos_from_previous())
        self.assertFalse(self.cycle_other.sensor_pos_ids)

    def test_copy_sensor_pos_ignores_cancelled_qualif(self):
        self._set_positions(self.cycle_qo, self.POSITIONS)
        self.q1_qo.write({"state": "cancelled"})
        self.assertFalse(self.cycle_qd1.action_copy_sensor_pos_from_previous())

    def test_copy_sensor_pos_skips_empty_previous(self):
        self._set_positions(self.cycle_qd1, self.POSITIONS)
        # cycle_qd2 vazio → cycle_qd3 copia do qd1 (anterior mais próximo com posições).
        self.assertTrue(self.cycle_qd3.action_copy_sensor_pos_from_previous())
        self.assertEqual(self._rows(self.cycle_qd3), self._rows(self.cycle_qd1))

    def test_copy_sensor_pos_as_usuario_replaces(self):
        """Review Focus 5: Usuário (não Gestor) copia por cima de linhas já
        existentes — substitui, não soma, e não dá AccessError."""
        self._set_positions(self.cycle_qd1, self.POSITIONS)
        self._set_positions(self.cycle_qd2, [("CH099", "Antiga", False)])
        usuario = self.env["res.users"].create({
            "name": "Usuário Relatório",
            "login": "usuario.relatorio.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
            ])],
        })
        done = self.cycle_qd2.with_user(usuario).action_copy_sensor_pos_from_previous()
        self.assertTrue(done)
        self.cycle_qd2.invalidate_recordset()
        self.assertEqual(self._rows(self.cycle_qd2), self._rows(self.cycle_qd1))

    def test_open_relatorio_cycle_action(self):
        action = self.cycle_qd1.action_open_relatorio_cycle()
        self.assertEqual(action["res_model"], "afr.qualificacao.cycle")
        self.assertEqual(action["res_id"], self.cycle_qd1.id)
        self.assertEqual(action["view_mode"], "form")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioModel --stop-after-init --no-http`
Expected: os 10 testes novos dão ERROR (`KeyError: 'afr.relatorio.sensor.pos'`, `ValueError: Invalid field 'janela_inicio'`); os 25 anteriores passam.

- [ ] **Step 3: Implementar**

Criar `models/relatorio_cycle.py`:

```python
# -*- coding: utf-8 -*-
"""Extensão do ciclo para o Relatório Final (P1, 16.0.8.0.0).

Acrescenta ao `afr.qualificacao.cycle` a janela de esterilização, a disposição
dos sensores (canal do validador → posição física → IB) e o `extracted_json`
reservado para a extração futura do arquivo bruto do validador (spec D1).
Fica fora de `qualificacao_cycle.py` de propósito, como `relatorio_os.py`.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AfrRelatorioSensorPos(models.Model):
    """Posição de um sensor (canal do validador) dentro da câmara num ciclo."""

    _name = "afr.relatorio.sensor.pos"
    _description = "Posição de Sensor no Ciclo"
    _order = "cycle_id, sequence, id"
    _rec_name = "canal"

    cycle_id = fields.Many2one(
        "afr.qualificacao.cycle",
        string="Ciclo",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    canal = fields.Char(required=True, help='Canal do validador, ex.: "CH006".')
    posicao = fields.Char(string="Posição", help='Ex.: "Dreno", "Centro geométrico".')
    ib_label = fields.Char(string="IB", help='Rótulo do IB junto ao sensor, ex.: "IB1".')


class AfrQualificacaoCycleRelatorio(models.Model):
    _inherit = "afr.qualificacao.cycle"

    janela_inicio = fields.Datetime(
        string="Início da esterilização",
        help="Início da janela de esterilização (patamar) do ciclo.",
    )
    janela_fim = fields.Datetime(
        string="Fim da esterilização",
    )
    sensor_pos_ids = fields.One2many(
        "afr.relatorio.sensor.pos",
        "cycle_id",
        string="Posição dos sensores",
        copy=True,
    )
    sensor_pos_count = fields.Integer(
        string="Sensores",
        compute="_compute_sensor_pos_count",
    )
    extracted_json = fields.Text(
        string="Dados extraídos (JSON)",
        copy=False,
        help=(
            "Reservado para a extração futura do arquivo do validador "
            "(min/max/média/F0 por canal). Vazio na fase 1."
        ),
    )

    @api.depends("sensor_pos_ids")
    def _compute_sensor_pos_count(self):
        for cycle in self:
            cycle.sensor_pos_count = len(cycle.sensor_pos_ids)

    @api.constrains("janela_inicio", "janela_fim")
    def _check_janela(self):
        for cycle in self:
            if (
                cycle.janela_inicio
                and cycle.janela_fim
                and cycle.janela_fim < cycle.janela_inicio
            ):
                raise ValidationError(_(
                    "Fim da esterilização deve ser ≥ início (%s)."
                ) % cycle.display_name)

    # Ordem das etapas no relatório: QI < QO < QD (demais tipos ao fim).
    _QUALIF_TYPE_RANK = {"installation": 0, "operational": 1, "performance": 2}

    def _relatorio_cycle_sort_key(self):
        """Chave de ordem dos ciclos no relatório do equipamento:
        tipo de qualificação (QI<QO<QD), tipo de ciclo (`sequence, name, id`
        do cycle.type, como o `_order` dele), sequence, id."""
        ctype = self.cycle_type_id
        return (
            self._QUALIF_TYPE_RANK.get(self.qualificacao_id.qualification_type, 9),
            ctype.sequence or 0,
            ctype.name or "",
            ctype.id,
            self.sequence or 0,
            self.id,
        )

    def _previous_cycle_with_sensor_pos(self):
        """Ciclo anterior mais próximo, no relatório do mesmo equipamento, com
        posições.

        Considera todos os ciclos das qualificações não canceladas da mesma
        OS e do mesmo equipamento (o escopo de um relatório final), na ordem
        `_relatorio_cycle_sort_key` — assim o 1º ciclo de QD copia do último
        ciclo de QO. Pula ciclos anteriores ainda sem posições. Retorna
        recordset vazio quando não há nenhum.
        """
        self.ensure_one()
        qualif = self.qualificacao_id
        if not qualif.os_id:
            return self.browse()
        siblings = self.search([
            ("qualificacao_id.os_id", "=", qualif.os_id.id),
            ("qualificacao_id.equipment_id", "=", qualif.equipment_id.id),
            ("qualificacao_id.state", "!=", "cancelled"),
        ]).sorted(key=lambda c: c._relatorio_cycle_sort_key())
        ids = siblings.ids
        if self.id not in ids:
            return self.browse()
        for candidate in reversed(siblings[: ids.index(self.id)]):
            if candidate.sensor_pos_ids:
                return candidate
        return self.browse()

    def action_copy_sensor_pos_from_previous(self):
        """Copia as posições de sensor do ciclo anterior (mesma OS + equipamento).

        Substitui as linhas atuais deste ciclo. Sem ciclo anterior com
        posições, não faz nada e retorna False (sem UserError: o botão
        simplesmente não tem efeito).
        """
        self.ensure_one()
        source = self._previous_cycle_with_sensor_pos()
        if not source:
            return False
        self.sensor_pos_ids.unlink()
        self.env["afr.relatorio.sensor.pos"].create([
            {
                "cycle_id": self.id,
                "sequence": pos.sequence,
                "canal": pos.canal,
                "posicao": pos.posicao,
                "ib_label": pos.ib_label,
            }
            for pos in source.sensor_pos_ids
        ])
        return True

    def action_open_relatorio_cycle(self):
        """Abre o form do ciclo (janela, sensores, arquivos) a partir da aba
        Ciclos do relatório final."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name,
            "res_model": "afr.qualificacao.cycle",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }
```

Anexar em `models/__init__.py`:

```python
from . import relatorio_cycle            # Relatório Final P1 — extensão do ciclo + sensor.pos
```

Anexar em `security/ir.model.access.csv`:

```csv
access_afr_relatorio_sensor_pos_technician,afr_relatorio_sensor_pos_technician,model_afr_relatorio_sensor_pos,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_afr_relatorio_sensor_pos_user,afr_relatorio_sensor_pos_user,model_afr_relatorio_sensor_pos,afr_qualificacao.group_afr_qualificacao_user,1,1,1,1
access_afr_relatorio_sensor_pos_manager,afr_relatorio_sensor_pos_manager,model_afr_relatorio_sensor_pos,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: o mesmo comando do Step 2.
Expected: `TestRelatorioModel`, 35 testes, 0 failures, 0 errors.

- [ ] **Step 5: Commit**

Commit via agente `git-commit-push`, cwd `addons/afr_qualificacao`, arquivos:
`models/relatorio_cycle.py models/__init__.py security/ir.model.access.csv tests/test_relatorio_model.py`
Mensagem:

```
feat(relatorio): extend cycles with sterilization window and sensor positions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 4: Telas — form do relatório, OS (smart button + gerar), ciclo, menu, manifest 16.0.8.0.0

**Files:**
- Create: `views/relatorio_views.xml`
- Create: `views/relatorio_cycle_views.xml`
- Modify: `models/relatorio.py` (campo `os_collect_item_ids`)
- Modify: `models/relatorio_os.py` (wrappers de UI)
- Modify: `__manifest__.py` (versão + `data`)
- Modify: `tests/test_relatorio_model.py` (append métodos na classe)

**Interfaces:**
- Consumes: tudo das Tasks 1–3; views `afr_qualificacao.view_afr_qualificacao_os_form` (tem `<div class="oe_button_box" name="button_box">` e `<header>` terminando em `<field name="state" widget="statusbar" …/>`) e `afr_qualificacao.view_afr_qualificacao_cycle_form` (tem `<header>` com `field state` e `<field name="notes">` dentro de um `<group string="Observações">`); menu `afr_qualificacao.menu_afr_qualificacao_root`.
- Produces:
  - `os.action_generate_relatorios_open() -> dict` e `os.action_view_relatorios_finais() -> dict`.
  - `relatorio.os_collect_item_ids` (M2M compute).
  - Form `view_afr_qualificacao_relatorio_form` com `<header>` só com `field state` (statusbar), `<div class="oe_button_box" name="button_box"/>` e `<notebook>` com `<page name="page_dados_campo">` e `<page name="page_ciclos">`. P2–P5 herdam por xpath `//header`, `//notebook`, `//page[@name='page_dados_campo']` etc.
  - Menu `afr_qualificacao.menu_afr_relatorio_final`.

- [ ] **Step 1: Escrever os testes que falham**

Anexar ao fim da classe `TestRelatorioModel`:

```python
    # ─────────────────────────────────────────────────────────────
    # UI (Task 4)
    # ─────────────────────────────────────────────────────────────
    def test_generate_open_action(self):
        action = self.os.action_generate_relatorios_open()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "afr.qualificacao.relatorio")
        self.assertEqual(action["domain"], [("os_id", "=", self.os.id)])
        self.assertEqual(self.os.relatorio_final_count, 2)

    def test_view_relatorios_finais_action_does_not_generate(self):
        action = self.os.action_view_relatorios_finais()
        self.assertEqual(action["res_model"], "afr.qualificacao.relatorio")
        self.assertEqual(self.os.relatorio_final_count, 0)

    def test_os_collect_item_ids_same_equipment(self):
        item1 = self.env["afr.qualificacao.collect.item"].create({
            "name": "PDF do validador", "qualif_id": self.q1_qd.id,
            "cycle_id": self.cycle_qd1.id,
        })
        item2 = self.env["afr.qualificacao.collect.item"].create({
            "name": "PDF do validador", "qualif_id": self.q2_qd.id,
        })
        self.os.action_generate_relatorios()
        rel1 = self._rel_for(self.os, self.equip1)
        self.assertIn(item1, rel1.os_collect_item_ids)
        self.assertNotIn(item2, rel1.os_collect_item_ids)

    def test_form_view_exposes_contract_hooks(self):
        """P2–P5 herdam por xpath nesses nomes — não podem sumir."""
        arch = self.env["afr.qualificacao.relatorio"].get_view(view_type="form")["arch"]
        self.assertIn('name="page_dados_campo"', arch)
        self.assertIn('name="page_ciclos"', arch)
        self.assertIn("<header", arch)
        self.assertIn('name="button_box"', arch)

    def test_os_form_has_relatorio_final_buttons(self):
        arch = self.env["afr.qualificacao.os"].get_view(
            self.env.ref("afr_qualificacao.view_afr_qualificacao_os_form").id,
            view_type="form",
        )["arch"]
        self.assertIn("action_view_relatorios_finais", arch)
        self.assertIn("action_generate_relatorios_open", arch)

    def test_cycle_form_has_copy_button(self):
        arch = self.env["afr.qualificacao.cycle"].get_view(
            self.env.ref("afr_qualificacao.view_afr_qualificacao_cycle_form").id,
            view_type="form",
        )["arch"]
        self.assertIn("action_copy_sensor_pos_from_previous", arch)
        self.assertIn('name="sensor_pos_ids"', arch)

    def test_menu_exists(self):
        menu = self.env.ref("afr_qualificacao.menu_afr_relatorio_final")
        self.assertEqual(
            menu.parent_id, self.env.ref("afr_qualificacao.menu_afr_qualificacao_root")
        )
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioModel --stop-after-init --no-http`
Expected: os 7 testes novos falham (`AttributeError: ... 'action_generate_relatorios_open'`, `ValueError: External ID not found … menu_afr_relatorio_final`, `AssertionError: 'name="page_dados_campo"' not found`); os 35 anteriores passam.

- [ ] **Step 3: Implementar modelo (campo lateral + wrappers)**

Em `models/relatorio.py`, logo depois do campo `cycle_ids`, adicionar:

```python
    os_collect_item_ids = fields.Many2many(
        "afr.qualificacao.collect.item",
        compute="_compute_os_collect_item_ids",
        string="Itens de coleta",
        help="Itens de coleta das qualificações deste equipamento (consulta).",
    )
```

e, junto aos demais computes (depois de `_compute_cycle_ids`):

```python
    @api.depends("qualificacao_ids.collect_item_ids")
    def _compute_os_collect_item_ids(self):
        for rel in self:
            rel.os_collect_item_ids = rel.qualificacao_ids.collect_item_ids
```

Em `models/relatorio_os.py`, no fim da classe:

```python
    def _relatorio_final_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Relatórios Finais"),
            "res_model": "afr.qualificacao.relatorio",
            "view_mode": "tree,form",
            "domain": [("os_id", "=", self.id)],
            "context": {"default_os_id": self.id, "create": False},
        }

    def action_generate_relatorios_open(self):
        """Botão "Gerar relatórios finais": gera os faltantes e abre a lista.

        Wrapper de UI: `action_generate_relatorios()` retorna recordset
        (contrato P1), que o web client não sabe serializar.
        """
        self.ensure_one()
        self.action_generate_relatorios()
        return self._relatorio_final_action()

    def action_view_relatorios_finais(self):
        """Smart button: só abre a lista, não gera."""
        return self._relatorio_final_action()
```

- [ ] **Step 4: Implementar as views**

Criar `views/relatorio_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<!--
    Relatório Final de Qualificação — P1 (16.0.8.0.0).

    O form expõe pontos de extensão estáveis para P2–P5 (herança por xpath):
      //header                          → botões (minuta, verificar, emitir…)
      //div[@name='button_box']         → smart buttons
      //notebook                        → novas páginas
      //page[@name='page_dados_campo']   → dados de campo
      //page[@name='page_ciclos']        → ciclos
    Não renomear esses `name`.
-->
<odoo>

    <!-- ======================================================== -->
    <!-- FORM                                                      -->
    <!-- ======================================================== -->
    <record id="view_afr_qualificacao_relatorio_form" model="ir.ui.view">
        <field name="name">afr.qualificacao.relatorio.form</field>
        <field name="model">afr.qualificacao.relatorio</field>
        <field name="arch" type="xml">
            <form string="Relatório Final" create="0">
                <header>
                    <field name="state" widget="statusbar"
                           statusbar_visible="draft,issued,client_approved"/>
                </header>
                <sheet>
                    <div class="oe_button_box" name="button_box"/>
                    <div class="oe_title">
                        <h1><field name="name" readonly="1"/></h1>
                        <h3><field name="revision_label"/></h3>
                    </div>
                    <group>
                        <group string="Identificação">
                            <field name="os_id" readonly="1"/>
                            <field name="equipment_id" readonly="1"/>
                            <field name="partner_id"/>
                            <field name="company_id" groups="base.group_multi_company"/>
                        </group>
                        <group string="Controle">
                            <field name="index" readonly="1"/>
                            <field name="revision" readonly="1"/>
                            <field name="proxima_qualificacao"/>
                            <field name="qualificacao_ids" widget="many2many_tags" readonly="1"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Dados de campo" name="page_dados_campo">
                            <div class="row">
                                <div class="col-lg-8">
                                    <group>
                                        <group string="Período dos ensaios">
                                            <field name="data_inicio_ensaios"/>
                                            <field name="data_fim_ensaios"/>
                                        </group>
                                        <group string="Ambiente">
                                            <field name="amb_temperatura" placeholder="22 a 25 °C"/>
                                            <field name="amb_umidade" placeholder="41 %UR"/>
                                        </group>
                                    </group>
                                    <group>
                                        <group string="Critérios de aceitação">
                                            <field name="tolerancia_acima"/>
                                            <field name="criterio_f0_fator"/>
                                        </group>
                                    </group>
                                    <separator string="Checklist de instalação"/>
                                    <field name="checklist_ids" nolabel="1">
                                        <tree editable="bottom"
                                              decoration-danger="status == 'reprovado'"
                                              decoration-muted="status == 'na'">
                                            <field name="sequence" widget="handle"/>
                                            <field name="grupo"/>
                                            <field name="descricao"/>
                                            <field name="status"/>
                                            <field name="comentario"/>
                                        </tree>
                                    </field>
                                    <separator string="Indicadores biológicos e químicos"/>
                                    <field name="indicador_ids" nolabel="1">
                                        <tree editable="bottom">
                                            <field name="tipo"/>
                                            <field name="marca"/>
                                            <field name="modelo_tipo"/>
                                            <field name="lote"/>
                                            <field name="validade"/>
                                            <field name="valor_d"/>
                                            <field name="populacao"/>
                                            <field name="evidencia_collect_item_id"
                                                   domain="[('os_id', '=', parent.os_id)]"
                                                   options="{'no_create': True}"/>
                                        </tree>
                                    </field>
                                    <separator string="Leituras de IB"/>
                                    <field name="leitura_ib_ids" nolabel="1">
                                        <tree editable="bottom"
                                              decoration-danger="resultado == 'positivo'">
                                            <field name="cycle_id"
                                                   domain="[('id', 'in', parent.cycle_ids)]"
                                                   options="{'no_create': True}"/>
                                            <field name="indicador_id"
                                                   domain="[('relatorio_id', '=', parent.id)]"
                                                   options="{'no_create': True}"/>
                                            <field name="data_incubacao"/>
                                            <field name="data_leitura"/>
                                            <field name="leitor"/>
                                            <field name="resultado"/>
                                            <field name="controle_positivo_ok"/>
                                        </tree>
                                    </field>
                                </div>
                                <div class="col-lg-4">
                                    <separator string="Itens de coleta (consulta)"/>
                                    <field name="os_collect_item_ids" nolabel="1" readonly="1">
                                        <tree>
                                            <field name="name"/>
                                            <field name="cycle_id" optional="show"/>
                                            <field name="state" widget="badge"/>
                                            <field name="filename" optional="hide"/>
                                        </tree>
                                    </field>
                                </div>
                            </div>
                        </page>
                        <page string="Ciclos" name="page_ciclos">
                            <field name="cycle_ids" nolabel="1" readonly="1">
                                <tree>
                                    <field name="qualificacao_id"/>
                                    <field name="cycle_type_id"/>
                                    <field name="sequence" optional="hide"/>
                                    <field name="state" widget="badge"/>
                                    <field name="janela_inicio"/>
                                    <field name="janela_fim"/>
                                    <field name="sensor_pos_count"/>
                                    <button name="action_open_relatorio_cycle" type="object"
                                            icon="fa-pencil" title="Editar janela e sensores"/>
                                </tree>
                            </field>
                        </page>
                    </notebook>
                </sheet>
                <div class="oe_chatter">
                    <field name="message_follower_ids"/>
                    <field name="activity_ids"/>
                    <field name="message_ids"/>
                </div>
            </form>
        </field>
    </record>

    <!-- ======================================================== -->
    <!-- TREE                                                      -->
    <!-- ======================================================== -->
    <record id="view_afr_qualificacao_relatorio_tree" model="ir.ui.view">
        <field name="name">afr.qualificacao.relatorio.tree</field>
        <field name="model">afr.qualificacao.relatorio</field>
        <field name="arch" type="xml">
            <tree create="0">
                <field name="name"/>
                <field name="os_id"/>
                <field name="equipment_id"/>
                <field name="partner_id"/>
                <field name="revision_label" string="Rev."/>
                <field name="data_fim_ensaios" optional="show"/>
                <field name="proxima_qualificacao" optional="show"/>
                <field name="state" widget="badge"
                       decoration-info="state == 'draft'"
                       decoration-success="state in ('issued', 'client_approved')"/>
            </tree>
        </field>
    </record>

    <!-- ======================================================== -->
    <!-- SEARCH                                                    -->
    <!-- ======================================================== -->
    <record id="view_afr_qualificacao_relatorio_search" model="ir.ui.view">
        <field name="name">afr.qualificacao.relatorio.search</field>
        <field name="model">afr.qualificacao.relatorio</field>
        <field name="arch" type="xml">
            <search>
                <field name="name"/>
                <field name="os_id"/>
                <field name="equipment_id"/>
                <field name="partner_id"/>
                <filter name="filter_draft" string="Rascunho"
                        domain="[('state', '=', 'draft')]"/>
                <filter name="filter_issued" string="Emitidos"
                        domain="[('state', '=', 'issued')]"/>
                <filter name="filter_client_approved" string="Aprovados pelo cliente"
                        domain="[('state', '=', 'client_approved')]"/>
                <group expand="0" string="Agrupar por">
                    <filter name="group_os" string="OS" context="{'group_by': 'os_id'}"/>
                    <filter name="group_partner" string="Cliente" context="{'group_by': 'partner_id'}"/>
                    <filter name="group_state" string="Status" context="{'group_by': 'state'}"/>
                </group>
            </search>
        </field>
    </record>

    <!-- ======================================================== -->
    <!-- ACTION + MENU                                             -->
    <!-- ======================================================== -->
    <record id="action_afr_qualificacao_relatorio" model="ir.actions.act_window">
        <field name="name">Relatórios Finais</field>
        <field name="res_model">afr.qualificacao.relatorio</field>
        <field name="view_mode">tree,form</field>
        <field name="search_view_id" ref="view_afr_qualificacao_relatorio_search"/>
        <field name="context">{'create': False}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">Nenhum relatório final ainda</p>
            <p>Abra uma OS de Qualificação e use "Gerar relatórios finais":
               é criado um relatório por equipamento.</p>
        </field>
    </record>

    <menuitem
        id="menu_afr_relatorio_final"
        name="Relatórios Finais"
        parent="menu_afr_qualificacao_root"
        action="action_afr_qualificacao_relatorio"
        sequence="16"
        groups="afr_qualificacao.group_afr_qualificacao_technician"
    />

    <!-- ======================================================== -->
    <!-- OS: smart button + botão Gerar                            -->
    <!-- ======================================================== -->
    <record id="view_afr_qualificacao_os_form_relatorio_final" model="ir.ui.view">
        <field name="name">afr.qualificacao.os.form.relatorio.final</field>
        <field name="model">afr.qualificacao.os</field>
        <field name="inherit_id" ref="afr_qualificacao.view_afr_qualificacao_os_form"/>
        <field name="arch" type="xml">
            <xpath expr="//div[@name='button_box']" position="inside">
                <button name="action_view_relatorios_finais" type="object"
                        class="oe_stat_button" icon="fa-file-pdf-o"
                        attrs="{'invisible': [('relatorio_final_count', '=', 0)]}">
                    <field name="relatorio_final_count" widget="statinfo"
                           string="Relatórios Finais"/>
                </button>
            </xpath>
            <xpath expr="//header/field[@name='state']" position="before">
                <button name="action_generate_relatorios_open" type="object"
                        string="Gerar relatórios finais" class="btn-secondary"
                        attrs="{'invisible': [('state', '=', 'cancelled')]}"
                        groups="afr_qualificacao.group_afr_qualificacao_user"/>
            </xpath>
        </field>
    </record>

</odoo>
```

Criar `views/relatorio_cycle_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<!--
    Relatório Final — P1 (16.0.8.0.0): extensão do form do ciclo.
    Janela de esterilização, posição dos sensores (com "copiar do ciclo
    anterior") e os arquivos coletados no ciclo, para consulta.
-->
<odoo>

    <record id="view_afr_qualificacao_cycle_form_relatorio_final" model="ir.ui.view">
        <field name="name">afr.qualificacao.cycle.form.relatorio.final</field>
        <field name="model">afr.qualificacao.cycle</field>
        <field name="inherit_id" ref="afr_qualificacao.view_afr_qualificacao_cycle_form"/>
        <field name="arch" type="xml">
            <xpath expr="//header/field[@name='state']" position="before">
                <button name="action_copy_sensor_pos_from_previous" type="object"
                        string="Copiar sensores do ciclo anterior" class="btn-secondary"
                        groups="afr_qualificacao.group_afr_qualificacao_user"
                        confirm="Substituir as posições de sensor deste ciclo pelas do ciclo anterior?"/>
            </xpath>
            <xpath expr="//field[@name='notes']/.." position="before">
                <group string="Janela de esterilização">
                    <group>
                        <field name="janela_inicio"/>
                        <field name="janela_fim"/>
                    </group>
                </group>
                <separator string="Posição dos sensores"/>
                <field name="sensor_pos_ids" nolabel="1">
                    <tree editable="bottom">
                        <field name="sequence" widget="handle"/>
                        <field name="canal"/>
                        <field name="posicao"/>
                        <field name="ib_label"/>
                    </tree>
                </field>
                <separator string="Arquivos do ciclo (coleta)"/>
                <field name="collect_item_ids" nolabel="1" readonly="1">
                    <tree>
                        <field name="name"/>
                        <field name="docx_section" optional="show"/>
                        <field name="state" widget="badge"/>
                        <field name="filename" invisible="1"/>
                        <field name="file" widget="binary" filename="filename"/>
                    </tree>
                </field>
            </xpath>
        </field>
    </record>

</odoo>
```

Em `__manifest__.py`:

1. `"version": "16.0.7.5.0",` → `"version": "16.0.8.0.0",`
2. Na docstring `description`, depois do bloco `F8.16 …` (antes da linha em branco que precede `Fluxo:`), adicionar:

```
          F11 (16.0.8.x): Relatório Final de Qualificação (montador).
            P1 (16.0.8.0.0): afr.qualificacao.relatorio por OS × equipamento
              + dados de campo (checklist, indicadores, leituras de IB)
              + ciclo com janela/posição de sensores.
```

3. Em `"data"`, logo depois de `"views/docx_template_views.xml",` (as views têm menuitem sob `menu_afr_qualificacao_root`, então precisam carregar **depois** de `views/qualificacao_menus.xml`):

```python
        # Relatório Final P1 (16.0.8.0.0) — menuitem sob menu_root, depois dos menus
        "views/relatorio_views.xml",
        "views/relatorio_cycle_views.xml",
```

Não criar `migrations/16.0.8.0.0/`: P1 não tem seed.

- [ ] **Step 5: Rodar e confirmar que passa**

Run: o mesmo comando do Step 2 (o `-u` recarrega as views).
Expected: `TestRelatorioModel`, 42 testes, 0 failures, 0 errors, e nenhum `ParseError`/`ValidationError` de view no log do upgrade.

- [ ] **Step 6: Regressão da suíte do módulo**

Delegar ao agente `test-runner`: suíte completa `--test-tags /afr_qualificacao`.
Expected: só as 3 falhas pré-existentes das Global Constraints. Em especial, `TestQualificacaoOsWorkflow` e `test_qo_cycles` verdes (a OS e o ciclo ganharam campos por herança).

- [ ] **Step 7: Validação de UI via agent-browser**

Reiniciar o container web para recarregar assets e fazer `-u afr_qualificacao` no banco de dev (ver `reference_browser_tools_wsl.md`: banco de dev `odoo-labquali`, porta `8083`). Depois:

```bash
agent-browser open http://localhost:8083/web/session/logout
agent-browser open http://localhost:8083/web/login
agent-browser snapshot -i          # preencher login/senha do admin de dev e entrar
agent-browser open "http://localhost:8083/web#action=afr_qualificacao.action_afr_qualificacao_os"
agent-browser snapshot -i          # abrir uma OS com qualificações
```

Conferir:
- botão "Gerar relatórios finais" no header;
- depois do clique, lista com um relatório por equipamento (`ReQT-<OS>-1…n`);
- smart button "Relatórios Finais" com a contagem;
- no form, abas "Dados de campo" (checklist/indicadores/leituras editáveis, coluna de itens de coleta) e "Ciclos" (lápis abre o form do ciclo);
- no ciclo: janela, sensores editáveis e "Copiar sensores do ciclo anterior";
- menu Qualificações → Relatórios Finais.

Se alguma coisa não renderizar, corrigir o XML e repetir os Steps 5 e 7. Anotar o resultado no relatório da task. Não pedir ao usuário que clique.

- [ ] **Step 8: Commit**

Commit via agente `git-commit-push`, cwd `addons/afr_qualificacao`, arquivos:
`views/relatorio_views.xml views/relatorio_cycle_views.xml models/relatorio.py models/relatorio_os.py __manifest__.py tests/test_relatorio_model.py`
Mensagem:

```
feat(relatorio): add final report views, OS buttons and menu (16.0.8.0.0)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

## Self-Review (feito pelo autor do plano)

**Cobertura do spec / contrato "P1 produz":**
- §4.1 campos P1: todos na Task 1, e os O2M de dados de campo na Task 2. `template_id`, `block_ids`, `anexo_ids`, `aprovacao_ids`, `achado_ids`, `emissao_ids`, `current_emissao_id` e `minuta_attachment_id` ficam de fora (P3–P5, conforme o índice).
- `name`/`_doc_number`: Task 1. `unique(os_id, equipment_id)`: Task 1.
- §4.2 checklist, indicador e leitura IB: Task 2. `_seed_checklist`: Task 2 (quem chama com as linhas do template é P3).
- §4.3 janela, `sensor_pos_ids`, `extracted_json` e "copiar do ciclo anterior": Task 3.
- §9 parcial: smart button, "Gerar relatórios", form com header/statusbar e abas `page_dados_campo`/`page_ciclos`, menu `menu_afr_relatorio_final`: Task 4.
- `proxima_qualificacao` = fim dos ensaios + 12 meses. O spec diz "emissão + 12 meses"; P4 pode trocar o `depends` quando existir data de emissão. Está anotado no `help` do campo.

**Placeholders:** nenhum. Todo passo de código tem o código completo.

**Consistência de nomes:** `action_generate_relatorios` (recordset), `action_generate_relatorios_open`/`action_view_relatorios_finais` (dict), `_relatorio_final_equipments`, `_relatorio_final_default_dates`, `_seed_checklist`, `_doc_number`, `action_copy_sensor_pos_from_previous`, `_previous_cycle_with_sensor_pos`, `action_open_relatorio_cycle`, `sensor_pos_count`, `os_collect_item_ids`. Cada nome é usado igual nos modelos, nas views e nos testes.

**Contagem de testes esperada:** Task 1 = 17, Task 2 = +8 (25), Task 3 = +10 (35), Task 4 = +7 (42).
