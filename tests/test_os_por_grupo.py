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
