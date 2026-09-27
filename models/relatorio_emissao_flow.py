"""Relatório Final — emissão, revisão, aprovações e portal (P4).

Parte 1 (Task 4): campos de emissão, URL pública e guarda dos campos que só
as ações mudam. Tasks 7–9 acrescentam métodos a estas classes.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools.misc import clean_context

from .relatorio_editorial import skip_editorial_hook

INTERNAL_ROLES = ("elaborador", "emissor")
ROLE_LABELS = {"elaborador": "Elaborador", "emissor": "Emissor"}


class AfrQualificacaoRelatorioEmissao(models.Model):
    _name = "afr.qualificacao.relatorio"
    _inherit = ["afr.qualificacao.relatorio", "afr.qualificacao.manager.guard.mixin"]

    # Só as ações (Emitir / Revisar / aprovação do cliente) mudam estes
    # campos — via sudo(). Mesmo motivo do _CERTIFICATE_FIELDS de
    # afr.qualificacao: a ir.rule escopa registros, não valores.
    _RQ_INTERNAL_FIELDS = frozenset({
        "state", "revision", "current_emissao_id", "rq_editorial_seq",
    })

    emissao_ids = fields.One2many(
        "afr.relatorio.emissao", "relatorio_id", string="Emissões", readonly=True,
    )
    current_emissao_id = fields.Many2one(
        "afr.relatorio.emissao", string="Emissão vigente", readonly=True, copy=False,
    )
    minuta_attachment_id = fields.Many2one(
        "ir.attachment", string="Última minuta", readonly=True, copy=False,
    )
    verify_url = fields.Char(
        compute="_compute_verify_url", string="URL pública de verificação",
    )

    @api.depends("current_emissao_id.token")
    @api.depends_context("rq_emission_token")
    def _compute_verify_url(self):
        """URL do QR. Durante a emissão o token vem do contexto: ele é gerado
        ANTES do PDF (o QR precisa dele) e a emissão só é criada depois,
        com o hash do PDF pronto."""
        icp = self.env["ir.config_parameter"].sudo()
        base = icp.get_param("web.base.url", default="")
        db_param = icp.get_param(
            "afr_qualificacao.verify_url_db", default=self.env.cr.dbname,
        )
        ctx_token = self.env.context.get("rq_emission_token")
        for rec in self:
            token = ctx_token or rec.current_emissao_id.token
            if not token:
                rec.verify_url = False
                continue
            url = "%s/qualificacao/relatorio/verify/%s" % (base, token)
            if db_param:
                url += "?db=%s" % db_param
            rec.verify_url = url

    # Campos do próprio relatório cuja edição muda o conteúdo do PDF (Task 7).
    _RQ_EDITORIAL_FIELDS = frozenset({
        "equipment_id", "template_id",
        "data_inicio_ensaios", "data_fim_ensaios",
        "amb_temperatura", "amb_umidade",
        "tolerancia_acima", "criterio_f0_fator",
        "block_ids", "anexo_ids", "checklist_ids", "indicador_ids", "leitura_ib_ids",
    })

    def write(self, vals):
        if not self.env.su and self._RQ_INTERNAL_FIELDS.intersection(vals):
            raise UserError(_(
                "Status, revisão e emissão vigente do relatório final só mudam "
                "pelas ações Emitir, Revisar e pela aprovação do cliente."
            ))
        editorial = (
            bool(self._RQ_EDITORIAL_FIELDS.intersection(vals))
            and not skip_editorial_hook(self.env)
        )
        if editorial:
            self._check_editable()
        result = super().write(vals)
        if editorial:
            self._rq_bump_editorial_seq()  # jobs de montagem comparam (Task 8B)
            self._invalidate_internal_approvals()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Fix round 1 (review do Task 4): o `write()` acima já bloqueava
        `_RQ_INTERNAL_FIELDS` fora de `env.su`, mas o `create()` não tinha
        override nenhum — o grupo Usuário (`create=1` na ACL de
        `afr.qualificacao.relatorio`) conseguia nascer o registro já
        `create({'state': 'issued', 'revision': 5, 'current_emissao_id': ...})`,
        sem passar pelas ações Emitir/Revisar/aprovação do cliente.

        Mesmo padrão de `qualificacao.py::create()` (Task 13/14): pré-check
        no `vals` recebido (erro cedo/claro no caso comum) + pós-check no
        registro EFETIVO já criado. O pós-check é o que realmente fecha o
        buraco — o ORM aplica `context['default_<campo>']`/`ir.default` a
        campos AUSENTES de `vals` dentro do próprio `super().create()`,
        depois deste pré-check, então um `with_context(default_state='issued')`
        sem `state` no vals sobreviveria só com o pré-check.
        """
        if not self.env.su:
            for vals in vals_list:
                if self._RQ_INTERNAL_FIELDS.intersection(vals):
                    raise UserError(_(
                        "Status, revisão e emissão vigente do relatório final só "
                        "mudam pelas ações Emitir, Revisar e pela aprovação do "
                        "cliente — nunca na criação do registro."
                    ))
        records = super().create(vals_list)
        if not self.env.su:
            for record in records:
                if (
                    record.state != "draft"
                    or record.revision != 0
                    or record.current_emissao_id
                ):
                    raise UserError(_(
                        "Status, revisão e emissão vigente do relatório final só "
                        "mudam pelas ações Emitir, Revisar e pela aprovação do "
                        "cliente — nunca na criação do registro."
                    ))
        return records

    @api.constrains("current_emissao_id")
    def _check_current_emissao_pertence_ao_relatorio(self):
        """A emissão vigente de um relatório só pode ser uma emissão DELE
        mesmo — sem isto, `current_emissao_id` podia ser apontado (por
        escrita interna ou bug futuro) para a emissão de outro relatório,
        e `verify_url`/o QR passariam a "confirmar" o relatório errado."""
        for rec in self:
            if rec.current_emissao_id and rec.current_emissao_id.relatorio_id != rec:
                raise ValidationError(_(
                    "A emissão vigente de um relatório precisa pertencer a ele "
                    "mesmo, nunca à emissão de outro relatório."
                ))

    # ------------------------------------------------------------------
    # Task 7 — aprovações internas, gate de emissão, invalidação e trava
    # ------------------------------------------------------------------

    def _check_editable(self):
        locked = self.filtered(lambda r: r.state != "draft")
        if locked:
            raise UserError(_(
                "O relatório %(name)s já foi emitido (%(rev)s). Use Revisar para "
                "abrir uma nova revisão antes de editar."
            ) % {"name": locked[0].name, "rev": locked[0].revision_label})

    def _invalidate_internal_approvals(self):
        """Zera elaborador/emissor dos relatórios em rascunho. True se zerou algo.

        Tudo via sudo + clean_context: o gatilho pode vir de um Técnico
        editando a janela do ciclo (sem write no relatório/aprovação) e o
        guard de write do P3 só aceita `approved_at`/`ip` sob `env.su`;
        clean_context tira `default_*` do contexto do chamador (ruling 5.1).
        """
        rels = self.sudo().with_context(clean_context(self.env.context))
        lines = rels.filtered(lambda r: r.state == "draft").mapped(
            "aprovacao_ids"
        ).filtered(lambda a: a.papel in INTERNAL_ROLES and a.approved_at)
        if not lines:
            return False
        lines.write({"approved_at": False, "ip": False})
        for rel in lines.mapped("relatorio_id"):
            rel.message_post(body=_(
                "Aprovações internas zeradas: o relatório foi editado depois "
                "da aprovação."
            ))
        return True

    def action_aprovar_interno(self):
        """Aprova TODAS as linhas elaborador/emissor pendentes do usuário atual."""
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Só é possível aprovar internamente um relatório em rascunho."))
        lines = self.aprovacao_ids.filtered(
            lambda a: a.papel in INTERNAL_ROLES
            and a.user_id == self.env.user
            and not a.approved_at
        )
        if not lines:
            raise UserError(_(
                "Você não está designado como elaborador ou emissor com aprovação "
                "pendente neste relatório."
            ))
        now = fields.Datetime.now()
        ip = request.httprequest.remote_addr if request else False
        clean_ctx = clean_context(self.env.context)
        # sudo: o guard do P3 só aceita approved_at/ip sob env.su.
        for line in lines.sudo().with_context(clean_ctx):
            line.write({
                "approved_at": now,
                "ip": ip or False,
                "nome_exibicao": line.nome_exibicao or self.env.user.name,
            })
        self.with_context(clean_ctx).message_post(
            body=_("Aprovado internamente por %(user)s (%(roles)s).") % {
                "user": self.env.user.name,
                "roles": ", ".join(ROLE_LABELS[p] for p in lines.mapped("papel")),
            },
        )
        return True

    def _check_emission_gate(self):
        """Impedimentos para emitir (lista vazia = pode). P5 estende com super().

        Síncrono e puro: só lê, não grava nada.
        """
        self.ensure_one()
        problems = []
        for papel in INTERNAL_ROLES:
            label = ROLE_LABELS[papel]
            lines = self.aprovacao_ids.filtered(lambda a, p=papel: a.papel == p)
            if not lines:
                problems.append(_("Nenhum %s designado.") % label.lower())
            for line in lines:
                who = line.nome_exibicao or line.user_id.name or "—"
                if not line.user_id:
                    problems.append(_("%(role)s %(who)s sem usuário designado.") % {
                        "role": label, "who": who})
                elif not line.approved_at:
                    problems.append(_("%(role)s %(who)s ainda não aprovou.") % {
                        "role": label, "who": who})
        return problems
