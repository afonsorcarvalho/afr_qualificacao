"""Relatório Final — texto (blocos), anexos (posições) e aprovações (P3).

Extensão por _inherit do modelo criado em P1 (models/relatorio.py), para não
misturar dados de campo com montagem de texto.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ._numbering import hierarchical_numbering, sort_key
from .relatorio_template import REPORT_BLOCK_KINDS


class AfrQualificacaoRelatorio(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    template_id = fields.Many2one(
        "afr.relatorio.template", string="Template", ondelete="set null",
        tracking=True, help="Sugerido pela categoria do equipamento.")
    block_ids = fields.One2many(
        "afr.relatorio.block", "relatorio_id", string="Blocos do texto", copy=False)
    anexo_ids = fields.One2many(
        "afr.relatorio.anexo", "relatorio_id", string="Anexos", copy=False)
    aprovacao_ids = fields.One2many(
        "afr.relatorio.aprovacao", "relatorio_id", string="Aprovações", copy=False)

    # ── criação / template ───────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records.filtered(lambda r: not r.template_id):
            rec.template_id = rec._suggest_template()
        return records

    def _suggest_template(self):
        """Template cuja categoria = categoria do equipamento; senão o de menor sequence."""
        self.ensure_one()
        Template = self.env["afr.relatorio.template"]
        company_dom = [("company_id", "in", [(self.company_id or self.env.company).id, False])]
        category = self.equipment_id.category_id
        if category:
            tpl = Template.search(
                company_dom + [("equipment_category_ids", "in", category.ids)],
                order="sequence, id", limit=1)
            if tpl:
                return tpl
        return Template.search(company_dom, order="sequence, id", limit=1)

    def _apply_template(self):
        """Copia o template para blocos/anexos/checklist/aprovações. Idempotente."""
        for rel in self:
            tpl = rel.template_id
            if tpl and not rel.block_ids:
                rel._apply_template_blocks(tpl)
            if tpl and not rel.anexo_ids:
                rel._apply_template_anexos(tpl)
            if tpl and tpl.checklist_line_ids:
                rel._seed_checklist([
                    {"grupo": l.grupo, "descricao": l.descricao, "sequence": l.sequence}
                    for l in tpl.checklist_line_ids.sorted(sort_key)
                ])
            if not rel.aprovacao_ids:
                rel._apply_default_aprovacoes()
        return True

    def _apply_template_blocks(self, tpl):
        self.ensure_one()
        Block = self.env["afr.relatorio.block"]
        labels = dict(REPORT_BLOCK_KINDS)
        line_to_block = {}
        for line in tpl.line_ids.sorted(sort_key):
            section = line.section_id
            line_to_block[line.id] = Block.create({
                "relatorio_id": self.id,
                "sequence": line.sequence,
                "block_kind": line.block_kind,
                "section_id": section.id if section else False,
                "title": line.title or section.name or labels.get(line.block_kind, ""),
                "body": section.body if section else False,
                "page_break": line.page_break,
                "show_number": line.show_number,
                "show_title": line.show_title,
                "anexo_code": line.anexo_code or False,
            })
        for line in tpl.line_ids.filtered("parent_id"):
            parent_block = line_to_block.get(line.parent_id.id)
            if parent_block:
                line_to_block[line.id].parent_id = parent_block

    def _apply_template_anexos(self, tpl):
        self.ensure_one()
        vals = []
        for line in tpl.anexo_line_ids.sorted(sort_key):
            block = self.env["afr.relatorio.block"]
            if line.slot_kind == "bloco":
                block = self.block_ids.filtered(
                    lambda b, c=line.code: b.anexo_code == c
                    and b.block_kind != "anexo_separador")[:1]
            vals.append({
                "relatorio_id": self.id,
                "sequence": line.sequence,
                "included": line.included_default,
                "code": line.code,
                "title": line.title,
                "slot_kind": line.slot_kind,
                "collect_sections": line.collect_sections or False,
                "cert_roles": line.cert_roles or False,
                "block_id": block.id or False,
            })
        self.env["afr.relatorio.anexo"].create(vals)

    def _apply_default_aprovacoes(self):
        """Elaborador/emissor vazios; executor = técnicos dos relatórios diários
        (aprovado pela assinatura já coletada no PWA); cliente = partner.

        Criado via `sudo()`: a linha do executor grava `approved_at` (a
        assinatura do técnico já coletada no relatório diário) e
        `afr.relatorio.aprovacao.create()` rejeita esse campo vindo de um
        chamador não-`env.su` (guard da Task 3) — este método roda dentro do
        wrapper de UI `action_generate_relatorios_open()`, que pode ser
        chamado por um usuário comum (grupo Usuário). O `access_token` do
        cliente continua nascendo no servidor, dentro do `create()` do
        próprio modelo.
        """
        self.ensure_one()
        vals = [
            {"relatorio_id": self.id, "sequence": 10, "papel": "elaborador"},
            {"relatorio_id": self.id, "sequence": 20, "papel": "emissor"},
        ]
        daily = self.os_id.sudo().relatorio_ids.filtered(lambda d: d.state != "cancel")
        seq = 30
        for emp in daily.mapped("tecnico_ids"):
            signed = daily.filtered(
                lambda d, e=emp: e in d.tecnico_ids and d.signature_technician_date)
            vals.append({
                "relatorio_id": self.id,
                "sequence": seq,
                "papel": "executor",
                "user_id": emp.user_id.id or False,
                "nome_exibicao": emp.name,
                "approved_at": max(signed.mapped("signature_technician_date")) if signed else False,
            })
            seq += 1
        vals.append({
            "relatorio_id": self.id,
            "sequence": 100,
            "papel": "cliente",
            "partner_id": self.partner_id.id or False,
            "nome_exibicao": self.partner_id.name or False,
        })
        self.env["afr.relatorio.aprovacao"].sudo().create(vals)

    def action_reload_template(self):
        """Descarta blocos e anexos (inclusive arquivos anexados) e reaplica.

        Checklist e aprovações NÃO são tocados (ruling 1.9): já podem ter
        dados de campo (status marcado, aprovação registrada) que outro
        template não deve apagar.
        """
        self.ensure_one()
        if not self.template_id:
            raise UserError(_("Selecione um template antes de recarregar."))
        if self.state != "draft":
            raise UserError(_("Só é possível recarregar o template com o relatório em rascunho."))
        self.anexo_ids.unlink()
        self.block_ids.unlink()
        self._apply_template()
        return True

    # ── numeração / anexos ───────────────────────────────────────────────
    def _body_blocks(self):
        """Blocos do texto principal (incluídos e sem vínculo a anexo), ordenados."""
        self.ensure_one()
        return self.block_ids.filtered(
            lambda b: b.included and not b.anexo_code).sorted(sort_key)

    def _block_numbering(self):
        self.ensure_one()
        return hierarchical_numbering(self._body_blocks())

    def _anexos_included(self):
        self.ensure_one()
        return self.anexo_ids.filtered("included").sorted(sort_key)

    def _anexo_number(self, code):
        """'4' para o 4º anexo incluído; '' se excluído ou inexistente."""
        self.ensure_one()
        anexo = self.anexo_ids.filtered(lambda a: a.code == code)[:1]
        if not anexo or not anexo.included or not anexo.numero:
            return ""
        return str(anexo.numero)

    def _anexo_separator_block(self, code):
        self.ensure_one()
        return self.block_ids.filtered(
            lambda b: b.block_kind == "anexo_separador" and b.anexo_code == code
            and b.included)[:1]


class AfrQualificacaoOs(models.Model):
    _inherit = "afr.qualificacao.os"

    def action_generate_relatorios_open(self):
        """Botão "Gerar relatórios finais": além de gerar (P1), aplica o
        template. `action_generate_relatorios()` (recordset) fica intacto —
        testes de P1 dependem de relatório sem checklist semeado."""
        action = super().action_generate_relatorios_open()
        self.mapped("relatorio_final_ids")._apply_template()
        return action
