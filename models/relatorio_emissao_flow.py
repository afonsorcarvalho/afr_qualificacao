"""Relatório Final — emissão, revisão, aprovações e portal (P4).

Parte 1 (Task 4): campos de emissão, URL pública e guarda dos campos que só
as ações mudam. Tasks 7–9 acrescentam métodos a estas classes.
"""
import hashlib
import json
import uuid

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools.misc import clean_context

from ._numbering import sort_key
from .relatorio_editorial import SKIP_CTX, skip_editorial_hook
from .relatorio_emissao import INTERNAL_CTX
from .relatorio_pdf import REPORT_CORPO

# Mesmos valores de relatorio_build_job (ACTIVE_STATES / HIDE_CLIENT_CTX).
# Importar aquele módulo aqui no topo registraria as classes dele ANTES desta
# (ordem do MRO do registry); por isso o import fica dentro dos métodos.

INTERNAL_ROLES = ("elaborador", "emissor")
DEFAULT_PUBLIC_TZ = "America/Sao_Paulo"


def company_tz(company):
    """Fuso da empresa emissora (páginas públicas e datas da emissão)."""
    return (company and company.partner_id.tz) or DEFAULT_PUBLIC_TZ


ROLE_LABELS = {"elaborador": "Elaborador", "emissor": "Emissor"}


class AfrQualificacaoRelatorioEmissao(models.Model):
    _name = "afr.qualificacao.relatorio"
    _inherit = ["afr.qualificacao.relatorio", "afr.qualificacao.manager.guard.mixin"]

    # Só as ações (Emitir / Revisar / aprovação do cliente) mudam estes
    # campos — via sudo(). Mesmo motivo do _CERTIFICATE_FIELDS de
    # afr.qualificacao: a ir.rule escopa registros, não valores.
    # `minuta_attachment_id` (revisão final P4, item 1): o finalize da minuta
    # apaga o anexo anterior sob sudo — um id gravado por RPC seria apagado.
    _RQ_INTERNAL_FIELDS = frozenset({
        "state", "revision", "current_emissao_id", "rq_editorial_seq",
        "minuta_attachment_id",
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

    # Âncoras do relatório (fix round 2 do Task 9): cliente/empresa derivam da
    # OS; OS e equipamento são fixos depois de criado. `partner_id` é a âncora
    # do check de contato do aprovador cliente — não pode ser regravado.
    _RQ_ANCHOR_FIELDS = ("partner_id", "company_id", "os_id", "equipment_id")
    _RQ_CREATE_DERIVED_FIELDS = ("partner_id", "company_id")

    def write(self, vals):
        if not self.env.su:
            anchors = [
                f for f in self._RQ_ANCHOR_FIELDS
                if f in vals and any(rec[f].id != (vals[f] or False) for rec in self)
            ]
            if anchors:
                raise UserError(_(
                    "Cliente, empresa, OS e equipamento do relatório final não podem "
                    "ser alterados (%s): cliente e empresa vêm da OS."
                ) % ", ".join(anchors))
        if not self.env.su and self._RQ_INTERNAL_FIELDS.intersection(vals):
            raise UserError(_(
                "Status, revisão, emissão vigente e minuta do relatório final só "
                "mudam pelas ações Emitir, Revisar, Gerar minuta e pela aprovação "
                "do cliente."
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
                        "Status, revisão, emissão vigente e minuta do relatório "
                        "final só mudam pelas ações Emitir, Revisar, Gerar minuta "
                        "e pela aprovação do cliente — nunca na criação do registro."
                    ))
                derived = [f for f in self._RQ_CREATE_DERIVED_FIELDS if f in vals]
                if derived:
                    raise UserError(_(
                        "Cliente e empresa do relatório final vêm da OS; não podem "
                        "ser informados na criação (%s).") % ", ".join(derived))
            # Idem pelo contexto: default_partner_id/default_company_id não valem.
            self = self.with_context({
                k: v for k, v in self.env.context.items()
                if k not in ("default_%s" % f for f in self._RQ_CREATE_DERIVED_FIELDS)
            })
        records = super().create(vals_list)
        if not self.env.su:
            for record in records:
                if (
                    record.state != "draft"
                    or record.revision != 0
                    or record.current_emissao_id
                    or record.minuta_attachment_id
                ):
                    raise UserError(_(
                        "Status, revisão, emissão vigente e minuta do relatório "
                        "final só mudam pelas ações Emitir, Revisar, Gerar minuta "
                        "e pela aprovação do cliente — nunca na criação do registro."
                    ))
        return records

    @api.constrains("partner_id", "company_id", "os_id")
    def _check_anchor_matches_os(self):
        """Cliente e empresa do relatório são os da OS (fix round 2 do Task 9)."""
        for rel in self:
            if (rel.partner_id != rel.os_id.partner_id
                    or rel.company_id != rel.os_id.company_id):
                raise ValidationError(_(
                    "O cliente e a empresa do relatório %s precisam ser os da OS."
                ) % rel.display_name)

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
        # D5b: só a EMISSÃO trava a edição durante a montagem (a minuta só
        # compara a versão editorial e é descartada se o relatório mudar).
        from .relatorio_build_job import ACTIVE_STATES
        emitting = self.env["afr.relatorio.build.job"].sudo().search_count([
            ("relatorio_id", "in", self.ids), ("kind", "=", "emissao"),
            ("state", "in", ACTIVE_STATES)])
        if emitting:
            raise UserError(_(
                "Há uma emissão em montagem para este relatório. Aguarde a "
                "conclusão ou cancele a emissão antes de editar."))

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

    def _rq_reset_alerta_decisions(self):
        """Item 2 (P5 final fix wave): Revisar zera a decisão de achados
        `alerta` (regra OU IA) já decididos — mesmo princípio de
        `_invalidate_internal_approvals` / spec §4.6 ("aprovar uma versão
        não aprova a próxima"). `bloqueia` nunca tem decisão (não precisa) e
        `info` nunca bloqueia, então só `alerta` importa aqui. Sudo +
        clean_context: o `write` de `afr.relatorio.achado` só aceita
        decisao/motivo fora de `env.su`, e mesmo esses só com o relatório em
        rascunho — já é o caso aqui (a escrita acima já abriu a Rev.N+1),
        mas sudo evita depender dessa ordem."""
        clean_ctx = clean_context(self.env.context)
        achados = self.sudo().with_context(clean_ctx).achado_ids.filtered(
            lambda a: a.gravidade == "alerta" and a.decisao != "pendente")
        if achados:
            achados.write({"decisao": "pendente", "motivo": False})

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

        Esta camada (P4) só lê. P5 estende com uma re-verificação síncrona
        (grava achados) antes de montar a lista final — o gate completo
        não é puro; roda no clique (D4), e uma falha de emissão aceita o
        rollback dos achados gravados por essa re-verificação (ruling 1.17).
        """
        self.ensure_one()
        return self._rq_internal_approval_problems()

    def _rq_internal_approval_problems(self):
        """Parte P4 do gate (aprovações internas) — rechecada no finalize (D4)."""
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

    # ------------------------------------------------------------------
    # Task 8 (revisado) — emissão enfileirada, revisão, próxima qualificação
    # ------------------------------------------------------------------

    @api.depends("current_emissao_id.issued_at")
    def _compute_proxima_qualificacao(self):
        """Emissão vigente + 12 meses; sem emissão, o resultado de P1.

        A data local é a do fuso do emissor (senão o da empresa, senão
        America/Sao_Paulo) — nunca a do contexto: o finalize roda no cron,
        sem tz, e 23:30 em Brasília já é o dia seguinte em UTC."""
        super()._compute_proxima_qualificacao()
        for rel in self:
            emissao = rel.current_emissao_id
            if emissao.issued_at:
                tz = emissao.issued_by.tz or company_tz(rel.company_id)
                local = fields.Datetime.context_timestamp(
                    rel.with_context(tz=tz), emissao.issued_at).date()
                rel.proxima_qualificacao = local + relativedelta(months=12)

    def _scan_snapshot(self):
        """JSON dos achados + decisões. P4 não tem varredura: '[]'. P5 sobrescreve."""
        self.ensure_one()
        return "[]"

    def _blocks_snapshot(self):
        """HTML final de cada bloco + corpo inteiro (tabelas dinâmicas incluídas)."""
        self.ensure_one()
        snapshot = {
            str(block.id): str(self._render_block_body(block))
            for block in self.block_ids.filtered("included")
        }
        html, _fmt = self.env["ir.actions.report"]._render_qweb_html(
            REPORT_CORPO, self.ids, data={"page_map": {}, "with_markers": False},
        )
        snapshot["__corpo__"] = html.decode() if isinstance(html, bytes) else str(html)
        return json.dumps(snapshot, ensure_ascii=False, sort_keys=True)

    def _report_signature_rows(self):
        """P3 + ocultar a aprovação do cliente na montagem (D3): a Rev.N+1 não
        pode sair com a aprovação que o cliente deu à Rev.N."""
        from .relatorio_build_job import HIDE_CLIENT_CTX
        rows = super()._report_signature_rows()
        if self.env.context.get(HIDE_CLIENT_CTX):
            for row, line in zip(rows, self.aprovacao_ids.sorted(sort_key)):
                if line.papel == "cliente":
                    row["approved_at"] = ""
        return rows

    def action_emitir(self):
        """Gate no clique; a montagem roda na fila e grava tudo no finalize."""
        self.ensure_one()
        self._check_manager_only(_("emitir o relatório final"))
        if self.state != "draft":
            raise UserError(_(
                "Só é possível emitir um relatório em rascunho. Use Revisar para "
                "abrir uma nova revisão."))
        Job = self.env["afr.relatorio.build.job"]
        Job._rq_check_no_active(self)
        problems = self._check_emission_gate()
        if problems:
            raise UserError(_("Não é possível emitir o relatório %s:\n- %s") % (
                self.name, "\n- ".join(problems)))
        # Token e data decididos AGORA, no servidor (D6): QR e cabeçalho usam os dois.
        Job._rq_enqueue(self, "emissao", token=uuid.uuid4().hex,
                        issued_at=fields.Datetime.now(), scan_snapshot=self._scan_snapshot())
        self.with_context(clean_context(self.env.context)).message_post(body=_(
            "Emissão da %s solicitada; o PDF está sendo montado.") % self.revision_label)
        return self._rq_enqueued_notification(_(
            "A emissão está sendo montada em segundo plano. O relatório fica travado "
            "para edição até concluir."))

    def _rq_finalize_emissao(self, job, attachment, warnings):
        """Chamado pelo job (sudo + contexto interno, SEM render): hash, emissão
        imutável, anterior substituída, reset do cliente, estado, chatter.
        Os invariantes (versão editorial, estado, revisão, aprovações internas)
        já foram rechecados por `job._rq_stale_reason()` antes desta unidade."""
        self.ensure_one()
        sha256 = hashlib.sha256(attachment.with_context(bin_size=False).raw).hexdigest()
        attachment.with_context(self.env.context).write({
            "res_model": self._name, "res_id": self.id, "public": False,
            "mimetype": "application/pdf",
            "name": "%s-%s.pdf" % (self.name, self.revision_label),
        })
        previous = self.emissao_ids.filtered(lambda e: not e.superseded)
        Emissao = self.env["afr.relatorio.emissao"].sudo().with_context(
            clean_context(self.env.context), **{INTERNAL_CTX: True})
        emissao = Emissao.create({
            "relatorio_id": self.id, "revision": job.revision,
            "pdf_attachment_id": attachment.id, "sha256": sha256,
            "token": job.token, "issued_at": job.issued_at,
            "issued_by": job.requested_by.id,
            "blocks_snapshot": job.blocks_snapshot, "scan_snapshot": job.scan_snapshot,
            "superseded": False,
        })
        # A anterior só vira "substituída" agora que a nova existe (spec §4.6).
        previous.with_env(Emissao.env).write({"superseded": True})
        self._reset_client_approvals()
        self.write({"state": "issued", "current_emissao_id": emissao.id})
        job.write({"emissao_id": emissao.id})
        body = _("Relatório emitido (%(rev)s). SHA-256: %(sha)s") % {
            "rev": self.revision_label, "sha": sha256}
        if warnings:
            body = Markup("%s<ul>%s</ul>") % (body, Markup("").join(
                Markup("<li>%s</li>") % w for w in warnings))
        self.message_post(body=body, attachment_ids=[attachment.id],
                          author_id=job.requested_by.partner_id.id)

    def action_revisar(self):
        """Abre Rev.N+1 em rascunho; a emissão vigente continua valendo até a nova."""
        self.ensure_one()
        self._check_manager_only(_("abrir uma revisão do relatório final"))
        if self.state not in ("issued", "client_approved"):
            raise UserError(_("Só é possível revisar um relatório emitido."))
        ctx = dict(clean_context(self.env.context), **{SKIP_CTX: True})
        self.sudo().with_context(ctx).write({"revision": self.revision + 1, "state": "draft"})
        # Revisão nova = conteúdo novo: uma minuta em montagem é descartada.
        self._rq_bump_editorial_seq()
        self._invalidate_internal_approvals()
        self._rq_reset_alerta_decisions()
        self.with_context(clean_context(self.env.context)).message_post(body=_(
            "Revisão %s aberta. A emissão anterior continua vigente até a nova "
            "ser emitida.") % self.revision_label)
        return True

    def _reset_client_approvals(self):
        """Nova revisão precisa de nova aprovação do cliente (link novo). Só no finalize."""
        lines = self.aprovacao_ids.filtered(lambda a: a.papel == "cliente")
        # Token novo no segredo (sudo + clean_context) e aprovação zerada.
        lines.with_context(clean_context(self.env.context))._rotate_client_token()

    def _rq_lock_for_update(self):
        """Serializa aprovações concorrentes do cliente (fix round 1, achado 2).

        UPDATE sem efeito em vez de só `SELECT ... FOR UPDATE`: além de travar
        a linha, cria versão nova dela. Em REPEATABLE READ, a segunda
        transação que esperava a trava toma erro de serialização e o Odoo
        repete a requisição (service.model.retrying) — já vendo a aprovação
        da primeira. Com FOR UPDATE puro ela seguiria com o snapshot antigo
        e o relatório podia ficar em `issued` com todos aprovados.
        """
        if not self.ids:
            return
        self.env.cr.execute(
            "UPDATE afr_qualificacao_relatorio SET write_date = write_date "
            "WHERE id IN %s",
            [tuple(self.ids)])
        self.invalidate_recordset(["state", "current_emissao_id"])
        self.env["afr.relatorio.aprovacao"].invalidate_model(["approved_at", "ip"])

    def _update_client_approval_state(self):
        """issued ↔ client_approved conforme as aprovações do cliente.

        issued → client_approved quando todos os aprovadores do cliente
        aprovaram; client_approved → issued quando uma aprovação do cliente
        deixa de valer (troca de contato/papel da linha — fix round 1 do
        Task 9). Rascunho (revisão aberta) não é tocado.
        """
        self._rq_lock_for_update()
        for rel in self:
            rel_su = rel.sudo().with_context(clean_context(rel.env.context))
            clientes = rel_su.aprovacao_ids.filtered(lambda a: a.papel == "cliente")
            all_approved = bool(clientes) and all(clientes.mapped("approved_at"))
            if rel.state == "issued" and all_approved:
                rel_su.write({"state": "client_approved"})
                rel_su.message_post(body=_(
                    "Todos os aprovadores do cliente aprovaram a %s."
                ) % rel.revision_label)
            elif rel.state == "client_approved" and not all_approved:
                rel_su.write({"state": "issued"})
                rel_su.message_post(body=_(
                    "Aprovação do cliente da %s deixou de valer (aprovador alterado); "
                    "o relatório voltou para Emitido.") % rel.revision_label)

    # ------------------------------------------------------------------
    # Task 9 — envio do link do portal ao cliente
    # ------------------------------------------------------------------

    def action_enviar_aprovacao_cliente(self):
        """E-mail com o link do portal para cada aprovador do cliente pendente.

        Só o Gestor (fix round 3 do Task 9): o e-mail entrega o access_token
        do cliente — o único outro caminho é `portal_url`, também só Gestor.
        Check no método (RPC direto), não só no botão.
        """
        self.ensure_one()
        self._check_manager_only(_("enviar o relatório para aprovação do cliente"))
        if self.state != "issued" or not self.current_emissao_id:
            raise UserError(_("Envie para aprovação do cliente só depois de emitir."))
        pending = self.aprovacao_ids.filtered(
            lambda a: a.papel == "cliente" and not a.approved_at and a.partner_id.email
        )
        if not pending:
            raise UserError(_(
                "Nenhum aprovador do cliente pendente com e-mail cadastrado."
            ))
        clean_ctx = clean_context(self.env.context)
        # Fix round 4 (ruling R3): sem mail.template (editável por qualquer
        # usuário interno — cc/beacon no modelo oficial ou modelo próprio com
        # o token). Corpo de uma view QWeb (só o administrador edita),
        # renderizado aqui; destinatário = só o contato da linha; mail.mail
        # via sudo + clean_context. Só `body_html` (a mensagem-base, legível
        # por quem lê a linha, fica sem corpo — o token não vai para ela).
        rel_su = self.sudo().with_context(clean_ctx)
        Mail = self.env["mail.mail"].sudo().with_context(clean_ctx)
        QWeb = self.env["ir.qweb"].sudo().with_context(clean_ctx)
        email_from = rel_su.company_id.email_formatted or self.env.user.email_formatted
        subject = _("Aprovação do relatório %(name)s %(rev)s") % {
            "name": rel_su.name, "rev": rel_su.revision_label}
        for line in pending.sudo().with_context(clean_ctx):
            body = QWeb._render("afr_qualificacao.mail_body_relatorio_aprovacao", {
                "line": line, "relatorio": rel_su, "portal_url": line._portal_url(),
            })
            Mail.create({
                "subject": subject,
                "body_html": body,
                "email_from": email_from,
                "recipient_ids": [(6, 0, line.partner_id.ids)],
                "model": "afr.relatorio.aprovacao",
                "res_id": line.id,
                "auto_delete": True,
            })
        self.with_context(clean_ctx).message_post(
            body=_("Link de aprovação enviado para: %s") % ", ".join(
                pending.mapped("partner_id.email")))
        return True


class AfrRelatorioAprovacaoPortal(models.Model):
    _inherit = "afr.relatorio.aprovacao"

    # Leva o access_token: mesmo grupo do token (ruling 1.16/4.5).
    portal_url = fields.Char(
        compute="_compute_portal_url", string="Link do portal",
        groups="afr_qualificacao.group_afr_qualificacao_manager",
    )

    @api.depends("papel", "access_token")
    @api.depends_context("uid")
    def _compute_portal_url(self):
        """Fix round 3: `groups=` não vale em acesso por atributo (render de
        mail.template via generate_email/send_mail por RPC, preview): o
        próprio compute só entrega o link sob su ou ao Gestor."""
        allowed = self.env.su or self.env.user.has_group(
            "afr_qualificacao.group_afr_qualificacao_manager")
        for line in self:
            line.portal_url = (
                line._portal_url() if allowed and line.papel == "cliente" else False)

    def _portal_url(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        url = "%s/my/relatorio/%d?access_token=%s" % (
            icp.get_param("web.base.url", default=""), self.id,
            self._rq_client_tokens().get(self.id) or "")
        db_param = icp.get_param(
            "afr_qualificacao.verify_url_db", default=self.env.cr.dbname)
        if db_param:
            url += "&db=%s" % db_param
        return url

    def _portal_approve(self, nome, ip):
        """Aprovação pelo portal. False se já estava aprovada.

        Só vale para a emissão vigente de um relatório emitido (não em
        revisão). Grava via sudo + clean_context: o guard do P3 só aceita
        approved_at/ip sob env.su e o contexto do chamador não pode injetar
        `default_*` (ruling 5.1).
        """
        self.ensure_one()
        rel = self.relatorio_id
        if self.papel != "cliente":
            raise UserError(_("Só aprovadores do cliente aprovam pelo portal."))
        rel.sudo()._rq_lock_for_update()  # antes de ler approved_at/estado
        if rel.state not in ("issued", "client_approved") or not rel.current_emissao_id:
            raise UserError(_("Não há revisão emitida aguardando aprovação."))
        if self.approved_at:
            return False
        clean_ctx = clean_context(self.env.context)
        line = self.sudo().with_context(clean_ctx)
        nome = (nome or "").strip()[:128]
        line.write({
            "approved_at": fields.Datetime.now(),
            "ip": ip or False,
            "nome_exibicao": nome or line.nome_exibicao or line.partner_id.name or "",
        })
        rel_su = rel.sudo().with_context(clean_ctx)
        # Corpo str (escapado pelo message_post): contém o nome digitado.
        rel_su.message_post(
            body=_("%(nome)s aprovou a %(rev)s pelo portal (IP %(ip)s).") % {
                "nome": line.nome_exibicao, "rev": rel.revision_label, "ip": ip or "—"},
            author_id=line.partner_id.id or None,
        )
        rel_su._update_client_approval_state()
        return True
