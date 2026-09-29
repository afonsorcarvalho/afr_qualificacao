"""Relatório Final — texto (blocos), anexos (posições) e aprovações (P3).

Extensão por _inherit do modelo criado em P1 (models/relatorio.py), para não
misturar dados de campo com montagem de texto.
"""

import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import is_html_empty
from odoo.tools.misc import clean_context

from ._numbering import hierarchical_numbering, sort_key
from .calibration_instruments import AFR_CERT_ROLES
from .relatorio_template import REPORT_BLOCK_KINDS

_logger = logging.getLogger(__name__)


def _fmt_num(value):
    """3.0 → '3'; 1.5 → '1,5'. None/False → ''."""
    if value is None or value is False:
        return ""
    return ("%g" % value).replace(".", ",")


class AfrQualificacaoRelatorio(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    template_id = fields.Many2one(
        "afr.relatorio.template", string="Template", ondelete="set null",
        tracking=True, help="Sugerido pela categoria do equipamento.")
    block_ids = fields.One2many(
        "afr.relatorio.block", "relatorio_id", string="Blocos do texto", copy=False)
    body_block_ids = fields.One2many(
        "afr.relatorio.block", "relatorio_id", string="Corpo do relatório",
        domain=[("is_anexo_content", "=", False)], copy=False,
        help="Blocos do corpo; conteúdo de anexo é editado pelo anexo.")
    anexo_ids = fields.One2many(
        "afr.relatorio.anexo", "relatorio_id", string="Anexos", copy=False)
    aprovacao_ids = fields.One2many(
        "afr.relatorio.aprovacao", "relatorio_id", string="Aprovações", copy=False)

    # ── criação / template ───────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """Findings review P3 (final), achado 4: o template sugerido entra
        em `vals` ANTES do `super().create()` — não é mais uma escrita
        separada depois de criado (a P4 trataria isso como escrita
        editorial fora do fluxo de criação).

        `default_template_id` no contexto é respeitado mesmo sem
        `template_id` em `vals`: o Odoo aplica esse default DENTRO do
        `super().create()`, depois deste laço. Se preenchêssemos `vals`
        aqui mesmo com um `default_template_id` presente, o campo deixaria
        de estar "ausente" e o default do contexto seria silenciosamente
        sobrescrito pela sugestão.
        """
        for vals in vals_list:
            if not vals.get("template_id") and not self.env.context.get("default_template_id"):
                template = self._suggest_template_from_vals(vals)
                if template:
                    vals["template_id"] = template.id
        return super().create(vals_list)

    def _suggest_template_from_vals(self, vals):
        """Sugestão de template a partir de um `vals` de criação (sem
        depender do registro já existir): mesma regra de `_suggest_template()`
        — categoria do equipamento primeiro, senão o de menor sequence."""
        Template = self.env["afr.relatorio.template"]
        os = self.env["afr.qualificacao.os"].browse(vals.get("os_id"))
        company_id = vals.get("company_id") or os.company_id.id or self.env.company.id
        company_dom = [("company_id", "in", [company_id, False])]
        equipment = self.env["engc.equipment"].browse(vals.get("equipment_id"))
        category = equipment.category_id if equipment else False
        if category:
            tpl = Template.search(
                company_dom + [("equipment_category_ids", "in", category.ids)],
                order="sequence, id", limit=1)
            if tpl:
                return tpl
        return Template.search(company_dom, order="sequence, id", limit=1)

    def _suggest_template(self):
        """Template cuja categoria = categoria do equipamento; senão o de menor sequence."""
        self.ensure_one()
        return self._suggest_template_from_vals({
            "equipment_id": self.equipment_id.id,
            "company_id": (self.company_id or self.env.company).id,
        })

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

        Fix round 1 (P3 Task 5): `.sudo()` sozinho não bastava. Ele só
        contorna o guard do `create()` (que olha `env.su`); a aplicação de
        `context['default_<campo>']` a campos AUSENTES de `vals`, dentro do
        `super().create()` do ORM, roda sempre — sudo ou não. As linhas de
        elaborador/emissor não traziam `user_id`/`approved_at`/`ip`, então um
        chamador RPC de `action_generate_relatorios_open()` com contexto
        `{"default_approved_at": ..., "default_user_id": <uid qualquer>}`
        forjava essas aprovações já assinadas por um usuário arbitrário —
        furando o gate de aprovação interna de que a P4 depende. Duas
        camadas: (1) `with_context(clean_context(...))` tira todo
        `default_*` do contexto antes do `create()`; (2) todo vals grava
        `user_id`/`approved_at`/`ip` explicitamente (mesmo que `False`), para
        que nenhum campo fique "ausente" e a defesa não dependa só do
        contexto estar limpo.
        """
        self.ensure_one()
        vals = [
            {"relatorio_id": self.id, "sequence": 10, "papel": "elaborador",
             "user_id": False, "approved_at": False, "ip": False},
            {"relatorio_id": self.id, "sequence": 20, "papel": "emissor",
             "user_id": False, "approved_at": False, "ip": False},
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
                "ip": False,
            })
            seq += 1
        vals.append({
            "relatorio_id": self.id,
            "sequence": 100,
            "papel": "cliente",
            "partner_id": self.partner_id.id or False,
            "nome_exibicao": self.partner_id.name or False,
            "user_id": False,
            "approved_at": False,
            "ip": False,
        })
        clean_ctx = clean_context(self.env.context)
        self.env["afr.relatorio.aprovacao"].sudo().with_context(clean_ctx).create(vals)

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
        """Blocos do corpo principal (incluídos e que não são conteúdo de
        anexo), ordenados. Conteúdo de anexo = bloco apontado por
        `afr.relatorio.anexo.block_id`."""
        self.ensure_one()
        return self.block_ids.filtered(
            lambda b: b.included and not b.is_anexo_content).sorted(sort_key)

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

    # ── tokens / render ──────────────────────────────────────────────────
    def _criterio_values(self):
        self.ensure_one()
        bio = self.indicador_ids.filtered(
            lambda i: i.tipo == "biologico" and i.valor_d)[:1]
        valor_d = bio.valor_d if bio else 0.0
        fator = self.criterio_f0_fator or 0.0
        return {
            "tolerancia": _fmt_num(self.tolerancia_acima),
            "f0_fator": _fmt_num(fator),
            "valor_d": _fmt_num(valor_d) if valor_d else "",
            "f0_minimo": _fmt_num(fator * valor_d) if valor_d else "",
        }

    def _token_context(self):
        """Contexto restrito do inline_template dos blocos."""
        self.ensure_one()
        rel = self
        return {
            "relatorio": self,
            "os": self.os_id,
            "partner": self.partner_id,
            "equipment": self.equipment_id,
            "company": self.company_id,
            "criterio": self._criterio_values(),
            "anexo": lambda code: rel._anexo_number(code),
        }

    def _render_block_body(self, block):
        """Resolve {{ }} do corpo do bloco. Erro de expressão ⇒ corpo cru
        (P5 acusa TOKEN_NAO_RESOLVIDO), nunca exceção no PDF."""
        self.ensure_one()
        body = block.body
        if not body or is_html_empty(body):
            return Markup("")
        try:
            # TODO(1.11): mecanismo real do risco — `sudo()` faz
            # `env.is_admin()` retornar True dentro do `inline_template`,
            # pulando o check de `mail.group_mail_template_editor` que a
            # mixin usaria pra restringir quem pode renderizar expressão
            # arbitrária; `object`/`ctx` no `safe_eval` é o registro EM
            # sudo (`self.env["mail.render.mixin"].sudo()`), então qualquer
            # pessoa com acesso de escrita ao corpo do bloco (não só Gestor)
            # pode embutir uma expressão que roda com privilégio de
            # superusuário — mesmo padrão de
            # sale_order.py::_render_proposal_block_body (cotação), aceito
            # na fase 1; ver ruling 1.11. Fix fase 2: renderizar sem
            # `sudo()` (aceitando que tokens que leem `os`/`equipment` fora
            # do que o autor do bloco vê passem a falhar) ou restringir
            # quem pode editar `body` a um grupo equivalente ao
            # `mail.group_mail_template_editor`.
            rendered = self.env["mail.render.mixin"].sudo()._render_template(
                str(body), self._name, [self.id], engine="inline_template",
                add_context=self._token_context(),
            )
        except UserError:
            _logger.warning(
                "Relatório %s: token inválido no bloco %s; corpo mantido sem render.",
                self.display_name, block.id, exc_info=True)
            return Markup(str(body))
        return Markup(rendered.get(self.id) or "")


    # ── helpers do corpo QWeb ────────────────────────────────────────────
    def _fmt_num(self, value):
        """Achado 7 (findings review P3 final): mesmo formatador pt-BR de
        `_criterio_values` (3.0 → '3'; 1.5 → '1,5'), exposto como método
        pro QWeb chamar (a função de módulo não é alcançável de `doc.`)."""
        return _fmt_num(value)

    def _fmt_date(self, value):
        return fields.Date.to_date(value).strftime("%d/%m/%Y") if value else ""

    def _fmt_datetime(self, value):
        if not value:
            return ""
        return fields.Datetime.context_timestamp(self, value).strftime("%d/%m/%Y %H:%M")

    def _sel_label(self, record, fname):
        value = record[fname]
        if not value:
            return ""
        return dict(record._fields[fname]._description_selection(self.env)).get(value, value)

    def _report_index_entries(self):
        """Linhas do índice: blocos titulados do texto + anexos incluídos.
        `key` casa com as chaves de page_map."""
        self.ensure_one()
        numbers = self._block_numbering()
        entries = []
        for blk in self._body_blocks():
            if blk.block_kind in ("capa", "indice") or not blk.show_title:
                continue
            entries.append({
                "key": "bloco:%d" % blk.id,
                "number": numbers.get(blk.id, ""),
                "title": blk.title or blk.display_label or "",
                "child": bool(blk.parent_id),
            })
        for anexo in self._anexos_included():
            entries.append({
                "key": "anexo:%s" % anexo.code,
                "number": "",
                "title": "Anexo %s — %s" % (anexo.numero, anexo.title or ""),
                "child": False,
            })
        return entries

    def _rq_fmt_number(self, number):
        """Número de bloco para exibição: nível 1 com 2 dígitos ('4' → '04')."""
        number = number or ""
        return number.zfill(2) if number.isdigit() else number

    def _report_section_entries(self):
        """[(marcador, rótulo)] das seções do cabeçalho: blocos de nível 1
        titulados (exceto capa) e anexos incluídos, na ordem do documento."""
        self.ensure_one()
        numbers = self._block_numbering()
        entries = []
        for blk in self._body_blocks():
            if blk.parent_id or blk.block_kind == "capa" or not blk.show_title:
                continue
            title = (blk.title or blk.display_label or "").upper()
            if not title:
                continue
            number = self._rq_fmt_number(numbers.get(blk.id, ""))
            entries.append(("bloco:%d" % blk.id, ("%s %s" % (number, title)).strip()))
        for anexo in self._anexos_included():
            entries.append(("anexo:%s" % anexo.code, "ANEXO %s" % anexo.numero))
        return entries

    def _report_cycles_sorted(self):
        """Ciclos na ordem do relatório (QI<QO<QD, tipo de ciclo, sequence)."""
        self.ensure_one()
        return self.cycle_ids.sorted(key=lambda c: c._relatorio_cycle_sort_key())

    def _report_cycle_rows(self):
        """Ciclos agrupados por (etapa, tipo de ciclo) com qtd/temperatura/tempo."""
        self.ensure_one()
        qtype_labels = dict(
            self.env["afr.qualificacao"]._fields["qualification_type"]
            ._description_selection(self.env))
        groups, order = {}, []
        for cycle in self._report_cycles_sorted():
            key = (cycle.qualificacao_id.qualification_type, cycle.cycle_type_id.id)
            if key not in groups:
                # Achado 5 (findings review P3 final): sale.order.line não é
                # legível pelo grupo Usuário (ACL de `sale`) — mas
                # temperatura/tempo da linha da cotação são dados que o
                # próprio relatório expõe a qualquer leitor. sudo() só na
                # leitura destes 2 campos, nunca no `doc`/`cycle` inteiro.
                line = cycle.sale_order_line_id.sudo()
                ctype = cycle.cycle_type_id
                groups[key] = {
                    "etapa": qtype_labels.get(key[0], ""),
                    "name": ctype.name or cycle.display_name,
                    "qty": 0,
                    "temperature": line.temperature or ctype.temperature or "",
                    "duration": line.duration or ctype.duration or "",
                }
                order.append(key)
            groups[key]["qty"] += 1
        return [groups[k] for k in order]

    def _report_sensor_tables(self):
        self.ensure_one()
        return [
            {"cycle": c.display_name,
             "rows": c.sensor_pos_ids.sorted(lambda s: (s.sequence, s.id))}
            for c in self._report_cycles_sorted()
            if c.sensor_pos_ids
        ]

    def _report_instrument_rows(self):
        """Validadores e padrões do plano de recursos com o certificado
        selecionado (P2). Rótulos das mesmas fontes da aba Certificados."""
        self.ensure_one()
        role_labels = dict(AFR_CERT_ROLES)
        resource_labels = dict(
            self.env["afr.qualificacao.resource.plan.line"]
            ._fields["resource_role"].selection)
        rows = []
        for sel in self._afr_certificate_selection():
            inst, cert = sel["instrument"], sel["certificate"]
            rows.append({
                "instrument": inst.name or "",
                "identification": inst.id_number or inst.tag or "",
                "resource_role": resource_labels.get(
                    sel["resource_role"], sel["resource_role"] or ""),
                "role": role_labels.get(sel["role"], sel["role"] or ""),
                "certificate": (cert.certificate_number or "—") if cert else "—",
                "date": self._fmt_date(cert.date_calibration) if cert else "",
                "validade": self._fmt_date(cert.validate_calibration) if cert else "",
            })
        return rows

    def _report_signature_rows(self):
        self.ensure_one()
        return [{
            "papel": self._sel_label(ap, "papel"),
            "nome": ap.nome_exibicao or ap.user_id.name or ap.partner_id.name or "",
            "registro": ap.registro or "",
            "approved_at": self._fmt_datetime(ap.approved_at),
        } for ap in self.aprovacao_ids.sorted(sort_key)]


class AfrQualificacaoOs(models.Model):
    _inherit = "afr.qualificacao.os"

    def action_generate_relatorios_open(self):
        """Botão "Gerar relatórios finais": além de gerar (P1), aplica o
        template. `action_generate_relatorios()` (recordset) fica intacto —
        testes de P1 dependem de relatório sem checklist semeado.

        Findings review P3 (final), achado 2: só em relatórios 'draft' — a
        P4 vai travar `create()` de blocos/anexos/aprovações fora do
        rascunho (editorial lock); aplicar o template num relatório já
        emitido derrubaria o botão pra toda a OS por um único equipamento
        já finalizado.
        """
        action = super().action_generate_relatorios_open()
        self.mapped("relatorio_final_ids").filtered(
            lambda r: r.state == "draft")._apply_template()
        return action
