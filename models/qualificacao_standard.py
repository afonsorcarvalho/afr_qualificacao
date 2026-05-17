"""Catálogo de Normas Aplicáveis em qualificações e calibrações.

Cada norma (ex: ISO 17025, FDA 21 CFR Part 11, ANVISA RDC 658) é
referenciada por:
- `cycle_type.standard_ids` — normas atendidas pelo ciclo QD
- `malha_type.standard_ids` — normas atendidas pela malha de calibração

A `sale.order` agrega `qualif_standard_ids` (M2M únicas das linhas) para
listar normas aplicáveis ao escopo total da cotação no relatório PDF.

Inspirado no campo livre que comerciais escreviam à mão em propostas —
formaliza estrutura para reuso e impressão consistente.
"""

from odoo import fields, models


class AfrQualificacaoStandard(models.Model):
    """Norma técnica/regulatória aplicável a qualificações e calibrações."""

    _name = "afr.qualificacao.standard"
    _description = "Norma Aplicável a Qualificação/Calibração"
    _order = "sequence, code, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Nome completo da norma (ex: 'Boas Práticas de Laboratório').",
    )
    code = fields.Char(
        required=True,
        help="Código curto/referência (ex: 'ISO 17025', 'ANVISA RDC 658/2022').",
    )
    organism = fields.Char(
        string="Organismo Emissor",
        help="Entidade emissora (ex: ABNT, FDA, ANVISA, ISO, ISPE).",
    )
    description = fields.Text(
        translate=True,
        help="Resumo do escopo da norma para exibição em propostas técnicas.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        (
            "code_company_unique",
            "unique(code, company_id)",
            "Código da norma deve ser único por empresa.",
        ),
    ]

    def name_get(self):
        """Display 'CODE — Name' para facilitar identificação em M2M widgets."""
        result = []
        for record in self:
            if record.code and record.name and record.code != record.name:
                label = "%s — %s" % (record.code, record.name)
            else:
                label = record.name or record.code or ""
            result.append((record.id, label))
        return result
