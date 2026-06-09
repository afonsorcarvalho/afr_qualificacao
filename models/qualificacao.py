"""Modelos de qualificação de equipamentos.

Este arquivo segue as orientações da documentação oficial do Odoo para criação
de modelos customizados:
https://www.odoo.com/documentation/16.0/pt_BR/developer/reference/backend/orm.html

Integração com docxtpl baseada no guia oficial:
https://docxtpl.readthedocs.io/en/latest/usage.html
"""

import base64
import copy
import hashlib
import json
import os
import uuid
from tempfile import NamedTemporaryFile

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

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
    # OS própria de qualificação (16.0.3.0.0). Em F1 só o campo;
    # a lógica de criação automática no SO confirm migra em F2.
    os_id = fields.Many2one(
        comodel_name="afr.qualificacao.os",
        string="OS de Qualificação",
        copy=False,
        ondelete="set null",
        index=True,
        tracking=True,
        help="Container hierárquico de qualificações (substitui engc_os a partir de 16.0.3.1.0).",
    )
    # DEPRECATED 16.0.3.1.0 — preservado para SOs antigas (sem migração: pré-produção).
    engc_os_id = fields.Many2one(
        comodel_name="engc.os",
        string="Ordem de Serviço (legacy)",
        copy=False,
        ondelete="set null",
        tracking=True,
        help="LEGACY (deprecated em 16.0.3.1.0): use os_id. Mantido para SOs antigas.",
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
    # F10.4 — grupo de execução paralela do equipamento nesta OS. Definido
    # manualmente na OS (PCP), não vem da cotação. Mesmo rótulo não-vazio
    # entre equipamentos = rodam simultâneos no plano de recursos.
    parallel_group = fields.Char(
        string="Grupo Paralelo",
        copy=False,
        help=(
            "Rótulo de execução simultânea (definido pelo PCP na OS). "
            "Equipamentos (qualifs) com o MESMO rótulo não-vazio rodam em "
            "paralelo no plano de recursos da OS; vazio = executado sozinho."
        ),
    )
    # F10 — snapshot dos pontos QD (cópia própria do template no confirm).
    # Mantém o plano de recursos estável mesmo que o template mude depois.
    qd_point_snapshot_ids = fields.One2many(
        comodel_name="afr.qualificacao.qd.point.snapshot",
        inverse_name="qualificacao_id",
        string="Pontos QD (snapshot)",
        copy=False,
        help=(
            "Cópia congelada dos pontos QD por grandeza no momento do "
            "confirm do SO. Independente do template de origem."
        ),
    )
    # F3 (16.0.3.2.0): coletas (checklist + anexos unificados)
    collect_item_ids = fields.One2many(
        comodel_name="afr.qualificacao.collect.item",
        inverse_name="qualif_id",
        string="Coletas",
    )
    collect_pending_count = fields.Integer(
        compute="_compute_collect_pending_count",
        string="Coletas pendentes",
    )
    # F4 (16.0.3.3.0): agregação de padrões metrológicos dos collect.items
    standard_instrument_ids = fields.Many2many(
        "engc.calibration.instruments",
        string="Padrões Metrológicos",
        compute="_compute_standard_instrument_ids",
        store=False,
        help="União dos padrões declarados nos collect.items desta qualificação.",
    )
    standard_instrument_count = fields.Integer(
        compute="_compute_standard_instrument_ids",
        string="Padrões",
    )
    standards_all_valid = fields.Boolean(
        compute="_compute_standards_validity",
        string="Padrões com certificado válido",
        store=False,
    )
    standards_warning_text = fields.Text(
        compute="_compute_standards_validity",
        string="Padrões sem certificado válido",
        store=False,
    )
    # F4.3 (16.0.3.4.0): agregação de cobertura de grandezas
    coverage_complete = fields.Boolean(
        compute="_compute_coverage_aggregate",
        store=False,
        string="Cobertura de grandezas completa",
    )
    coverage_warning_text = fields.Text(
        compute="_compute_coverage_aggregate",
        store=False,
        string="Coletas com cobertura incompleta",
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

    @api.depends("collect_item_ids", "collect_item_ids.state", "collect_item_ids.required")
    def _compute_collect_pending_count(self):
        for record in self:
            record.collect_pending_count = len(
                record.collect_item_ids.filtered(
                    lambda c: c.required and c.state == "pending"
                )
            )

    @api.depends("collect_item_ids.standard_instrument_ids")
    def _compute_standard_instrument_ids(self):
        for record in self:
            instruments = record.collect_item_ids.mapped("standard_instrument_ids")
            record.standard_instrument_ids = instruments
            record.standard_instrument_count = len(instruments)

    @api.depends(
        "collect_item_ids.coverage_complete",
        "collect_item_ids.required",
        "collect_item_ids.requires_instrument",
        "collect_item_ids.name",
        "collect_item_ids.coverage_warning_text",
    )
    def _compute_coverage_aggregate(self):
        for record in self:
            incomplete = record.collect_item_ids.filtered(
                lambda c: c.required and c.requires_instrument and not c.coverage_complete
            )
            record.coverage_complete = not incomplete
            if incomplete:
                lines = []
                for c in incomplete:
                    detail = c.coverage_warning_text or _("(sem padrão)")
                    lines.append("• %s — %s" % (c.name, detail))
                record.coverage_warning_text = "\n".join(lines)
            else:
                record.coverage_warning_text = ""

    @api.depends(
        "collect_item_ids.standard_instrument_ids",
        "collect_item_ids.standard_instrument_ids.certificate_ids.validate_calibration",
    )
    def _compute_standards_validity(self):
        today = fields.Date.today()
        for record in self:
            invalid = []
            instruments = record.collect_item_ids.mapped("standard_instrument_ids")
            for inst in instruments:
                has_valid = any(
                    c.validate_calibration and c.validate_calibration >= today
                    for c in inst.certificate_ids
                )
                if not has_valid:
                    invalid.append(
                        inst.display_name
                        or inst.name
                        or inst.id_number
                        or _("Instrumento #%s") % inst.id
                    )
            record.standards_all_valid = not invalid
            record.standards_warning_text = ", ".join(invalid)

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
        """Altera o status para 'Aprovada', emite certificado e propaga qty_delivered.

        F4 (16.0.3.3.0): valida padrões metrológicos. Se algum instrumento
        sem certificado válido (`validate_calibration >= today`):
        - flag `qualif_block_approval_expired_standards` True → ValidationError
        - flag False (default) → message_post warning (não-bloqueante)

        F4.3 (16.0.3.4.0): valida cobertura de grandezas dos collect.items
        required que exigem instrumento (requires_instrument=True). Se algum
        item required tem coverage_complete=False:
        - flag `qualif_block_approval_incomplete_coverage` True → ValidationError
        - flag False (default) → message_post warning
        """
        ICP = self.env["ir.config_parameter"].sudo()
        block_expired = str(
            ICP.get_param(
                "afr_qualificacao.qualif_block_approval_expired_standards",
                default="False",
            )
        ).lower() in ("true", "1", "yes")
        block_coverage = str(
            ICP.get_param(
                "afr_qualificacao.qualif_block_approval_incomplete_coverage",
                default="False",
            )
        ).lower() in ("true", "1", "yes")
        for record in self:
            if not record.standards_all_valid and record.standard_instrument_count:
                msg = _(
                    "Padrões metrológicos sem certificado de calibração válido: %s"
                ) % record.standards_warning_text
                if block_expired:
                    raise ValidationError(msg)
                record.message_post(
                    body=msg,
                    subject=_("Aviso: padrões com certificado expirado"),
                )
            if not record.coverage_complete:
                msg = _(
                    "Coletas com cobertura de grandezas incompleta:\n%s"
                ) % (record.coverage_warning_text or _("(sem detalhes)"))
                if block_coverage:
                    raise ValidationError(msg)
                record.message_post(
                    body=msg,
                    subject=_("Aviso: cobertura de grandezas incompleta"),
                )
            # F4.7: coletas required materializadas precisam vir de relatório
            orphan = record.collect_item_ids.filtered(
                lambda c: c.required and c.state == "collected" and not c.relatorio_id
            )
            if orphan:
                names = ", ".join(orphan.mapped("name"))
                raise ValidationError(_(
                    "Coletas marcadas como coletadas mas sem relatório vinculado: %s. "
                    "Coletas devem ser realizadas através de um Relatório da OS."
                ) % names)
            # F4.8: ciclos/malhas materializados precisam vir de relatório
            orphan_cycles = record.cycle_ids.filtered(
                lambda c: c.state in ("passed", "failed") and not c.relatorio_id
            )
            if orphan_cycles:
                names = ", ".join(orphan_cycles.mapped("display_name"))
                raise ValidationError(_(
                    "Ciclos marcados como executados sem relatório vinculado: %s. "
                    "Execução de ciclos deve ser registrada via Relatório da OS."
                ) % names)
            orphan_malhas = record.malha_ids.filtered(
                lambda m: m.state in ("collected", "certified", "failed") and not m.relatorio_id
            )
            if orphan_malhas:
                names = ", ".join(orphan_malhas.mapped("display_name"))
                raise ValidationError(_(
                    "Malhas marcadas como executadas sem relatório vinculado: %s. "
                    "Execução de malhas deve ser registrada via Relatório da OS."
                ) % names)
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
                # qty_delivered em HORAS (UdM da linha) = ciclos aprovados ×
                # horas/ciclo, casando com product_uom_qty (horas pedidas).
                hours = line.estimated_hours or line.cycle_type_id.estimated_hours or 0.0
                line.qty_delivered = passed * hours
        elif self.qualification_type == "calibration":
            from collections import defaultdict
            by_line = defaultdict(lambda: [0, 0])
            for malha in self.malha_ids:
                if not malha.sale_order_line_id:
                    continue
                key = malha.sale_order_line_id
                by_line[key][1] += 1
                if malha.state in ("collected", "certified"):
                    by_line[key][0] += 1
            for line, (passed, _total) in by_line.items():
                # qty_delivered em HORAS = malhas concluídas × horas/malha.
                hours = line.estimated_hours or line.malha_type_id.estimated_hours or 0.0
                line.qty_delivered = passed * hours

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

    # ------------------------------------------------------------------
    # F6.1 (16.0.3.5.0) — geração do relatório DOCX (QI/QO/QD/QS)
    # ------------------------------------------------------------------
    # Mapeia qualification_type → xmlid do template default em data seed.
    # QS reusa template QI até existir template específico (gap F6.x).
    _DOCX_TEMPLATE_XMLID_BY_TYPE = {
        "installation": "afr_qualificacao.tpl_docx_qi",
        "operational": "afr_qualificacao.tpl_docx_qo",
        "performance": "afr_qualificacao.tpl_docx_qd",
        "software": "afr_qualificacao.tpl_docx_qi",
    }

    def _docx_partner_dict(self):
        """Bloco `cliente` do contexto DOCX (chaves do exemplo_contexto.json)."""
        self.ensure_one()
        p = self.partner_id
        if not p:
            return {}
        return {
            "nome": p.name or "",
            "fantasia": getattr(p, "commercial_company_name", "") or p.name or "",
            "cnpj": p.vat or "",
            "endereco": p.street or "",
            "cidade": p.city or "",
            "uf": (p.state_id.code if p.state_id else "") or "",
            "cep": p.zip or "",
            "unidade": "",
            "responsavel_tecnico": "",
            "email": p.email or "",
            "telefone": p.phone or "",
        }

    def _docx_equipment_dict(self):
        """Bloco `equipamento` do contexto DOCX. Defensivo: campos opcionais."""
        self.ensure_one()
        e = self.equipment_id
        if not e:
            return {}

        def g(field, default=""):
            return getattr(e, field, default) or default

        return {
            "descricao": e.display_name or e.name or "",
            "tag": g("tag", "") or g("internal_code", ""),
            "fabricante": g("manufacturer", ""),
            "modelo": g("model", ""),
            "numero_serie": g("serial_number", ""),
            "ano_fabricacao": g("manufacture_year", ""),
            "capacidade": g("capacity", ""),
            "faixa_operacao": g("operation_range", ""),
            "tensao": g("voltage", ""),
            "frequencia": g("frequency", ""),
            "localizacao": g("location", ""),
            "software": g("software", ""),
            "versao_software": g("software_version", ""),
        }

    def _docx_company_dict(self):
        c = self.env.company
        parts = [c.street, c.city, c.state_id.code if c.state_id else ""]
        endereco = ", ".join(p for p in parts if p)
        return {
            "nome": c.name or "",
            "cnpj": c.vat or "",
            "endereco": endereco,
        }

    def _docx_user_block(self, user):
        """Bloco {nome, cargo, data} para aprovacao.elaborado/revisado/aprovado."""
        if not user:
            return {"nome": "", "cargo": "", "data": ""}
        emp = self.env["hr.employee"].search(
            [("user_id", "=", user.id)], limit=1
        )
        cargo = (emp.job_title if emp else "") or ""
        data = self.execution_date.isoformat() if self.execution_date else ""
        return {"nome": user.name or "", "cargo": cargo, "data": data}

    def _docx_aprovacao_dict(self):
        """Bloco aprovacao: elaborado / revisado / aprovado."""
        self.ensure_one()
        revisor = (
            self.os_id.tecnico_default_id.user_id
            if self.os_id and self.os_id.tecnico_default_id
            else False
        )
        return {
            "elaborado": self._docx_user_block(self.responsible_id),
            "revisado": self._docx_user_block(revisor or self.responsible_id),
            "aprovado": self._docx_user_block(self.approver_id),
        }

    def _docx_instruments_summary(self):
        """Bloco `instrumentos[]`: deduplica padrões dos collect.items."""
        self.ensure_one()
        rows = []
        seen = set()
        for inst in self.standard_instrument_ids:
            if inst.id in seen:
                continue
            seen.add(inst.id)
            cert = inst.certificate_ids[:1]
            rows.append({
                "tag": getattr(inst, "id_number", "") or "",
                "descricao": inst.display_name or inst.name or "",
                "fabricante": getattr(inst, "manufacturer", "") or "",
                "modelo": getattr(inst, "model", "") or "",
                "numero_serie": getattr(inst, "serial_number", "") or "",
                "certificado": (cert.number if cert and hasattr(cert, "number") else "") or "",
                "validade": cert.validate_calibration.isoformat()
                if cert and cert.validate_calibration else "",
            })
        return rows

    def _docx_collect_item_row(self, item):
        """Linha tabular padrão para uma coleta dentro de qualquer seção do DOCX.

        F6.1 — sem parse granular de XLSX/CSV: usa apenas metadados da coleta.
        F6.x futuro popula colunas como sensor/posicao/t_min/t_max a partir
        do binário `item.file`.
        """
        captured = (
            item.captured_at.isoformat() if item.captured_at else ""
        )
        return {
            "nome": item.name or "",
            "descricao": item.description or item.instruction or "",
            "kind": dict(item._fields["kind"].selection).get(item.kind, item.kind),
            "state": item.state,
            "captured_at": captured,
            "captured_by": item.captured_by.name if item.captured_by else "",
            "arquivo": item.filename or "",
            "conforme": "Sim" if item.state == "collected" else "Não",
            # Campos placeholder para colunas técnicas (preenchidos em F6.x):
            "especificado": "",
            "encontrado": "",
            "criterio": "",
            "resultado": "",
            "sensor": "",
            "posicao": "",
            "t_min": "",
            "t_max": "",
            "t_media": "",
            "delta_t": "",
            "t_plateau": "",
            "tempo": "",
            "f0": "",
        }

    def _docx_group_by_section(self, prefix):
        """Agrupa collect.items por docx_section que comece com `prefix`.

        Retorna dict {sub_section_name: [row_dict, ...]} pronto pra
        `ctx['qi'] = {'utilidades': [...], 'documentos': [...]}`.
        """
        self.ensure_one()
        out = {}
        prefix_full = prefix + "_"
        for item in self.collect_item_ids:
            sec = item.docx_section or ""
            if not sec.startswith(prefix_full):
                continue
            sub = sec[len(prefix_full):]
            out.setdefault(sub, []).append(self._docx_collect_item_row(item))
        return out

    # Skeletons mínimos por tipo: templates docxtpl chamam {{ qx.sub_block.attr }}
    # mesmo quando user não tem dados, então TODAS as chaves precisam existir
    # (jinja2 strict undefined). Listas vazias e dicts com strings vazias são
    # renderizados como linhas vazias / colunas em branco — comportamento OK
    # para F6.1. Sub-dicts (programa, resumo, carga, bowie_dick) virão de
    # campos custom em F6.x próximo (parse XLSX, modelo dedicado, ou form
    # extra no qualif).
    _DOCX_QX_SKELETONS = {
        "qi": {
            "utilidades": [],
            "documentos": [],
            "componentes": [],
            "instalacao": [],
            "calibracoes": [],
            "treinamentos": [],
        },
        "qo": {
            "testes_funcionais": [],
            "testes_seguranca": [],
            "programa": {
                "nome": "", "setpoint": "", "tempo_exposicao": "",
                "qtd_sensores": "", "intervalo_leitura": "", "qtd_ciclos": "",
            },
            "mapeamento_ciclo1": [],
            "mapeamento_ciclo2": [],
            "mapeamento_ciclo3": [],
            "resumo": {
                "tempo_total": "", "t_max_global": "", "t_min_global": "",
                "t_media_global": "", "delta_t_max": "",
                "pressao_saturacao": "", "t_calc_pressao": "", "f0": "",
            },
        },
        "qd": {
            "carga": {
                "tipo": "", "descricao": "", "densidade": "",
                "embalagem": "", "posicionamento": "", "itens": [],
            },
            "penetracao_ciclo1": [],
            "penetracao_ciclo2": [],
            "penetracao_ciclo3": [],
            "indicadores_quimicos": [],
            "indicadores_biologicos": [],
            "bowie_dick": {
                "aplicavel": "", "tipo": "", "lote": "",
                "validade": "", "resultado": "", "conforme": "",
            },
            "repetibilidade": [],
        },
    }

    def _docx_qx_block(self, prefix):
        """Monta bloco qi/qo/qd com skeleton completo + popula via coletas."""
        self.ensure_one()
        # Deep-copy do skeleton (dicts nested precisam de cópia)
        block = copy.deepcopy(self._DOCX_QX_SKELETONS.get(prefix, {}))
        # Popula listas a partir das coletas com docx_section correspondente
        grouped = self._docx_group_by_section(prefix)
        for sub, rows in grouped.items():
            if sub == "carga":
                # qd_carga: coletas viram itens dentro do dict carga
                block.setdefault("carga", {"itens": []})
                if isinstance(block["carga"], dict):
                    block["carga"]["itens"] = rows
            elif sub in block and isinstance(block[sub], list):
                block[sub] = rows
            else:
                # Section não declarada no skeleton — adiciona como lista
                # (template novo no futuro pode pedir; não quebra render)
                block[sub] = rows
        block.update({
            "resultado": dict(self._fields["state"].selection).get(
                self.state, self.state
            ),
            "observacoes": "",
            "acoes_corretivas": "",
            "executor": self.responsible_id.name if self.responsible_id else "",
            "data_execucao": self.execution_date.isoformat()
            if self.execution_date else "",
        })
        return block

    def _build_docx_context(self):
        """Monta dict completo conforme docs/exemplo_contexto.json.

        F6.1 (16.0.3.5.0): cobre empresa, documento, cliente, equipamento,
        aprovacao, instrumentos[]. Blocos qi/qo/qd populados conforme
        `qualification_type` da qualif (outros ficam vazios). Blocos
        `revisoes[]` e `conclusao` ficam com defaults vazios — gap declarado
        para etapa F6.x futura.
        """
        self.ensure_one()
        type_to_prefix = {
            "installation": "qi",
            "operational": "qo",
            "performance": "qd",
            "software": "qi",  # QS reusa estrutura QI nesta etapa
        }
        ctx = {
            "empresa": self._docx_company_dict(),
            "documento": {
                "titulo": "%s — %s" % (
                    dict(self._fields["qualification_type"].selection).get(
                        self.qualification_type, ""
                    ),
                    self.name or "",
                ),
                "codigo": self.name or "",
                "revisao": "01",
                "data_emissao": self.execution_date.isoformat()
                if self.execution_date else "",
                "proxima_revisao": "",
                "procedimento_referencia": "",
                "qi_codigo": "",
                "qo_codigo": "",
            },
            "cliente": self._docx_partner_dict(),
            "equipamento": self._docx_equipment_dict(),
            "aprovacao": self._docx_aprovacao_dict(),
            "revisoes": [],  # F6.x: modelo dedicado se necessário
            "instrumentos": self._docx_instruments_summary(),
            "qi": {},
            "qo": {},
            "qd": {},
            "conclusao": {
                "status": dict(self._fields["state"].selection).get(
                    self.state, self.state
                ),
                "validade": "",
                "proxima_qualificacao": "",
                "observacoes": "",
            },
            "anexos": {"observacoes": ""},
        }
        prefix = type_to_prefix.get(self.qualification_type)
        if prefix:
            ctx[prefix] = self._docx_qx_block(prefix)
        return ctx

    def _resolve_docx_template_bytes(self):
        """Retorna (bytes, source_label) do template DOCX a renderizar.

        Ordem: 1) docx_template_id manual; 2) lookup por xmlid baseado em
        qualification_type. Raise UserError se nenhum disponível.
        """
        self.ensure_one()
        # 1) Escolha manual no formulário da qualif
        if self.docx_template_id and self.docx_template_id.datas:
            try:
                return (
                    base64.b64decode(self.docx_template_id.datas),
                    self.docx_template_id.display_name,
                )
            except Exception as error:
                raise UserError(
                    _("Falha ao decodificar o template selecionado: %s") % error
                ) from error
        # 2) Fallback automático por tipo via data seed
        xmlid = self._DOCX_TEMPLATE_XMLID_BY_TYPE.get(self.qualification_type)
        if xmlid:
            tpl = self.env.ref(xmlid, raise_if_not_found=False)
            if tpl and tpl.datas:
                try:
                    return base64.b64decode(tpl.datas), tpl.display_name
                except Exception as error:
                    raise UserError(
                        _("Falha ao decodificar template default %s: %s") % (
                            xmlid, error,
                        )
                    ) from error
        raise UserError(_(
            "Nenhum template DOCX disponível para a qualificação tipo '%s'. "
            "Selecione manualmente em 'Template DOCX' ou verifique se o "
            "data seed do módulo foi carregado (afr.qualificacao.docx.template)."
        ) % self.qualification_type)

    def action_generate_docx(self):
        """Gera relatório DOCX da qualificação via docxtpl (F6.1).

        Resolve template (manual ou default por tipo), monta contexto rico
        conforme docs/exemplo_contexto.json, renderiza e cria ir.attachment.
        Retorna act_url abrindo o attachment em nova aba.

        Calibração: NÃO suportado nesta etapa — use `action_print_certificate`
        (report QWeb nativo de engc.calibration). Gap declarado em F6.x.
        """
        self.ensure_one()
        if self.qualification_type == "calibration":
            raise UserError(_(
                "Geração DOCX não suportada para qualificação tipo Calibração. "
                "Use o botão 'Imprimir Certificado' (report QWeb nativo de "
                "engc.calibration)."
            ))
        if DocxTemplate is None:
            raise UserError(_(
                "A biblioteca docxtpl não está disponível. Verifique se o "
                "pacote Python foi instalado conforme a documentação."
            ))

        template_bytes, _source = self._resolve_docx_template_bytes()

        temp_template = NamedTemporaryFile(suffix=".docx", delete=False)
        temp_template_path = temp_template.name
        try:
            temp_template.write(template_bytes)
            temp_template.flush()
            temp_template.close()
            try:
                document = DocxTemplate(temp_template_path)
            except Exception as error:
                raise UserError(
                    _("Falha ao carregar o template DOCX: %s") % error
                ) from error

            context = self._build_docx_context()
            try:
                document.render(context)
            except Exception as error:
                raise UserError(
                    _("Falha ao renderizar template DOCX: %s") % error
                ) from error

            with NamedTemporaryFile(suffix=".docx") as out:
                document.save(out.name)
                out.seek(0)
                file_content = out.read()
        finally:
            if os.path.exists(temp_template_path):
                try:
                    os.unlink(temp_template_path)
                except OSError:
                    pass

        if not file_content:
            raise UserError(_("O arquivo gerado está vazio."))

        report_name = "%s.docx" % (self.name or "qualificacao")
        attachment = self.env["ir.attachment"].create({
            "name": report_name,
            "type": "binary",
            "datas": base64.b64encode(file_content),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s" % attachment.id,
            "target": "new",
        }


class AfrQualificacaoQdPointSnapshot(models.Model):
    """F10 — snapshot de pontos QD por grandeza numa qualificação.

    Cópia própria de `config_template.qd_point_ids`, gravada no confirm do SO
    para que o plano de recursos não dependa do template (que pode mudar).
    """

    _name = "afr.qualificacao.qd.point.snapshot"
    _description = "Snapshot de Pontos QD por Grandeza"
    _order = "sensor_kind_id, id"

    qualificacao_id = fields.Many2one(
        comodel_name="afr.qualificacao",
        string="Qualificação",
        required=True,
        ondelete="cascade",
    )
    sensor_kind_id = fields.Many2one(
        comodel_name="afr.qualificacao.sensor.kind",
        string="Grandeza",
        required=True,
    )
    points = fields.Integer(string="Pontos", default=1, required=True)

