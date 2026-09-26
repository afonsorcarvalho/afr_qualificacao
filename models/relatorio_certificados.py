# -*- coding: utf-8 -*-
"""Relatório final — P2 (16.0.8.1.0): biblioteca de certificados.

Seleção automática, por data de ensaio, do certificado de cada instrumento
do plano de recursos da OS (validador → antes + depois; padrão → externo) e
fornecimento dos bytes para a montagem do PDF (P4). Certificados de malha
seguem D4: PDF do report engc_os quando a malha tem calibração vinculada,
senão os arquivos anexados à malha.
"""
import base64

from odoo import models
from odoo.tools.mimetypes import guess_mimetype

from .calibration_instruments import AFR_CERT_ROLES

# resource_role do plano → papéis de certificado exigidos, na ordem do anexo.
_ROLES_BY_RESOURCE = (
    ("validador", ("antes", "depois")),
    ("padrao", ("externo",)),
)

# Report QWeb do certificado de calibração do engc_os (model engc.calibration).
ENGC_CALIBRATION_REPORT = "engc_os.report_engc_os_calibration_certificate"


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
        role_labels = dict(AFR_CERT_ROLES)
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
                role_labels[entry["role"]],
            )
            files.append((content, _mimetype_of(content), caption))
        return files

    # ------------------------------------------------------------------
    # Malhas de controle (D4 — híbrido)
    # ------------------------------------------------------------------
    def _afr_malha_certificate_files(self):
        """Por malha dos qualificacao_ids: PDF do certificado engc_os quando
        há calibração vinculada (uma vez por calibração); senão PDFs/imagens
        dos itens de coleta da malha.
        """
        # TODO(4.9): qualificacao.engc_calibration_id (nível qualif, não
        # malha) é ignorado de propósito — D4 é por malha
        # (engc_calibration_measurement_id), não por qualificação; P5
        # detecta anexo vazio (ANEXO_VAZIO) se isso deixar uma malha sem
        # certificado.
        self.ensure_one()
        Report = self.env["ir.actions.report"].sudo()
        files = []
        rendered = set()
        for malha in self.qualificacao_ids.mapped("malha_ids"):
            calibration = malha.engc_calibration_measurement_id.calibration_id
            if calibration:
                if calibration.id in rendered:
                    continue
                rendered.add(calibration.id)
                pdf, _fmt = Report._render_qweb_pdf(
                    ENGC_CALIBRATION_REPORT, [calibration.id])
                caption = "Certificado de calibração %s — %s" % (
                    calibration.name, malha.display_name)
                files.append((pdf, "application/pdf", caption))
                continue
            items = malha.collect_item_ids.with_context(bin_size=False).sorted(
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
