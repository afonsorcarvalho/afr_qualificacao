# -*- coding: utf-8 -*-
"""Relatório final — P2 (16.0.8.1.0): biblioteca de certificados.

Seleção automática, por data de ensaio, do certificado de cada instrumento
do plano de recursos da OS (validador → antes + depois; padrão → externo) e
fornecimento dos bytes para a montagem do PDF (P4). Certificados de malha
seguem D4: PDF do report engc_os quando a malha tem calibração vinculada,
senão os arquivos anexados à malha.
"""
from odoo import models
from odoo.tools.mimetypes import guess_mimetype

from .calibration_instruments import AFR_CERT_ROLES

# resource_role do plano → papéis de certificado exigidos, na ordem do anexo.
_ROLES_BY_RESOURCE = (
    ("validador", ("antes", "depois")),
    ("padrao", ("externo",)),
)


def _mimetype_of(content):
    return guess_mimetype(content, default="application/octet-stream")


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
