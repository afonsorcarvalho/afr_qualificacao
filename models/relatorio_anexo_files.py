"""Arquivos de cada posição de anexo do Relatório Final (spec §4.5).

`_resolve_files()` devolve só o que a montagem consegue usar; `_check_files()`
lista os problemas (consumido pela varredura de P5: `PROBLEM_EMPTY` →
ANEXO_VAZIO, qualquer outro → ANEXO_ILEGIVEL). Nada aqui levanta exceção por
causa de arquivo ruim — arquivo de terceiro exótico vira problema listado.
"""
import base64

from odoo import _, models
from odoo.tools.mimetypes import guess_mimetype

from .relatorio_certificados import _afr_resolve_mimetype
from .relatorio_pdf import file_problem

PROBLEM_EMPTY = "Nenhum arquivo encontrado para este anexo."
ALL_CERT_ROLES = ("antes", "depois", "externo")


class AfrRelatorioAnexoFiles(models.Model):
    _inherit = "afr.relatorio.anexo"

    def _cert_roles_list(self):
        self.ensure_one()
        roles = [r.strip() for r in (self.cert_roles or "").split(",") if r.strip()]
        return roles or list(ALL_CERT_ROLES)

    def _collect_sections_list(self):
        self.ensure_one()
        return [s.strip() for s in (self.collect_sections or "").split(",") if s.strip()]

    def _collect_items(self):
        """Itens coletados (com arquivo) das seções pedidas, das
        qualificações do relatório.

        `rel.qualificacao_ids` já filtra pelo mesmo equipamento e exclui as
        canceladas (P1) — a busca aqui não reabre esse filtro por
        `os_id`/`equipment_id` para não trazer de volta qualificação
        cancelada por outra via (Ruling 1.6).

        Ordem: itens sem ciclo primeiro, depois por ciclo
        (`_relatorio_cycle_sort_key`, P1), depois `sequence`, `id`.
        """
        self.ensure_one()
        Item = self.env["afr.qualificacao.collect.item"]
        sections = self._collect_sections_list()
        rel = self.relatorio_id
        if not sections or not rel:
            return Item
        # bin_size=False: precisamos do conteúdo real de `file`, não só do
        # tamanho (Ruling 1.5) — vale para toda leitura de `item.file` feita
        # a partir deste recordset (inclusive em `_raw_files`).
        items = Item.with_context(bin_size=False).search([
            ("qualif_id", "in", rel.qualificacao_ids.ids),
            ("docx_section", "in", sections),
            ("state", "=", "collected"),
        ]).filtered(lambda i: i.file)

        def sort_key(item):
            has_cycle = bool(item.cycle_id)
            cycle_key = item.cycle_id._relatorio_cycle_sort_key() if has_cycle else ()
            return (has_cycle, cycle_key, item.sequence, item.id)

        return items.sorted(key=sort_key)

    def _raw_files(self):
        """Candidatos `(bytes, mimetype, legenda)` sem validação.

        `attachment_ids` substitui a resolução automática do slot quando
        preenchido (override manual). Lidos via `sudo()` (Ruling 1.4/5.2):
        um upload `many2many_binary` num anexo ainda não salvo grava o
        `ir.attachment` com `res_id=0`, que a ACL padrão não deixa ler sem
        sudo.
        """
        self.ensure_one()
        if self.slot_kind == "bloco":
            # Conteúdo renderizado no próprio corpo (P3), logo após o separador.
            return []
        if self.attachment_ids:
            attachments = self.attachment_ids.sudo().sorted("id")
            return [
                (att.raw or b"", att.mimetype or "", att.name or "")
                for att in attachments
            ]
        if self.slot_kind == "collect_section":
            files = []
            for item in self._collect_items():
                caption = item.name or ""
                if item.cycle_id:
                    caption = "%s — %s" % (item.cycle_id.display_name, caption)
                content = base64.b64decode(item.file)
                # PWA grava mimetype 'application/octet-stream' (Ruling P2
                # 4.7) — sniffa os bytes reusando o helper de P2.
                mimetype = _afr_resolve_mimetype(item.mimetype, content)
                files.append((content, mimetype, caption))
            return files
        if self.slot_kind == "instrument_certs":
            return list(self.relatorio_id._afr_certificate_files(self._cert_roles_list()))
        if self.slot_kind == "malha_certs":
            return list(self.relatorio_id._afr_malha_certificate_files())
        return []

    def _resolve_files(self):
        """Lista ordenada `(bytes, mimetype, legenda)` só com arquivos utilizáveis."""
        self.ensure_one()
        files = []
        for content, mimetype, caption in self._raw_files():
            if file_problem(content, mimetype) is None:
                detected = guess_mimetype(content, default=mimetype or "")
                files.append((content, detected, caption))
        return files

    def _check_files(self):
        """Problemas do anexo (`[]` = ok).

        Formato dos itens: `PROBLEM_EMPTY` sozinho, ou
        `"<legenda do arquivo>: <motivo>"` (motivo de `file_problem`, ex.:
        `"cert.pdf: PDF protegido por senha"`).
        """
        self.ensure_one()
        if self.slot_kind == "bloco":
            ok = self.block_id and self.block_id.included
            return [] if ok else [PROBLEM_EMPTY]
        raw = self._raw_files()
        if not raw:
            return [PROBLEM_EMPTY]
        problems = []
        for content, mimetype, caption in raw:
            problem = file_problem(content, mimetype)
            if problem:
                problems.append("%s: %s" % (caption or _("arquivo sem nome"), problem))
        return problems
