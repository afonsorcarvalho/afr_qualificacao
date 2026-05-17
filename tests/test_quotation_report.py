"""Testes do relatório PDF de cotação dedicado (quotation_template.xml).

Valida:
- `has_qualif_lines` compute correto (True com linhas managed, False sem)
- `qualif_standard_ids` agrega normas únicas das linhas
- `_qualif_equipment_summary()` agrupa por equipamento → tipo qualif
- `_qualif_type_descriptions()` retorna descritivos por tipo presente
- Render PDF não vazio quando SO tem qualif (template inherit ativo)
- Render PDF não vazio quando SO regular (fallback template Odoo)
"""

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestQuotationReport(AfrQualificacaoTestCommon):
    """Cotação PDF dedicada — agregações + render."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Norma técnica de teste
        Standard = cls.env["afr.qualificacao.standard"]
        cls.std_iso = Standard.create({
            "code": "TEST-ISO-1",
            "name": "Norma de Teste ISO",
            "organism": "ISO",
            "sequence": 10,
        })
        cls.std_anvisa = Standard.create({
            "code": "TEST-ANVISA-2",
            "name": "Norma de Teste ANVISA",
            "organism": "ANVISA",
            "sequence": 20,
        })
        # Vincula normas a cycle_type e malha_type
        cls.cycle_cmax.standard_ids = [(6, 0, [cls.std_iso.id])]
        cls.cycle_cmin.standard_ids = [(6, 0, [cls.std_iso.id, cls.std_anvisa.id])]
        cls.malha_temp.standard_ids = [(6, 0, [cls.std_anvisa.id])]

    # ------------------------------------------------------------------
    # Helpers de fixture
    # ------------------------------------------------------------------
    def _make_quote_with_qualif(self):
        """Cria SO com 2 equipamentos × QI + QD (2 ciclos) + Calib."""
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
        })
        SOL = self.env["sale.order.line"]
        # equip1: QI + QD (CMax x2) + QD (CMin x3) + Calib (Temp x2)
        SOL.create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "is_qualificacao_managed": True,
            "qualification_type": "installation",
            "equipment_id": self.equip1.id,
            "product_uom_qty": 1,
            "price_unit": 1000,
        })
        SOL.create({
            "order_id": so.id,
            "product_id": self.product_qd_cmax.id,
            "is_qualificacao_managed": True,
            "qualification_type": "performance",
            "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmax.id,
            "product_uom_qty": 2,
            "price_unit": 700,
        })
        SOL.create({
            "order_id": so.id,
            "product_id": self.product_qd_cmin.id,
            "is_qualificacao_managed": True,
            "qualification_type": "performance",
            "equipment_id": self.equip1.id,
            "cycle_type_id": self.cycle_cmin.id,
            "product_uom_qty": 3,
            "price_unit": 500,
        })
        SOL.create({
            "order_id": so.id,
            "product_id": self.product_malha_temp.id,
            "is_qualificacao_managed": True,
            "qualification_type": "calibration",
            "equipment_id": self.equip1.id,
            "malha_type_id": self.malha_temp.id,
            "product_uom_qty": 2,
            "price_unit": 400,
        })
        # equip2: só QI
        SOL.create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "is_qualificacao_managed": True,
            "qualification_type": "installation",
            "equipment_id": self.equip2.id,
            "product_uom_qty": 1,
            "price_unit": 1000,
        })
        return so

    def _make_regular_quote(self):
        """SO sem linhas managed — qualquer produto avulso."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "product_uom_qty": 1,
            "price_unit": 100,
        })
        return so

    # ------------------------------------------------------------------
    # has_qualif_lines
    # ------------------------------------------------------------------
    def test_has_qualif_lines_true_when_managed_lines_present(self):
        so = self._make_quote_with_qualif()
        self.assertTrue(so.has_qualif_lines)

    def test_has_qualif_lines_false_for_regular_so(self):
        so = self._make_regular_quote()
        self.assertFalse(so.has_qualif_lines)

    def test_has_qualif_lines_false_for_empty_so(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertFalse(so.has_qualif_lines)

    # ------------------------------------------------------------------
    # qualif_standard_ids
    # ------------------------------------------------------------------
    def test_qualif_standard_ids_aggregates_unique(self):
        so = self._make_quote_with_qualif()
        codes = sorted(so.qualif_standard_ids.mapped("code"))
        # std_iso (cycle_cmax + cycle_cmin) + std_anvisa (cycle_cmin + malha_temp)
        # devem aparecer 1× cada
        self.assertEqual(codes, ["TEST-ANVISA-2", "TEST-ISO-1"])

    def test_qualif_standard_ids_empty_when_no_standards(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "is_qualificacao_managed": True,
            "qualification_type": "installation",
            "equipment_id": self.equip1.id,
            "product_uom_qty": 1,
        })
        self.assertFalse(so.qualif_standard_ids)

    # ------------------------------------------------------------------
    # _qualif_equipment_summary
    # ------------------------------------------------------------------
    def test_equipment_summary_groups_by_equipment(self):
        so = self._make_quote_with_qualif()
        summary = so._qualif_equipment_summary()
        equips = [s["equipment"] for s in summary]
        self.assertEqual(len(summary), 2)
        self.assertIn(self.equip1, equips)
        self.assertIn(self.equip2, equips)

    def test_equipment_summary_type_order_follows_selection(self):
        """QI deve vir antes de QD; QD antes de Calibração."""
        so = self._make_quote_with_qualif()
        summary = so._qualif_equipment_summary()
        equip1_entry = next(s for s in summary if s["equipment"] == self.equip1)
        codes = [t["code"] for t in equip1_entry["types"]]
        # Ordem: installation < performance < calibration
        self.assertEqual(
            codes,
            ["installation", "performance", "calibration"],
        )

    def test_equipment_summary_includes_items_with_qty(self):
        so = self._make_quote_with_qualif()
        summary = so._qualif_equipment_summary()
        equip1_entry = next(s for s in summary if s["equipment"] == self.equip1)
        qd_block = next(t for t in equip1_entry["types"] if t["code"] == "performance")
        item_names = [i["name"] for i in qd_block["items"]]
        # Helper agora usa line.name (descrição Sale, default = nome produto).
        self.assertIn("Test Ciclo CMax", item_names)
        self.assertIn("Test Ciclo CMin", item_names)
        # Qtys
        item_qtys = {i["name"]: i["qty"] for i in qd_block["items"]}
        self.assertEqual(item_qtys["Test Ciclo CMax"], 2)
        self.assertEqual(item_qtys["Test Ciclo CMin"], 3)

    def test_equipment_summary_subtotal_sums_lines(self):
        so = self._make_quote_with_qualif()
        summary = so._qualif_equipment_summary()
        equip1_entry = next(s for s in summary if s["equipment"] == self.equip1)
        # 1×1000 (QI) + 2×700 (CMax) + 3×500 (CMin) + 2×400 (Calib) = 4700
        # NB: price_subtotal pode aplicar impostos; sem taxes configurados,
        # vale price_unit × qty
        self.assertAlmostEqual(equip1_entry["subtotal"], 4700.0, places=2)

    def test_equipment_summary_skips_non_managed_lines(self):
        so = self._make_quote_with_qualif()
        # Linha avulsa: não-managed, sem equipment
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qo.id,
            "product_uom_qty": 1,
            "price_unit": 999,
        })
        summary = so._qualif_equipment_summary()
        # Continua agrupando só 2 equipamentos (não cria 3º bucket)
        self.assertEqual(len(summary), 2)

    # ------------------------------------------------------------------
    # _qualif_type_descriptions
    # ------------------------------------------------------------------
    def test_type_descriptions_returns_present_types_only(self):
        so = self._make_quote_with_qualif()
        descs = so._qualif_type_descriptions()
        codes = [d["code"] for d in descs]
        # Presentes: installation, performance, calibration
        self.assertIn("installation", codes)
        self.assertIn("performance", codes)
        self.assertIn("calibration", codes)
        # Não-presente: operational, software
        self.assertNotIn("operational", codes)
        self.assertNotIn("software", codes)

    def test_type_descriptions_uses_cycle_description_when_available(self):
        """Quando cycle_type tem description, deve aparecer no descritivo."""
        self.cycle_cmax.description = "Detalhe técnico ciclo CMax XYZ"
        so = self._make_quote_with_qualif()
        descs = so._qualif_type_descriptions()
        perf = next(d for d in descs if d["code"] == "performance")
        self.assertIn("XYZ", perf["description"])

    def test_type_descriptions_fallback_to_default_when_no_specific(self):
        """Sem description em cycle/malha, usa fallback hardcoded."""
        # installation: linhas não têm cycle/malha → usa fallback
        so = self._make_quote_with_qualif()
        descs = so._qualif_type_descriptions()
        inst = next(d for d in descs if d["code"] == "installation")
        # Fallback hardcoded contém "Verificação documentada"
        self.assertIn("Verificação documentada", inst["description"])

    # ------------------------------------------------------------------
    # Render PDF
    # ------------------------------------------------------------------
    def test_render_pdf_returns_non_empty_bytes_with_qualif(self):
        """Render do report padrão Odoo deve passar pelo inherit + gerar PDF."""
        so = self._make_quote_with_qualif()
        report = self.env.ref("sale.action_report_saleorder")
        pdf, _content_type = report._render_qweb_pdf(report.report_name, so.ids)
        self.assertTrue(pdf)
        self.assertGreater(len(pdf), 1000, "PDF gerado parece vazio/curto")

    def test_render_pdf_returns_non_empty_bytes_for_regular_so(self):
        """SO sem qualif: fallback template Odoo padrão também deve renderizar."""
        so = self._make_regular_quote()
        report = self.env.ref("sale.action_report_saleorder")
        pdf, _content_type = report._render_qweb_pdf(report.report_name, so.ids)
        self.assertTrue(pdf)
        self.assertGreater(len(pdf), 500)

    def test_render_html_contains_proposta_tecnico_comercial(self):
        """Render HTML do template qualif deve conter título da capa."""
        so = self._make_quote_with_qualif()
        report = self.env.ref("sale.action_report_saleorder")
        html, _content_type = report._render_qweb_html(report.report_name, so.ids)
        html_str = html.decode("utf-8") if isinstance(html, bytes) else html
        self.assertIn("PROPOSTA TÉCNICO-COMERCIAL", html_str)
        self.assertIn("Qualificação de Equipamentos", html_str)

    def test_render_html_regular_so_no_qualif_marker(self):
        """SO sem qualif: HTML NÃO deve ter título dedicado."""
        so = self._make_regular_quote()
        report = self.env.ref("sale.action_report_saleorder")
        html, _content_type = report._render_qweb_html(report.report_name, so.ids)
        html_str = html.decode("utf-8") if isinstance(html, bytes) else html
        self.assertNotIn("PROPOSTA TÉCNICO-COMERCIAL", html_str)

    def test_render_html_lists_standards(self):
        """HTML deve listar códigos das normas agregadas."""
        so = self._make_quote_with_qualif()
        report = self.env.ref("sale.action_report_saleorder")
        html, _content_type = report._render_qweb_html(report.report_name, so.ids)
        html_str = html.decode("utf-8") if isinstance(html, bytes) else html
        self.assertIn("TEST-ISO-1", html_str)
        self.assertIn("TEST-ANVISA-2", html_str)
