"""Bloco de proposta montado por cotação (F8.2 — Proposta LEGO).

Cada `afr.proposal.block` é uma peça de lego de uma proposta concreta.
O wizard configurador (ou o botão "Carregar Blocos") copia os slots do
`afr.proposal.template` escolhido para blocos da `sale.order`, onde o
comercial monta a proposta: reordena, liga/desliga (`included`) e edita
o texto (`body`) sem afetar a biblioteca institucional de seções.

O relatório de cotação (F8.3) percorre os blocos `included=True` na
ordem de `sequence`.
"""

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang

from .proposal_template import PROPOSAL_APPLIES_WHEN, PROPOSAL_BLOCK_KINDS


class AfrProposalBlock(models.Model):
    """Bloco de proposta de uma sale.order específica."""

    _name = "afr.proposal.block"
    _description = "Bloco de Proposta da Cotação"
    _order = "sequence, id"

    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    block_kind = fields.Selection(
        selection=PROPOSAL_BLOCK_KINDS,
        string="Tipo de Bloco",
        required=True,
        default="static",
    )
    section_id = fields.Many2one(
        comodel_name="afr.proposal.section",
        string="Seção de Origem",
        ondelete="set null",
        domain=[("document_type", "=", "proposal")],
        help="Bloco de texto da biblioteca que originou este bloco.",
    )
    title = fields.Char(
        string="Título",
        help="Título exibido no relatório (editável por proposta).",
    )
    body = fields.Html(
        string="Conteúdo",
        sanitize=True,
        help=(
            "Conteúdo do bloco, cópia editável da seção de origem. Aceita "
            "expressões {{ ... }} resolvidas na renderização da proposta."
        ),
    )
    included = fields.Boolean(
        string="Incluir na Proposta",
        default=True,
        help="Desmarque para omitir este bloco do PDF sem apagá-lo.",
    )
    page_break = fields.Boolean(
        string="Nova Página",
        default=False,
        help=(
            "Se marcado, o bloco inicia em nova página no PDF. Caso "
            "contrário, continua na mesma página do bloco anterior."
        ),
    )
    # F9.1 — Hierarquia pai/filho entre blocos da mesma cotação
    parent_id = fields.Many2one(
        comodel_name="afr.proposal.block",
        string="Bloco Pai",
        domain="[('sale_order_id', '=', sale_order_id), ('id', '!=', id)]",
        ondelete="set null",
        index=True,
        help="Bloco pai na hierarquia da proposta. Ex: 'Qualificação Térmica' é pai de QI, QO, QD.",
    )
    child_ids = fields.One2many(
        comodel_name="afr.proposal.block",
        inverse_name="parent_id",
        string="Sub-blocos",
    )
    show_number = fields.Boolean(
        string="Numerado",
        default=True,
        help=(
            "Exibe numeração hierárquica automática no título do PDF "
            "(ex: 3, 3.1, 3.2). Desmarque para omitir o número."
        ),
    )
    show_title = fields.Boolean(
        string="Titulado",
        default=True,
        help=(
            "Exibe o título do bloco no PDF. Desmarque para renderizar "
            "apenas o conteúdo, sem cabeçalho."
        ),
    )
    applies_when = fields.Selection(
        selection=PROPOSAL_APPLIES_WHEN,
        string="Aplica-se",
        required=True,
        default="always",
        help=(
            "Condição para o bloco aparecer na proposta, avaliada contra o "
            "conteúdo atual da cotação. Sub-blocos seguem também a condição "
            "do pai."
        ),
    )
    service_group_id = fields.Many2one(
        comodel_name="afr.servico.grupo",
        string="Grupo de Serviço",
        ondelete="restrict",
        help="Grupo cujo serviço na cotação ativa o bloco (aplica-se = grupo).",
    )
    is_applicable = fields.Boolean(
        compute="_compute_is_applicable",
        string="Aplicável",
        help="False quando a condição do bloco (ou do pai) não é satisfeita pela cotação.",
    )
    hidden_reason = fields.Char(
        compute="_compute_hidden_reason",
        string="Motivo",
        help="Por que o bloco não aparece na proposta (vazio se aplicável).",
    )
    # F9.2 — display fields (preview UX no editor da SO + popup parent_id)
    display_label = fields.Char(
        compute="_compute_display_label",
        string="Conteúdo",
        help="Cascade: título → nome da seção → rótulo do tipo.",
    )
    display_number = fields.Char(
        compute="_compute_display_number",
        string="Nº",
        help="Preview do número hierárquico calculado da posição na cotação.",
    )

    def _own_condition_holds(self):
        """True se a condição própria do bloco vale na cotação (sem o pai)."""
        self.ensure_one()
        order = self.sale_order_id
        if self.applies_when == "qualification":
            return bool(order.has_qualif_lines)
        if self.applies_when == "service_group":
            return bool(self.service_group_id) and (
                self.service_group_id in order._service_groups()
            )
        return True

    def _is_applicable(self):
        """True se a condição do bloco — e a do pai, se houver — vale na cotação."""
        self.ensure_one()
        ok = self._own_condition_holds()
        if ok and self.parent_id:
            ok = self.parent_id._is_applicable()
        return ok

    def _prints_chapter(self):
        """True se o bloco, quando visível, imprime um capítulo nesta cotação.

        Fonte única de "este bloco tem conteúdo a imprimir": a numeração e
        os dois índices (`sale.order._proposal_chapter_blocks`) e o `t-if`
        do wrapper dos templates de bloco (PDF e portal) consultam este
        método, para que nenhum bloco ganhe número sem imprimir nada.

        - `equipment_scope`: só com qualificação (sem ela o bloco pode
          continuar visível para emitir os totais, sem título);
        - `standards_table`: só com normas a listar;
        - `optionals`: só com linhas opcionais;
        - `service_group`: só com linhas de serviço do grupo;
        - `financial`: só o emissor de totais (um segundo bloco não imprime);
        - `sales_items`: só com linhas de venda a listar;
        - demais (`static`, `schedule`, `acceptance`): sempre.
        """
        self.ensure_one()
        order = self.sale_order_id
        kind = self.block_kind
        if kind == "equipment_scope":
            return bool(order.has_qualif_lines)
        if kind == "standards_table":
            return bool(order.qualif_standard_ids)
        if kind == "optionals":
            return bool(order._proposal_optional_lines())
        if kind == "service_group":
            return bool(self.service_group_id) and bool(
                order._service_lines(self.service_group_id))
        if kind == "financial":
            return self == order._proposal_totals_emitter()
        if kind == "sales_items":
            return bool(order._proposal_sales_item_lines())
        return True

    # Gatilhos comuns de tudo que depende da condição do bloco.
    _APPLICABLE_DEPENDS = (
        "applies_when", "service_group_id", "parent_id", "sale_order_id",
        "sale_order_id.has_qualif_lines", "sale_order_id.order_line",
    )

    @api.depends(*_APPLICABLE_DEPENDS)
    def _compute_is_applicable(self):
        for block in self:
            block.is_applicable = (
                bool(block.sale_order_id) and block._is_applicable()
            )

    @api.depends(*_APPLICABLE_DEPENDS, "service_group_id.name")
    def _compute_hidden_reason(self):
        for block in self:
            reason = ""
            if block.sale_order_id and not block._is_applicable():
                if not block._own_condition_holds():
                    if block.applies_when == "qualification":
                        reason = _("Sem qualificação na cotação")
                    else:
                        reason = _(
                            "Sem serviço do grupo %s",
                            block.service_group_id.name or "",
                        )
                else:
                    reason = _("Bloco pai oculto")
            block.hidden_reason = reason

    @api.constrains("applies_when", "block_kind", "service_group_id")
    def _check_applies_when_group(self):
        for record in self:
            if (
                "service_group" in (record.applies_when, record.block_kind)
                and not record.service_group_id
            ):
                raise ValidationError(
                    _("Informe o Grupo de Serviço quando o bloco é do tipo "
                      "Serviços do Grupo ou se aplica a um grupo de serviço.")
                )

    @api.depends("title", "section_id", "block_kind")
    def _compute_display_label(self):
        kind_labels = dict(PROPOSAL_BLOCK_KINDS)
        for block in self:
            block.display_label = (
                block.title
                or (block.section_id.name if block.section_id else "")
                or kind_labels.get(block.block_kind, "")
            )

    @api.depends(
        "sale_order_id",
        "sequence",
        "parent_id",
        "show_number",
        "included",
        "applies_when",
        "service_group_id",
        # Mesmos gatilhos de `is_applicable`: a numeração só conta blocos
        # aplicáveis.
        "sale_order_id.has_qualif_lines",
        "sale_order_id.order_line",
        "sale_order_id.proposal_block_ids.sequence",
        "sale_order_id.proposal_block_ids.parent_id",
        "sale_order_id.proposal_block_ids.show_number",
        "sale_order_id.proposal_block_ids.included",
        "sale_order_id.proposal_block_ids.applies_when",
        "sale_order_id.proposal_block_ids.service_group_id",
    )
    def _compute_display_number(self):
        """Preview da numeração hierárquica por cotação. Reusa
        SaleOrder._proposal_block_numbering()."""
        for block in self:
            block.display_number = ""
        orders = self.mapped("sale_order_id")
        for order in orders:
            numbers = order._proposal_block_numbering()
            for block in order.proposal_block_ids:
                block.display_number = numbers.get(block.id, "")

    @api.constrains("parent_id")
    def _check_no_cycle(self):
        """Impede referências circulares na hierarquia de blocos."""
        for record in self:
            ancestor = record.parent_id
            visited = {record.id}
            while ancestor:
                if ancestor.id in visited:
                    raise ValidationError(
                        _("Hierarquia circular detectada no bloco '%s'.")
                        % record.title or record.id
                    )
                visited.add(ancestor.id)
                ancestor = ancestor.parent_id

    def name_get(self):
        """Display: título do bloco ou rótulo do tipo dinâmico."""
        kind_labels = dict(PROPOSAL_BLOCK_KINDS)
        result = []
        for record in self:
            label = record.title or kind_labels.get(
                record.block_kind, record.block_kind or ""
            )
            result.append((record.id, label))
        return result

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, name_get_uid=None):
        """F9.2: busca por título, nome da seção OU rótulo do tipo de bloco."""
        args = args or []
        domain = []
        if name:
            kind_labels = dict(PROPOSAL_BLOCK_KINDS)
            matched_kinds = [
                code for code, label in kind_labels.items()
                if name.lower() in (label or "").lower()
            ]
            domain = ["|", "|",
                      ("title", operator, name),
                      ("section_id.name", operator, name),
                      ("block_kind", "in", matched_kinds) if matched_kinds else ("id", "=", 0)]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)

    # ------------------------------------------------------------------
    # F8.5 — editar bloco (modal); snapshot de bloco dinâmico → texto
    # ------------------------------------------------------------------
    def action_edit_block(self):
        """Abre o editor do bloco em modal.

        Bloco dinâmico (escopo, ciclos, financeiro...) é convertido por
        snapshot: o conteúdo auto-gerado é congelado em HTML editável e o
        bloco passa a ser `static` — a partir daí é texto livre.
        """
        self.ensure_one()
        if self.block_kind == "financial":
            raise UserError(_(
                "O bloco de totais é recalculado a cada emissão da proposta "
                "e não pode ser convertido em bloco editável. Para alterar o "
                "que aparece nos totais, edite as linhas da cotação."
            ))
        if self.block_kind != "static":
            self.body = self._snapshot_html()
            if not self.title:
                self.title = dict(PROPOSAL_BLOCK_KINDS).get(self.block_kind, "")
            self.block_kind = "static"
        return {
            "type": "ir.actions.act_window",
            "name": _("Editar Bloco da Proposta"),
            "res_model": "afr.proposal.block",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(
                self.env.ref("afr_qualificacao.view_proposal_block_form").id,
                "form",
            )],
            "target": "new",
        }

    def _qualif_is_frozen_financial_summary(self):
        """True se este bloco `static` é um Resumo Financeiro congelado.

        Critério ESTREITO (3 condições cumulativas) usado pela migração
        16.0.7.0.0 para limpar blocos `financial` que alguém converteu
        para `static` (snapshot manual) ANTES do `UserError` em
        `action_edit_block` passar a proibir essa conversão — cobre o
        caso real da base (afr.proposal.block id=636, SO C26-08-0018,
        com "TOTAL GERAL: R$ 10.373,48" congelado no body).

        As 3 condições, cumulativas, para não apagar um bloco de texto
        livre que o usuário só batizou com o mesmo título:
        - `block_kind == 'static'`;
        - `title` igual ao rótulo do bloco financeiro
          (`PROPOSAL_BLOCK_KINDS['financial']`, hoje "Resumo Financeiro");
        - `body` contendo o texto "TOTAL GERAL" (assinatura do totalizador
          antigo, `_qualif_grand_total_html`/SEÇÃO 6 do fallback).
        """
        self.ensure_one()
        if self.block_kind != "static":
            return False
        financial_label = dict(PROPOSAL_BLOCK_KINDS).get("financial")
        if not financial_label or self.title != financial_label:
            return False
        return bool(self.body) and "TOTAL GERAL" in str(self.body)

    def _snapshot_html(self):
        """Renderiza o conteúdo dinâmico atual do bloco em HTML editável."""
        self.ensure_one()
        builder = {
            "equipment_scope": self._html_equipment_scope,
            "schedule": self._html_schedule,
            "service_group": self._html_service_group,
            "standards_table": self._html_standards,
            "optionals": self._html_optionals,
            "acceptance": self._html_acceptance,
        }.get(self.block_kind)
        if not builder:
            return self.body or Markup("")
        return builder(self.sale_order_id)

    def _money(self, order, value):
        """Formata valor monetário na moeda da cotação."""
        return formatLang(self.env, value, currency_obj=order.currency_id)

    def _html_equipment_scope(self, order):
        """Snapshot HTML da tabela de escopo (DOCX + bloco editável).

        Espelha o QWeb `qq_block_equipment_scope` byte-a-byte na estrutura
        (mesmas classes de `reports/templates_blocos/styles.xml`): o
        snapshot é reaproveitado dentro do PDF/portal sob o mesmo CSS, e
        precisa renderizar igual ao bloco dinâmico ao lado (card, quebra
        de página controlada, etc).
        """
        parts = []
        for index, table in enumerate(order._qualif_scope_tables()):
            equip = table["equipment"]
            letter = chr(ord("a") + index)
            head = escape("%s. %s" % (letter, equip.name or ""))
            if equip.serial_number:
                head += Markup(" — S/N: ") + escape(equip.serial_number)
            rows = [Markup(
                "<tr class='qq-scope-equip-header'>"
                "<td colspan='2'><strong>%s</strong></td></tr>") % head]
            for group in table["groups"]:
                for row in group["rows"]:
                    rows.append(Markup(
                        "<tr class='qq-scope-group-row'>"
                        "<td class='qq-scope-stage'>%s</td>"
                        "<td class='qq-scope-description'>%s</td></tr>"
                    ) % (escape(row["label"]), self._html_scope_cell(row)))
                rows.append(Markup(
                    "<tr class='qq-scope-subtotal-row'><td>%s</td>"
                    "<td>%s: %s</td></tr>"
                ) % (
                    escape(order._qualif_days_label(group["days"])),
                    escape(group["subtotal_label"]),
                    escape(self._money(order, group["subtotal"])),
                ))
            rows.append(Markup(
                "<tr class='qq-scope-footer-row'><td>%s</td>"
                "<td>Valor Unitário: %s</td></tr>"
            ) % (
                escape(order._qualif_days_label(table["footer"]["days"])),
                escape(self._money(order, table["footer"]["unit_price"])),
            ))
            head_row, body_rows = rows[0], Markup("").join(rows[1:])
            parts.append(Markup(
                "<div class='qq-equip-card'>"
                "<table class='qq-scope-table'>"
                "<thead>%s</thead><tbody>%s</tbody></table></div>"
            ) % (head_row, body_rows))
        # SEM tabela de totais: o snapshot congela só o escopo. Os totais são
        # sempre ao vivo, impressos pelo emissor (`_proposal_totals_emitter`:
        # bloco `financial` ou o fim da lista de blocos). Congelá-los aqui
        # duplicaria a tabela (e deixaria uma cópia desatualizada).
        return Markup("").join(parts) or Markup("<p></p>")

    def _html_scope_cell(self, row):
        """Conteúdo da coluna direita de uma linha do escopo."""
        if row["kind"] == "ref":
            return escape(row["ref"])
        if row["kind"] == "cycles":
            body = Markup("").join(
                Markup("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>")
                % (
                    escape("%02d" % cyc["qty"]), escape(cyc["name"]),
                    escape(cyc["temperature"]), escape(cyc["duration"]),
                )
                for cyc in row["cycles"]
            )
            return Markup(
                "<div class='qq-scope-subtitle'><strong>%s</strong></div>"
                "<table class='qq-cycle-table'><thead><tr>"
                "<th>Quantidade</th><th>Ciclo</th><th>Temperatura</th>"
                "<th>%s</th></tr></thead><tbody>%s</tbody></table>"
            ) % (escape(row["title"]), escape(row["time_label"]), body)
        items = Markup("").join(
            Markup("<li>%s</li>") % escape(it) for it in row["items"])
        title = (
            Markup("<div class='qq-scope-subtitle'><strong>%s</strong></div>")
            % escape(row["title"]) if row["title"] else Markup("")
        )
        return title + Markup("<ul class='qq-scope-list'>%s</ul>") % items

    def _html_schedule(self, order):
        """F8.14 — tabela cronograma equipamento × horas × dias úteis."""
        rows = order._qualif_schedule_rows()
        if not rows:
            return Markup("<p></p>")
        first_col = (
            "Equipamento / Serviço"
            if any(not r["equipment"] for r in rows) else "Equipamento"
        )
        body = [Markup(
            "<table class='qq-table'>"
            "<thead><tr><th>%s</th>"
            "<th style='text-align:right;'>Horas</th>"
            "<th style='text-align:right;'>h/dia</th>"
            "<th style='text-align:right;'>Dias úteis</th></tr></thead><tbody>"
        ) % first_col]
        total_h = 0.0
        total_d = 0.0
        for r in rows:
            body.append(Markup(
                "<tr><td>%s</td>"
                "<td style='text-align:right;'>%.1f</td>"
                "<td style='text-align:right;'>%.1f</td>"
                "<td style='text-align:right;'>%.2f</td></tr>"
            ) % (
                escape(r.get("label") or r["equipment"].display_name or ""),
                r["hours"], r["work_hours_per_day"], r["days"],
            ))
            total_h += r["hours"]
            total_d += r["days"]
        body.append(Markup(
            "</tbody>"
            "<tfoot><tr><td><strong>TOTAL</strong></td>"
            "<td style='text-align:right;'><strong>%.1f</strong></td>"
            "<td></td>"
            "<td style='text-align:right;'><strong>%.2f</strong></td></tr></tfoot>"
            "</table>"
        ) % (total_h, total_d))
        return Markup("").join(body)

    def _html_service_group(self, order):
        """Snapshot HTML do capítulo de serviço (tabela + relação de unidades).

        Mesmos dados do QWeb `qq_block_service_group` e do portal
        (`_service_group_table`). Congela só a tabela do capítulo.
        """
        group = self.service_group_id
        table = order._service_group_table(group) if group else None
        if not table or not table["rows"]:
            return Markup("<p></p>")
        rows = Markup("").join(
            Markup(
                "<tr><td>%s</td><td><strong>%s</strong>%s%s</td><td>%s</td>"
                "<td style='text-align:right;'>%s</td>"
                "<td style='text-align:right;'>%s</td></tr>"
            ) % (
                row["item"],
                escape(row["name"]),
                Markup("<br/><small>%s</small>") % escape(row["description"])
                if row["description"] else Markup(""),
                Markup("<br/><small>Procedimento: %s</small>")
                % escape(row["procedure"])
                if row["procedure"] else Markup(""),
                self._plain_qty(row["qty"]),
                escape(self._money(order, row["price_unit"])),
                escape(self._money(order, row["subtotal"])),
            )
            for row in table["rows"]
        )
        html = Markup(
            "<table class='qq-table'><thead><tr><th>Item</th><th>Serviço</th>"
            "<th>Qtd</th><th style='text-align:right;'>Valor Unitário</th>"
            "<th style='text-align:right;'>Valor Total</th></tr></thead>"
            "<tbody>%s</tbody></table>"
            "<p style='text-align:right;'><strong>%s</strong> %s</p>"
        ) % (
            rows,
            escape("Subtotal %s:" % group._chapter_title()),
            escape(self._money(order, table["subtotal"])),
        )
        if table["days_label"]:
            html += Markup("<p style='text-align:right;'>%s</p>") % escape(
                table["days_label"])
        if table["units"]:
            units = Markup("").join(
                Markup(
                    "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                    "<td>%s</td><td>%s</td></tr>"
                ) % (
                    unit.item_number or "—",
                    escape(unit.tag or ""),
                    escape(unit.description or ""),
                    escape(" / ".join(
                        v for v in (unit.marca, unit.model) if v)),
                    escape(unit.serial_number or ""),
                    escape(unit.location or ""),
                )
                for unit in table["units"]
            )
            html += Markup(
                "<p><strong>%s</strong></p>"
                "<table class='qq-table'><thead><tr><th>Item</th>"
                "<th>Identificação</th><th>Descrição</th>"
                "<th>Marca / Modelo</th><th>Série</th><th>Local</th></tr>"
                "</thead><tbody>%s</tbody></table>"
            ) % (
                escape("Relação de %s" % group._unit_label_plural()),
                units,
            )
        return html

    @staticmethod
    def _plain_qty(qty):
        """Quantidade sem casas quando inteira (8, não 8.0)."""
        return int(qty) if qty == int(qty) else qty

    def _html_standards(self, order):
        rows = Markup("").join(
            Markup(
                "<tr><td><strong>%s</strong></td><td>%s</td>"
                "<td>%s</td><td>%s</td></tr>"
            ) % (
                escape(std.code or ""), escape(std.name or ""),
                escape(std.organism or ""), escape(std.description or ""),
            )
            for std in order.qualif_standard_ids
        )
        return Markup(
            "<table><thead><tr><th>Código</th><th>Nome</th>"
            "<th>Organismo</th><th>Escopo</th></tr></thead>"
            "<tbody>%s</tbody></table>"
        ) % rows

    def _html_optionals(self, order):
        opt_lines = order.order_line.filtered("is_proposal_optional")
        rows = Markup("").join(
            Markup(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            ) % (
                "☑" if line.optional_accepted else "☐",
                escape(line.name or ""),
                line.optional_qty,
                escape(self._money(order, line.price_unit)),
                escape(self._money(order, line.optional_ref_subtotal)),
            )
            for line in opt_lines
        )
        return Markup(
            "<table><thead><tr><th></th><th>Serviço</th><th>Qtd</th>"
            "<th>Valor Unit.</th><th>Subtotal (ref.)</th></tr></thead>"
            "<tbody>%s</tbody></table>"
            "<p style='font-size:10px;color:#666'>☑ = autorizado pelo "
            "cliente. Apenas os itens marcados entram no total.</p>"
        ) % rows

    def _html_acceptance(self, order):
        return Markup(
            "<p>Declaro estar de acordo com os termos, escopo e valores "
            "apresentados nesta proposta.</p>"
            "<p><br/></p>"
            "<p>____________________________________</p>"
            "<p><strong>CLIENTE</strong> — %s</p>"
            "<p><br/></p>"
            "<p>____________________________________</p>"
            "<p><strong>EMPRESA</strong> — %s</p>"
            "<p>Local e data: ____________________, ____ / ____ / ________</p>"
        ) % (
            escape(order.partner_id.name or ""),
            escape(order.company_id.name or ""),
        )
