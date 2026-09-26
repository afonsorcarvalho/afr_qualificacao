"""Registro de aprovações do Relatório Final (P3: só o registro).

Fluxo de aprovação (botões, portal, gate) é de P4.
"""

import uuid

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

APROVACAO_PAPEIS = [
    ("elaborador", "Elaborador"),
    ("emissor", "Emissor / Responsável Técnico"),
    ("executor", "Executor"),
    ("cliente", "Cliente"),
]

# Fix round 1, achado 1: campos gravados só pelo fluxo interno de aprovação
# (P4, via sudo) — nunca por escrita direta de um usuário comum.
_APPROVAL_CONTROL_FIELDS = ("approved_at", "ip", "access_token")
# Fix round 2, achado 1: mesma regra na criação — `approved_at`/`ip` nunca
# aceitos de um chamador não-sudo (nasceria já aprovada). `access_token` não
# entra aqui: na criação ele é apenas ignorado/substituído (ver create()),
# nunca levanta — o valor de verdade sempre nasce no servidor.
_CREATE_BLOCKED_FIELDS = ("approved_at", "ip")


class AfrRelatorioAprovacao(models.Model):
    _name = "afr.relatorio.aprovacao"
    _description = "Aprovação do Relatório Final"
    _order = "sequence, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    papel = fields.Selection(APROVACAO_PAPEIS, required=True)
    user_id = fields.Many2one("res.users", string="Usuário")
    partner_id = fields.Many2one("res.partner", string="Contato")
    nome_exibicao = fields.Char(string="Nome no relatório")
    registro = fields.Char(string="Registro (CREA etc.)")
    approved_at = fields.Datetime(string="Aprovado em", readonly=True, copy=False)
    ip = fields.Char(readonly=True, copy=False)
    # Fix round 1, achado 2: token de acesso do cliente só visível ao Gestor
    # (Técnico/Usuário têm leitura=1 no registro, mas não neste campo).
    access_token = fields.Char(
        readonly=True, copy=False,
        groups="afr_qualificacao.group_afr_qualificacao_manager",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Fix round 2, achado 1.

        `approved_at`/`ip` nunca podem vir de um `create()` não-sudo — sem
        isto, um membro do grupo Usuário nascia a linha já aprovada. Um
        `access_token` "escolhido" pelo chamador não-sudo é descartado (não
        levanta, só é ignorado): o token de `papel='cliente'` é sempre
        gerado aqui no servidor, nunca aceito de fora — sob `sudo()` (fluxo
        interno confiável) um token fornecido é mantido.

        O pré-check abaixo só vê o `vals` RECEBIDO. Como em
        `qualificacao_os.py::create()` (Task 13/14), o Odoo aplica defaults
        (`default_<campo>` do contexto, `ir.default`) DEPOIS deste override,
        dentro do próprio `super().create()` — um `with_context(default_approved_at=...)`
        não-sudo sobrevivia ao pré-check. O pós-check olha o valor EFETIVO
        do registro já criado, agnóstico ao vetor usado.
        """
        for vals in vals_list:
            if not self.env.su:
                touched = set(vals) & set(_CREATE_BLOCKED_FIELDS)
                if touched:
                    raise AccessError(_(
                        "Apenas o sistema pode definir os campos de controle "
                        "da aprovação (%s) na criação."
                    ) % ", ".join(sorted(touched)))
                vals.pop("access_token", None)
            if vals.get("papel") == "cliente" and not vals.get("access_token"):
                vals["access_token"] = uuid.uuid4().hex
        records = super().create(vals_list)
        if not self.env.su:
            recs_su = records.sudo()
            touched = set()
            if any(recs_su.mapped("approved_at")):
                touched.add("approved_at")
            if any(recs_su.mapped("ip")):
                touched.add("ip")
            if touched:
                raise AccessError(_(
                    "Apenas o sistema pode definir os campos de controle "
                    "da aprovação (%s) na criação."
                ) % ", ".join(sorted(touched)))
            stray_tokens = recs_su.filtered(lambda r: r.papel != "cliente" and r.access_token)
            if stray_tokens:
                stray_tokens.write({"access_token": False})
        return records

    def write(self, vals):
        """Fix round 1, achado 1.

        `approved_at`/`ip`/`access_token` só podem ser gravados pelo sistema
        (sudo interno — fluxo de aprovação da P4), nunca por escrita direta
        de um usuário comum via RPC/form. Trocar de fato o responsável
        (`user_id`) ou o `papel` de uma linha já aprovada invalida a
        aprovação: limpa `approved_at`/`ip` para forçar reaprovação.

        "Trocar de fato": só quando o valor novo difere do atual — regravar
        o mesmo `user_id` não apaga a aprovação — e nunca quando o próprio
        `vals` já está definindo `approved_at` (uma aprovação interna via
        sudo que grava `user_id` + `approved_at` juntos não deve se
        autoinvalidar).
        """
        touched = set(vals) & set(_APPROVAL_CONTROL_FIELDS)
        if touched and not self.env.su:
            raise AccessError(_(
                "Apenas o sistema pode alterar os campos de controle da "
                "aprovação (%s)."
            ) % ", ".join(sorted(touched)))
        to_invalidate = self.browse()
        if ("user_id" in vals or "papel" in vals) and "approved_at" not in vals:
            to_invalidate = self.filtered(lambda rec: rec.approved_at and (
                ("user_id" in vals and rec.user_id.id != (vals.get("user_id") or False))
                or ("papel" in vals and rec.papel != vals.get("papel"))
            ))
        result = super().write(vals)
        if to_invalidate:
            to_invalidate.sudo().write({"approved_at": False, "ip": False})
        return result
