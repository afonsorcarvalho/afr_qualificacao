"""Setup compartilhado dos testes do catálogo de serviços (cotação multi-serviço)."""

from .common import AfrQualificacaoTestCommon


class AfrServicoTestCommon(AfrQualificacaoTestCommon):
    """Fixtures: 2 grupos de serviço (calibração, NR-13) + 3 serviços.

    Herda `cls.partner` da base de qualificação.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env["product.product"]
        Grupo = cls.env["afr.servico.grupo"]
        Servico = cls.env["afr.servico"]

        cls.group_calib = Grupo.create({
            "name": "Calibração de Instrumentos",
            "sequence": 10,
            "unit_label": "instrumento",
        })
        cls.group_nr13 = Grupo.create({
            "name": "NR-13",
            "sequence": 20,
        })

        def _product(name, price):
            return Product.create({
                "name": name, "type": "service",
                "invoice_policy": "delivery", "list_price": price,
            })

        cls.svc_seladora = Servico.create({
            "name": "Test Calibração Seladora",
            "group_id": cls.group_calib.id,
            "product_id": _product("Test Svc Seladora", 120).id,
            "estimated_hours": 0.5,
            "procedure_code": "QPC-008",
        })
        cls.svc_incubadora = Servico.create({
            "name": "Test Calibração Incubadora",
            "group_id": cls.group_calib.id,
            "product_id": _product("Test Svc Incubadora", 180).id,
            "estimated_hours": 1.0,
        })
        cls.svc_nr13 = Servico.create({
            "name": "Test Inspeção NR-13",
            "group_id": cls.group_nr13.id,
            "product_id": _product("Test Svc NR13", 2400).id,
            "estimated_hours": 8.0,
        })

    @classmethod
    def _make_order(cls, partner=None):
        """Cotação (sale.order) em rascunho para `partner` (default `cls.partner`)."""
        return cls.env["sale.order"].create({
            "partner_id": (partner or cls.partner).id,
        })

    @classmethod
    def _add_service(cls, order, service, qty, unit_price=None):
        """Cria uma linha de serviço (via `_service_line_vals`) em `order`."""
        vals = cls.env["sale.order.line"]._service_line_vals(
            service, qty, unit_price=unit_price,
        )
        vals["order_id"] = order.id
        return cls.env["sale.order.line"].create(vals)
