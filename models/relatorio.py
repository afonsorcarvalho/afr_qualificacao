# -*- coding: utf-8 -*-
"""Relatório Final de Qualificação Térmica (afr.qualificacao.relatorio).

Um registro por (OS, equipamento). Agrega as qualificações QI/QO/QD daquele
equipamento na OS e guarda os dados de campo que o escritório digita no
backend: datas dos ensaios, ambiente, critérios, checklist, indicadores e
leituras de IB.

P1 (16.0.8.0.0): modelo + dados de campo + ciclos. Os planos seguintes
estendem por herança: certificados (P2), template/blocos/anexos (P3),
montagem/emissão (P4) e varredura (P5).
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AfrQualificacaoRelatorio(models.Model):
    _name = "afr.qualificacao.relatorio"
    _description = "Relatório Final de Qualificação"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "os_id desc, index, id"

    _sql_constraints = [
        (
            "os_equipment_uniq",
            "unique(os_id, equipment_id)",
            "Já existe um relatório final para este equipamento nesta OS.",
        ),
    ]

    STATE_SELECTION = [
        ("draft", "Rascunho"),
        ("issued", "Emitido"),
        ("client_approved", "Aprovado pelo cliente"),
    ]

    # ───────── Identificação ─────────
    name = fields.Char(
        string="Número",
        compute="_compute_name",
        store=True,
        readonly=True,
        copy=False,
        help="ReQT-<OS>-<posição do equipamento na OS>.",
    )
    index = fields.Integer(
        string="Posição na OS",
        readonly=True,
        copy=False,
        help=(
            "Posição do equipamento na OS (1..n). Atribuída na criação e "
            "nunca renumerada: é ela que fixa o número do relatório."
        ),
    )
    os_id = fields.Many2one(
        "afr.qualificacao.os",
        string="OS de Qualificação",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    equipment_id = fields.Many2one(
        "engc.equipment",
        string="Equipamento",
        required=True,
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        related="os_id.partner_id",
        store=True,
        string="Cliente",
    )
    company_id = fields.Many2one(
        related="os_id.company_id",
        store=True,
        string="Empresa",
    )

    # ───────── Escopo agregado ─────────
    qualificacao_ids = fields.Many2many(
        "afr.qualificacao",
        relation="afr_relatorio_final_qualificacao_rel",
        column1="relatorio_id",
        column2="qualificacao_id",
        compute="_compute_qualificacao_ids",
        store=True,
        string="Qualificações",
        help="Qualificações da OS (QI/QO/QD…) do mesmo equipamento, exceto canceladas.",
    )
    cycle_ids = fields.Many2many(
        "afr.qualificacao.cycle",
        compute="_compute_cycle_ids",
        string="Ciclos",
    )

    # ───────── Estado e revisão ─────────
    state = fields.Selection(
        STATE_SELECTION,
        string="Status",
        default="draft",
        required=True,
        copy=False,
        tracking=True,
    )
    revision = fields.Integer(
        string="Revisão",
        default=0,
        copy=False,
        readonly=True,
        tracking=True,
    )
    revision_label = fields.Char(
        string="Rev.",
        compute="_compute_revision_label",
    )

    # ───────── Dados de campo ─────────
    data_inicio_ensaios = fields.Date(string="Início dos ensaios", tracking=True)
    data_fim_ensaios = fields.Date(string="Fim dos ensaios", tracking=True)
    amb_temperatura = fields.Char(
        string="Temperatura ambiente",
        help='Texto livre, ex.: "22 a 25 °C".',
    )
    amb_umidade = fields.Char(
        string="Umidade relativa",
        help='Texto livre, ex.: "41 %UR".',
    )
    tolerancia_acima = fields.Float(
        string="Tolerância acima da nominal (°C)",
        default=3.0,
    )
    criterio_f0_fator = fields.Float(
        string="Fator do critério F0 (× D)",
        default=12.0,
        help="12 = SAL 10⁻⁶ (sobre-morte); 7 = líquidos.",
    )
    proxima_qualificacao = fields.Date(
        string="Próxima qualificação",
        compute="_compute_proxima_qualificacao",
        store=True,
        help=(
            "P1: fim dos ensaios + 12 meses. P4 acrescenta current_emissao_id "
            "ao depends e recomputa (spec §4.1: emissão + 12 meses)."
        ),
    )

    # ───────── Dados de campo (filhos) ─────────
    checklist_ids = fields.One2many(
        "afr.relatorio.checklist",
        "relatorio_id",
        string="Checklist",
        copy=True,
    )
    indicador_ids = fields.One2many(
        "afr.relatorio.indicador",
        "relatorio_id",
        string="Indicadores",
        copy=True,
    )
    leitura_ib_ids = fields.One2many(
        "afr.relatorio.leitura.ib",
        "relatorio_id",
        string="Leituras de IB",
    )

    # ═════════════════════════════════════════════════════════════
    # CREATE — índice automático
    # ═════════════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        """Atribui `index = max + 1` por OS quando não vier no vals.

        O contador por OS é mantido em memória durante o lote, para que um
        `create([...])` com vários equipamentos da mesma OS não repita índice.
        sudo() na busca: o índice é da OS inteira, não do que o usuário enxerga.
        """
        next_by_os = {}
        for vals in vals_list:
            os_id = vals.get("os_id")
            if vals.get("index") or not os_id:
                continue
            if os_id not in next_by_os:
                last = self.sudo().search(
                    [("os_id", "=", os_id)], order="index desc", limit=1
                )
                next_by_os[os_id] = (last.index or 0) + 1
            vals["index"] = next_by_os[os_id]
            next_by_os[os_id] += 1
        return super().create(vals_list)

    # ═════════════════════════════════════════════════════════════
    # COMPUTES
    # ═════════════════════════════════════════════════════════════
    @api.depends("os_id.name", "index")
    def _compute_name(self):
        for rel in self:
            rel.name = rel._doc_number("ReQT") if rel.os_id else _("Novo")

    @api.depends(
        "os_id.qualificacao_ids.equipment_id",
        "os_id.qualificacao_ids.state",
        "equipment_id",
    )
    def _compute_qualificacao_ids(self):
        """Qualificações da OS do mesmo equipamento, exceto as canceladas."""
        for rel in self:
            rel.qualificacao_ids = rel.os_id.qualificacao_ids.filtered(
                lambda q: q.equipment_id == rel.equipment_id
                and q.state != "cancelled"
            )

    @api.depends("qualificacao_ids.cycle_ids")
    def _compute_cycle_ids(self):
        for rel in self:
            rel.cycle_ids = rel.qualificacao_ids.cycle_ids

    @api.depends("revision")
    def _compute_revision_label(self):
        for rel in self:
            rel.revision_label = "Rev.%02d" % (rel.revision or 0)

    @api.depends("data_fim_ensaios")
    def _compute_proxima_qualificacao(self):
        for rel in self:
            rel.proxima_qualificacao = (
                rel.data_fim_ensaios + relativedelta(months=12)
                if rel.data_fim_ensaios
                else False
            )

    # ═════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ═════════════════════════════════════════════════════════════
    @api.constrains("os_id", "equipment_id")
    def _check_equipment_in_os(self):
        """O equipamento precisa ter ao menos uma qualificação na OS.

        Só roda na criação/troca de OS ou equipamento. Se o equipamento
        sair da OS depois, o relatório não é apagado (decisão do escritório).
        """
        for rel in self:
            if rel.equipment_id not in rel.os_id.sudo().equipment_ids:
                raise ValidationError(_(
                    "O equipamento '%s' não tem qualificação na OS '%s'."
                ) % (rel.equipment_id.display_name, rel.os_id.display_name))

    # ═════════════════════════════════════════════════════════════
    # HELPERS
    # ═════════════════════════════════════════════════════════════
    def _doc_number(self, prefix):
        """Número de documento derivado da OS: `<prefix>-<OS>-<index>`.

        prefix ∈ {"ReQT" (relatório), "PrQT" (protocolo), "ReQM" (laudo micro)}.
        """
        self.ensure_one()
        return "%s-%s-%d" % (prefix, self.os_id.name, self.index or 0)

    def _seed_checklist(self, lines):
        """Semeia o checklist a partir de `lines` (list de dict
        `{grupo, descricao, sequence}`). Idempotente: relatório que já tem
        qualquer linha não é tocado (não duplica nem sobrescreve status).

        Retorna as linhas criadas (vazio quando nada foi semeado).
        """
        Checklist = self.env["afr.relatorio.checklist"]
        created = Checklist
        if not lines:
            return created
        for rel in self:
            if rel.checklist_ids:
                continue
            created |= Checklist.create([
                {
                    "relatorio_id": rel.id,
                    "sequence": line.get("sequence", (i + 1) * 10),
                    "grupo": line.get("grupo") or False,
                    "descricao": line["descricao"],
                }
                for i, line in enumerate(lines)
            ])
        return created
