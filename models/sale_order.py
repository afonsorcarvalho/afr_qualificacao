"""Extensão de sale.order para fluxo de qualificação quote-first.

- Botão `Configurar Qualificações` no header abre wizard que gera linhas SO
- Stat buttons mostram qualificações + OSs geradas
- `action_confirm()` override dispara `_create_qualificacoes_from_lines()`
  que materializa engc.os (1/equipamento) + afr.qualificacao (1/equip×tipo)
  + sub-records (cycles/malhas explodidos por qty).
- Helpers `has_qualif_lines`, `qualif_standard_ids` e
  `_qualif_equipment_summary()` alimentam o template QWeb dedicado de
  cotação (inherit condicional em `sale.report_saleorder_document`).
"""

from collections import OrderedDict, defaultdict

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


# Selection labels (mantidos em sync com sale_order_line.qualification_type).
QUALIF_TYPE_LABELS = OrderedDict([
    ("installation", "Qualificação de Instalação (QI)"),
    ("operational", "Qualificação Operacional (QO)"),
    ("performance", "Qualificação de Desempenho (QD)"),
    ("software", "Qualificação de Software (QS)"),
    ("calibration", "Calibração"),
])

# Descrições padrão por tipo — usadas no Descritivo Técnico do relatório
# de cotação. Texto voltado ao cliente leigo (sem jargão excessivo).
# Sobrescrita possível via campo `description` do `cycle_type`/`malha_type`
# ou via `qualificacao_type_config.description` (não-obrigatório).
QUALIF_TYPE_DEFAULT_DESCRIPTION = {
    "installation": (
        "Verificação documentada de que o equipamento foi instalado de "
        "acordo com as especificações do fabricante e os requisitos do "
        "local de uso — incluindo utilidades, espaço físico, conexões "
        "elétricas, hidráulicas e ambiente operacional."
    ),
    "operational": (
        "Verificação documentada de que o equipamento opera dentro das "
        "faixas e tolerâncias previstas em sua especificação — incluindo "
        "todos os modos de operação, alarmes, intertravamentos e funções "
        "de segurança."
    ),
    "performance": (
        "Verificação documentada de que o equipamento entrega desempenho "
        "consistente em condições reais de uso, executando ciclos "
        "representativos do processo. Inclui análise de uniformidade, "
        "repetibilidade e atendimento a critérios de aceitação técnicos."
    ),
    "software": (
        "Validação documentada de sistemas computadorizados associados ao "
        "equipamento — verificando integridade de dados, controles de "
        "acesso, registros eletrônicos e conformidade com requisitos "
        "regulatórios aplicáveis."
    ),
    "calibration": (
        "Conjunto de operações que estabelece a relação entre os valores "
        "indicados pelo instrumento e os valores correspondentes de "
        "padrões rastreáveis. Inclui emissão de certificado com pontos "
        "medidos, incertezas e comparação com critérios de aceitação."
    ),
}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    qualificacao_ids = fields.One2many(
        comodel_name="afr.qualificacao",
        inverse_name="sale_order_id",
        string="Qualificações",
    )
    qualificacao_count = fields.Integer(
        compute="_compute_qualificacao_count",
        string="Total de Qualificações",
    )
    # OS própria de qualificação (16.0.3.1.0 — substitui engc_os no fluxo qualif)
    qualificacao_os_ids = fields.One2many(
        comodel_name="afr.qualificacao.os",
        inverse_name="sale_order_id",
        string="OS de Qualificação",
    )
    qualificacao_os_count = fields.Integer(
        compute="_compute_qualificacao_os_count",
        string="Total OS Qualif",
    )
    # DEPRECATED 16.0.3.1.0 — preservado para SOs antigas (cutover sem migração).
    engc_os_ids = fields.One2many(
        comodel_name="engc.os",
        inverse_name="sale_order_id",
        string="OSs engc (legacy)",
    )
    engc_os_count = fields.Integer(
        compute="_compute_engc_os_count",
        string="Total OSs engc (legacy)",
    )

    has_qualif_lines = fields.Boolean(
        compute="_compute_has_qualif_lines",
        string="Possui Linhas de Qualificação",
        help=(
            "True se a SO tem linhas geradas pelo configurador "
            "(is_qualificacao_managed). Usado pelo template QWeb de "
            "cotação para chavear entre layout dedicado e fallback Odoo."
        ),
    )
    qualif_standard_ids = fields.Many2many(
        comodel_name="afr.qualificacao.standard",
        string="Normas Aplicáveis (agregado)",
        compute="_compute_qualif_standard_ids",
        help=(
            "Normas únicas agregadas das linhas managed (via cycle_type/"
            "malha_type). Não persistido — recalculado on-the-fly."
        ),
    )
    qualif_subtotals_html = fields.Html(
        compute="_compute_qualif_subtotals_html",
        string="Subtotais por Equipamento",
        sanitize=False,
        help=(
            "Tabela HTML resumo de subtotais por equipamento, gerada do "
            "agregado das linhas managed. Exibida no form do SO abaixo "
            "das linhas (Odoo não suporta coluna por section nativo)."
        ),
    )
    # F8.2 — Proposta LEGO: template + blocos montáveis por cotação
    proposal_template_id = fields.Many2one(
        comodel_name="afr.proposal.template",
        string="Template de Proposta",
        default=lambda self: self._default_proposal_template(),
        help="Template de blocos usado para montar o relatório de cotação.",
    )
    proposal_block_ids = fields.One2many(
        comodel_name="afr.proposal.block",
        inverse_name="sale_order_id",
        string="Blocos da Proposta",
        copy=True,
    )

    @api.depends("qualificacao_ids")
    def _compute_qualificacao_count(self):
        for order in self:
            order.qualificacao_count = len(order.qualificacao_ids)

    @api.depends("qualificacao_os_ids")
    def _compute_qualificacao_os_count(self):
        for order in self:
            order.qualificacao_os_count = len(order.qualificacao_os_ids)

    @api.depends("engc_os_ids")
    def _compute_engc_os_count(self):
        for order in self:
            order.engc_os_count = len(order.engc_os_ids)

    @api.depends(
        "order_line.is_qualificacao_managed",
        "order_line.equipment_id",
        "order_line.display_type",
    )
    def _compute_has_qualif_lines(self):
        for order in self:
            order.has_qualif_lines = any(
                line.is_qualificacao_managed
                and line.equipment_id
                and not line.display_type
                for line in order.order_line
            )

    @api.depends(
        "order_line.is_qualificacao_managed",
        "order_line.equipment_id",
        "order_line.display_type",
        "order_line.price_subtotal",
        "currency_id",
    )
    def _compute_qualif_subtotals_html(self):
        """Render tabela HTML com subtotal por equipamento.

        Vazio se SO não tem qualif_lines. Usado em painel form do SO
        (Odoo não permite injetar coluna por section line — colspan=99).
        """
        for order in self:
            if not order.has_qualif_lines:
                order.qualif_subtotals_html = False
                continue
            summary = order._qualif_equipment_summary()
            if not summary:
                order.qualif_subtotals_html = False
                continue
            rows = []
            total = 0.0
            for s in summary:
                equip_label = s["equipment"].display_name or _("Equipamento")
                if s["equipment"].serial_number:
                    equip_label += " — S/N: %s" % s["equipment"].serial_number
                value = formatLang(
                    self.env, s["subtotal"],
                    currency_obj=order.currency_id,
                )
                rows.append(
                    '<tr><td style="padding:4px 12px;">%s</td>'
                    '<td style="padding:4px 12px;text-align:right;'
                    'font-weight:bold;">%s</td></tr>' % (equip_label, value)
                )
                total += s["subtotal"]
            total_str = formatLang(
                self.env, total, currency_obj=order.currency_id,
            )
            rows.append(
                '<tr style="border-top:2px solid #333;">'
                '<td style="padding:6px 12px;font-weight:bold;">TOTAL</td>'
                '<td style="padding:6px 12px;text-align:right;'
                'font-weight:bold;font-size:14px;">%s</td></tr>' % total_str
            )
            order.qualif_subtotals_html = (
                '<div style="margin-top:12px;">'
                '<div style="font-weight:bold;color:#444;margin-bottom:4px;">'
                'Subtotais por Equipamento'
                '</div>'
                '<table style="border-collapse:collapse;min-width:50%%;'
                'border:1px solid #ddd;font-size:12px;">'
                '<thead><tr style="background:#f4f4f4;border-bottom:1px solid #ccc;">'
                '<th style="padding:6px 12px;text-align:left;">Equipamento</th>'
                '<th style="padding:6px 12px;text-align:right;">Subtotal</th>'
                '</tr></thead>'
                '<tbody>%s</tbody>'
                '</table></div>'
            ) % "".join(rows)

    @api.depends(
        "order_line.is_qualificacao_managed",
        "order_line.display_type",
        "order_line.cycle_type_id.standard_ids",
        "order_line.malha_type_id.standard_ids",
    )
    def _compute_qualif_standard_ids(self):
        for order in self:
            standards = self.env["afr.qualificacao.standard"]
            for line in order.order_line:
                if not line.is_qualificacao_managed or line.display_type:
                    continue
                if line.cycle_type_id:
                    standards |= line.cycle_type_id.standard_ids
                if line.malha_type_id:
                    standards |= line.malha_type_id.standard_ids
            order.qualif_standard_ids = standards.sorted(
                key=lambda s: (s.sequence, s.code or "", s.name or "")
            )

    # ------------------------------------------------------------------
    # Helpers para template QWeb de cotação
    # ------------------------------------------------------------------
    def _qualif_equipment_summary(self):
        """Agrega linhas managed por equipamento → tipo qualif → itens.

        Retorna lista ordenada de dicts:
            [
                {
                    "equipment": <engc.equipment record>,
                    "types": [
                        {
                            "code": "performance",
                            "label": "Qualificação de Desempenho (QD)",
                            "items": [
                                {"name": "Ciclo X", "qty": 3, "subtype": "cycle_type"},
                                ...
                            ],
                            "subtotal": 4500.00,
                        },
                        ...
                    ],
                    "subtotal": 7800.00,
                },
                ...
            ]

        Usado pelo QWeb: `<t t-set="summary" t-value="o._qualif_equipment_summary()"/>`.
        """
        self.ensure_one()
        # equipment_id → qualification_type → list of lines
        by_equip = OrderedDict()
        for line in self.order_line.sorted(key=lambda l: (
            l.equipment_id.name or "",
            l.qualification_type or "",
            l.sequence,
        )):
            if not (line.is_qualificacao_managed and line.equipment_id):
                continue
            if line.display_type:
                # Linhas visuais (section/note) — ignorar no agregado.
                continue
            equip = line.equipment_id
            if equip not in by_equip:
                by_equip[equip] = OrderedDict()
            qtype = line.qualification_type or "other"
            by_equip[equip].setdefault(qtype, []).append(line)

        summary = []
        for equip, types_dict in by_equip.items():
            equip_subtotal = 0.0
            types_list = []
            # Preserva ordem do selection (QI → QO → QD → QS → Calib).
            ordered_types = [
                t for t in QUALIF_TYPE_LABELS if t in types_dict
            ] + [
                t for t in types_dict if t not in QUALIF_TYPE_LABELS
            ]
            for qtype in ordered_types:
                lines = types_dict[qtype]
                items = []
                type_subtotal = 0.0
                for line in lines:
                    # User pref: usar `line.name` (descrição da linha SO,
                    # editável pelo comercial) em vez do nome técnico do
                    # cycle/malha/produto. Cai pro nome técnico se vazio.
                    if line.cycle_type_id:
                        item_name = line.name or line.cycle_type_id.name
                        subtype = "cycle_type"
                    elif line.malha_type_id:
                        # F8.10 — calib na proposta: "Calibração de <malha>"
                        # (prefixo de quantidade aplicado no render do report;
                        # line.name é geralmente o nome do produto e fica
                        # menos informativo que o nome da malha).
                        item_name = "Calibração de %s" % line.malha_type_id.name
                        subtype = "malha_type"
                    else:
                        # QI/QO/QS: line.name = descrição (default Odoo
                        # popula com description_sale do produto).
                        item_name = (
                            line.name
                            or line.product_id.display_name
                            or ""
                        )
                        subtype = "product"
                    items.append({
                        "name": item_name,
                        "qty": line.product_uom_qty,
                        "subtype": subtype,
                        "line": line,
                    })
                    type_subtotal += line.price_subtotal
                equip_subtotal += type_subtotal
                types_list.append({
                    "code": qtype,
                    "label": QUALIF_TYPE_LABELS.get(qtype, qtype),
                    "items": items,
                    "subtotal": type_subtotal,
                })
            summary.append({
                "equipment": equip,
                "types": types_list,
                "subtotal": equip_subtotal,
            })
        return summary

    def _qualif_estimated_hours(self, equipment=None):
        """F8.14 — soma horas estimadas das qualif lines do SO.

        Override `sale.order.line.estimated_hours` prevalece; fallback
        cycle_type/malha_type/type.config.estimated_hours.
        """
        self.ensure_one()
        TypeConfig = self.env["afr.qualificacao.type.config"]
        lines = self.order_line.filtered("is_qualificacao_managed")
        if equipment:
            lines = lines.filtered(lambda l: l.equipment_id == equipment)
        total = 0.0
        for line in lines:
            hours = line.estimated_hours
            if not hours:
                if line.cycle_type_id:
                    hours = line.cycle_type_id.estimated_hours
                elif line.malha_type_id:
                    hours = line.malha_type_id.estimated_hours
                elif line.qualification_type in ("installation", "software"):
                    cfg = TypeConfig.get_config_for(
                        line.qualification_type, self.company_id,
                    )
                    if cfg:
                        hours = cfg.estimated_hours
            total += (hours or 0.0) * (line.product_uom_qty or 0)
        return total

    def _qualif_estimated_days(self, equipment=None):
        """F8.14 — horas / 8 (Float decimal — 1 dia útil = 8h)."""
        return self._qualif_estimated_hours(equipment) / 8.0

    def _qualif_section_hours(self, equipment, phase):
        """F8.14 — soma horas só de uma fase (qo/qd/calibration) por equip.

        Usado pelos tfoots das tabelas QO/QD/Calib inline no Equipment Scope.
        phase ∈ {'qo', 'qd', 'calibration'}.
        """
        self.ensure_one()
        phase_to_qtype = {
            "qo": "operational",
            "qd": "performance",
            "calibration": "calibration",
        }
        qtype = phase_to_qtype.get(phase)
        if not qtype:
            return 0.0
        lines = self.order_line.filtered(
            lambda l: l.is_qualificacao_managed
            and l.equipment_id == equipment
            and l.qualification_type == qtype
        )
        total = 0.0
        for line in lines:
            hours = line.estimated_hours
            if not hours:
                if line.cycle_type_id:
                    hours = line.cycle_type_id.estimated_hours
                elif line.malha_type_id:
                    hours = line.malha_type_id.estimated_hours
            total += (hours or 0.0) * (line.product_uom_qty or 0)
        return total

    def _qualif_schedule_rows(self):
        """F8.14 — retorna lista [{equipment, hours, days}] por equip + total geral.

        Usado pelo bloco `schedule` do PDF. Equipments na ordem de
        primeira aparição nas qualif lines.
        """
        self.ensure_one()
        equipments = []
        for line in self.order_line.filtered("is_qualificacao_managed"):
            if line.equipment_id and line.equipment_id not in equipments:
                equipments.append(line.equipment_id)
        rows = []
        for eq in equipments:
            hours = self._qualif_estimated_hours(eq)
            rows.append({
                "equipment": eq,
                "hours": hours,
                "days": hours / 8.0 if hours else 0.0,
            })
        return rows

    def _qualif_type_descriptions(self):
        """Retorna descritivos técnicos por tipo qualif presente na SO.

        Lista ordenada de dicts: `[{"code", "label", "description"}, ...]`.

        Description hierarquia (primeiro não-vazio):
        1. Description específico do `cycle_type`/`malha_type` da linha
           (concatena os únicos quando múltiplos)
        2. Fallback hardcoded em `QUALIF_TYPE_DEFAULT_DESCRIPTION`
        """
        self.ensure_one()
        types_present = OrderedDict()
        for line in self.order_line:
            if not line.is_qualificacao_managed:
                continue
            if line.display_type:
                continue
            qtype = line.qualification_type
            if not qtype:
                continue
            types_present.setdefault(qtype, []).append(line)

        result = []
        ordered_types = [
            t for t in QUALIF_TYPE_LABELS if t in types_present
        ] + [
            t for t in types_present if t not in QUALIF_TYPE_LABELS
        ]
        for qtype in ordered_types:
            lines = types_present[qtype]
            # Coleta descriptions específicas de cycle/malha types
            specific_descs = []
            seen = set()
            for line in lines:
                cm_type = line.cycle_type_id or line.malha_type_id
                if cm_type and cm_type.description:
                    key = (cm_type._name, cm_type.id)
                    if key not in seen:
                        seen.add(key)
                        specific_descs.append(
                            "%s: %s" % (cm_type.name, cm_type.description)
                        )
            description = (
                "\n".join(specific_descs)
                if specific_descs
                else QUALIF_TYPE_DEFAULT_DESCRIPTION.get(qtype, "")
            )
            result.append({
                "code": qtype,
                "label": QUALIF_TYPE_LABELS.get(qtype, qtype),
                "description": description,
            })
        return result

    # ------------------------------------------------------------------
    # Configurador (abre wizard)
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # F8.2 — Proposta LEGO: blocos montáveis
    # ------------------------------------------------------------------
    @api.model
    def _default_proposal_template(self):
        """Template de proposta default da empresa (menor sequência)."""
        return self.env["afr.proposal.template"].search(
            [("company_id", "in", [self.env.company.id, False])],
            order="sequence, id", limit=1,
        )

    def _seed_proposal_blocks(self):
        """Copia os slots do proposal_template_id para proposal_block_ids.

        Idempotente: pula a SO se já tem blocos. Use
        action_reload_proposal_blocks() para forçar recarga.
        """
        Block = self.env["afr.proposal.block"]
        for order in self:
            if order.proposal_block_ids or not order.proposal_template_id:
                continue
            kind_labels = dict(
                self.env["afr.proposal.block"]._fields["block_kind"].selection
            )
            vals = []
            for line in order.proposal_template_id.line_ids.sorted("sequence"):
                section = line.section_id
                title = line.title or (
                    section.name if section
                    else kind_labels.get(line.block_kind, "")
                )
                vals.append({
                    "sale_order_id": order.id,
                    "sequence": line.sequence,
                    "block_kind": line.block_kind,
                    "section_id": section.id if section else False,
                    "title": title,
                    "body": section.body if section else False,
                    "page_break": line.page_break,
                })
            if vals:
                Block.create(vals)

    def action_reload_proposal_blocks(self):
        """Apaga blocos atuais e recarrega do template (descarta edições)."""
        self.ensure_one()
        self.proposal_block_ids.unlink()
        self._seed_proposal_blocks()
        return True

    def _render_proposal_block_body(self, body):
        """Renderiza o corpo de um bloco static resolvendo {{ expressões }}.

        Usa o engine `inline_template` do mail.render.mixin (sandbox de
        expressões {{ }}) com contexto restrito — `partner`, `company`,
        `doc` — sem expor `env` arbitrário. Retorna Markup p/ saída raw
        no QWeb (`t-out`).
        """
        self.ensure_one()
        if not body:
            return Markup("")
        rendered = self.env["mail.render.mixin"].sudo()._render_template(
            str(body), "sale.order", [self.id], engine="inline_template",
            add_context={
                "partner": self.partner_id,
                "company": self.company_id,
                "doc": self,
            },
        )
        return Markup(rendered.get(self.id) or "")

    def _qualif_cycle_rows_for(self, equipment, phase):
        """F8.8 — Linhas de ciclo (qtd/ciclo/temp/tempo) para o
        Equipment Scope inline. `phase` = 'qo' (operational) ou 'qd'
        (performance). Apenas linhas com `cycle_type_id` setado.
        """
        self.ensure_one()
        qtype = "operational" if phase == "qo" else "performance"
        lines = self.order_line.filtered(
            lambda l: l.is_qualificacao_managed
            and not l.display_type
            and not l.is_proposal_optional
            and l.equipment_id == equipment
            and l.qualification_type == qtype
            and l.cycle_type_id
        )
        return [
            {
                "name": line.cycle_type_id.name,
                "qty": int(line.product_uom_qty or 0),
                "temperature": line.cycle_type_id.temperature or "",
                "duration": line.cycle_type_id.duration or "",
            }
            for line in lines
        ]

    def _qualif_cycle_specs(self):
        """Specs técnicas de ciclos QD por equipamento (bloco cycle_specs).

        Retorna lista ordenada de dicts:
            [{"equipment": <rec>, "rows": [
                {"name", "qty", "temperature", "duration", "load_type"}, ...
            ]}, ...]
        """
        self.ensure_one()
        managed = self.order_line.filtered(
            lambda l: l.is_qualificacao_managed
            and not l.display_type
            and not l.is_proposal_optional
            and l.cycle_type_id
        )
        load_labels = dict(
            self.env["afr.qualificacao.cycle.type"]._fields["load_type"].selection
        )
        by_equip = OrderedDict()
        for line in managed:
            by_equip.setdefault(line.equipment_id, []).append(line)
        result = []
        for equip, lines in by_equip.items():
            rows = []
            for line in lines:
                cycle_type = line.cycle_type_id
                rows.append({
                    "name": cycle_type.name,
                    "qty": int(line.product_uom_qty or 0),
                    "temperature": cycle_type.temperature or "",
                    "duration": cycle_type.duration or "",
                    "load_type": load_labels.get(cycle_type.load_type, ""),
                })
            result.append({"equipment": equip, "rows": rows})
        return result

    def action_open_configurator(self):
        """Abre wizard configurador de qualificações em modal fullscreen."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_(
                "Defina o cliente antes de abrir o configurador de qualificações."
            ))
        if self.state not in ("draft", "sent"):
            raise UserError(_(
                "Configurador disponível apenas em orçamentos (draft/sent)."
            ))
        wizard = self.env["afr.qualificacao.configurator"].create({
            "sale_order_id": self.id,
        })
        wizard._load_from_existing_lines()
        return {
            "type": "ir.actions.act_window",
            "name": _("Configurar Qualificações"),
            "res_model": "afr.qualificacao.configurator",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }

    def action_view_qualificacoes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Qualificações"),
            "res_model": "afr.qualificacao",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.qualificacao_ids.ids)],
        }

    def action_view_qualificacao_os(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("OS de Qualificação"),
            "res_model": "afr.qualificacao.os",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.qualificacao_os_ids.ids)],
        }

    def action_view_engc_os(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("OSs engc (legacy)"),
            "res_model": "engc.os",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.engc_os_ids.ids)],
        }

    # ------------------------------------------------------------------
    # Confirm → gera engc.os + afr.qualificacao + sub-records
    # ------------------------------------------------------------------
    def action_confirm(self):
        """Override: após confirmar SO, gera estrutura de qualificações."""
        result = super().action_confirm()
        for order in self:
            order._create_qualificacoes_from_lines()
        return result

    def _create_qualificacoes_from_lines(self):
        """Materializa afr.qualificacao.os + afr.qualificacao + sub-records.

        Cutover 16.0.3.1.0:
        - 1 afr.qualificacao.os por SO (agregando N equipamentos × N tipos)
        - 1 afr.qualificacao por (equipamento, qualification_type)
        - Para QD: N afr.qualificacao.cycle por linha SO (qty=N)
        - Para Calib: N afr.qualificacao.malha por linha SO
        - Para QI/QO/QS: sem sub-records (1 linha = 1 qualificação)

        engc.os NÃO é mais criado para SOs de qualificação. SOs antigas
        (pré-3.1.0) ficam com engc.os existente; cutover sem migração.

        Idempotência: skip se afr_qualificacao_id já populado (evita
        re-gerar em re-confirm).
        """
        self.ensure_one()
        managed = self.order_line.filtered(
            lambda l: l.is_qualificacao_managed
            and not l.display_type
            and not l.is_proposal_optional
        )
        if not managed:
            return
        # Skip linhas já processadas
        managed = managed.filtered(lambda l: not l.afr_qualificacao_id)
        if not managed:
            return

        QualifOs = self.env["afr.qualificacao.os"]
        Qualif = self.env["afr.qualificacao"]
        Cycle = self.env["afr.qualificacao.cycle"]
        Malha = self.env["afr.qualificacao.malha"]
        Procedimento = self.env["afr.qualificacao.procedimento"]
        CollectItem = self.env["afr.qualificacao.collect.item"]

        # 1 OS por SO (reusa se já existe — re-confirmação parcial)
        os = self.qualificacao_os_ids[:1] or QualifOs.create(
            self._prepare_qualificacao_os_values()
        )

        # Agrupa linhas por equipamento
        by_equipment = defaultdict(lambda: self.env["sale.order.line"])
        for line in managed:
            by_equipment[line.equipment_id] |= line

        for equipment, equip_lines in by_equipment.items():
            # Por (equipment, qualification_type): 1 afr.qualificacao
            by_type = defaultdict(lambda: self.env["sale.order.line"])
            for line in equip_lines:
                by_type[line.qualification_type] |= line

            for qtype, type_lines in by_type.items():
                qualif = Qualif.create(
                    self._prepare_qualificacao_values(equipment, qtype, os)
                )
                type_lines.write({"afr_qualificacao_id": qualif.id})

                # Sub-records explodidos por qty.
                # F8.8 — QO cycle-based explode igual ao QD: linhas
                # operational com cycle_type_id geram afr.qualificacao.cycle.
                if qtype in ("performance", "operational"):
                    for line in type_lines:
                        if not line.cycle_type_id:
                            # operational sem cycle (do_qo boolean): sem sub-records
                            continue
                        qty = int(line.product_uom_qty or 0)
                        for seq in range(1, qty + 1):
                            Cycle.create({
                                "qualificacao_id": qualif.id,
                                "cycle_type_id": line.cycle_type_id.id,
                                "sale_order_line_id": line.id,
                                "sequence": seq * 10,
                            })
                elif qtype == "calibration":
                    for line in type_lines:
                        qty = int(line.product_uom_qty or 0)
                        for seq in range(1, qty + 1):
                            Malha.create({
                                "qualificacao_id": qualif.id,
                                "malha_type_id": line.malha_type_id.id,
                                "sale_order_line_id": line.id,
                                "sequence": seq * 10,
                            })
                # QI/QS: sem sub-records. QO boolean: sem sub-records (pulado acima).

                # F3 (16.0.3.2.0): explode procedimento default em collect.items
                # sudo: vendedor pode confirmar SO sem precisar de grupos qualif
                proc = Procedimento.sudo().resolve_for(qtype, equipment.category_id)
                if proc:
                    self._explode_collect_items(CollectItem.sudo(), qualif, proc)

    def _explode_collect_items(self, CollectItem, qualif, procedimento):
        """F3: Cria N collect.items por procedimento.item conforme target_level.

        target_level=qualificacao → 1 item por qualif
        target_level=cycle → 1 item por cycle existente (qualif QD)
        target_level=malha → 1 item por malha existente (qualif Calib)
        """
        for pi in procedimento.item_ids:
            base_vals = {
                "name": pi.name,
                "sequence": pi.sequence,
                "kind": pi.kind,
                "required": pi.required,
                "instruction": pi.instruction,
                "procedimento_item_id": pi.id,
                "qualif_id": qualif.id,
            }
            if pi.target_level == "qualificacao":
                CollectItem.create(base_vals)
            elif pi.target_level == "cycle":
                for cycle in qualif.cycle_ids:
                    vals = dict(base_vals)
                    vals["cycle_id"] = cycle.id
                    vals["name"] = _("%s — Ciclo %d") % (pi.name, cycle.sequence)
                    CollectItem.create(vals)
            elif pi.target_level == "malha":
                for malha in qualif.malha_ids:
                    vals = dict(base_vals)
                    vals["malha_id"] = malha.id
                    vals["name"] = _("%s — Malha %d") % (pi.name, malha.sequence)
                    CollectItem.create(vals)

    def _prepare_qualificacao_os_values(self):
        """Hook: valores para criar afr.qualificacao.os a partir do SO."""
        self.ensure_one()
        return {
            "sale_order_id": self.id,
            "company_id": self.company_id.id,
            # tecnico_default_id + datas planejadas: gestor preenche pós-confirm
        }

    def _prepare_qualificacao_values(self, equipment, qualification_type, os):
        """Hook: valores para criar afr.qualificacao vinculada à OS qualif.

        Assinatura mudada em 16.0.3.1.0: `engc_os` → `os` (afr.qualificacao.os).
        """
        self.ensure_one()
        return {
            "name": _("Q-%s-%s-%s") % (
                self.name,
                equipment.id,
                qualification_type[:3].upper(),
            ),
            "equipment_id": equipment.id,
            "partner_id": self.partner_id.id,
            "qualification_type": qualification_type,
            "company_id": self.company_id.id,
            "sale_order_id": self.id,
            "os_id": os.id,
            # engc_os_id deprecated — não preenchido para SOs novas.
        }
