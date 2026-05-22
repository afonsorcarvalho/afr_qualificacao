"""Testes F8.1 — camada de dados da Proposta LEGO.

Cobre:
- specs técnicas adicionadas a cycle.type / malha.type / config.template;
- modelos novos proposal.section / proposal.template(.line) / proposal.optional;
- constraint de bloco estático exigir seção;
- seeds carregados (biblioteca de blocos + template default + opcionais).
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProposalCatalog(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["product.product"].create({
            "name": "Serviço Teste Proposta", "type": "service",
        })

    # --- specs técnicas nos catálogos existentes ---------------------------

    def test_cycle_type_carries_technical_specs(self):
        """cycle.type aceita temperatura, tempo, tipo de carga e dias."""
        cycle = self.env["afr.qualificacao.cycle.type"].create({
            "name": "Ciclo Teste Specs",
            "product_id": self.service.id,
            "temperature": "134°C",
            "duration": "7 min",
            "load_type": "com_carga",
            "estimated_days": 1.5,
        })
        self.assertEqual(cycle.temperature, "134°C")
        self.assertEqual(cycle.duration, "7 min")
        self.assertEqual(cycle.load_type, "com_carga")
        self.assertEqual(cycle.estimated_days, 1.5)

    def test_malha_type_carries_technical_specs(self):
        """malha.type aceita faixa nominal e dias estimados."""
        sensor = self.env["afr.qualificacao.sensor.kind"].search([], limit=1)
        malha = self.env["afr.qualificacao.malha.type"].create({
            "name": "Malha Teste Specs",
            "product_id": self.service.id,
            "sensor_kind_id": sensor.id,
            "range_spec": "0–150 °C",
            "estimated_days": 0.5,
        })
        self.assertEqual(malha.range_spec, "0–150 °C")
        self.assertEqual(malha.estimated_days, 0.5)

    def test_config_template_carries_price_suggestion(self):
        """config.template aceita preço base, dias e moeda derivada da empresa."""
        tpl = self.env["afr.qualificacao.config.template"].create({
            "name": "Pacote Teste Preço",
            "price_base": 2400.0,
            "estimated_days": 1.5,
        })
        self.assertEqual(tpl.price_base, 2400.0)
        self.assertEqual(tpl.estimated_days, 1.5)
        self.assertEqual(tpl.currency_id, self.env.company.currency_id)

    # --- modelo proposal.section ------------------------------------------

    def test_proposal_section_create_and_name_get(self):
        """section guarda corpo HTML e exibe 'CODE — Name'."""
        section = self.env["afr.proposal.section"].create({
            "code": "SEC-TEST",
            "name": "Bloco de Teste",
            "category": "objetivo",
            "body": "<p>Olá {{ partner.name }}</p>",
        })
        self.assertIn("{{ partner.name }}", section.body)
        self.assertEqual(section.display_name, "SEC-TEST — Bloco de Teste")

    # --- modelo proposal.template -----------------------------------------

    def test_template_static_line_requires_section(self):
        """Bloco do tipo 'static' sem seção viola a constraint."""
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl Teste"})
        with self.assertRaises(ValidationError):
            self.env["afr.proposal.template.line"].create({
                "template_id": tpl.id,
                "block_kind": "static",
            })

    def test_template_dynamic_line_needs_no_section(self):
        """Bloco dinâmico (ex: financial) não exige seção."""
        tpl = self.env["afr.proposal.template"].create({"name": "Tpl Teste 2"})
        line = self.env["afr.proposal.template.line"].create({
            "template_id": tpl.id,
            "block_kind": "financial",
        })
        self.assertFalse(line.section_id)
        self.assertEqual(line.block_kind, "financial")

    # --- modelo proposal.optional -----------------------------------------

    def test_proposal_optional_create(self):
        """optional guarda tipo, produto e preço padrão."""
        opt = self.env["afr.proposal.optional"].create({
            "code": "OPT-TEST",
            "name": "Opcional de Teste",
            "kind": "folder",
            "product_id": self.service.id,
            "default_price": 200.0,
        })
        self.assertEqual(opt.kind, "folder")
        self.assertEqual(opt.default_price, 200.0)

    def test_proposal_optional_rejects_non_service_product(self):
        """optional só aceita produto de serviço."""
        consu = self.env["product.product"].create({
            "name": "Consumível Teste", "type": "consu",
        })
        with self.assertRaises(ValidationError):
            self.env["afr.proposal.optional"].create({
                "name": "Opcional Inválido",
                "kind": "custom",
                "product_id": consu.id,
            })

    # --- seeds -------------------------------------------------------------

    def test_seed_section_library_loaded(self):
        """Biblioteca de blocos default foi semeada."""
        objetivo = self.env.ref("afr_qualificacao.proposal_section_objetivo")
        self.assertEqual(objetivo.category, "objetivo")
        sections = self.env["afr.proposal.section"].search([])
        self.assertGreaterEqual(len(sections), 14)

    def test_seed_default_template_loaded(self):
        """Template default 'Proposta LabQuali' tem os blocos na ordem."""
        tpl = self.env.ref("afr_qualificacao.proposal_template_labquali")
        self.assertEqual(len(tpl.line_ids), 18)
        first = tpl.line_ids.sorted("sequence")[0]
        self.assertEqual(first.block_kind, "static")
        self.assertEqual(
            first.section_id,
            self.env.ref("afr_qualificacao.proposal_section_objetivo"),
        )

    def test_seed_optionals_loaded(self):
        """Opcionais default (pasta, viagem, diária) foram semeados."""
        kinds = self.env["afr.proposal.optional"].search([]).mapped("kind")
        self.assertIn("folder", kinds)
        self.assertIn("travel", kinds)
        self.assertIn("extra_day", kinds)
