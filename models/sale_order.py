"""Extensão de sale.order para fluxo de qualificação quote-first.

- Botão `Configurar Qualificações` no header abre wizard que gera linhas SO
- Stat buttons mostram qualificações + OSs geradas
- Botão `Gerar OS de Qualificação` (SO confirmada) abre wizard que cria 1
  OS por grupo de equipamentos selecionados, materializando
  afr.qualificacao (1/equip×tipo) + sub-records (cycles/malhas por qty).
  1 cotação → N OS, sem equipamento repetido entre elas.
- Helpers `has_qualif_lines`, `qualif_standard_ids` e
  `_qualif_equipment_summary()` alimentam o template QWeb dedicado de
  cotação (inherit condicional em `sale.report_saleorder_document`).
"""

import math
import re
from collections import OrderedDict, defaultdict

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


# Sufixo "— N ciclo(s)/malha(s)" anexado pelo configurador ao nome da linha.
_QTY_SUFFIX_RE = re.compile(r"\s+—\s+\d+\s+(?:ciclo|malha)\(s\)$")


# Selection labels (mantidos em sync com sale_order_line.qualification_type).
QUALIF_TYPE_LABELS = OrderedDict([
    # F8.15 — ordem: QI → Calibração → QO → QD → QS.
    # F8.16 — labels alinhadas ao padrão (sem abreviação parentética).
    ("installation", "Qualificação de Instalação"),
    ("calibration", "Calibração"),
    ("operational", "Qualificação de Operação"),
    ("performance", "Qualificação de Desempenho"),
    ("software", "Qualificação de Software"),
])

# Tipo de qualificação → code da seção da biblioteca que o descreve.
# Usado pela remissiva do escopo ("Conforme item 5.1 — ...").
SCOPE_REF_SECTION_CODES = {
    "installation": "SEC-QI",
    "operational": "SEC-QO",
    "performance": "SEC-QD",
    "software": "SEC-QS",
    "calibration": "SEC-CALIB",
}

# Agrupamento das linhas "Previsão de dias / Subtotal" no escopo impresso.
# Fiel à proposta antiga do cliente: QI parte 01 e QO parte 01 fecham
# sozinhos; parte 02 (calibrações + ciclos sem carga) e QD fecham juntos
# sob o rótulo "Subtotal QD". `part=None` = qualquer parte.
SCOPE_GROUPS = (
    {
        "key": "qi1",
        "subtotal_label": "Subtotal QI",
        "members": (("installation", "01"),),
    },
    {
        "key": "qo1",
        "subtotal_label": "Subtotal QO",
        "members": (("operational", "01"),),
    },
    {
        "key": "parte2",
        "subtotal_label": "Subtotal QD",
        "members": (
            ("installation", "02"),
            ("calibration", None),
            ("operational", "02"),
            ("performance", None),
        ),
    },
)

# Como cada (tipo, parte) se apresenta na coluna direita da tabela.
SCOPE_ROW_SPECS = {
    ("installation", "01"): {
        "label": "Qualificação da Instalação — QI (primeira parte)",
        "kind": "ref", "title": "",
    },
    ("operational", "01"): {
        "label": "Qualificação de Operação — QO (primeira parte)",
        "kind": "ref", "title": "",
    },
    ("installation", "02"): {
        "label": "Qualificação da Instalação — QI (segunda parte)",
        "kind": "list", "title": "Itens a serem avaliados:",
    },
    ("calibration", None): {
        "label": "Qualificação da Instalação — QI (segunda parte)",
        "kind": "list", "title": "Calibração dos equipamentos de controle:",
    },
    ("operational", "02"): {
        "label": "Qualificação de Operação — QO (segunda parte)",
        "kind": "cycles", "title": "Execução dos ciclos sem carga",
    },
    ("performance", None): {
        "label": "Qualificação de Desempenho — QD",
        "kind": "cycles", "title": "Execução dos ciclos com carga",
    },
}

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
    equipamentos_sem_os_ids = fields.Many2many(
        comodel_name="engc.equipment",
        string="Equipamentos sem OS",
        compute="_compute_equipamentos_sem_os",
        help=(
            "Equipamentos das linhas de qualificação que ainda não foram "
            "materializados em nenhuma OS desta cotação."
        ),
    )
    pode_gerar_os = fields.Boolean(
        string="Pode Gerar OS",
        compute="_compute_equipamentos_sem_os",
        help="True se a cotação está confirmada e ainda há equipamento sem OS.",
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
        string="Totais da Proposta",
        sanitize=False,
        help=(
            "Painel HTML exibido no form do SO abaixo das linhas: banner do "
            "TOTAL GERAL DA PROPOSTA e, quando houver, a tabela de opcionais "
            "aceitos."
        ),
    )
    regular_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="order_id",
        domain=[("is_proposal_optional", "=", False)],
        string="Linhas",
        help=(
            "Linhas NÃO-opcionais (comercial + seções/notas). Mesmo conjunto "
            "de registros de order_line filtrado por domain — usado na aba "
            "Comercial do form."
        ),
    )
    optional_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="order_id",
        domain=[("is_proposal_optional", "=", True)],
        string="Opcionais",
        help=(
            "Linhas opcionais (is_proposal_optional=True). Usado na aba "
            "Opcionais. Novas linhas recebem o flag via context default da view."
        ),
    )
    equipment_target_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="order_id",
        domain=[("display_type", "=", "line_section"),
                ("equipment_id", "!=", False)],
        string="Preços por Equipamento",
        help=(
            "Linhas de section com equipamento — onde vive o preço-alvo do "
            "rateio. Datapoint próprio porque o tree de linhas usa "
            "section_and_note_one2many, que esconde colunas em sections."
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

    # ═════════════════════════════════════════════════════════════
    # CREATE — sequência SO C[YY]-[MM]-NNNN
    # ═════════════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "afr.qualificacao.sale.order"
                    )
                    or _("New")
                )
        return super().create(vals_list)

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
        "state",
        "order_line.equipment_id",
        "order_line.afr_qualificacao_id",
        "order_line.is_qualificacao_managed",
        "order_line.display_type",
        "order_line.part01_declined",
        "order_line.is_proposal_optional",
        "order_line.optional_accepted",
        "order_line.qualification_type",
        # Reatividade live no form: a aba Opcionais edita optional_accepted
        # via optional_line_ids (datapoint OWL distinto de order_line, ver
        # _compute_qualif_subtotals_html). Sem este path o compute não
        # recomputa ao aceitar um opcional após a SO confirmada.
        "optional_line_ids.optional_accepted",
    )
    def _compute_equipamentos_sem_os(self):
        for order in self:
            pendentes = order._pending_qualif_lines().mapped("equipment_id")
            order.equipamentos_sem_os_ids = pendentes
            order.pode_gerar_os = bool(pendentes) and order.state == "sale"

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
        "order_line.estimated_hours",
        "order_line.qualif_cycle_qty",
        "order_line.is_proposal_optional",
        "order_line.optional_accepted",
        # Reatividade live no form: as abas Comercial/Opcionais editam via
        # regular_line_ids/optional_line_ids (datapoints OWL distintos de
        # order_line). Sem estes paths o painel não recomputa ao togglar.
        "regular_line_ids.price_subtotal",
        "optional_line_ids.price_subtotal",
        "optional_line_ids.optional_accepted",
        "currency_id",
    )
    def _compute_qualif_subtotals_html(self):
        """Render o painel de totais abaixo das linhas no form do SO.

        Só o TOTAL GERAL, com adicionais enumerados quando houver (ver
        `_qualif_grand_total_html`). A tabela de subtotais por equipamento
        foi retirada em 16.0.6.13.5 (preço por equipamento editável na aba
        Comercial via `equipment_target_ids`) e a de opcionais aceitos
        nesta task — o opcional aceito agora aparece como adicional no
        próprio banner de total, evitando duplicidade.

        Vazio se a SO não tem qualif_lines.
        """
        for order in self:
            if not order.has_qualif_lines:
                order.qualif_subtotals_html = False
                continue
            summary = order._qualif_equipment_summary()
            if not summary:
                order.qualif_subtotals_html = False
                continue
            order.qualif_subtotals_html = str(order._qualif_grand_total_html())

    def _qualif_additional_lines(self):
        """Adicionais: tudo que não entra no escopo de nenhum equipamento.

        Ex.: despesas de viagem, pasta impressa, e também opcionais
        ACEITOS (o rateio os exclui do escopo; sem esta regra o valor
        sumiria do impresso sem sumir do amount_untaxed).
        Opcional recusado tem product_uom_qty=0 → subtotal 0 → fora,
        sem precisar de regra especial.
        """
        self.ensure_one()
        in_scope = self.env["sale.order.line"]
        for table in self._qualif_scope_tables():
            in_scope |= self._qualif_scope_lines(table["equipment"])
        out = []
        for line in self.order_line.sorted(key=lambda l: (l.sequence, l.id or 0)):
            if line.display_type or line in in_scope:
                continue
            if self.currency_id.is_zero(line.price_subtotal):
                continue
            out.append({
                "name": line.name or line.product_id.display_name or "",
                "amount": line.price_subtotal,
            })
        return out

    def _qualif_proposal_totals(self):
        """Totais da proposta — fonte única do form, do PDF e do portal.

        `grand_total` continua sendo `amount_untaxed` (o total real). Ele
        é decomposto em:

        - `equip_total`: soma dos Valores Unitários IMPRESSOS nas tabelas
          de escopo (preço-alvo quando bate, soma real quando desviado).
        - `adicionais`: lista enumerada `[{"name", "amount"}]`.
        - `residual`: o que sobra. Deve ser zero; quando não for (alvo
          desviado, arredondamento), é impresso como linha "Outros" para
          que nenhum valor do amount_untaxed fique invisível — foi
          exatamente esse o bug C26-06-0005.
        """
        self.ensure_one()
        equip_total = sum(
            t["footer"]["unit_price"] for t in self._qualif_scope_tables())
        adicionais = self._qualif_additional_lines()
        grand_total = self.amount_untaxed
        residual = self.currency_id.round(
            grand_total - equip_total - sum(a["amount"] for a in adicionais))
        return {
            "equip_total": equip_total,
            "adicionais": adicionais,
            "residual": residual,
            "grand_total": grand_total,
        }

    def _qualif_grand_total_html(self):
        """Banner de totais do form + base do bloco de totais do PDF.

        Sem adicionais nem residual, imprime só a linha do total geral.
        """
        self.ensure_one()
        totals = self._qualif_proposal_totals()
        rows = []
        breakdown = bool(totals["adicionais"]) or not self.currency_id.is_zero(
            totals["residual"])
        if breakdown:
            rows.append((
                _("Total dos Serviços de Qualificação"), totals["equip_total"]))
            for adicional in totals["adicionais"]:
                rows.append((adicional["name"], adicional["amount"]))
            if not self.currency_id.is_zero(totals["residual"]):
                rows.append((_("Outros"), totals["residual"]))
        body = "".join(
            '<tr><td style="padding:4px 12px;">%s</td>'
            '<td style="padding:4px 12px;text-align:right;">%s</td></tr>'
            % (escape(name), escape(formatLang(
                self.env, value, currency_obj=self.currency_id)))
            for name, value in rows
        )
        grand_str = formatLang(
            self.env, totals["grand_total"], currency_obj=self.currency_id)
        return Markup(
            '<div style="margin-top:12px;width:100%%;">'
            '<table style="border-collapse:collapse;width:100%%;'
            'font-size:12px;">%s'
            '<tr style="border-top:2px solid #333;">'
            '<td style="padding:6px 12px;font-weight:bold;">'
            'TOTAL GERAL DA PROPOSTA</td>'
            '<td style="padding:6px 12px;text-align:right;font-weight:bold;'
            'font-size:14px;">%s</td></tr>'
            '</table></div>'
        ) % (Markup(body), escape(grand_str))

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
                    extra = {}
                    if line.cycle_type_id:
                        item_name = line.name or line.cycle_type_id.name
                        subtype = "cycle_type"
                        # F8.16 — bullets QO/QD precisam de temp/tempo
                        # esteril pra exibir junto do ciclo no Escopo.
                        extra["temperature"] = line.temperature or line.cycle_type_id.temperature or ""
                        extra["duration"] = line.duration or line.cycle_type_id.duration or ""
                        # F8.16 — sufixo do processo no bullet segue a categoria
                        # (esterilização/lavagem/desinfecção), igual à tabela de ciclos.
                        extra["process_word"] = (
                            equip.category_id._qualif_process_word()
                            if equip.category_id else ""
                        )
                    elif line.malha_type_id:
                        # F10.4 — calib na proposta usa a DESCRIÇÃO da linha
                        # (line.name sem o sufixo "— N malha(s)"), não o nome
                        # do produto. Fallback p/ "Calibração de <malha>".
                        desc = _QTY_SUFFIX_RE.sub("", line.name or "").strip()
                        item_name = desc or (
                            "Calibração de %s" % line.malha_type_id.name
                        )
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
                        "qty": line.qualif_cycle_qty or line.product_uom_qty,
                        "subtype": subtype,
                        "line": line,
                        "part": line.part or "",
                        "declined": line.part01_declined,
                        # declinada: price_subtotal=0; usar price_unit como referência
                        "ref_price": line.price_unit if line.part01_declined else line.price_subtotal,
                        **extra,
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

    def _qualif_declined_items(self):
        """Linhas Parte 01 declinadas, p/ o box 'Itens Não Solicitados'."""
        self.ensure_one()
        out = []
        for line in self.order_line.sorted(key=lambda l: (
            l.equipment_id.name or "", l.sequence,
        )):
            if not (line.is_qualificacao_managed and line.part01_declined):
                continue
            out.append({
                "equipment": line.equipment_id,
                "qualification_type": line.qualification_type or "",
                "label": QUALIF_TYPE_LABELS.get(
                    line.qualification_type, line.qualification_type or ""),
                "name": line.name or (line.product_id.display_name or ""),
                "ref_price": line.price_unit,
            })
        return out

    def _qualif_part_header(self, part, code):
        """Rótulo de cabeçalho por Parte (compartilhado PDF + portal)."""
        if part == "01":
            return "PARTE 01 — Verificações"
        if part == "02":
            if code == "installation":
                return "PARTE 02 — Calibrações"
            if code == "operational":
                return "PARTE 02 — Ciclos de Operação"
            return "PARTE 02"
        return ""

    def _qualif_estimated_hours(self, equipment=None):
        """F8.14 — soma horas estimadas das qualif lines do SO.

        Override `sale.order.line.estimated_hours` prevalece; fallback
        cycle_type/malha_type/type.config.estimated_hours.
        """
        self.ensure_one()
        TypeConfig = self.env["afr.qualificacao.type.config"]
        lines = self.order_line.filtered(
            lambda l: l.is_qualificacao_managed and not l.part01_declined
        )
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
            total += (hours or 0.0) * (line.qualif_cycle_qty or int(line.product_uom_qty or 0))
        return total

    def _qualif_work_hours_per_day(self, equipment):
        """Jornada (h/dia) do equipamento — lê da section line; fallback 8.0."""
        self.ensure_one()
        section = self.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id == equipment
        )[:1]
        return section.work_hours_per_day or 8.0

    def _qualif_scope_lines(self, equipment, qtype=None, part=None):
        """Linhas que compõem o escopo impresso de um equipamento.

        Conjunto IDÊNTICO ao de `sale.order.line._rateio_base_lines()` —
        managed, sem display_type, não opcional, não declinada, qty > 0.
        Manter os dois em sincronia é o que garante que a soma dos
        subtotais dos grupos bata com `equipment_subtotal` (e portanto
        com o Valor Unitário impresso).

        `qtype` filtra por qualification_type; `part` filtra por parte
        ('01'/'02'). `part=None` = qualquer parte.
        """
        self.ensure_one()
        lines = self.order_line.filtered(
            lambda l: l.equipment_id == equipment
            and l.is_qualificacao_managed
            and not l.display_type
            and not l.is_proposal_optional
            and not l.part01_declined
            and l.product_uom_qty > 0
        )
        if qtype:
            lines = lines.filtered(lambda l: l.qualification_type == qtype)
        if part is not None:
            lines = lines.filtered(lambda l: (l.part or "") == part)
        return lines

    def _qualif_group_hours(self, lines):
        """Horas estimadas de um conjunto de linhas do escopo.

        Hierarquia da hora unitária: override na linha → cycle_type →
        malha_type → afr.qualificacao.type.config (QI/QS). Multiplicada
        por `qualif_cycle_qty` (fallback `product_uom_qty`).
        """
        self.ensure_one()
        TypeConfig = self.env["afr.qualificacao.type.config"]
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
            qty = line.qualif_cycle_qty or int(line.product_uom_qty or 0)
            total += (hours or 0.0) * qty
        return total

    def _qualif_days_from_hours(self, hours, equipment):
        """Horas → dias de serviço, arredondado PARA CIMA ao próximo 0,5.

        3,2 dias → 3,5; 3,6 → 4,0. `round(..., 6)` antes do ceil evita
        que 3.0000000001 (ruído de float) vire 3,5.
        """
        self.ensure_one()
        wh = self._qualif_work_hours_per_day(equipment) or 8.0
        return math.ceil(round((hours / wh) * 2, 6)) / 2.0

    def _qualif_scope_ref(self, qtype):
        """Remissiva ao tópico da proposta que descreve o tipo.

        Com bloco incluído e numerado:
            "Conforme item 5.1 — Qualificação de Instalação (QI)"
        Sem bloco (cliente removeu) ou com bloco presente mas sem número
        (show_number=False) — mesmo texto nos dois casos, sempre citando
        o nome da seção da biblioteca:
            "Conforme descrito no tópico Qualificação de Instalação (QI)"

        NUNCA devolve vazio/None — o QWeb interpola direto.
        """
        self.ensure_one()
        code = SCOPE_REF_SECTION_CODES.get(qtype)
        label = QUALIF_TYPE_LABELS.get(qtype) or _("este escopo")
        if code:
            section = self.env["afr.proposal.section"].search(
                [("code", "=", code)], limit=1)
            if section.name:
                label = section.name
        block = self.env["afr.proposal.block"]
        if code:
            block = self.proposal_block_ids.filtered(
                lambda b: b.included and b.section_id
                and b.section_id.code == code
            )[:1]
        if not block:
            return _("Conforme descrito no tópico %s") % label
        name = block.section_id.name or label
        num = self._proposal_block_numbering().get(block.id) or ""
        if not num:
            return _("Conforme descrito no tópico %s") % name
        return _("Conforme item %s — %s") % (num, name)

    def _qualif_scope_row(self, equipment, qtype, row_spec, lines):
        """Monta uma linha da coluna direita da tabela de escopo."""
        self.ensure_one()
        row = {
            "kind": row_spec["kind"],
            "label": row_spec["label"],
            "title": row_spec["title"],
        }
        if row_spec["kind"] == "ref":
            row["ref"] = self._qualif_scope_ref(qtype)
        elif row_spec["kind"] == "cycles":
            row["time_label"] = (
                equipment.category_id._qualif_time_label()
                if equipment.category_id else _("Tempo de Esterilização")
            )
            row["cycles"] = [{
                "qty": line.qualif_cycle_qty or int(line.product_uom_qty or 0),
                "name": line.cycle_type_id.name or line.name or "",
                "temperature": (
                    line.temperature
                    or line.cycle_type_id.temperature or ""
                ),
                "duration": (
                    line.duration or line.cycle_type_id.duration or ""
                ),
            } for line in lines]
        else:
            row["items"] = [
                line.name or line.product_id.display_name or ""
                for line in lines
            ]
        return row

    def _qualif_scope_table(self, equipment):
        """Tabela de escopo completa de um equipamento.

        Fonte ÚNICA dos três renders (PDF, portal, HTML do bloco). Nenhum
        deles refaz agregação nem aritmética. Ver spec
        docs/superpowers/specs/2026-08-20-escopo-tabela-ciclos-design.md.
        """
        self.ensure_one()
        all_lines = self._qualif_scope_lines(equipment)
        used = self.env["sale.order.line"]
        groups = []
        for spec in SCOPE_GROUPS:
            rows = []
            group_lines = self.env["sale.order.line"]
            for qtype, part in spec["members"]:
                lines = self._qualif_scope_lines(equipment, qtype, part)
                if not lines:
                    continue
                group_lines |= lines
                rows.append(self._qualif_scope_row(
                    equipment, qtype, SCOPE_ROW_SPECS[(qtype, part)], lines,
                ))
            if not group_lines:
                continue
            used |= group_lines
            groups.append({
                "key": spec["key"],
                "rows": rows,
                "days": self._qualif_days_from_hours(
                    self._qualif_group_hours(group_lines), equipment),
                "subtotal": sum(group_lines.mapped("price_subtotal")),
                "subtotal_label": spec["subtotal_label"],
            })

        # Sobras: tipo/parte fora da matriz (ex.: QS). Cada tipo vira um
        # grupo próprio — nada some silenciosamente do escopo impresso.
        leftovers = all_lines - used
        for qtype in OrderedDict.fromkeys(
                leftovers.mapped("qualification_type")):
            lines = leftovers.filtered(
                lambda l: l.qualification_type == qtype)
            label = QUALIF_TYPE_LABELS.get(qtype) or _("Outros serviços")
            groups.append({
                "key": "extra-%s" % (qtype or "other"),
                "rows": [{
                    "kind": "list", "label": label, "title": "",
                    "items": [
                        line.name or line.product_id.display_name or ""
                        for line in lines
                    ],
                }],
                "days": self._qualif_days_from_hours(
                    self._qualif_group_hours(lines), equipment),
                "subtotal": sum(lines.mapped("price_subtotal")),
                "subtotal_label": _("Subtotal %s") % label,
            })

        # Valor Unitário: o preço-alvo quando ele bate com a soma real;
        # senão a soma real, para o impresso sempre fechar com o
        # amount_untaxed do SO. Drift continua sinalizado no form.
        section = self.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id == equipment
        )[:1]
        if section and section.equipment_target_state == "ok":
            unit_price = section.equipment_target_price
        else:
            unit_price = sum(all_lines.mapped("price_subtotal"))

        return {
            "equipment": equipment,
            "groups": groups,
            "footer": {
                "days": sum(g["days"] for g in groups),
                "unit_price": unit_price,
            },
        }

    def _qualif_scope_tables(self):
        """Tabelas de escopo de todos os equipamentos, na ordem do resumo.

        Equipamento cujas linhas foram todas declinadas/optadas fora não
        gera tabela (grupos vazios) e é omitido — os itens declinados
        continuam aparecendo no box de auditoria.
        """
        self.ensure_one()
        out = []
        for summary in self._qualif_equipment_summary():
            table = self._qualif_scope_table(summary["equipment"])
            if table["groups"]:
                out.append(table)
        return out

    def _qualif_estimated_days(self, equipment=None):
        """F8.14 — horas / jornada (h/dia) do equipamento (default 8)."""
        wh = self._qualif_work_hours_per_day(equipment) if equipment else 8.0
        return self._qualif_estimated_hours(equipment) / (wh or 8.0)

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
            and not l.part01_declined
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
            total += (hours or 0.0) * (line.qualif_cycle_qty or int(line.product_uom_qty or 0))
        return total

    def _qualif_schedule_rows(self):
        """F8.14 — retorna lista [{equipment, hours, days}] por equip + total geral.

        Usado pelo bloco `schedule` do PDF. Equipments na ordem de
        primeira aparição nas qualif lines.
        """
        self.ensure_one()
        equipments = []
        for line in self.order_line.filtered(
            lambda l: l.is_qualificacao_managed and not l.part01_declined
        ):
            if line.equipment_id and line.equipment_id not in equipments:
                equipments.append(line.equipment_id)
        rows = []
        for eq in equipments:
            hours = self._qualif_estimated_hours(eq)
            wh = self._qualif_work_hours_per_day(eq)
            rows.append({
                "equipment": eq,
                "hours": hours,
                "work_hours_per_day": wh,
                "days": hours / wh if hours else 0.0,
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

        F9.1 — propaga parent_id e show_number das linhas do template.
        Duas passagens: 1ª cria blocos e mapeia line_id→block_id;
        2ª resolve parent_id usando o mapa.
        """
        Block = self.env["afr.proposal.block"]
        for order in self:
            if order.proposal_block_ids or not order.proposal_template_id:
                continue
            kind_labels = dict(
                self.env["afr.proposal.block"]._fields["block_kind"].selection
            )
            # 1ª passagem: criar blocos (sem parent ainda)
            line_to_block = {}
            for line in order.proposal_template_id.line_ids.sorted("sequence"):
                section = line.section_id
                title = line.title or (
                    section.name if section
                    else kind_labels.get(line.block_kind, "")
                )
                block = Block.create({
                    "sale_order_id": order.id,
                    "sequence": line.sequence,
                    "block_kind": line.block_kind,
                    "section_id": section.id if section else False,
                    "title": title,
                    "body": section.body if section else False,
                    "page_break": line.page_break,
                    "show_number": line.show_number,
                    "show_title": line.show_title,
                })
                line_to_block[line.id] = block.id
            # 2ª passagem: propagar parent_id
            for line in order.proposal_template_id.line_ids:
                if line.parent_id and line.id in line_to_block:
                    parent_block_id = line_to_block.get(line.parent_id.id)
                    if parent_block_id:
                        Block.browse(line_to_block[line.id]).write(
                            {"parent_id": parent_block_id}
                        )

    def _proposal_block_numbering(self):
        """Retorna dict {block_id: 'número_hierárquico'} para todos os blocos incluídos.

        Ex: {1: '1', 2: '2', 3: '3', 4: '3.1', 5: '3.2', 6: '3.3', 7: '4'}
        Blocos com show_number=False recebem string vazia ''.
        Suporta profundidade arbitrária (1, 1.1, 1.1.1, …).
        """
        self.ensure_one()
        def _sort_key(b):
            rec_id = b.id
            if not isinstance(rec_id, int):
                # NewId (registro virtual em onchange): usa origin ou 0
                rec_id = getattr(rec_id, "origin", 0) or 0
            return (b.sequence, rec_id)

        blocks = self.proposal_block_ids.filtered("included").sorted(_sort_key)
        numbers = {}
        root_counter = 0
        child_counters = {}  # parent_id → contagem de filhos vistos

        for block in blocks:
            if not block.parent_id:
                if block.show_number:
                    root_counter += 1
                    numbers[block.id] = str(root_counter)
                    child_counters[block.id] = 0
                else:
                    numbers[block.id] = ""
            else:
                pid = block.parent_id.id
                child_counters.setdefault(pid, 0)
                if block.show_number:
                    child_counters[pid] += 1
                    parent_num = numbers.get(pid, "")
                    numbers[block.id] = (
                        f"{parent_num}.{child_counters[pid]}"
                        if parent_num
                        else str(child_counters[pid])
                    )
                else:
                    numbers[block.id] = ""

        return numbers

    def action_reload_proposal_blocks(self):
        """Apaga blocos atuais e recarrega do template (descarta edições)."""
        self.ensure_one()
        self.proposal_block_ids.unlink()
        self._seed_proposal_blocks()
        return True

    def _find_mail_template(self):
        """F9.3: override — usa template LabQuali quando SO tem linhas de qualificação.

        Demais SOs caem no template padrão Odoo (sale.email_template_edi_sale).
        Confirmation/done seguem fluxo padrão também.
        """
        self.ensure_one()
        if (
            not self.env.context.get('proforma')
            and self.state not in ('sale', 'done')
            and self.has_qualif_lines
        ):
            tmpl = self.env.ref(
                'afr_qualificacao.email_template_proposal_labquali',
                raise_if_not_found=False,
            )
            if tmpl:
                return tmpl
        return super()._find_mail_template()

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
        rows = []
        for line in lines:
            qty = line.qualif_cycle_qty or int(line.product_uom_qty or 0)
            hours = line.estimated_hours or line.cycle_type_id.estimated_hours or 0.0
            rows.append({
                "name": line.cycle_type_id.name,
                "qty": qty,
                "temperature": line.temperature or line.cycle_type_id.temperature or "",
                "duration": line.duration or line.cycle_type_id.duration or "",
                "estimated_hours_total": hours * qty,
            })
        return rows

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
                qty = line.qualif_cycle_qty or int(line.product_uom_qty or 0)
                hours = line.estimated_hours or cycle_type.estimated_hours or 0.0
                rows.append({
                    "name": cycle_type.name,
                    "qty": qty,
                    "temperature": line.temperature or cycle_type.temperature or "",
                    "duration": line.duration or cycle_type.duration or "",
                    "load_type": load_labels.get(
                        line.load_type or cycle_type.load_type, ""
                    ),
                    "estimated_hours_total": hours * qty,
                })
            result.append({
                "equipment": equip,
                "rows": rows,
                "time_label": (
                    equip.category_id._qualif_time_label()
                    if equip.category_id else _("Tempo de Esterilização")
                ),
            })
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

    def action_open_generate_os_wizard(self):
        """Abre o wizard de geração de OS por grupo de equipamentos."""
        self.ensure_one()
        if self.state != "sale":
            raise UserError(_(
                "Confirme a cotação antes de gerar OS de Qualificação."
            ))
        if not self.equipamentos_sem_os_ids:
            raise UserError(_(
                "Todos os equipamentos desta cotação já têm OS gerada."
            ))
        return {
            "type": "ir.actions.act_window",
            "name": _("Gerar OS de Qualificação"),
            "res_model": "afr.qualificacao.os.generate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_sale_order_id": self.id},
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

    def action_apply_all_equipment_targets(self):
        """Ratea todos os equipamentos com alvo definido e fora do alvo.

        Cada section é rateada isoladamente: uma que não pode ser rateada
        (base vazia/zerada) não pode derrubar a transação inteira e travar
        o rateio dos equipamentos saudáveis — daí o try/except por section.
        Seguro porque `_apply_equipment_target` só levanta `UserError`
        (base vazia/zerada) em `return`/`raise`, nunca depois de um
        `write()` — inclusive o guard de alvo inválido (target<=0) também
        retorna antes de qualquer write. Nenhum dos dois caminhos de falha
        deixa write parcial pra trás. As falhas são acumuladas e
        reportadas junto com os inexatos na mesma notification.
        """
        self.ensure_one()
        inexatos = []
        falhas = []
        for section in self.equipment_target_ids:
            if section.equipment_target_state != "drift":
                continue
            try:
                res = section._apply_equipment_target()
            except UserError as exc:
                falhas.append("%s: %s" % (
                    section.equipment_id.display_name or "",
                    exc.args[0] if exc.args else "",
                ))
                continue
            if not res["exact"]:
                inexatos.append(section.equipment_id.display_name or "")
        if not inexatos and not falhas:
            return True
        messages = []
        if inexatos:
            messages.append(_(
                "Não foi possível fechar exatamente: %s. Veja o histórico "
                "do pedido."
            ) % ", ".join(inexatos))
        if falhas:
            messages.append(_(
                "Não foi possível ratear: %s."
            ) % "; ".join(falhas))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning",
                "title": _("Rateio parcial") if falhas
                else _("Rateio aproximado"),
                "message": "\n".join(messages),
                "sticky": False,
            },
        }

    @api.onchange("partner_id")
    def _onchange_partner_id_qualif_equipment_warning(self):
        """Avisa ao trocar o cliente se há equipamentos de qualificação que
        pertencem a outro cliente — eles podem não ser do cliente escolhido.

        Onchange não bloqueia a troca (Odoo não tem confirm nativo aqui); o
        aviso lista os equipamentos divergentes para o usuário revisar o
        escopo / reabrir o configurador.
        """
        managed = self.order_line.filtered(
            lambda l: l.is_qualificacao_managed and l.equipment_id
        )
        equips = managed.mapped("equipment_id")
        if not equips:
            return
        mismatched = equips.filtered(
            lambda e: e.client_id and e.client_id != self.partner_id
        )
        if not mismatched:
            return
        return {
            "warning": {
                "title": _("Cliente alterado — confira os equipamentos"),
                "message": _(
                    "Esta cotação já tem equipamentos de qualificação que "
                    "pertencem a outro cliente e podem não ser de %s:\n%s\n\n"
                    "Revise o escopo (reabra o Configurador) antes de "
                    "confirmar."
                ) % (
                    self.partner_id.display_name or _("(sem cliente)"),
                    "\n".join("• %s" % e.display_name for e in mismatched),
                ),
            }
        }

    # ------------------------------------------------------------------
    # F10 — helpers usados no confirm. O plano de recursos em si vive em
    # afr.qualificacao.os (operacional/PCP), não no SO.
    # ------------------------------------------------------------------
    def _qd_template_for(self, equipment):
        """Template de equipamento (da section line) p/ snapshot dos pontos QD."""
        self.ensure_one()
        section = self.order_line.filtered(
            lambda l: l.display_type == "line_section"
            and l.equipment_id == equipment
            and l.config_template_id
        )[:1]
        if section:
            return section.config_template_id
        any_line = self.order_line.filtered(
            lambda l: l.equipment_id == equipment and l.config_template_id
        )[:1]
        return any_line.config_template_id if any_line else False

    # ------------------------------------------------------------------
    # Confirm → NÃO gera mais engc.os/afr.qualificacao. Geração de OS de
    # qualificação é manual e incremental, por grupo de equipamentos, via
    # action_open_generate_os_wizard() na SO já confirmada (16.0.6.13.0).
    # ------------------------------------------------------------------
    def action_confirm(self):
        """Override: sincroniza qty de opcionais antes de confirmar.

        16.0.6.13.0 — o confirm NÃO materializa mais qualificações/OS. A
        geração passou a ser manual e incremental, por grupo de equipamentos,
        via `action_open_generate_os_wizard()` na SO confirmada.
        """
        for order in self:
            order.order_line._sync_optional_qty()
        return super().action_confirm()

    def _pending_qualif_lines(self):
        """Linhas managed elegíveis que ainda não têm afr.qualificacao.

        Elegível = gerada pelo configurador, não é seção/nota, não teve a
        Parte 01 recusada, e — se for opcional — foi aceita e tem tipo.
        """
        self.ensure_one()
        managed = self.order_line.filtered(
            lambda l: l.is_qualificacao_managed
            and not l.display_type
            and not l.part01_declined
            and not (l.is_proposal_optional and not l.optional_accepted)
            and not (l.is_proposal_optional and not l.qualification_type)
        )
        return managed.filtered(lambda l: not l.afr_qualificacao_id)

    def _materialize_qualificacoes(self, lines, os):
        """Cria afr.qualificacao + sub-records de `lines`, dentro de `os`.

        - 1 afr.qualificacao por (equipamento, qualification_type)
        - QD/QO com cycle_type: N afr.qualificacao.cycle por linha (qty=N)
        - Calibração: N afr.qualificacao.malha por linha
        - QI/QS e QO booleano: sem sub-records
        - Snapshot dos pontos QD + explosão de collect.items do procedimento

        Não resolve OS — o chamador escolhe o destino. É o que permite
        1 cotação → N OS.
        """
        self.ensure_one()
        Qualif = self.env["afr.qualificacao"]
        Cycle = self.env["afr.qualificacao.cycle"]
        Malha = self.env["afr.qualificacao.malha"]
        Procedimento = self.env["afr.qualificacao.procedimento"]
        CollectItem = self.env["afr.qualificacao.collect.item"]

        by_equipment = defaultdict(lambda: self.env["sale.order.line"])
        for line in lines:
            by_equipment[line.equipment_id] |= line

        for equipment, equip_lines in by_equipment.items():
            by_type = defaultdict(lambda: self.env["sale.order.line"])
            for line in equip_lines:
                by_type[line.qualification_type] |= line

            for qtype, type_lines in by_type.items():
                qualif = Qualif.create(
                    self._prepare_qualificacao_values(equipment, qtype, os)
                )
                type_lines.write({"afr_qualificacao_id": qualif.id})

                # F10 — snapshot dos pontos QD (cópia própria do template),
                # p/ o plano de recursos não depender do template depois.
                if qtype == "performance":
                    tpl = self._qd_template_for(equipment)
                    if tpl and tpl.qd_point_ids:
                        qualif.sudo().write({
                            "qd_point_snapshot_ids": [
                                (0, 0, {
                                    "sensor_kind_id": p.sensor_kind_id.id,
                                    "points": p.points,
                                })
                                for p in tpl.qd_point_ids
                            ]
                        })

                # F8.8 — QO cycle-based explode igual ao QD.
                if qtype in ("performance", "operational"):
                    for line in type_lines:
                        if not line.cycle_type_id:
                            continue
                        qty = line.qualif_cycle_qty or int(line.product_uom_qty or 0)
                        for seq in range(1, qty + 1):
                            Cycle.create({
                                "qualificacao_id": qualif.id,
                                "cycle_type_id": line.cycle_type_id.id,
                                "sale_order_line_id": line.id,
                                "sequence": seq * 10,
                            })
                elif qtype == "calibration":
                    for line in type_lines:
                        qty = line.qualif_cycle_qty or int(line.product_uom_qty or 0)
                        for seq in range(1, qty + 1):
                            Malha.create({
                                "qualificacao_id": qualif.id,
                                "malha_type_id": line.malha_type_id.id,
                                "sale_order_line_id": line.id,
                                "sequence": seq * 10,
                            })

                # F3/F1: explode procedimento default em collect.items.
                # sudo: quem confirma a SO pode não ter grupos de qualificação.
                proc = Procedimento.sudo().resolve_for(equipment.category_id)
                if proc:
                    self._explode_collect_items(CollectItem.sudo(), qualif, proc, qtype)

    def _explode_collect_items(self, CollectItem, qualif, procedimento, phase):
        """F3/F1: Cria N collect.items por procedimento.item conforme target_level.

        Filtra os itens do procedimento pela `phase` da qualificação (F1).
        target_level=qualificacao → 1 item por qualif
        target_level=cycle → 1 item por cycle existente (qualif QD)
        target_level=malha → 1 item por malha existente (qualif Calib)
        """
        items = procedimento.item_ids.filtered(lambda pi: pi.phase == phase)
        for pi in items:
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
                    vals["name"] = cycle.display_name
                    CollectItem.create(vals)
            elif pi.target_level == "malha":
                for malha in qualif.malha_ids:
                    vals = dict(base_vals)
                    vals["malha_id"] = malha.id
                    vals["name"] = malha.display_name
                    CollectItem.create(vals)

    def _prepare_qualificacao_os_values(self, equipments=None, pending_equipments=None):
        """Hook: valores para criar afr.qualificacao.os a partir do SO.

        Nome derivado: substitui 'C' inicial pelo prefixo 'OS'.
        Ex: C26-06-0001 → OS26-06-0001

        Com N OS por cotação o nome precisa de sufixo — `unique(name,
        company_id)` no modelo. A decisão é tomada na criação, sem rename
        retroativo:

        - 1ª OS cobrindo TODOS os equipamentos pendentes → sem sufixo
          (a cotação nunca terá uma segunda OS).
        - Qualquer outro caso → `-1`, `-2`, `-3`… Um primeiro clique parcial
          já nasce `-1` porque virá pelo menos a `-2`.

        `equipments`/`pending_equipments` a None = caminho legado (sem sufixo).

        Fallback: se a SO não tem formato esperado, o nome é gerado por
        sequência no create() do modelo.
        """
        self.ensure_one()
        vals = {
            "sale_order_id": self.id,
            "company_id": self.company_id.id,
        }
        so_name = self.name or ""
        if so_name.startswith("C") and len(so_name) > 1:
            base = "OS" + so_name[1:]
            existentes = len(self.qualificacao_os_ids)
            cobre_tudo = (
                equipments is not None
                and pending_equipments is not None
                and set(equipments.ids) == set(pending_equipments.ids)
            )
            if existentes == 0 and (equipments is None or cobre_tudo):
                vals["name"] = base
            else:
                vals["name"] = self._next_free_qualificacao_os_name(
                    base, existentes + 1
                )
        return vals

    def _next_free_qualificacao_os_name(self, base, start):
        """Próximo nome `base-N` livre, a partir de `start`, pulando ocupados.

        `existentes` (nº de OS vinculadas à cotação) não é o mesmo que
        "sufixos já emitidos": se uma OS sufixada for apagada ou
        desvinculada da cotação, `existentes` cai e recalcular `-N` direto
        poderia colidir com `unique(name, company_id)` de
        `afr.qualificacao.os`. Por isso consulta os nomes já usados com o
        mesmo prefixo/empresa (sudo — record rule não pode esconder um nome
        ocupado) e incrementa até achar um livre. Em uso normal (nenhuma OS
        apagada), devolve `start` mesmo — produz -1, -2, -3 em sequência.
        """
        self.ensure_one()
        ocupados = set(
            self.env["afr.qualificacao.os"]
            .sudo()
            .search([
                ("name", "=like", base + "%"),
                ("company_id", "=", self.company_id.id),
            ])
            .mapped("name")
        )
        n = start
        candidate = "%s-%d" % (base, n)
        while candidate in ocupados:
            n += 1
            candidate = "%s-%d" % (base, n)
        return candidate

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
            # F10.4 — parallel_group definido manualmente na OS (não vem do SO).
            # engc_os_id deprecated — não preenchido para SOs novas.
        }

    def _portal_toggle_optional(self, line_id, accepted):
        """Grava optional_accepted numa linha opcional, a partir do portal.
        Valida estado editável + pertença + tipo. Retorna dict de estado."""
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            raise UserError(_(
                "Esta cotação já foi confirmada; os opcionais não podem "
                "mais ser alterados."))
        line = self.order_line.filtered(lambda l: l.id == int(line_id))
        if not line or not line.is_proposal_optional:
            raise UserError(_("Item opcional inválido."))
        line.optional_accepted = bool(accepted)
        line._sync_optional_qty()
        return {
            "accepted": line.optional_accepted,
            "amount_total": self.amount_total,
        }
