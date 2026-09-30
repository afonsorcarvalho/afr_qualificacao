# -*- coding: utf-8 -*-
"""Wizard: template dos Relatórios Finais (16.0.8.9.0, design decisão 8).

Aberto por `afr.qualificacao.os.action_generate_relatorios_open()` quando
algum equipamento da OS ainda sem relatório final não resolve template
(`_resolve_template`: OS > cliente > categoria; sem fallback silencioso).

Uma linha por equipamento sem relatório: as que não resolvem (`pending`)
pedem o template; as resolvidas aparecem só como informação (readonly, com a
origem). Confirmar grava o template escolhido nas qualificações
não-canceladas do equipamento na OS ("Definido na OS") e, com
`save_as_default`, no cliente (parceiro comercial); depois segue o fluxo
normal do botão (gera + aplica template + abre a lista).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import clean_context

ORIGEM_SELECTION = [
    ("qualificacao", "Definido na OS"),
    ("cliente", "Cliente"),
    ("categoria", "Categoria"),
]


class AfrQualificacaoRelatorioTemplateWizard(models.TransientModel):
    _name = "afr.qualificacao.relatorio.template.wizard"
    _description = "Wizard: template dos Relatórios Finais"

    def _default_os_id(self):
        ctx = self.env.context
        if ctx.get("active_model") == "afr.qualificacao.os":
            return ctx.get("active_id")
        return False

    os_id = fields.Many2one(
        "afr.qualificacao.os",
        string="OS",
        required=True,
        readonly=True,
        default=_default_os_id,
    )
    company_id = fields.Many2one(
        related="os_id.company_id",
        help="Auxiliar para o domain client-side dos templates.",
    )
    line_ids = fields.One2many(
        "afr.qualificacao.relatorio.template.wizard.line",
        "wizard_id",
        string="Equipamentos",
    )
    save_as_default = fields.Boolean(
        string="Salvar como padrão do cliente",
        help="Grava o template escolhido no cliente (empresa/parceiro "
             "comercial) da OS: os próximos relatórios dele já nascem com "
             "este template.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "line_ids" not in fields_list or res.get("line_ids"):
            return res
        os_id = res.get("os_id")
        if not os_id:
            return res
        os_rec = self.env["afr.qualificacao.os"].browse(os_id)
        res["line_ids"] = [
            (0, 0, {
                "equipment_id": line["equipment"].id,
                "relatorio_template_id": line["template"].id or False,
                "origem": line["origem"] or False,
                "pending": not line["template"],
            })
            for line in os_rec._relatorio_final_template_lines()
        ]
        return res

    def _server_pending_lines(self):
        """Linhas pendentes recalculadas no servidor — o `pending` que vem do
        client não é confiável (um `pending=True` forjado numa linha já
        resolvida sobrescreveria o template das qualificações dela). Retorna
        `(linhas, equipamentos_pendentes)`: as linhas cujos equipamentos
        ainda não resolvem template (`_relatorio_final_template_lines`)."""
        pending_equips = self.env["engc.equipment"].browse([
            line["equipment"].id
            for line in self.os_id._relatorio_final_template_lines()
            if not line["template"]
        ])
        lines = self.line_ids.filtered(lambda l: l.equipment_id in pending_equips)
        return lines, pending_equips

    def _validate(self, pending, pending_equips=None):
        """Validação server-side antes de qualquer mutação. Todo equipamento
        pendente (recalculado no servidor) precisa de uma linha com
        template — pega também um `pending=False` forjado."""
        if pending_equips is None:
            pending_equips = pending.mapped("equipment_id")
        chosen = pending.filtered("relatorio_template_id").mapped("equipment_id")
        missing = pending_equips - chosen
        if missing:
            raise UserError(_(
                "Escolha o template do relatório para: %s."
            ) % ", ".join(missing.mapped("display_name")))
        company = self.os_id.company_id
        wrong_company = pending.filtered(
            lambda l: l.relatorio_template_id.company_id
            and l.relatorio_template_id.company_id != company
        )
        if wrong_company:
            raise UserError(_(
                "Template de outra empresa em: %s."
            ) % ", ".join(wrong_company.mapped("equipment_id.display_name")))
        if self.save_as_default:
            if len(pending.mapped("relatorio_template_id")) > 1:
                raise UserError(_(
                    "Para salvar como padrão do cliente, use o mesmo template "
                    "em todos os equipamentos (o cliente guarda um só)."
                ))
            if not self.os_id.partner_id:
                raise UserError(_(
                    "A OS não tem cliente: não há onde salvar o template padrão."
                ))

    def action_confirm(self):
        self.ensure_one()
        os_rec = self.os_id
        pending, pending_equips = self._server_pending_lines()
        self._validate(pending, pending_equips)

        # sudo(): o usuário de qualificação pode não ter escrita em
        # qualificações de outro responsável / no res.partner; a permissão
        # de gerar relatórios da OS (grupo do botão) é a autorização — mesma
        # lógica do wizard Gerar OS (`_save_as_default`).
        for line in pending:
            qualifs = os_rec.sudo().qualificacao_ids.filtered(
                lambda q, e=line.equipment_id: q.equipment_id == e
                and q.state != "cancelled"
            )
            qualifs.write({"relatorio_template_id": line.relatorio_template_id.id})
        if self.save_as_default and pending:
            commercial = os_rec.partner_id.commercial_partner_id
            commercial.sudo().afr_relatorio_template_id = pending.relatorio_template_id[:1]

        # O wizard roda no contexto do botão: nenhum `default_*` pode vazar
        # para relatório/blocos/aprovações (defesa P3 Task 5).
        return os_rec.with_context(
            clean_context(self.env.context)
        ).action_generate_relatorios_open()


class AfrQualificacaoRelatorioTemplateWizardLine(models.TransientModel):
    _name = "afr.qualificacao.relatorio.template.wizard.line"
    _description = "Linha do wizard de template dos Relatórios Finais"

    wizard_id = fields.Many2one(
        "afr.qualificacao.relatorio.template.wizard",
        required=True,
        ondelete="cascade",
    )
    equipment_id = fields.Many2one(
        "engc.equipment",
        string="Equipamento",
        required=True,
    )
    category_id = fields.Many2one(
        related="equipment_id.category_id",
        string="Categoria",
    )
    company_id = fields.Many2one(
        related="wizard_id.os_id.company_id",
        help="Auxiliar apenas para o domain client-side.",
    )
    pending = fields.Boolean(
        string="Sem template",
        help="Nenhuma regra resolveu o template: escolha na linha. Linhas "
             "já resolvidas são só informativas.",
    )
    relatorio_template_id = fields.Many2one(
        "afr.relatorio.template",
        string="Template do relatório",
        domain="[('company_id', 'in', [company_id, False])]",
    )
    origem = fields.Selection(
        ORIGEM_SELECTION,
        string="Origem do template",
    )
    # Rótulo exibido (badge): origem vazia aparece como "—".
    origem_label = fields.Char(string="Origem", compute="_compute_origem_label")

    @api.depends("origem")
    def _compute_origem_label(self):
        labels = dict(ORIGEM_SELECTION)
        for line in self:
            line.origem_label = labels.get(line.origem, "—")
