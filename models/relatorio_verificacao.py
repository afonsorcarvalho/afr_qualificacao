# -*- coding: utf-8 -*-
"""Relatório Final — varredura de inconsistência e gate de emissão (P5)."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import clean_context

from . import relatorio_rules
from .relatorio_achado import SCAN_CTX

AI_SKIP_CTX = "afr_skip_ai"


class AfrQualificacaoRelatorio(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    achado_ids = fields.One2many(
        "afr.relatorio.achado",
        "relatorio_id",
        string="Achados da verificação",
    )
    has_blocking = fields.Boolean(compute="_compute_blocking", string="Tem bloqueio")
    blocking_summary = fields.Text(compute="_compute_blocking", string="Aguardando")
    achado_pendente_count = fields.Integer(
        compute="_compute_blocking", string="Achados pendentes"
    )

    @api.depends("achado_ids.gravidade", "achado_ids.decisao", "achado_ids.mensagem")
    def _compute_blocking(self):
        for r in self:
            blocking = r.achado_ids.filtered(
                lambda a: a.gravidade == "bloqueia" and a.decisao == "pendente"
            )
            r.has_blocking = bool(blocking)
            r.blocking_summary = "\n".join("• %s" % a.mensagem for a in blocking)
            r.achado_pendente_count = len(r.achado_ids.filtered(
                lambda a: a.decisao == "pendente" and a.gravidade != "info"
            ))

    # ------------------------------------------------------------ varredura
    def action_verificar(self):
        for rel in self:
            if rel.state != "draft":
                raise UserError(_("Só é possível verificar um relatório em rascunho."))
            rel._run_verificacao()
        return True

    def _ai_findings(self):
        """Achados da IA (dicts sem `origem`). Substituído na Task 5."""
        return []

    def _run_verificacao(self):
        """Recria achados pendentes; herda decisões de achados que se repetem.

        Chave de carry-over: (origem, codigo, onde). Decidido que se repete →
        mantém decisão, atualiza mensagem/gravidade (volta a pendente se virar
        bloqueia). Decidido que não se repete → apagado. Com AI_SKIP_CTX os
        achados de IA existentes não são tocados.

        Ruling 1.12: toda escrita interna (create/message_post) roda em
        `sudo().with_context(clean_context(self.env.context))` — o contexto
        do chamador pode trazer `default_decidido_por`/`default_decisao`/etc
        (o cliente JSON-RPC controla o contexto) e o ORM aplicaria esses
        valores a um achado novo se a chave não estiver em `vals`. Por isso
        um achado novo grava decidido_por/decidido_em/motivo=False e
        decisao='pendente' explicitamente — nunca implícito via default do
        contexto.
        """
        self.ensure_one()
        skip_ai = bool(self.env.context.get(AI_SKIP_CTX))
        clean_ctx = clean_context(self.env.context)
        Achado = self.env["afr.relatorio.achado"].sudo().with_context(
            clean_ctx, **{SCAN_CTX: True})

        findings = [dict(f, origem="regra") for f in relatorio_rules.run_rules(self)]
        origens = ["regra"]
        if not skip_ai:
            origens.append("ia")
            findings += [dict(f, origem="ia") for f in self._ai_findings()]

        existing = Achado.search([
            ("relatorio_id", "=", self.id),
            ("origem", "in", origens),
        ])
        pending = existing.filtered(lambda a: a.decisao == "pendente")
        decided_recs = existing - pending
        pending.unlink()
        decided = {(a.origem, a.codigo, a.onde or ""): a for a in decided_recs}

        kept = Achado.browse()
        to_create = []
        seen = set()
        for f in findings:
            key = (f["origem"], f["codigo"], f.get("onde") or "")
            if key in seen:
                continue
            seen.add(key)
            rec = decided.get(key)
            if rec:
                vals = {"mensagem": f["mensagem"], "gravidade": f["gravidade"]}
                if f["gravidade"] == "bloqueia":
                    vals.update(decisao="pendente", motivo=False)
                rec.write(vals)
                kept |= rec
            else:
                to_create.append({
                    "relatorio_id": self.id,
                    "origem": f["origem"],
                    "codigo": f["codigo"],
                    "gravidade": f["gravidade"],
                    "mensagem": f["mensagem"],
                    "onde": f.get("onde") or "",
                    "decisao": "pendente",
                    "decidido_por": False,
                    "decidido_em": False,
                    "motivo": False,
                })
        (decided_recs - kept).unlink()
        if to_create:
            Achado.create(to_create)
        self.invalidate_recordset(["achado_ids"])

        if not self.env.context.get(relatorio_rules.EMISSION_CTX):
            grav = [f["gravidade"] for f in findings]
            self.sudo().with_context(clean_ctx).message_post(body=_(
                "Verificação executada: %(b)s bloqueio(s), %(a)s alerta(s), "
                "%(i)s informativo(s).",
                b=grav.count("bloqueia"), a=grav.count("alerta"), i=grav.count("info"),
            ))
        return True
