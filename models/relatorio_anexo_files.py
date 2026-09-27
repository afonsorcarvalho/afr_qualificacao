"""Arquivos de cada posição de anexo do Relatório Final (spec §4.5).

`_resolve_files()` devolve só o que a montagem consegue usar; `_check_files()`
lista os problemas (consumido pela varredura de P5: `PROBLEM_EMPTY` →
ANEXO_VAZIO, qualquer outro → ANEXO_ILEGIVEL). Nada aqui levanta exceção por
causa de arquivo ruim — arquivo de terceiro exótico vira problema listado.
"""
import base64

from odoo import _, models
from odoo.exceptions import AccessError
from odoo.tools.mimetypes import guess_mimetype

from .relatorio_certificados import _afr_resolve_mimetype
from .relatorio_pdf import file_problem

PROBLEM_EMPTY = "Nenhum arquivo encontrado para este anexo."
PROBLEM_NO_ACCESS = "sem permissão de acesso"
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

    def _raw_attachment_files(self):
        """`(bytes|None, mimetype, legenda)` de `attachment_ids`.

        Fix round 1, finding 2 (segurança): `sudo()` só é usado para o
        upload ainda não vinculado ao PRÓPRIO anexo (`res_model` desta
        classe e `res_id` em `(0, self.id)` — o widget `many2many_binary`
        grava o `ir.attachment` com `res_id=0` antes do anexo ser salvo, e
        a ACL padrão do Odoo nega leitura de um anexo com `res_id=0`
        criado por outro usuário, mesmo sendo o próprio upload do anexo em
        edição). Qualquer OUTRO `ir.attachment` (ex.: um id de terceiro que
        um chamador RPC tentasse colar em `attachment_ids`) é lido com o
        direito do usuário atual: sem permissão → `AccessError` → o
        arquivo NUNCA entra no PDF (`content=None`, diferente de `b""` =
        "arquivo vazio") e `_check_files()` relata o problema. `name`/
        `mimetype` são sempre lidos via `sudo()` só para identificar o
        arquivo na mensagem de erro — não expõe o conteúdo.

        `with_context(prefetch_fields=False)` no `meta` sudo é
        obrigatório: sem isso, o Odoo faz prefetch em lote de TODAS as
        colunas simples do registro (inclusive `store_fname`/`db_datas`,
        de quem `raw` depende) na MESMA query — como o cache de campo é
        da transação (compartilhado entre `sudo()` e o env do usuário
        atual, não por env), o `att.raw` não-sudo mais abaixo encontraria
        o valor JÁ em cache e nunca chamaria `check('read')`, deixando
        passar o AccessError que este método existe pra impor. É o mesmo
        padrão que `ir.attachment.validate_access` usa no core (base) por
        exatamente este motivo.
        """
        self.ensure_one()
        files = []
        for att in self.attachment_ids.sorted("id"):
            meta = att.sudo().with_context(prefetch_fields=False)
            caption = meta.name or ""
            if meta.res_model == self._name and meta.res_id in (0, self.id):
                files.append((meta.raw or b"", meta.mimetype or "", caption))
                continue
            try:
                files.append((att.raw or b"", att.mimetype or "", caption))
            except AccessError:
                files.append((None, meta.mimetype or "", caption))
        return files

    def _raw_files(self):
        """Candidatos `(bytes, mimetype, legenda)` sem validação.

        `attachment_ids` substitui a resolução automática do slot quando
        preenchido (override manual) — ver `_raw_attachment_files`.
        """
        self.ensure_one()
        if self.slot_kind == "bloco":
            # Conteúdo renderizado no próprio corpo (P3), logo após o separador.
            return []
        if self.attachment_ids:
            return self._raw_attachment_files()
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
        """Lista ordenada `(bytes, mimetype, legenda)` só com arquivos utilizáveis.

        `content is None` (sentinela de `_raw_attachment_files` para
        "sem permissão de acesso") nunca entra — diferente de `b""`
        (arquivo vazio de verdade), que passa por `file_problem` como
        qualquer outro.
        """
        self.ensure_one()
        files = []
        for content, mimetype, caption in self._raw_files():
            if content is None:
                continue
            if file_problem(content, mimetype) is None:
                detected = guess_mimetype(content, default=mimetype or "")
                files.append((content, detected, caption))
        return files

    def _check_files(self):
        """Problemas do anexo (`[]` = ok).

        Formato dos itens: `PROBLEM_EMPTY` sozinho, ou
        `"<legenda do arquivo>: <motivo>"` (motivo de `file_problem`, ex.:
        `"cert.pdf: PDF protegido por senha"`, ou `PROBLEM_NO_ACCESS`
        quando `content is None`).
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
            name = caption or _("arquivo sem nome")
            if content is None:
                problems.append("%s: %s" % (name, PROBLEM_NO_ACCESS))
                continue
            problem = file_problem(content, mimetype)
            if problem:
                problems.append("%s: %s" % (name, problem))
        return problems
