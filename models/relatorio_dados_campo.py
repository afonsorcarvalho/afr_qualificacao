# -*- coding: utf-8 -*-
"""Dados de campo do Relatório Final (P1, 16.0.8.0.0).

Filhos de `afr.qualificacao.relatorio` digitados pelo escritório a partir do
que o técnico trouxe de campo (fase 1 não altera o PWA — spec D6):
checklist de instalação (QI), indicadores biológicos/químicos usados e as
leituras de IB por ciclo.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AfrRelatorioChecklist(models.Model):
    """Item do checklist de instalação (QI) do relatório."""

    _name = "afr.relatorio.checklist"
    _description = "Checklist do Relatório Final"
    _order = "relatorio_id, sequence, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio",
        string="Relatório",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    grupo = fields.Char(help='Agrupador, ex.: "Instalações elétricas".')
    descricao = fields.Char(string="Descrição", required=True)
    status = fields.Selection(
        [
            ("aprovado", "Aprovado"),
            ("reprovado", "Reprovado"),
            ("na", "N/A"),
        ],
        help="Vazio = ainda não avaliado.",
    )
    comentario = fields.Char(string="Comentário")


class AfrRelatorioIndicador(models.Model):
    """Indicador biológico ou químico usado nos ensaios."""

    _name = "afr.relatorio.indicador"
    _description = "Indicador do Relatório Final"
    _order = "relatorio_id, tipo, id"
    _rec_name = "lote"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio",
        string="Relatório",
        required=True,
        ondelete="cascade",
        index=True,
    )
    tipo = fields.Selection(
        [("biologico", "Biológico"), ("quimico", "Químico")],
        required=True,
        default="biologico",
    )
    marca = fields.Char()
    modelo_tipo = fields.Char(
        string="Modelo / tipo",
        help='Ex.: "Geobacillus stearothermophilus", "Type 5".',
    )
    lote = fields.Char()
    validade = fields.Date()
    valor_d = fields.Float(string="Valor D (min)")
    populacao = fields.Char(
        string="População",
        help='Texto livre, ex.: "1,7 x 10^6".',
    )
    evidencia_collect_item_id = fields.Many2one(
        "afr.qualificacao.collect.item",
        string="Evidência (foto da bula)",
        ondelete="set null",
    )

    def name_get(self):
        tipos = dict(self._fields["tipo"].selection)
        return [
            (r.id, "%s — lote %s" % (tipos.get(r.tipo, ""), r.lote or "?"))
            for r in self
        ]


class AfrRelatorioLeituraIb(models.Model):
    """Leitura de indicador biológico incubado após um ciclo."""

    _name = "afr.relatorio.leitura.ib"
    _description = "Leitura de IB do Relatório Final"
    _order = "relatorio_id, cycle_id, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio",
        string="Relatório",
        required=True,
        ondelete="cascade",
        index=True,
    )
    cycle_id = fields.Many2one(
        "afr.qualificacao.cycle",
        string="Ciclo",
        ondelete="cascade",
        index=True,
    )
    indicador_id = fields.Many2one(
        "afr.relatorio.indicador",
        string="Indicador",
        ondelete="set null",
    )
    data_incubacao = fields.Date(string="Data de incubação")
    data_leitura = fields.Date(string="Data de leitura")
    leitor = fields.Char(help="Quem fez a leitura.")
    resultado = fields.Selection(
        [("negativo", "Negativo"), ("positivo", "Positivo")],
    )
    controle_positivo_ok = fields.Boolean(string="Controle positivo OK")
    quantidade = fields.Integer(
        string="Qtd. IB",
        default=1,
        help="Quantos indicadores biológicos foram usados neste ciclo.",
    )

    @api.constrains("relatorio_id", "cycle_id", "indicador_id")
    def _check_same_relatorio(self):
        """Ciclo e indicador precisam ser do próprio relatório.

        O domain da view não basta: import e RPC passam por fora dele.
        """
        for leitura in self:
            rel = leitura.relatorio_id
            if leitura.cycle_id and leitura.cycle_id not in rel.cycle_ids:
                raise ValidationError(_(
                    "O ciclo '%s' não pertence às qualificações do relatório %s."
                ) % (leitura.cycle_id.display_name, rel.name))
            if leitura.indicador_id and leitura.indicador_id.relatorio_id != rel:
                raise ValidationError(_(
                    "O indicador '%s' é de outro relatório."
                ) % leitura.indicador_id.display_name)

    @api.constrains("quantidade")
    def _check_quantidade(self):
        for leitura in self:
            if leitura.quantidade <= 0:
                raise ValidationError(_(
                    "Qtd. IB precisa ser maior que zero."
                ))


class AfrQualificacaoRelatorioLeituraIbLote(models.Model):
    """Botão "Preencher leituras em lote" (abre o wizard homônimo)."""

    _inherit = "afr.qualificacao.relatorio"

    def action_preencher_leituras_lote(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Preencher leituras de IB em lote"),
            "res_model": "afr.relatorio.leitura.ib.lote",
            "view_mode": "form",
            "target": "new",
            "context": {"default_relatorio_id": self.id},
        }
