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

    def test_sufixo_ocupado_e_pulado(self):
        """OS -1 já existe com o nome (não vinculada à cotação) → pula p/ -2."""
        so = self._so_dois_equipamentos()
        so.write({"name": "C26-06-0004"})
        self.env["afr.qualificacao.os"].create({
            "name": "OS26-06-0004-1",
            "company_id": so.company_id.id,
        })
        pending = so._pending_qualif_lines().mapped("equipment_id")
        vals = so._prepare_qualificacao_os_values(pending[:1], pending)
        self.assertEqual(vals["name"], "OS26-06-0004-2")

    def test_sequencia_normal_com_os_ja_vinculadas(self):
        """N OS já vinculadas à cotação → próximo nome é -{N+1}."""
        so = self._so_dois_equipamentos()
        so.write({"name": "C26-06-0005"})
        self.env["afr.qualificacao.os"].create({
            "name": "OS26-06-0005-1",
            "company_id": so.company_id.id,
            "sale_order_id": so.id,
        })
        pending = so._pending_qualif_lines().mapped("equipment_id")
        vals = so._prepare_qualificacao_os_values(pending[:1], pending)
        self.assertEqual(vals["name"], "OS26-06-0005-2")

    def test_fallback_nome_sem_prefixo_c(self):
        """Cotação sem nome C... não recebe chave 'name' (ir.sequence resolve)."""
        so = self._so_dois_equipamentos()
        so.write({"name": "Novo"})
        pending = so._pending_qualif_lines().mapped("equipment_id")
        vals = so._prepare_qualificacao_os_values(pending, pending)
        self.assertNotIn("name", vals)

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
