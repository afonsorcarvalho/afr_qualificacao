"""Fluxo 1 cotação : N OS de qualificação por grupo de equipamentos."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestOsPorGrupo(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Terceiro equipamento p/ testes de N-OS (equip1/equip2 já existem
        # em AfrQualificacaoTestCommon.setUpClass) — mesmo padrão do setUp.
        cls.equip3 = cls.env["engc.equipment"].create({
            "client_id": cls.partner.id,
            "category_id": cls.category.id,
            "model": "TestModel3", "serial_number": "TSN-003",
            "means_of_aquisition_id": cls.means.id,
            "location_id": cls.location.id,
            "marca_id": cls.marca.id,
        })
        # Um quarto equipamento, nunca colocado em nenhuma SO destes testes —
        # usado só para provar que o wizard rejeita seleção fora do pool.
        cls.equip4 = cls.env["engc.equipment"].create({
            "client_id": cls.partner.id,
            "category_id": cls.category.id,
            "model": "TestModel4", "serial_number": "TSN-004",
            "means_of_aquisition_id": cls.means.id,
            "location_id": cls.location.id,
            "marca_id": cls.marca.id,
        })

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

    def test_wizard_rejeita_equipamento_fora_do_pool(self):
        """Equipamento que nunca esteve nesta cotação (equip4) também cai
        no guard de revalidação — mesmo caminho de código do equipamento
        já gerado, cobrindo a restrição de pool que o domínio do XML
        implementa (não exercitável por teste unitário)."""
        so = self._so_tres_equipamentos()
        so.action_confirm()
        fora_do_pool = so.equipamentos_sem_os_ids[:1] | self.equip4
        with self.assertRaises(UserError):
            self._gerar(so, fora_do_pool)

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
                    "cycle_type_id": self.cycle_cmax.id, "qty": 2,
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

    def test_wizard_nunca_reusa_os_existente_da_cotacao(self):
        """Cada execução do wizard cria uma OS NOVA — nunca reaproveita uma
        OS já vinculada à cotação (comportamento do antigo
        `_create_qualificacoes_from_lines`, removido nesta task).

        Gera uma OS parcial, depois gera a segunda, e confirma: a segunda
        é um registro com id diferente da primeira, e a primeira não ganhou
        qualificações da segunda leva.
        """
        so = self._so_tres_equipamentos()
        so.action_confirm()
        os1 = self._gerar(so, so.equipamentos_sem_os_ids[:1])
        os1_qualif_ids_antes = os1.qualificacao_ids.ids
        os2 = self._gerar(so, so.equipamentos_sem_os_ids)
        self.assertNotEqual(os1.id, os2.id)
        self.assertEqual(os1.qualificacao_ids.ids, os1_qualif_ids_antes)
        self.assertEqual(so.qualificacao_os_count, 2)

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

    def test_recompute_apos_aceitar_opcional_pos_confirmacao(self):
        """Aceitar um opcional após a SO confirmada deve recomputar os
        campos de pendência — regressão do depends incompleto.
        """
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create({"sale_order_id": so.id})
        wiz.equipment_line_ids = [(0, 0, {
            "equipment_id": self.equip1.id, "do_qi": True,
        })]
        self.env["afr.qualificacao.configurator.optional.qualif"].create({
            "wizard_id": wiz.id, "equipment_id": self.equip2.id,
            "qualification_type": "performance",
            "cycle_type_id": self.cycle_cmax.id, "qty": 1,
            "estimated_hours": 1.0, "accepted": False,
        })
        wiz.action_apply()

        self._confirm_and_generate_os(so)
        self.assertFalse(so.equipamentos_sem_os_ids)
        self.assertFalse(so.pode_gerar_os)

        opt_line = so.order_line.filtered(
            lambda l: l.is_proposal_optional and l.equipment_id == self.equip2
        )
        self.assertTrue(opt_line)
        opt_line.optional_accepted = True

        self.assertEqual(so.equipamentos_sem_os_ids, self.equip2)
        self.assertTrue(so.pode_gerar_os)
