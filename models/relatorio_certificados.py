# -*- coding: utf-8 -*-
"""Relatório final — P2 (16.0.8.1.0): biblioteca de certificados.

Seleção automática, por data de ensaio, do certificado de cada instrumento
do plano de recursos da OS (validador → antes + depois; padrão → externo) e
fornecimento dos bytes para a montagem do PDF (P4). Certificados de malha
seguem D4 (híbrido): PDF do report engc_os quando há calibração concluída
vinculada — pela malha (`engc_calibration_measurement_id`) ou, na ausência
dessa, pela qualificação (`qualificacao.engc_calibration_id`) — senão os
arquivos anexados (coletados) à malha.
"""
import base64

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.tools.mimetypes import guess_mimetype

from .calibration_instruments import AFR_CERT_ROLES

# resource_role do plano → papéis de certificado exigidos, na ordem do anexo.
_ROLES_BY_RESOURCE = (
    ("validador", ("antes", "depois")),
    ("padrao", ("externo",)),
)

# Report QWeb do certificado de calibração do engc_os (model engc.calibration).
ENGC_CALIBRATION_REPORT = "engc_os.report_engc_os_calibration_certificate"

# Legenda curta do papel para a legenda do anexo (finding 5 do review P2):
# rótulos de AFR_CERT_ROLES têm parênteses próprios ("Certificado externo
# (padrão)") que ficam duplicados/aninhados dentro da legenda "Certificado
# X — inst (<rótulo>)"; este mapa fica só para a legenda, sem tocar os
# rótulos de seleção do campo afr_role.
_CAPTION_ROLE_LABELS = {
    "antes": "antes da campanha",
    "depois": "depois da campanha",
    "externo": "padrão externo",
}


def _mimetype_of(content):
    return guess_mimetype(content, default="application/octet-stream")


def _afr_resolve_mimetype(stored_mimetype, content):
    """Mimetype confiável de um arquivo anexado.

    O mimetype armazenado é aceito quando já é PDF ou `image/*`; em
    qualquer outro caso (ausente, ou `application/octet-stream` — como o
    PWA grava) ele é sniffado a partir dos próprios bytes. Reusado por P4
    para os arquivos de `collect_section`.
    """
    if stored_mimetype == "application/pdf" or (stored_mimetype or "").startswith("image/"):
        return stored_mimetype
    return _mimetype_of(content)


class AfrQualificacaoRelatorio(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    # ------------------------------------------------------------------
    # Task 4 — aba "Certificados" (só leitura)
    # ------------------------------------------------------------------
    certificados_html = fields.Html(
        string="Certificados",
        compute="_compute_certificados_html",
        sanitize=False,
        help=(
            "Certificados escolhidos automaticamente pelas datas dos ensaios "
            "para os instrumentos do plano de recursos da OS."
        ),
    )

    @api.depends(
        "data_inicio_ensaios",
        "data_fim_ensaios",
        "equipment_id",
        "os_id.resource_plan_line_ids.instrument_id",
        "os_id.resource_plan_line_ids.resource_role",
        "os_id.resource_plan_line_ids.equipment_ids",
        "os_id.resource_plan_line_ids.instrument_id.name",
        "os_id.resource_plan_line_ids.instrument_id.id_number",
        "os_id.resource_plan_line_ids.instrument_id.tag",
        "os_id.resource_plan_line_ids.instrument_id.marca",
        "os_id.resource_plan_line_ids.instrument_id.modelo",
        "os_id.resource_plan_line_ids.instrument_id.certificate_ids.afr_role",
        "os_id.resource_plan_line_ids.instrument_id.certificate_ids.certificate_number",
        "os_id.resource_plan_line_ids.instrument_id.certificate_ids.date_calibration",
        "os_id.resource_plan_line_ids.instrument_id.certificate_ids.validate_calibration",
        "os_id.resource_plan_line_ids.instrument_id.certificate_ids.superseded_by_id",
    )
    def _compute_certificados_html(self):
        for rel in self:
            rel.certificados_html = rel._afr_certificados_html()

    def _afr_certificados_html(self):
        """Tabela só de leitura da seleção; 'AUSENTE' em vermelho quando
        não há certificado para o papel exigido."""
        self.ensure_one()
        selection = self._afr_certificate_selection() if self.os_id else []
        if not selection:
            return Markup(
                '<p class="text-muted">Nenhum instrumento no plano de recursos '
                'da OS. Gere/ajuste o plano de recursos para listar os '
                'certificados.</p>')
        role_labels = dict(AFR_CERT_ROLES)
        resource_labels = dict(
            self.env["afr.qualificacao.resource.plan.line"]
            ._fields["resource_role"].selection)

        def fmt(value):
            return value.strftime("%d/%m/%Y") if value else "—"

        rows = Markup("")
        for entry in selection:
            cert = entry["certificate"]
            if cert:
                number = escape(cert.certificate_number or "s/nº")
                cal_date = escape(fmt(cert.date_calibration))
                validity = escape(fmt(cert.validate_calibration))
            else:
                number = Markup(
                    '<span style="color:#c00;font-weight:bold;">AUSENTE</span>')
                cal_date = validity = Markup("—")
            rows += (
                Markup("<tr><td>") + escape(entry["instrument"].display_name)
                + Markup("</td><td>")
                + escape(resource_labels.get(entry["resource_role"], ""))
                + Markup("</td><td>") + escape(role_labels[entry["role"]])
                + Markup("</td><td>") + number
                + Markup("</td><td>") + cal_date
                + Markup("</td><td>") + validity
                + Markup("</td></tr>")
            )
        return (
            Markup(
                '<table class="table table-sm table-bordered o_afr_cert_table">'
                "<thead><tr><th>Instrumento</th><th>Papel no plano</th>"
                "<th>Certificado exigido</th><th>Nº</th><th>Calibração</th>"
                "<th>Validade</th></tr></thead><tbody>")
            + rows
            + Markup("</tbody></table>")
        )

    # ------------------------------------------------------------------
    # Instrumentos (validador / padrão)
    # ------------------------------------------------------------------
    def _afr_certificate_selection(self):
        """Uma entrada por (instrumento, papel exigido). Validadores
        primeiro, depois padrões (grupo fixado por `_ROLES_BY_RESOURCE`);
        dentro de cada grupo, a ordem segue o `_order` de
        `afr.qualificacao.resource.plan.line` ("os_id, resource_role,
        sensor_kind_id, id"). Só entram linhas com instrumento e que
        atendem este equipamento (equipment_ids vazio = linha da OS
        inteira); (instrumento, resource_role) repetido conta uma vez."""
        self.ensure_one()
        equipment = self.equipment_id
        lines = self.os_id.resource_plan_line_ids.filtered(
            lambda l: l.instrument_id
            and (not l.equipment_ids or equipment in l.equipment_ids)
        )
        result = []
        seen = set()
        for resource_role, cert_roles in _ROLES_BY_RESOURCE:
            for line in lines.filtered(lambda l: l.resource_role == resource_role):
                instrument = line.instrument_id
                key = (instrument.id, resource_role)
                if key in seen:
                    continue
                seen.add(key)
                for role in cert_roles:
                    result.append({
                        "instrument": instrument,
                        "resource_role": resource_role,
                        "role": role,
                        "certificate": instrument._afr_select_certificate(
                            role,
                            self.data_inicio_ensaios,
                            self.data_fim_ensaios,
                        ),
                    })
        return result

    def _afr_certificate_files(self, roles):
        """(bytes, mimetype, legenda) dos certificados selecionados com
        role em `roles` e arquivo presente, na ordem da seleção."""
        self.ensure_one()
        files = []
        for entry in self._afr_certificate_selection():
            cert = entry["certificate"]
            if entry["role"] not in roles or not cert:
                continue
            content = cert._afr_file_content()
            if not content:
                continue
            caption = "Certificado %s — %s (%s)" % (
                cert.certificate_number or "s/nº",
                entry["instrument"].display_name,
                _CAPTION_ROLE_LABELS[entry["role"]],
            )
            files.append((content, _mimetype_of(content), caption))
        return files

    # ------------------------------------------------------------------
    # Malhas de controle (D4 — híbrido)
    # ------------------------------------------------------------------
    def _afr_resolve_malha_calibration(self, malha):
        """Calibração 'oficial' da malha, na ordem de fallback do review
        P2 (findings 1+2): link próprio da malha
        (`engc_calibration_measurement_id.calibration_id`); na ausência,
        o link da qualificação (`qualificacao_id.engc_calibration_id`).
        Uma calibração só conta como vinculada quando concluída
        (`state == 'done'`) — em rascunho/andamento ela ainda não tem
        certificado assinado, então cai para o próximo fallback (incluindo
        os itens de coleta da malha). Retorna recordset vazio quando
        nenhuma das duas se qualifica."""
        for calibration in (
            malha.engc_calibration_measurement_id.calibration_id,
            malha.qualificacao_id.engc_calibration_id,
        ):
            if calibration and calibration.state == "done":
                return calibration
        return self.env["engc.calibration"]

    def _afr_render_engc_certificate(self, calibration):
        """`bytes` do certificado de calibração do engc_os, com cache por
        transação (Ruling P2 final 4.3/5.4: `_afr_malha_certificate_files`
        é chamado ≥3× por emissão — check/resolve/scan — e o report do
        engc_os pode falhar, por exemplo sem wkhtmltopdf disponível).

        Qualquer falha (exceção do render, ou formato != 'pdf') devolve
        bytes vazios em vez de propagar — `_check_files()` reporta
        "arquivo vazio" (não utilizável) ao invés de a montagem inteira
        estourar por causa de um certificado de terceiro.
        """
        self.ensure_one()
        cache = getattr(self.env.cr, "_afr_malha_cert_cache", None)
        if cache is None:
            cache = {}
            self.env.cr._afr_malha_cert_cache = cache
        if calibration.id in cache:
            return cache[calibration.id]
        try:
            content, fmt = self.env["ir.actions.report"].sudo()._render_qweb_pdf(
                ENGC_CALIBRATION_REPORT, [calibration.id])
            result = content if fmt == "pdf" else b""
        except Exception:
            result = b""
        cache[calibration.id] = result
        return result

    def _afr_malha_certificate_files(self):
        """Por malha dos qualificacao_ids: PDF do certificado engc_os quando
        há calibração concluída vinculada (uma vez por calibração, via
        `_afr_resolve_malha_calibration`); senão PDFs/imagens dos itens de
        coleta já coletados (`state == 'collected'`) da malha.
        """
        self.ensure_one()
        files = []
        rendered = set()
        for malha in self.qualificacao_ids.mapped("malha_ids"):
            calibration = self._afr_resolve_malha_calibration(malha)
            if calibration:
                if calibration.id in rendered:
                    continue
                rendered.add(calibration.id)
                pdf = self._afr_render_engc_certificate(calibration)
                caption = "Certificado de calibração %s — %s" % (
                    calibration.name, malha.display_name)
                files.append((pdf, "application/pdf", caption))
                continue
            items = malha.collect_item_ids.filtered(
                lambda i: i.state == "collected"
            ).with_context(bin_size=False).sorted(
                key=lambda i: (i.sequence, i.id))
            for item in items:
                if not item.file:
                    continue
                content = base64.b64decode(item.file)
                mimetype = _afr_resolve_mimetype(item.mimetype, content)
                if mimetype != "application/pdf" and not mimetype.startswith("image/"):
                    continue
                caption = "%s — %s" % (item.name, malha.display_name)
                files.append((content, mimetype, caption))
        return files
