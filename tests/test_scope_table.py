# -*- coding: utf-8 -*-
"""Escopo por equipamento como tabela única — camada de agregação."""

from odoo.tests.common import tagged
from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install")
class TestScopeLinesAndHours(AfrQualificacaoTestCommon):

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _section(self, so, equip, work_hours=8.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "display_type": "line_section",
            "name": equip.display_name,
            "is_qualificacao_managed": True,
            "equipment_id": equip.id,
            "work_hours_per_day": work_hours,
        })

    def _cycle_line(self, so, equip, qtype, part, qty, hours, price):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.cycle_cmax.product_id.id,
            "name": "Ciclo",
            "is_qualificacao_managed": True,
            "qualification_type": qtype,
            "part": part,
            "equipment_id": equip.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": qty,
            "estimated_hours": hours,
            "product_uom_qty": qty * hours,
            "price_unit": price,
        })

    def test_scope_lines_match_rateio_base(self):
        """O conjunto do escopo é exatamente o do rateio."""
        so = self._so()
        section = self._section(so, self.equip1)
        firme = self._cycle_line(so, self.equip1, "performance", False, 3, 2.0, 200.0)
        opcional = self._cycle_line(so, self.equip1, "performance", False, 1, 1.0, 500.0)
        opcional.write({"is_proposal_optional": True, "optional_accepted": True})
        declinada = self._cycle_line(so, self.equip1, "installation", "01", 1, 1.0, 900.0)
        declinada.write({"part01_declined": True, "product_uom_qty": 0.0})

        scope = so._qualif_scope_lines(self.equip1)
        self.assertEqual(scope, section._rateio_base_lines())
        self.assertIn(firme, scope)
        self.assertNotIn(opcional, scope)
        self.assertNotIn(declinada, scope)
        self.assertNotIn(section, scope)

    def test_scope_lines_filter_by_type_and_part(self):
        so = self._so()
        self._section(so, self.equip1)
        qo2 = self._cycle_line(so, self.equip1, "operational", "02", 2, 1.0, 100.0)
        qd = self._cycle_line(so, self.equip1, "performance", False, 3, 1.0, 200.0)

        self.assertEqual(so._qualif_scope_lines(self.equip1, "operational", "02"), qo2)
        self.assertEqual(so._qualif_scope_lines(self.equip1, "performance", None), qd)
        self.assertFalse(so._qualif_scope_lines(self.equip1, "operational", "01"))

    def test_group_hours_uses_qualif_cycle_qty(self):
        so = self._so()
        self._section(so, self.equip1)
        lines = self._cycle_line(so, self.equip1, "performance", False, 3, 2.5, 200.0)
        self.assertEqual(so._qualif_group_hours(lines), 7.5)

    def test_days_round_up_to_next_half(self):
        so = self._so()
        self._section(so, self.equip1, work_hours=8.0)
        self.assertEqual(so._qualif_days_from_hours(4.0, self.equip1), 0.5)
        self.assertEqual(so._qualif_days_from_hours(4.1, self.equip1), 1.0)
        self.assertEqual(so._qualif_days_from_hours(8.0, self.equip1), 1.0)
        self.assertEqual(so._qualif_days_from_hours(25.6, self.equip1), 3.5)
        self.assertEqual(so._qualif_days_from_hours(0.0, self.equip1), 0.0)

    def test_days_respect_work_hours_per_day(self):
        so = self._so()
        self._section(so, self.equip1, work_hours=4.0)
        self.assertEqual(so._qualif_days_from_hours(4.0, self.equip1), 1.0)

    def test_days_label_uses_comma_as_decimal_separator(self):
        """pt-BR: vírgula, nunca ponto — mesmo para os múltiplos de 0,5."""
        so = self._so()
        self.assertEqual(
            so._qualif_days_label(0.0),
            "Previsão de 0,0 dia(s) de serviço")
        self.assertEqual(
            so._qualif_days_label(0.5),
            "Previsão de 0,5 dia(s) de serviço")
        self.assertEqual(
            so._qualif_days_label(5.5),
            "Previsão de 5,5 dia(s) de serviço")
        self.assertEqual(
            so._qualif_days_label(2.0),
            "Previsão de 2,0 dia(s) de serviço")


@tagged("post_install", "-at_install")
class TestScopeRef(AfrQualificacaoTestCommon):

    def _so_with_blocks(self):
        """SO com 2 blocos numerados: SEC-QI (nº 1) e SEC-QO (nº 2)."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        Block = self.env["afr.proposal.block"]
        self.sec_qi = self.env.ref("afr_qualificacao.proposal_section_qi")
        self.sec_qo = self.env.ref("afr_qualificacao.proposal_section_qo")
        self.blk_qi = Block.create({
            "sale_order_id": so.id, "block_kind": "static",
            "section_id": self.sec_qi.id, "sequence": 10, "included": True,
        })
        self.blk_qo = Block.create({
            "sale_order_id": so.id, "block_kind": "static",
            "section_id": self.sec_qo.id, "sequence": 20, "included": True,
        })
        return so

    def test_ref_cites_block_number(self):
        so = self._so_with_blocks()
        ref = so._qualif_scope_ref("installation")
        self.assertIn("Conforme item 1", ref)
        self.assertIn(self.sec_qi.name, ref)

    def test_ref_second_block_gets_number_two(self):
        so = self._so_with_blocks()
        self.assertIn("Conforme item 2", so._qualif_scope_ref("operational"))

    def test_ref_without_block_degrades_to_topic_name(self):
        so = self._so_with_blocks()
        ref = so._qualif_scope_ref("performance")
        self.assertNotIn("Conforme item", ref)
        self.assertIn("Qualificação de Desempenho", ref)

    def test_ref_without_number_degrades(self):
        """show_number=False → numbering devolve '' → sem 'Conforme item'."""
        so = self._so_with_blocks()
        self.blk_qi.show_number = False
        ref = so._qualif_scope_ref("installation")
        self.assertNotIn("Conforme item", ref)
        self.assertIn(self.sec_qi.name, ref)

    def test_ref_unknown_type_never_returns_falsy(self):
        so = self._so_with_blocks()
        self.assertTrue(so._qualif_scope_ref(False))
        self.assertTrue(so._qualif_scope_ref("inexistente"))

    def test_both_degradations_use_the_same_topic_name(self):
        """Bloco ausente e bloco sem número citam o mesmo nome de tópico."""
        so = self._so_with_blocks()
        self.blk_qi.show_number = False
        sem_numero = so._qualif_scope_ref("installation")
        self.blk_qi.included = False
        sem_bloco = so._qualif_scope_ref("installation")
        self.assertEqual(sem_numero, sem_bloco)
        self.assertIn(self.sec_qi.name, sem_bloco)


@tagged("post_install", "-at_install")
class TestScopeTable(AfrQualificacaoTestCommon):

    def _so(self):
        return self.env["sale.order"].create({"partner_id": self.partner.id})

    def _section(self, so, equip, target=0.0):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "display_type": "line_section",
            "name": equip.display_name,
            "is_qualificacao_managed": True,
            "equipment_id": equip.id,
            "work_hours_per_day": 8.0,
            "equipment_target_price": target,
        })

    def _line(self, so, equip, qtype, part, price, hours=1.0, qty=1,
              cycle=None, malha=None, name="Item"):
        vals = {
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "name": name,
            "is_qualificacao_managed": True,
            "qualification_type": qtype,
            "part": part,
            "equipment_id": equip.id,
            "qualif_cycle_qty": qty,
            "estimated_hours": hours,
            "product_uom_qty": qty * hours,
            "price_unit": price / (qty * hours) if qty * hours else price,
        }
        if cycle:
            vals.update({
                "cycle_type_id": cycle.id,
                "product_id": cycle.product_id.id,
                "temperature": "134°C",
                "duration": "7 minutos",
            })
        if malha:
            vals.update({
                "malha_type_id": malha.id,
                "product_id": malha.product_id.id,
            })
        return self.env["sale.order.line"].create(vals)

    def _full_so(self):
        """SO no formato da proposta alvo: QI-1, QO-1, calib, QO-2, QD."""
        so = self._so()
        self.section = self._section(so, self.equip1)
        self._line(so, self.equip1, "installation", "01", 1500.0, hours=4.0,
                   name="Verificações QI")
        self._line(so, self.equip1, "operational", "01", 1700.0, hours=4.0,
                   name="Verificações QO")
        self._line(so, self.equip1, "calibration", "02", 400.0, hours=1.0,
                   malha=self.malha_temp, name="Calibração de Malha de Temperatura")
        self._line(so, self.equip1, "operational", "02", 500.0, hours=1.0, qty=3,
                   cycle=self.cycle_qo_test, name="Bowie Dick")
        self._line(so, self.equip1, "performance", False, 948.0, hours=1.0, qty=3,
                   cycle=self.cycle_cmax, name="Carga Mista")
        return so

    def test_three_groups_in_order(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        self.assertEqual([g["key"] for g in table["groups"]],
                         ["qi1", "qo1", "parte2"])

    def test_group_subtotal_labels(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        self.assertEqual(
            [g["subtotal_label"] for g in table["groups"]],
            ["Subtotal QI", "Subtotal QO", "Subtotal QD"],
        )

    def test_parte2_rows_order_and_kinds(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        parte2 = table["groups"][2]
        self.assertEqual([r["kind"] for r in parte2["rows"]],
                         ["list", "cycles", "cycles"])
        self.assertEqual(parte2["rows"][0]["title"],
                         "Calibração dos equipamentos de controle:")
        self.assertEqual(parte2["rows"][1]["title"],
                         "Execução dos ciclos sem carga")
        self.assertEqual(parte2["rows"][2]["title"],
                         "Execução dos ciclos com carga")

    def test_qi1_and_qo1_are_refs(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        self.assertEqual(table["groups"][0]["rows"][0]["kind"], "ref")
        self.assertTrue(table["groups"][0]["rows"][0]["ref"])
        self.assertEqual(table["groups"][1]["rows"][0]["kind"], "ref")

    def test_cycle_row_fields(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        cycles = table["groups"][2]["rows"][2]["cycles"]
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0]["qty"], 3)
        self.assertEqual(cycles[0]["name"], self.cycle_cmax.name)
        self.assertEqual(cycles[0]["temperature"], "134°C")
        self.assertEqual(cycles[0]["duration"], "7 minutos")
        self.assertTrue(table["groups"][2]["rows"][2]["time_label"])

    def test_group_subtotals_sum_to_equipment_subtotal(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        soma = sum(g["subtotal"] for g in table["groups"])
        self.assertAlmostEqual(soma, self.section.equipment_subtotal, places=2)

    def test_footer_days_is_sum_of_rounded_group_days(self):
        so = self._full_so()
        table = so._qualif_scope_table(self.equip1)
        self.assertAlmostEqual(
            table["footer"]["days"],
            sum(g["days"] for g in table["groups"]),
            places=2,
        )
        # QI 4h → 0,5 | QO 4h → 0,5 | parte2 (1+3+3=7h) → 1,0
        self.assertAlmostEqual(table["footer"]["days"], 2.0, places=2)

    def test_unit_price_uses_target_when_state_ok(self):
        """Alvo sub-centavo acima da soma: estado segue 'ok' e o impresso é o ALVO.

        A moeda padrão do ambiente de teste arredonda Monetary a 2 casas —
        um desvio de 0,004 escrito em `equipment_target_price` seria
        colapsado de volta para o valor do subtotal (mesmo float), tornando
        alvo e fallback indistinguíveis por construção (visto empiricamente:
        `write({"equipment_target_price": subtotal + 0.004})` guarda
        exatamente `subtotal`). Para tornar os dois caminhos numericamente
        diferentes preservando o estado 'ok' — que compara a 2 casas via
        `float_compare(..., precision_digits=2)`, hardcoded na produção —
        a moeda do teste é elevada para 4 casas só aqui, liberando o
        sub-centavo para sobreviver ao write sem afetar o estado.
        """
        so = self._full_so()
        self.company.currency_id.rounding = 0.0001
        subtotal = self.section.equipment_subtotal
        self.section.equipment_target_price = subtotal + 0.004
        self.assertEqual(self.section.equipment_target_state, "ok")
        table = so._qualif_scope_table(self.equip1)
        self.assertAlmostEqual(table["footer"]["unit_price"],
                               self.section.equipment_target_price, places=4)
        self.assertNotAlmostEqual(table["footer"]["unit_price"], subtotal,
                                  places=4)

    def test_unit_price_falls_back_when_target_drifts(self):
        so = self._full_so()
        self.section.equipment_target_price = 1.0  # desviado de propósito
        self.assertEqual(self.section.equipment_target_state, "drift")
        table = so._qualif_scope_table(self.equip1)
        self.assertAlmostEqual(table["footer"]["unit_price"],
                               self.section.equipment_subtotal, places=2)

    def test_group_subtotals_reconcile_with_leftovers_present(self):
        """Com tipo fora da matriz, a soma dos grupos ainda fecha com o rateio."""
        so = self._full_so()
        self._line(so, self.equip1, "software", False, 800.0, hours=2.0,
                   name="Validação de software")
        table = so._qualif_scope_table(self.equip1)
        soma = sum(g["subtotal"] for g in table["groups"])
        self.assertAlmostEqual(soma, self.section.equipment_subtotal, places=2)

    def test_no_line_is_counted_in_two_groups(self):
        """Partição exaustiva e sem sobreposição: cada linha aparece 1x."""
        so = self._full_so()
        self._line(so, self.equip1, "software", False, 800.0, hours=2.0,
                   name="Validação de software")
        table = so._qualif_scope_table(self.equip1)
        total_rows = sum(
            len(r.get("items") or r.get("cycles") or [1])
            for g in table["groups"] for r in g["rows"]
        )
        self.assertEqual(total_rows, len(so._qualif_scope_lines(self.equip1)))

    def test_unknown_type_becomes_its_own_group(self):
        so = self._full_so()
        self._line(so, self.equip1, "software", False, 800.0, hours=2.0,
                   name="Validação de software")
        table = so._qualif_scope_table(self.equip1)
        keys = [g["key"] for g in table["groups"]]
        self.assertIn("extra-software", keys)
        extra = table["groups"][keys.index("extra-software")]
        self.assertEqual(extra["rows"][0]["kind"], "list")
        self.assertIn("Validação de software", extra["rows"][0]["items"])

    def test_optional_and_declined_never_reach_the_table(self):
        so = self._full_so()
        opt = self._line(so, self.equip1, "performance", False, 999.0,
                         cycle=self.cycle_cmin, name="Ciclo opcional")
        opt.write({"is_proposal_optional": True, "optional_accepted": True})
        declined = self._line(so, self.equip1, "installation", "01", 1500.0,
                              hours=4.0, name="Verificação QI declinada")
        declined.write({"part01_declined": True, "product_uom_qty": 0.0})
        table = so._qualif_scope_table(self.equip1)
        nomes = [c["name"] for r in table["groups"][2]["rows"]
                 if r["kind"] == "cycles" for c in r["cycles"]]
        self.assertNotIn(self.cycle_cmin.name, nomes)
        # qi1 é kind "ref" (não lista items) — a checagem real é que a linha
        # declinada não entra no conjunto que alimenta o grupo/subtotal.
        self.assertEqual(
            len(so._qualif_scope_lines(self.equip1, "installation", "01")), 1)
        self.assertAlmostEqual(table["groups"][0]["subtotal"], 1500.0, places=2)

    def test_scope_tables_lists_every_equipment_with_scope(self):
        so = self._full_so()
        self._section(so, self.equip2)
        self._line(so, self.equip2, "performance", False, 300.0,
                   cycle=self.cycle_cmax, name="Ciclo eq2")
        tables = so._qualif_scope_tables()
        self.assertEqual([t["equipment"] for t in tables],
                         [self.equip1, self.equip2])


@tagged("post_install", "-at_install")
class TestProposalTotals(TestScopeTable):
    """Herda os fixtures de TestScopeTable (_full_so, _line, _section)."""

    def _extra(self, so, name, price):
        return self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "name": name,
            "product_uom_qty": 1.0,
            "price_unit": price,
        })

    def test_additional_lines_are_enumerated_by_name(self):
        so = self._full_so()
        self._extra(so, "Despesas de viagem, hospedagem e alimentação", 1000.0)
        self._extra(so, "Pasta impressa e envio correio", 400.0)
        adicionais = so._qualif_additional_lines()
        self.assertEqual(
            [a["name"] for a in adicionais],
            ["Despesas de viagem, hospedagem e alimentação",
             "Pasta impressa e envio correio"],
        )
        self.assertAlmostEqual(adicionais[0]["amount"], 1000.0, places=2)

    def test_accepted_optional_with_equipment_is_an_additional(self):
        """Rateio exclui opcional; se ele não virasse adicional, sumia."""
        so = self._full_so()
        opt = self._line(so, self.equip1, "performance", False, 700.0,
                         cycle=self.cycle_cmin, name="Ciclo extra opcional")
        opt.write({"is_proposal_optional": True, "optional_accepted": True})
        nomes = [a["name"] for a in so._qualif_additional_lines()]
        self.assertIn("Ciclo extra opcional", nomes)

    def test_declined_optional_is_not_listed(self):
        so = self._full_so()
        opt = self._line(so, self.equip1, "performance", False, 700.0,
                         cycle=self.cycle_cmin, name="Ciclo recusado")
        opt.write({"is_proposal_optional": True, "optional_accepted": False,
                   "product_uom_qty": 0.0})
        nomes = [a["name"] for a in so._qualif_additional_lines()]
        self.assertNotIn("Ciclo recusado", nomes)

    def test_pending_optional_with_qty_is_not_an_additional(self):
        """Opcional pendente com qty forçada (write direto) não vira adicional."""
        so = self._full_so()
        opt = self._line(so, self.equip1, "performance", False, 700.0,
                         cycle=self.cycle_cmin, name="Ciclo pendente")
        opt.write({"is_proposal_optional": True, "optional_accepted": False})
        # burla o invariante procedural: qty > 0 sem aceite
        opt.write({"product_uom_qty": 1.0})
        self.assertTrue(opt.price_subtotal)
        nomes = [a["name"] for a in so._qualif_additional_lines()]
        self.assertNotIn("Ciclo pendente", nomes)

    def test_declined_line_with_forced_subtotal_is_not_an_additional(self):
        """Linha declinada (Parte 01) com subtotal forçado ≠ 0 não vira adicional.

        Guard simétrico ao do opcional pendente: normalmente uma linha
        declinada tem qty=0 → subtotal 0 → já fora pelo filtro de
        is_zero(). O guard explícito cobre o caso em que esse invariante
        procedural é violado (write direto) — senão a linha apareceria ao
        mesmo tempo riscada na caixa "Itens Não Solicitados" E listada
        como item pago nos adicionais (contradição visual; o total geral
        não muda, o valor só trocaria de rótulo).
        """
        so = self._full_so()
        decl = self._line(so, self.equip1, "installation", "01", 900.0,
                          name="Verificação recusada")
        decl.write({"part01_declined": True})
        # burla o invariante procedural: qty > 0 sem declinar de fato a qty
        decl.write({"product_uom_qty": 1.0})
        self.assertTrue(decl.price_subtotal)
        nomes = [a["name"] for a in so._qualif_additional_lines()]
        self.assertNotIn("Verificação recusada", nomes)

    def test_sections_are_not_additionals(self):
        so = self._full_so()
        nomes = [a["name"] for a in so._qualif_additional_lines()]
        self.assertNotIn(self.equip1.display_name, nomes)

    def test_totals_reconcile_with_amount_untaxed(self):
        so = self._full_so()
        self._extra(so, "Despesas de viagem", 1000.0)
        totals = so._qualif_proposal_totals()
        self.assertAlmostEqual(totals["residual"], 0.0, places=2)
        self.assertAlmostEqual(
            totals["equip_total"] + sum(a["amount"] for a in totals["adicionais"]),
            totals["grand_total"], places=2,
        )

    def test_residual_absorbs_unaccounted_money(self):
        """Alvo desviado não pode fazer dinheiro sumir do total impresso."""
        so = self._full_so()
        self.section.equipment_target_price = self.section.equipment_subtotal
        # força drift artificial mexendo no alvo depois de 'ok'
        self.section.equipment_target_price = self.section.equipment_subtotal + 50.0
        totals = so._qualif_proposal_totals()
        self.assertAlmostEqual(
            totals["equip_total"]
            + sum(a["amount"] for a in totals["adicionais"])
            + totals["residual"],
            totals["grand_total"], places=2,
        )

    def test_no_additionals_yields_empty_list(self):
        so = self._full_so()
        self.assertEqual(so._qualif_proposal_totals()["adicionais"], [])

    def test_grand_total_html_lists_additionals(self):
        so = self._full_so()
        self._extra(so, "Pasta impressa e envio correio", 400.0)
        html = str(so._qualif_grand_total_html())
        self.assertIn("Total dos Serviços de Qualificação", html)
        self.assertIn("Pasta impressa e envio correio", html)
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)

    def test_grand_total_html_omits_breakdown_without_additionals(self):
        so = self._full_so()
        html = str(so._qualif_grand_total_html())
        self.assertNotIn("Total dos Serviços de Qualificação", html)
        self.assertIn("TOTAL GERAL DA PROPOSTA", html)
