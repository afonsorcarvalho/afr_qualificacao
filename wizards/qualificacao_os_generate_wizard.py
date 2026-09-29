# -*- coding: utf-8 -*-
"""Wizard: gerar OS de Qualificação por grupo de equipamentos.

Uma cotação confirmada pode render N OS — tipicamente uma por visita de campo
(setor, andar, disponibilidade do cliente). Cada execução cria uma OS nova com
o subconjunto de equipamentos escolhido que ainda não tem OS; repete-se até
não sobrar pendente.

Exceção: se um equipamento selecionado JÁ TEM OS nesta cotação (ex.: um
opcional dele foi aceito depois que outra OS já o cobriu), a linha nova cai
DENTRO da OS existente do equipamento em vez de abrir uma OS nova — é o único
jeito de manter a invariante abaixo sem deixar o serviço vendido sem OS.

Invariante: um equipamento nunca entra em duas OS da mesma cotação. Garantida
aqui (linhas só dos pendentes + revalidação + roteamento p/ OS existente) e no
modelo (`afr.qualificacao._check_equipamento_unico_por_os_da_so`).

16.0.8.9.0 — a M2M de equipamentos virou uma linha por equipamento pendente
(`afr.qualificacao.os.generate.wizard.line`): incluir, procedimento e template
do Relatório Final, pré-preenchidos por `_resolve_for_equipment` /
`_resolve_template` com a origem (badge). A escolha é gravada nas
qualificações criadas (nas duas rotas: OS nova e OS existente) e, com
`save_as_default`, no equipamento/cliente.
"""
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AfrQualificacaoOsGenerateWizard(models.TransientModel):
    _name = "afr.qualificacao.os.generate.wizard"
    _description = "Wizard: gerar OS de Qualificação por grupo de equipamentos"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Cotação",
        required=True,
        readonly=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    company_id = fields.Many2one(
        related="sale_order_id.company_id",
        help="Auxiliar para o domain client-side dos procedimentos/templates.",
    )
    line_ids = fields.One2many(
        "afr.qualificacao.os.generate.wizard.line",
        "wizard_id",
        string="Equipamentos",
    )
    save_as_default = fields.Boolean(
        string="Salvar escolhas como padrão (equipamento e cliente)",
        help="Grava o procedimento de cada linha incluída no equipamento e o "
             "template no cliente (empresa/parceiro comercial) da cotação.",
    )

    @api.model
    def default_get(self, fields_list):
        """Uma linha por equipamento pendente da cotação, pré-preenchida."""
        res = super().default_get(fields_list)
        if "line_ids" not in fields_list or res.get("line_ids"):
            return res
        so_id = res.get("sale_order_id")
        if not so_id:
            return res
        so = self.env["sale.order"].browse(so_id)
        res["line_ids"] = [
            (0, 0, vals)
            for vals in self._prepare_line_values(so, so.equipamentos_sem_os_ids)
        ]
        return res

    @api.model
    def _existing_qualifs_by_equipment(self, so, equipments):
        """Qualificações já em OS desta cotação, por equipamento.

        sudo(): record rule não pode esconder uma qualificação irmã (mesmo
        argumento de `_next_free_qualificacao_os_name`)."""
        qualifs = self.env["afr.qualificacao"].sudo().search([
            ("sale_order_id", "=", so.id),
            ("equipment_id", "in", equipments.ids),
            ("os_id", "!=", False),
        ])
        res = defaultdict(lambda: self.env["afr.qualificacao"].sudo())
        for q in qualifs:
            res[q.equipment_id.id] |= q
        return res

    @api.model
    def _prepare_line_values(self, so, equipments):
        """Valores das linhas para `equipments`, resolvidos na empresa da
        cotação: procedimento pela regra 5 e template pela regra 6 (com as
        qualificações não-canceladas do equipamento numa OS já existente
        desta cotação → origem "Definido na OS")."""
        Procedimento = self.env["afr.qualificacao.procedimento"]
        Relatorio = self.env["afr.qualificacao.relatorio"]
        existentes = self._existing_qualifs_by_equipment(so, equipments)
        vals_list = []
        for equipment in equipments:
            proc, proc_origem = Procedimento._resolve_for_equipment(
                equipment, so.partner_id, company=so.company_id
            )
            qualifs = existentes[equipment.id].filtered(
                lambda q: q.state != "cancelled"
            )
            tpl, tpl_origem = Relatorio._resolve_template(
                equipment, so.partner_id, qualifs, company=so.company_id
            )
            vals_list.append({
                "include": True,
                "equipment_id": equipment.id,
                "procedimento_id": proc.id if proc else False,
                "procedimento_origem": proc_origem or False,
                "relatorio_template_id": tpl.id if tpl else False,
                "template_origem": tpl_origem or False,
            })
        return vals_list

    def _validate_lines(self, included):
        """Validação server-side (o domain do campo só protege a UI), antes
        de qualquer mutação."""
        sem_proc = included.filtered(lambda l: not l.procedimento_id)
        if sem_proc:
            raise UserError(_(
                "Selecione um procedimento para: %s"
            ) % ", ".join(sem_proc.mapped("equipment_id.display_name")))
        company = self.sale_order_id.company_id
        for line in included:
            proc = line.procedimento_id
            equip_cat = line.equipment_id.category_id
            if proc.equipment_category_id and proc.equipment_category_id != equip_cat:
                raise UserError(_(
                    "Procedimento '%(proc)s' é específico da categoria "
                    "'%(proc_cat)s', incompatível com o equipamento "
                    "'%(equip)s' (categoria '%(equip_cat)s')."
                ) % {
                    "proc": proc.name,
                    "proc_cat": proc.equipment_category_id.name,
                    "equip": line.equipment_id.display_name,
                    "equip_cat": equip_cat.name if equip_cat else _("(sem categoria)"),
                })
            if proc.company_id and proc.company_id != company:
                raise UserError(_(
                    "Procedimento '%(proc)s' pertence a outra empresa "
                    "(%(proc_co)s) — a cotação é da empresa %(co)s."
                ) % {
                    "proc": proc.name,
                    "proc_co": proc.company_id.name,
                    "co": company.name,
                })
            tpl = line.relatorio_template_id
            if tpl and tpl.company_id and tpl.company_id != company:
                raise UserError(_(
                    "Template '%(tpl)s' pertence a outra empresa (%(tpl_co)s) "
                    "— a cotação é da empresa %(co)s."
                ) % {
                    "tpl": tpl.name,
                    "tpl_co": tpl.company_id.name,
                    "co": company.name,
                })
        if self.save_as_default:
            templates = included.mapped("relatorio_template_id")
            if len(templates) > 1:
                raise UserError(_(
                    "Para salvar como padrão do cliente, as linhas incluídas "
                    "precisam usar o mesmo template (escolhidos: %s). "
                    "Unifique o template ou desmarque \"Salvar escolhas como "
                    "padrão\"."
                ) % ", ".join(templates.mapped("name")))

    def _save_as_default(self, included):
        """Grava as escolhas como padrão: procedimento no equipamento e
        template no parceiro comercial da cotação.

        sudo(): o usuário de qualificação pode não ter escrita em
        engc.equipment/res.partner; o próprio ato de gerar a OS (grupo de
        qualificação) é a autorização — mesma lógica do sudo da
        materialização."""
        for line in included:
            if line.equipment_id.afr_procedimento_id != line.procedimento_id:
                line.equipment_id.sudo().afr_procedimento_id = line.procedimento_id
        template = included.mapped("relatorio_template_id")[:1]
        commercial = self.sale_order_id.partner_id.commercial_partner_id
        if template and commercial.afr_relatorio_template_id != template:
            commercial.sudo().afr_relatorio_template_id = template

    def action_generate(self):
        self.ensure_one()
        so = self.sale_order_id
        if so.state != "sale":
            raise UserError(_(
                "Confirme a cotação antes de gerar OS de Qualificação."
            ))
        included = self.line_ids.filtered("include")
        equipments = included.mapped("equipment_id")
        if not equipments:
            raise UserError(_("Selecione ao menos um equipamento."))

        # Revalidação no momento da execução: outra aba/sessão pode ter gerado
        # OS para parte da seleção depois que este wizard foi aberto.
        pendentes = so.equipamentos_sem_os_ids
        ja_gerados = equipments - pendentes
        if ja_gerados:
            raise UserError(_(
                "Estes equipamentos já têm OS nesta cotação: %s"
            ) % ", ".join(ja_gerados.mapped("display_name")))

        lines = so._pending_qualif_lines().filtered(
            lambda l: l.equipment_id in equipments
        )
        if not lines:
            raise UserError(_(
                "Nenhuma linha de qualificação pendente para os equipamentos "
                "selecionados."
            ))

        # Um equipamento selecionado pode já ter OS nesta cotação (ex.: um
        # opcional dele foi aceito depois que outra OS já o cobriu — ver
        # `_compute_equipamentos_sem_os`, que o recoloca no pool de
        # pendentes de propósito). Nesse caso a linha nova precisa cair
        # DENTRO da OS existente do equipamento, nunca numa OS nova —
        # senão a constraint de equipamento único por OS da cotação
        # (`afr.qualificacao._check_equipamento_unico_por_os_da_so`)
        # rejeita a criação e o clique vira um dead-end sem saída pela UI.
        # sudo(): record rule não pode esconder uma qualificação irmã e
        # reabrir o dead-end (mesmo argumento de `_next_free_qualificacao_os_name`).
        os_por_equipamento = {
            equip_id: qualifs[:1].os_id
            for equip_id, qualifs in self._existing_qualifs_by_equipment(
                so, equipments
            ).items()
        }

        # Bloqueio: a OS existente pode já estar num estado fechado
        # (aprovada/concluída/cancelada) — o mesmo conjunto que o próprio
        # modelo trata como travado para reversão de status
        # (`_STATE_LOCKED_ONCE_REACHED`, ver models/qualificacao_os.py).
        # `draft`/`scheduled`/`in_progress` continuam aceitando qualificação
        # nova — passam por `action_request_approval()` antes de chegar a
        # `in_approved`, que checa relatórios em rascunho, qualifs
        # rejeitadas e coleta pendente.
        #
        # O WIZARD bloqueia mais um estado que `_STATE_LOCKED_ONCE_REACHED`:
        # `in_approved`. Nele o portão de `action_request_approval()` já foi
        # ultrapassado, e a única ação que resta —`action_approve()` —
        # cascade-aprova qualquer qualificação em `draft`/`in_progress` SEM
        # revalidar trabalho executado, emitindo certificado e propagando
        # qty_delivered. Se a qualificação nova entrasse aqui, o equipamento
        # seria aprovado e faturado sem inspeção nenhuma. Por isso o
        # conjunto do wizard é `_STATE_LOCKED_ONCE_REACHED` (que serve outro
        # propósito no modelo: travar reversão de status) + `in_approved`,
        # não o mesmo conjunto reaproveitado sem alteração.
        #
        # Materializar numa OS já `approved`/`done` quebraria a invariante de
        # `action_done` (exige TODAS as qualificações aprovadas para
        # fechar); numa OS `cancelled` empurraria o serviço recém-vendido
        # para dentro de uma OS morta. Checado ANTES de qualquer
        # `_materialize_qualificacoes` — nenhum efeito parcial se alguma OS
        # de destino estiver fechada.
        Os = self.env["afr.qualificacao.os"]
        equipamentos_por_id = {e.id: e for e in equipments}
        estados_fechados_wizard = Os._STATE_LOCKED_ONCE_REACHED | {"in_approved"}
        os_fechadas = {
            equip_id: os_rec
            for equip_id, os_rec in os_por_equipamento.items()
            if os_rec.state in estados_fechados_wizard
        }
        if os_fechadas:
            state_labels = dict(Os.STATE_SELECTION)
            detalhes = ", ".join(
                "%s (OS %s, status '%s')" % (
                    equipamentos_por_id[equip_id].display_name,
                    os_rec.display_name,
                    state_labels.get(os_rec.state, os_rec.state),
                )
                for equip_id, os_rec in os_fechadas.items()
            )
            raise UserError(_(
                "Não é possível adicionar qualificação a uma OS já fechada: "
                "%s. Reabra a OS (quando o fluxo permitir) ou trate este "
                "caso manualmente."
            ) % detalhes)

        # Procedimento/template/empresa validados antes de qualquer
        # materialização — nenhum efeito parcial.
        self._validate_lines(included)
        choices = {
            line.equipment_id.id: {
                "procedimento": line.procedimento_id,
                "template": line.relatorio_template_id,
            }
            for line in included
        }

        lines_os_existente = lines.filtered(
            lambda l: l.equipment_id.id in os_por_equipamento
        )
        lines_os_nova = lines - lines_os_existente

        os_afetadas = self.env["afr.qualificacao.os"]
        por_os_existente = defaultdict(lambda: self.env["sale.order.line"])
        for line in lines_os_existente:
            por_os_existente[os_por_equipamento[line.equipment_id.id]] |= line
        for os_existente, grupo in por_os_existente.items():
            so._materialize_qualificacoes(grupo, os_existente, choices=choices)
            os_afetadas |= os_existente

        os_nova = self.env["afr.qualificacao.os"]
        if lines_os_nova:
            os_nova = self.env["afr.qualificacao.os"].create(
                so._prepare_qualificacao_os_values(equipments, pendentes)
            )
            so._materialize_qualificacoes(lines_os_nova, os_nova, choices=choices)

        if self.save_as_default:
            self._save_as_default(included)

        if os_nova:
            return {
                "type": "ir.actions.act_window",
                "name": os_nova.display_name,
                "res_model": "afr.qualificacao.os",
                "res_id": os_nova.id,
                "view_mode": "form",
                "target": "current",
            }
        if len(os_afetadas) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": os_afetadas.display_name,
                "res_model": "afr.qualificacao.os",
                "res_id": os_afetadas.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("OS de Qualificação Afetadas"),
            "res_model": "afr.qualificacao.os",
            "view_mode": "tree,form",
            "domain": [("id", "in", os_afetadas.ids)],
        }


PROCEDIMENTO_ORIGEM_SELECTION = [
    ("equipamento", "Equipamento"),
    ("cliente", "Cliente"),
    ("categoria", "Categoria"),
    ("generico", "Genérico"),
]

TEMPLATE_ORIGEM_SELECTION = [
    ("qualificacao", "Definido na OS"),
    ("cliente", "Cliente"),
    ("categoria", "Categoria"),
]


class AfrQualificacaoOsGenerateWizardLine(models.TransientModel):
    _name = "afr.qualificacao.os.generate.wizard.line"
    _description = "Linha do wizard Gerar OS: equipamento + procedimento + template"

    wizard_id = fields.Many2one(
        "afr.qualificacao.os.generate.wizard",
        required=True,
        ondelete="cascade",
    )
    include = fields.Boolean(string="Incluir", default=True)
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
        related="wizard_id.sale_order_id.company_id",
        help="Auxiliar apenas para o domain client-side.",
    )
    procedimento_id = fields.Many2one(
        "afr.qualificacao.procedimento",
        string="Procedimento",
        domain="[('company_id', '=', company_id), "
               "'|', ('equipment_category_id', '=', category_id), "
               "('equipment_category_id', '=', False)]",
    )
    procedimento_origem = fields.Selection(
        PROCEDIMENTO_ORIGEM_SELECTION,
        string="Origem do procedimento",
        help="De onde veio o procedimento pré-preenchido. Vazio (—) quando "
             "escolhido manualmente ou quando nada resolve.",
    )
    relatorio_template_id = fields.Many2one(
        "afr.relatorio.template",
        string="Template do relatório",
        domain="[('company_id', 'in', [company_id, False])]",
    )
    template_origem = fields.Selection(
        TEMPLATE_ORIGEM_SELECTION,
        string="Origem do template",
        help="De onde veio o template pré-preenchido. Vazio (—) quando "
             "escolhido manualmente ou quando nada resolve.",
    )

    def _so(self):
        return self.wizard_id.sale_order_id

    @api.onchange("procedimento_id")
    def _onchange_procedimento_origem(self):
        """Origem só vale enquanto o procedimento é o resolvido; escolha
        manual diferente → sem origem (—)."""
        for line in self:
            so = line._so()
            if not line.equipment_id or not so:
                continue
            proc, origem = self.env["afr.qualificacao.procedimento"]._resolve_for_equipment(
                line.equipment_id, so.partner_id, company=so.company_id
            )
            line.procedimento_origem = (
                origem if line.procedimento_id and line.procedimento_id == proc else False
            )

    @api.onchange("relatorio_template_id")
    def _onchange_template_origem(self):
        for line in self:
            so = line._so()
            if not line.equipment_id or not so:
                continue
            qualifs = self.env["afr.qualificacao.os.generate.wizard"]._existing_qualifs_by_equipment(
                so, line.equipment_id
            )[line.equipment_id.id].filtered(lambda q: q.state != "cancelled")
            tpl, origem = self.env["afr.qualificacao.relatorio"]._resolve_template(
                line.equipment_id, so.partner_id, qualifs, company=so.company_id
            )
            line.template_origem = (
                origem if line.relatorio_template_id and line.relatorio_template_id == tpl else False
            )
