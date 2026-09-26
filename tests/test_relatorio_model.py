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

    def test_generate_skips_equipment_with_only_cancelled_qualifs(self):
        """Controller ruling / spec §12: equipamento cujas qualificações na
        OS estão TODAS canceladas não deve gerar um relatório final vazio."""
        equip3 = self._make_equip("TSN-CANC")
        q3 = self._make_qualif(self.os, equip3, "installation")
        q3.write({"state": "cancelled"})
        rels = self.os.action_generate_relatorios()
        self.assertNotIn(equip3, rels.mapped("equipment_id"))
        self.assertFalse(self._rel_for(self.os, equip3))
        # os outros 2 equipamentos (com qualificação ativa) são gerados normalmente.
        self.assertEqual(len(rels), 2)

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

    def _make_usuario(self, login):
        """Usuário do grupo `group_afr_qualificacao_user`.

        Os botões de header desta task têm `groups=...`: o postprocess do
        `get_view` remove o nó do arch para quem não tem o grupo — inclusive
        o superusuário dos testes, que não tem grupos de aplicação. Por isso
        os testes de arch abaixo chamam `get_view` como Usuário, não como
        `self.env` puro.
        """
        return self.env["res.users"].create({
            "name": "Usuário Arch %s" % login,
            "login": login,
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("afr_qualificacao.group_afr_qualificacao_user").id,
            ])],
        })

    def test_os_form_has_relatorio_final_buttons(self):
        usuario = self._make_usuario("usuario.arch.os.test")
        view_id = self.env.ref("afr_qualificacao.view_afr_qualificacao_os_form").id
        arch = self.env["afr.qualificacao.os"].with_user(usuario).get_view(
            view_id, view_type="form",
        )["arch"]
        self.assertIn("action_view_relatorios_finais", arch)
        self.assertIn("action_generate_relatorios_open", arch)

    def test_cycle_form_has_copy_button(self):
        usuario = self._make_usuario("usuario.arch.cycle.test")
        view_id = self.env.ref("afr_qualificacao.view_afr_qualificacao_cycle_form").id
        arch = self.env["afr.qualificacao.cycle"].with_user(usuario).get_view(
            view_id, view_type="form",
        )["arch"]
        self.assertIn("action_copy_sensor_pos_from_previous", arch)
        self.assertIn('name="sensor_pos_ids"', arch)

    def test_menu_exists(self):
        menu = self.env.ref("afr_qualificacao.menu_afr_relatorio_final")
        self.assertEqual(
            menu.parent_id, self.env.ref("afr_qualificacao.menu_afr_qualificacao_root")
        )
