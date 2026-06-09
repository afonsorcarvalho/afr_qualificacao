"""Verifica remoção de step/deviation e presença da aba Coletas."""

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestRemoveModelsColetas(TransactionCase):

    def test_step_deviation_models_removed(self):
        self.assertNotIn("afr.qualificacao.step", self.env)
        self.assertNotIn("afr.qualificacao.deviation", self.env)

    def test_qualif_fields_removed(self):
        fields = self.env["afr.qualificacao"]._fields
        for f in ("step_ids", "deviation_ids", "step_count", "deviation_count"):
            self.assertNotIn(f, fields)

    def test_collect_item_ids_present(self):
        self.assertIn("collect_item_ids", self.env["afr.qualificacao"]._fields)
