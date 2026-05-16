"""Modelos de qualificação de equipamentos.

Este arquivo segue as orientações da documentação oficial do Odoo para criação
de modelos customizados:
https://www.odoo.com/documentation/16.0/pt_BR/developer/reference/backend/orm.html

Integração com docxtpl baseada no guia oficial:
https://docxtpl.readthedocs.io/en/latest/usage.html
"""

import base64
import hashlib
import json
import os
import uuid
from tempfile import NamedTemporaryFile

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.modules.module import get_module_resource

try:
    from docxtpl import DocxTemplate  # type: ignore[import]
except ImportError:  # pragma: no cover - tratado em tempo de execução
    DocxTemplate = None


class AfrQualificacao(models.Model):
    """Representa uma qualificação de equipamento conforme QI, QO ou QD."""

    _name = "afr.qualificacao"
    _description = "Qualificação de Equipamento"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_date desc, name"

    name = fields.Char(
        string="Referência",
        required=True,
        tracking=True,
        default=lambda self: _("Nova qualificação"),
        help="Identificação única da qualificação registrada.",
    )
    equipment_id = fields.Many2one(
        comodel_name="engc.equipment",
        string="Equipamento",
        required=True,
        tracking=True,
        help="Equipamento proveniente do módulo engc_os vinculado à qualificação.",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        tracking=True,
        compute="_compute_partner_id",
        store=True,
        readonly=False,
        help=(
            "Cliente contratante da qualificação. Por padrão herdado do "
            "equipamento (engc.equipment.client_id), mas pode ser ajustado "
            "manualmente caso o serviço seja prestado a outro parceiro."
        ),
    )
    qualification_type = fields.Selection(
        selection=[
            ("installation", "Instalação (QI)"),
            ("operational", "Operacional (QO)"),
            ("performance", "Desempenho (QD)"),
            ("software", "Software (QS)"),
            ("calibration", "Calibração"),
        ],
        string="Tipo de Qualificação",
        required=True,
        default="installation",
        tracking=True,
        help=(
            "Classificação da etapa de qualificação conforme práticas "
            "QI/QO/QD/QS + Calibração metrológica."
        ),
    )
    state = fields.Selection(
        selection=[
            ("draft", "Rascunho"),
            ("in_progress", "Em andamento"),
            ("approved", "Aprovada"),
            ("rejected", "Reprovada"),
            ("cancelled", "Cancelada"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        help="Situação atual da qualificação conforme documentação de fluxos do Odoo.",
    )
    planned_date = fields.Date(
        string="Data planejada",
        tracking=True,
        help="Data prevista para realização da qualificação.",
    )
    execution_date = fields.Date(
        string="Data de execução",
        tracking=True,
        help="Data em que a qualificação foi concluída.",
    )
    responsible_id = fields.Many2one(
        comodel_name="res.users",
        string="Responsável",
        tracking=True,
        help="Usuário responsável por acompanhar a execução da qualificação.",
    )
    approver_id = fields.Many2one(
        comodel_name="res.users",
        string="Aprovador",
        tracking=True,
        help="Usuário que aprova a qualificação após análise dos resultados.",
    )
    notes = fields.Html(
        string="Observações",
        help="Resumo dos principais detalhes coletados durante a qualificação.",
    )
    deviation_ids = fields.One2many(
        comodel_name="afr.qualificacao.deviation",
        inverse_name="qualificacao_id",
        string="Desvios",
        help="Registros de desvios identificados durante as etapas de qualificação.",
    )
    step_ids = fields.One2many(
        comodel_name="afr.qualificacao.step",
        inverse_name="qualificacao_id",
        string="Etapas de teste",
        help="Lista de roteiros executados para validar o equipamento.",
    )
    step_count = fields.Integer(
        string="Total de etapas",
        compute="_compute_step_count",
        help="Total de etapas vinculadas a esta qualificação.",
    )
    deviation_count = fields.Integer(
        string="Total de desvios",
        compute="_compute_deviation_count",
        help="Total de desvios registrados na qualificação.",
    )
    docx_template_id = fields.Many2one(
        comodel_name="afr.qualificacao.docx.template",
        string="Template DOCX",
        help="Selecione o template DOCX a ser utilizado para gerar o relatório.",
        domain=[("active", "=", True)],
    )

    # ------------------------------------------------------------------
    # Multi-company + integração comercial (quote-first SO → qualif)
    # ------------------------------------------------------------------
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
        help="Empresa proprietária do registro (multi-company).",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Pedido de Venda (origem)",
        copy=False,
        readonly=True,
        tracking=True,
        ondelete="set null",
        help=(
            "Pedido de venda que originou esta qualificação. Populado "
            "automaticamente quando o SO é confirmado via fluxo quote-first."
        ),
    )
    sale_order_line_ids = fields.Many2many(
        comodel_name="sale.order.line",
        string="Linhas do Pedido",
        compute="_compute_sale_order_line_ids",
        help=(
            "Linhas SO que originaram esta qualificação. Para Calibração/QD "
            "agrega linhas dos sub-records (cycles/malhas). Para QI/QO/QS "
            "tipicamente 1 única linha."
        ),
    )
    invoice_status = fields.Selection(
        selection=[
            ("upselling", "Upselling"),
            ("invoiced", "Faturado"),
            ("to invoice", "A faturar"),
            ("no", "Nada a faturar"),
        ],
        string="Status de Faturamento",
        compute="_compute_invoice_status",
        store=False,
        help="Pior status entre as linhas SO ligadas.",
    )
    invoice_ids = fields.Many2many(
        comodel_name="account.move",
        string="Faturas",
        compute="_compute_invoice_ids",
        help="Faturas geradas a partir das linhas SO associadas.",
    )
    invoice_count = fields.Integer(
        string="Total de Faturas",
        compute="_compute_invoice_ids",
    )

    # ------------------------------------------------------------------
    # Vínculos engc_os + sub-records (cycles / malhas)
    # ------------------------------------------------------------------
    engc_os_id = fields.Many2one(
        comodel_name="engc.os",
        string="Ordem de Serviço",
        copy=False,
        ondelete="set null",
        tracking=True,
        help="OS gerada automaticamente para esta qualificação (1 por equipamento).",
    )
    cycle_ids = fields.One2many(
        comodel_name="afr.qualificacao.cycle",
        inverse_name="qualificacao_id",
        string="Ciclos (QD)",
        help="Sub-records de ciclos para Qualificação de Desempenho.",
    )
    cycle_count = fields.Integer(
        string="Total de Ciclos",
        compute="_compute_cycle_count",
    )
    malha_ids = fields.One2many(
        comodel_name="afr.qualificacao.malha",
        inverse_name="qualificacao_id",
        string="Malhas (Calibração)",
        help="Sub-records de malhas para Calibração.",
    )
    malha_count = fields.Integer(
        string="Total de Malhas",
        compute="_compute_malha_count",
    )

    # ------------------------------------------------------------------
    # Integração engc.calibration (Opção A — schema preparado, link manual)
    # ------------------------------------------------------------------
    engc_calibration_id = fields.Many2one(
        comodel_name="engc.calibration",
        string="Calibração engc_os",
        copy=False,
        ondelete="set null",
        help=(
            "Link manual para a engc.calibration que contém certificado + "
            "pontos de medição desta qualificação tipo Calibração. Permite "
            "reuso do framework metrológico existente (incerteza, erro, Veff)."
        ),
    )
    engc_calibration_state = fields.Selection(
        related="engc_calibration_id.state",
        string="Status Calibração",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # F4.3 — Certificado: hash imutável + token UUID + QR público
    # ------------------------------------------------------------------
    certificate_token = fields.Char(
        string="Token de Verificação",
        copy=False,
        readonly=True,
        index=True,
        help=(
            "UUID4 hex gerado ao approval. Usado na URL pública de "
            "verificação do certificado: /qualificacao/verify/<token>."
        ),
    )
    certificate_hash = fields.Char(
        string="Hash SHA-256",
        copy=False,
        readonly=True,
        help=(
            "Hash SHA-256 hex (64 chars) do snapshot dos campos técnicos + "
            "sub-records, congelado ao approval. Validação recomputa e "
            "compara — qualquer alteração pós-approval = certificado adulterado."
        ),
    )
    certificate_issued_at = fields.Datetime(
        string="Emissão do Certificado",
        copy=False,
        readonly=True,
        help="Datetime em que hash + token foram congelados (no approval).",
    )
    certificate_verify_url = fields.Char(
        compute="_compute_certificate_verify_url",
        string="URL Pública de Verificação",
    )

    @api.depends("certificate_token")
    def _compute_certificate_verify_url(self):
        ICP = self.env["ir.config_parameter"].sudo()
        base = ICP.get_param("web.base.url", default="")
        # Inclui ?db=<dbname> para evitar fallhar com db_filter em ambientes
        # multi-db (pula 404 quando primeiro DB não tem o módulo). Override
        # via config param 'afr_qualificacao.verify_url_db' (set para ""
        # se deployment single-db sem db_filter).
        db_param = ICP.get_param(
            "afr_qualificacao.verify_url_db",
            default=self.env.cr.dbname,
        )
        for rec in self:
            if rec.certificate_token:
                url = "%s/qualificacao/verify/%s" % (base, rec.certificate_token)
                if db_param:
                    url += "?db=%s" % db_param
                rec.certificate_verify_url = url
            else:
                rec.certificate_verify_url = False

    def _snapshot_for_hash(self):
        """Serializa estado técnico em JSON estável p/ hash SHA-256.

        Inclui: identidade, partner, equipamento, tipo, approval, state +
        sub-records (cycles/malhas com state, type, sequence, executed).
        Mudança em qualquer um destes = hash diferente na revalidação.
        """
        self.ensure_one()
        cycles = sorted([
            {
                "id": c.id,
                "type_id": c.cycle_type_id.id,
                "type": c.cycle_type_id.name,
                "sequence": c.sequence,
                "state": c.state,
                "executed_date": c.executed_date.isoformat() if c.executed_date else None,
            }
            for c in self.cycle_ids
        ], key=lambda d: (d["type_id"] or 0, d["sequence"], d["id"]))
        malhas = sorted([
            {
                "id": m.id,
                "type_id": m.malha_type_id.id,
                "type": m.malha_type_id.name,
                "sensor_kind": m.sensor_kind_id.name if m.sensor_kind_id else None,
                "sequence": m.sequence,
                "sensor_serial": m.sensor_serial or "",
                "state": m.state,
                "executed_date": m.executed_date.isoformat() if m.executed_date else None,
                "engc_calibration_measurement_id": m.engc_calibration_measurement_id.id
                or None,
            }
            for m in self.malha_ids
        ], key=lambda d: (d["type_id"] or 0, d["sequence"], d["id"]))
        snapshot = {
            "id": self.id,
            "name": self.name,
            "partner": self.partner_id.name or "",
            "partner_id": self.partner_id.id or 0,
            "equipment": self.equipment_id.display_name or "",
            "equipment_serial": self.equipment_id.serial_number or "",
            "qualification_type": self.qualification_type,
            "execution_date": self.execution_date.isoformat()
            if self.execution_date else None,
            "approver": self.approver_id.login if self.approver_id else None,
            "state": self.state,
            "company_id": self.company_id.id,
            "cycles": cycles,
            "malhas": malhas,
            "engc_calibration_id": self.engc_calibration_id.id or None,
        }
        return snapshot

    def _compute_certificate_hash(self):
        """Calcula SHA-256 hex do snapshot JSON estável (sort_keys + ensure_ascii)."""
        self.ensure_one()
        payload = json.dumps(
            self._snapshot_for_hash(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _issue_certificate(self):
        """Gera token + congela hash + marca issued_at. Idempotente: skip se já emitido."""
        self.ensure_one()
        if self.certificate_token and self.certificate_hash:
            return
        self.write({
            "certificate_token": uuid.uuid4().hex,
            "certificate_hash": self._compute_certificate_hash(),
            "certificate_issued_at": fields.Datetime.now(),
        })

    def verify_certificate(self):
        """Recomputa hash atual e compara com hash congelado.

        Retorna dict: {valid: bool, expected_hash, current_hash, issued_at}.
        Usado pelo controller público /qualificacao/verify/<token>.
        """
        self.ensure_one()
        current = self._compute_certificate_hash()
        return {
            "valid": bool(self.certificate_hash) and current == self.certificate_hash,
            "expected_hash": self.certificate_hash,
            "current_hash": current,
            "issued_at": self.certificate_issued_at,
        }

    def action_print_certificate(self):
        """Dispara o report QWeb apropriado.

        - Calibração COM engc_calibration_id linkada: usa report nativo
          engc_os (mostra certificado metrológico completo + bloco QR/hash).
        - Calibração SEM link: fallback usa template próprio
          (mostra afr.qualificacao.malha internas + QR/hash). Útil enquanto
          técnico ainda não preencheu engc.calibration ou pra qualifs
          standalone sem framework metrológico.
        - Outros tipos: sempre template próprio.
        """
        self.ensure_one()
        if not self.certificate_token:
            raise UserError(_(
                "Certificado ainda não emitido. Aprove a qualificação primeiro."
            ))
        if self.qualification_type == "calibration" and self.engc_calibration_id:
            return self.env.ref(
                "engc_os.report_engc_os_calibration_certificate"
            ).report_action(self.engc_calibration_id)
        return self.env.ref(
            "afr_qualificacao.action_report_qualificacao_certificate"
        ).report_action(self)

    @api.constrains("execution_date", "planned_date")
    def _check_dates(self):
        """Garante que a data de execução não seja anterior ao planejamento."""
        for record in self:
            if (
                record.execution_date
                and record.planned_date
                and record.execution_date < record.planned_date
            ):
                raise ValidationError(
                    _(
                        "A data de execução (%s) não pode ser anterior à data planejada (%s)."
                    )
                    % (record.execution_date, record.planned_date)
                )

    @api.depends("equipment_id", "sale_order_id.partner_id")
    def _compute_partner_id(self):
        """Cliente: SO.partner_id quando linkado, senão equipment.client_id (sticky).

        Quando qualif vem do fluxo quote-first (com sale_order_id), o cliente
        é a fonte da verdade do SO. Para qualifs standalone (sem SO), mantém
        sticky de equipment.client_id sem sobrescrever escolha manual.
        """
        for record in self:
            if record.sale_order_id:
                record.partner_id = record.sale_order_id.partner_id
            elif record.equipment_id and not record.partner_id:
                record.partner_id = record.equipment_id.client_id

    @api.depends("step_ids")
    def _compute_step_count(self):
        """Calcula a quantidade de etapas associadas à qualificação."""
        for record in self:
            record.step_count = len(record.step_ids)

    @api.depends("deviation_ids")
    def _compute_deviation_count(self):
        """Calcula a quantidade de desvios associados à qualificação."""
        for record in self:
            record.deviation_count = len(record.deviation_ids)

    # ------------------------------------------------------------------
    # Computes — sub-records + agregações comerciais
    # ------------------------------------------------------------------
    @api.depends("cycle_ids")
    def _compute_cycle_count(self):
        for record in self:
            record.cycle_count = len(record.cycle_ids)

    @api.depends("malha_ids")
    def _compute_malha_count(self):
        for record in self:
            record.malha_count = len(record.malha_ids)

    @api.depends(
        "qualification_type",
        "cycle_ids.sale_order_line_id",
        "malha_ids.sale_order_line_id",
        "sale_order_id.order_line",
    )
    def _compute_sale_order_line_ids(self):
        """Agrega linhas SO ligadas (direto ou via sub-records).

        - QI/QO/QS: linha SO única ligada via sale_order_line.afr_qualificacao_id
        - QD: agrega cycle_ids.sale_order_line_id
        - Calib: agrega malha_ids.sale_order_line_id
        """
        for record in self:
            lines = self.env["sale.order.line"]
            if record.qualification_type == "performance":
                lines = record.cycle_ids.mapped("sale_order_line_id")
            elif record.qualification_type == "calibration":
                lines = record.malha_ids.mapped("sale_order_line_id")
            else:
                # QI/QO/QS — busca direta via back-ref no sale.order.line
                if record.id and record.sale_order_id:
                    lines = record.sale_order_id.order_line.filtered(
                        lambda l: l.afr_qualificacao_id == record
                    )
            record.sale_order_line_ids = lines

    @api.depends(
        "qualification_type",
        "cycle_ids.sale_order_line_id.invoice_status",
        "malha_ids.sale_order_line_id.invoice_status",
        "sale_order_id.order_line.invoice_status",
        "sale_order_id.order_line.afr_qualificacao_id",
    )
    def _compute_invoice_status(self):
        """Pior status entre as linhas. Ordem: no < invoiced < upselling < to invoice."""
        priority = {"no": 0, "invoiced": 1, "upselling": 2, "to invoice": 3}
        for record in self:
            if not record.sale_order_line_ids:
                record.invoice_status = "no"
                continue
            statuses = record.sale_order_line_ids.mapped("invoice_status")
            best = max(statuses, key=lambda s: priority.get(s, 0))
            record.invoice_status = best

    @api.depends(
        "qualification_type",
        "cycle_ids.sale_order_line_id.invoice_lines.move_id",
        "malha_ids.sale_order_line_id.invoice_lines.move_id",
        "sale_order_id.order_line.invoice_lines.move_id",
        "sale_order_id.order_line.afr_qualificacao_id",
    )
    def _compute_invoice_ids(self):
        """Coleta faturas geradas a partir das linhas SO ligadas."""
        for record in self:
            moves = record.sale_order_line_ids.mapped("invoice_lines.move_id")
            record.invoice_ids = moves
            record.invoice_count = len(moves)

    def action_start(self):
        """Altera o status para 'Em andamento' seguindo o fluxo padrão do Odoo."""
        for record in self:
            record.state = "in_progress"
        return True

    def action_mark_approved(self):
        """Altera o status para 'Aprovada', emite certificado e propaga qty_delivered."""
        for record in self:
            record.state = "approved"
            record.execution_date = record.execution_date or fields.Date.context_today(
                self
            )
            record._issue_certificate()
            record._propagate_qty_delivered()
        return True

    def _propagate_qty_delivered(self):
        """Atualiza qty_delivered das linhas SO ligadas conforme tipo da qualif.

        - QI/QO/QS: qty_delivered = 1.0 nas linhas com afr_qualificacao_id == self
        - QD: qty_delivered = count(cycles state='passed') por linha SO
        - Calib: qty_delivered = count(malhas state='passed') por linha SO

        Permite que faturamento padrão do Odoo (sale.order.action_invoice)
        capture o valor a faturar sem hooks customizados em invoice creation.
        """
        self.ensure_one()
        if not self.sale_order_id:
            return
        if self.qualification_type in ("installation", "operational", "software"):
            lines = self.sale_order_id.order_line.filtered(
                lambda l: l.afr_qualificacao_id == self
            )
            for line in lines:
                line.qty_delivered = line.product_uom_qty
        elif self.qualification_type == "performance":
            # Agrupa cycles por linha SO, conta passed
            from collections import defaultdict
            by_line = defaultdict(lambda: [0, 0])  # [passed, total]
            for cycle in self.cycle_ids:
                if not cycle.sale_order_line_id:
                    continue
                key = cycle.sale_order_line_id
                by_line[key][1] += 1
                if cycle.state == "passed":
                    by_line[key][0] += 1
            for line, (passed, _total) in by_line.items():
                line.qty_delivered = passed
        elif self.qualification_type == "calibration":
            from collections import defaultdict
            by_line = defaultdict(lambda: [0, 0])
            for malha in self.malha_ids:
                if not malha.sale_order_line_id:
                    continue
                key = malha.sale_order_line_id
                by_line[key][1] += 1
                if malha.state == "passed":
                    by_line[key][0] += 1
            for line, (passed, _total) in by_line.items():
                line.qty_delivered = passed

    def action_mark_rejected(self):
        """Altera o status para 'Reprovada' quando os critérios não forem atendidos."""
        for record in self:
            record.state = "rejected"
            record.execution_date = record.execution_date or fields.Date.context_today(
                self
            )
        return True

    def action_cancel(self):
        """Cancela a qualificação sem excluir os registros já coletados."""
        for record in self:
            record.state = "cancelled"
        return True

    # ------------------------------------------------------------------
    # Navegação para registros relacionados (stat buttons)
    # ------------------------------------------------------------------
    def action_view_sale_order(self):
        """Abre o pedido de venda de origem."""
        self.ensure_one()
        if not self.sale_order_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.sale_order_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_invoices(self):
        """Abre lista de faturas geradas das linhas SO ligadas."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "name": _("Faturas"),
            "view_mode": "tree,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
        }

    def action_view_engc_os(self):
        """Abre a OS gerada."""
        self.ensure_one()
        if not self.engc_os_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "engc.os",
            "res_id": self.engc_os_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_engc_calibration(self):
        """Abre a engc.calibration linkada (Calib only)."""
        self.ensure_one()
        if not self.engc_calibration_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "engc.calibration",
            "res_id": self.engc_calibration_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_generate_docx(self):
        """Gera relatório DOCX usando docxtpl conforme documentação oficial.

        A seleção de template respeita a escolha do usuário no campo
        'Template DOCX'. Caso não haja seleção, utiliza o arquivo padrão
        em 'static/docx/qualificacao_template.docx'.
        """
        self.ensure_one()
        if DocxTemplate is None:
            raise UserError(
                _(
                    "A biblioteca docxtpl não está disponível. Verifique se o "
                    "pacote Python foi instalado conforme a documentação."
                )
            )
        document = None
        temp_template_path = None
        # 1) Tenta usar o template selecionado na qualificação (binário)
        if self.docx_template_id and self.docx_template_id.datas:  # type: ignore[attr-defined]
            try:
                template_bytes = base64.b64decode(self.docx_template_id.datas)  # type: ignore[attr-defined]
            except Exception as error:
                raise UserError(
                    _("Falha ao decodificar o template selecionado: %s") % error
                ) from error
            # Cria arquivo temporário que não será deletado automaticamente
            # para que o DocxTemplate possa acessá-lo durante o render
            temp_template = NamedTemporaryFile(suffix=".docx", delete=False)
            temp_template_path = temp_template.name
            try:
                temp_template.write(template_bytes)
                temp_template.flush()
                temp_template.close()  # Fecha o handle, mas mantém o arquivo
                try:
                    document = DocxTemplate(temp_template_path)
                except Exception as error:
                    raise UserError(
                        _("Falha ao carregar o template selecionado: %s") % error
                    ) from error
            except Exception:
                # Se houver erro, remove o arquivo temporário antes de relançar
                if temp_template_path and os.path.exists(temp_template_path):
                    os.unlink(temp_template_path)
                raise
        # 2) Fallback: template padrão no módulo
        if document is None:
            template_path = get_module_resource(
                "afr_qualificacao", "static", "docx", "qualificacao_template.docx"
            )
            if not template_path:
                raise UserError(
                    _(
                        "Modelo DOCX não encontrado. Adicione o arquivo "
                        "'qualificacao_template.docx' em afr_qualificacao/static/docx "
                        "ou selecione um Template DOCX na qualificação."
                    )
                )
            try:
                document = DocxTemplate(template_path)
            except Exception as error:  # docxtpl lança erros genéricos
                raise UserError(
                    _("Falha ao carregar o modelo DOCX: %s") % error
                ) from error

        context = {
            "qualificacao": self,
            "equipamento": self.equipment_id.name,  # type: ignore[attr-defined]
            "responsavel": self.responsible_id.name,
            "aprovador": self.approver_id.name,
            "company": self.env.company,
        }
        try:
            document.render(context)
        finally:
            # Remove o arquivo temporário após o render, se existir
            if temp_template_path and os.path.exists(temp_template_path):
                try:
                    os.unlink(temp_template_path)
                except Exception:
                    pass  # Ignora erros ao remover arquivo temporário

        with NamedTemporaryFile(suffix=".docx") as temp:
            document.save(temp.name)
            temp.seek(0)
            file_content = temp.read()

        if not file_content:
            raise UserError(_("O arquivo gerado está vazio."))

        report_name = "%s.docx" % (self.name or "qualificacao")  # type: ignore[attr-defined]
        attachment = self.env["ir.attachment"].create(
            {
                "name": report_name,
                "type": "binary",
                "datas": base64.b64encode(file_content),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }
        )

        # Abre o attachment em uma nova aba sem forçar download
        # O navegador tentará abrir com o aplicativo padrão ou oferecerá download
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s" % attachment.id,
            "target": "new",
        }


class AfrQualificacaoStep(models.Model):
    """Etapas executadas durante uma qualificação de equipamento."""

    _name = "afr.qualificacao.step"
    _description = "Etapa de Qualificação"
    _order = "sequence, id"

    qualificacao_id = fields.Many2one(
        comodel_name="afr.qualificacao",
        string="Qualificação",
        required=True,
        ondelete="cascade",
        help="Qualificação à qual esta etapa pertence.",
    )
    name = fields.Char(
        string="Descrição da etapa",
        required=True,
        help="Identificação clara da etapa executada.",
    )
    sequence = fields.Integer(
        string="Sequência",
        default=10,
        help="Ordem de execução sugerida para a etapa.",
    )
    acceptance_criteria = fields.Text(
        string="Critérios de aceitação",
        help="Condições esperadas conforme protocolos da etapa.",
    )
    result_notes = fields.Text(
        string="Resultados observados",
        help="Registro textual dos resultados obtidos na execução.",
    )
    approved = fields.Selection(
        selection=[
            ("pending", "Pendente"),
            ("yes", "Aprovado"),
            ("no", "Reprovado"),
        ],
        string="Resultado",
        default="pending",
        help="Resultado final da etapa conforme validação realizada.",
    )
    deviation_ids = fields.One2many(
        comodel_name="afr.qualificacao.deviation",
        inverse_name="step_id",
        string="Desvios associados",
        help="Desvios vinculados a esta etapa específica.",
    )


class AfrQualificacaoDeviation(models.Model):
    """Registra desvios identificados durante a qualificação."""

    _name = "afr.qualificacao.deviation"
    _description = "Desvio de Qualificação"
    _order = "create_date desc"

    qualificacao_id = fields.Many2one(
        comodel_name="afr.qualificacao",
        string="Qualificação",
        required=True,
        ondelete="cascade",
        help="Qualificação em que o desvio foi identificado.",
    )
    step_id = fields.Many2one(
        comodel_name="afr.qualificacao.step",
        string="Etapa",
        ondelete="set null",
        help="Etapa da qualificação em que o desvio ocorreu.",
    )
    name = fields.Char(
        string="Título do desvio",
        required=True,
        help="Título resumido para facilitar a identificação do desvio.",
    )
    description = fields.Text(
        string="Descrição detalhada",
        help="Detalhes completos do desvio encontrado durante a qualificação.",
    )
    corrective_action = fields.Text(
        string="Ação corretiva",
        help="Plano de ação definido para tratar o desvio identificado.",
    )
    responsible_id = fields.Many2one(
        comodel_name="res.users",
        string="Responsável",
        help="Usuário que acompanhará a execução da ação corretiva.",
    )
    deadline_date = fields.Date(
        string="Prazo",
        help="Data limite desejada para conclusão da ação corretiva.",
    )
    resolved = fields.Boolean(
        string="Resolvido",
        default=False,
        help="Indica se a ação corretiva foi implementada.",
    )

