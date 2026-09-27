"""Registro de aprovações do Relatório Final (P3: só o registro).

Fluxo de aprovação (botões, portal, gate) é de P4.
"""

import uuid

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.misc import clean_context

APROVACAO_PAPEIS = [
    ("elaborador", "Elaborador"),
    ("emissor", "Emissor / Responsável Técnico"),
    ("executor", "Executor"),
    ("cliente", "Cliente"),
]

# Fix round 1, achado 1: campos gravados só pelo fluxo interno de aprovação
# (P4, via sudo) — nunca por escrita direta de um usuário comum.
_APPROVAL_CONTROL_FIELDS = ("approved_at", "ip", "access_token")
# Findings review P3 (final), achado 1: campos de IDENTIDADE de uma linha
# já aprovada — trocar qualquer um deles é "trocar quem está aprovando",
# não só user_id/papel. nome_exibicao/registro/partner_id entram aqui.
_IDENTITY_FIELDS = ("user_id", "papel", "nome_exibicao", "registro", "partner_id")
# Fix round 2, achado 1: mesma regra na criação — `approved_at`/`ip` nunca
# aceitos de um chamador não-sudo (nasceria já aprovada). `access_token` não
# entra aqui: na criação ele é apenas ignorado/substituído (ver create()),
# nunca levanta — o valor de verdade sempre nasce no servidor.
_CREATE_BLOCKED_FIELDS = ("approved_at", "ip")
# Fix round 1 do P4 Task 7, achado 2: designar o EMISSOR (responsável
# técnico) é do Gestor — senão um Usuário se designava emissor numa linha
# pendente e se autoaprovava por `action_aprovar_interno`. Elaborador segue
# atribuível pelo grupo Usuário (o autor costuma se designar).
_MANAGER_GROUP = "afr_qualificacao.group_afr_qualificacao_manager"


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
            if (any(r.papel == "emissor" and r.user_id for r in recs_su)
                    and not self.env.user.has_group(_MANAGER_GROUP)):
                raise AccessError(_(
                    "Apenas o Gestor pode designar o usuário emissor "
                    "(responsável técnico) do relatório."
                ))
            stray_tokens = recs_su.filtered(lambda r: r.papel != "cliente" and r.access_token)
            if stray_tokens:
                stray_tokens.write({"access_token": False})
            recs_su._check_client_partner()
        # Fix round 2 do P4 Task 9, achado 3: o papel efetivo pode vir de
        # `default_papel` do contexto (fora do vals) — token pelo registro.
        missing = records.sudo().filtered(lambda r: r.papel == "cliente" and not r.access_token)
        if missing:
            missing._rotate_client_token(clear_approval=False)
        return records

    def _check_client_partner(self):
        """Fix round 1 do P4 Task 9, achado 1b: fora de `env.su`, o contato de
        uma linha `cliente` tem de ser o cliente do relatório ou um contato
        dele (mesmo `commercial_partner_id`). Senão um Usuário apontava a
        linha para um e-mail seu e recebia o link (token) por
        `action_enviar_aprovacao_cliente`."""
        for rec in self.sudo():
            if rec.papel != "cliente" or not rec.partner_id:
                continue
            allowed = rec.relatorio_id.partner_id.commercial_partner_id
            if not allowed or rec.partner_id.commercial_partner_id != allowed:
                raise ValidationError(_(
                    "O aprovador do cliente (%(contato)s) precisa ser o cliente do "
                    "relatório (%(cliente)s) ou um contato dele."
                ) % {"contato": rec.partner_id.display_name,
                     "cliente": rec.relatorio_id.partner_id.display_name or "—"})

    def _rotate_client_token(self, clear_approval=True):
        """Token novo (servidor, sudo + clean_context) — o link antigo morre."""
        lines = self.sudo().with_context(clean_context(self.env.context))
        for line in lines:
            vals = {"access_token": uuid.uuid4().hex}
            if clear_approval:
                vals.update(approved_at=False, ip=False)
            line.write(vals)

    def _identity_field_changed(self, field, vals):
        """True quando `vals[field]` difere do valor atual do registro
        (`self`, um único registro). Ausente de `vals` nunca é "mudança"."""
        if field not in vals:
            return False
        new = vals.get(field)
        if field in ("user_id", "partner_id"):
            return self[field].id != (new or False)
        return (self[field] or False) != (new or False)

    def _emissor_designation_changed(self, vals):
        """True se `vals` troca quem é o emissor desta linha: muda `user_id`
        de uma linha emissor (inclusive para vazio), ou vira `papel`
        emissor uma linha que fica com usuário."""
        new_papel = vals.get("papel", self.papel)
        user_changed = self._identity_field_changed("user_id", vals)
        if user_changed and "emissor" in (self.papel, new_papel):
            return True
        new_user = vals["user_id"] if "user_id" in vals else self.user_id.id
        return bool(new_papel == "emissor" and self.papel != "emissor" and new_user)

    def write(self, vals):
        """Fix round 1, achado 1 + findings review P3 (final), achado 1.

        `approved_at`/`ip`/`access_token` só podem ser gravados pelo sistema
        (sudo interno — fluxo de aprovação da P4), nunca por escrita direta
        de um usuário comum via RPC/form.

        Trocar de fato quem está aprovando numa linha já aprovada
        (`user_id`, `papel`, `nome_exibicao`, `registro` ou `partner_id`)
        invalida a aprovação: limpa `approved_at`/`ip` para forçar
        reaprovação — EXCETO para `papel='executor'`: esse papel não tem
        fluxo de reaprovação (a "aprovação" é a assinatura já coletada no
        relatório diário), então fora de `env.su` a troca é REJEITADA
        (`AccessError`) em vez de invalidada. Dentro de `env.su` (fluxo
        interno) a troca é permitida e invalida como qualquer outro papel.

        "Trocar de fato": só quando o valor novo difere do atual — regravar
        o mesmo valor não apaga a aprovação — e nunca quando o próprio
        `vals` já está definindo `approved_at` (uma aprovação interna via
        sudo que grava a identidade + `approved_at` juntos, como o próprio
        fluxo de aprovação da P4 faz, não deve se autoinvalidar).
        """
        # Fix round 2 do P4 Task 9, achado 2: linha de aprovação nunca muda
        # de relatório fora do fluxo interno (levaria token/aprovação junto).
        if (not self.env.su and "relatorio_id" in vals
                and any(rec.relatorio_id.id != (vals["relatorio_id"] or False) for rec in self)):
            raise AccessError(_(
                "Uma linha de aprovação não pode ser movida para outro relatório."
            ))
        touched = set(vals) & set(_APPROVAL_CONTROL_FIELDS)
        if touched and not self.env.su:
            raise AccessError(_(
                "Apenas o sistema pode alterar os campos de controle da "
                "aprovação (%s)."
            ) % ", ".join(sorted(touched)))
        if (not self.env.su and ({"user_id", "papel"} & set(vals))
                and not self.env.user.has_group(_MANAGER_GROUP)
                and any(rec._emissor_designation_changed(vals) for rec in self)):
            raise AccessError(_(
                "Apenas o Gestor pode designar ou trocar o usuário emissor "
                "(responsável técnico) do relatório."
            ))
        touched_identity = set(vals) & set(_IDENTITY_FIELDS)
        changed = self.browse()
        if touched_identity and "approved_at" not in vals:
            changed = self.filtered(lambda rec: rec.approved_at and any(
                rec._identity_field_changed(f, vals) for f in touched_identity
            ))
        if changed and not self.env.su:
            locked = changed.filtered(lambda rec: rec.papel == "executor")
            if locked:
                raise AccessError(_(
                    "Uma aprovação de Executor já registrada não pode ser "
                    "alterada (%s); não há fluxo de reaprovação para este "
                    "papel."
                ) % ", ".join(sorted(touched_identity)))
        # Fix round 1 do P4 Task 9, achado 1a: trocar o contato de uma linha
        # cliente (ou virar cliente) gera token novo — o link já enviado ao
        # contato anterior deixa de valer.
        rotate = self.filtered(lambda rec: vals.get("papel", rec.papel) == "cliente" and (
            rec.papel != "cliente" or rec._identity_field_changed("partner_id", vals)))
        drop = self.filtered(
            lambda rec: rec.papel == "cliente" and vals.get("papel", "cliente") != "cliente")
        result = super().write(vals)
        if changed:
            changed.sudo().write({"approved_at": False, "ip": False})
        if rotate:
            rotate._rotate_client_token(clear_approval="approved_at" not in vals)
        if drop:
            drop.sudo().with_context(clean_context(self.env.context)).write(
                {"access_token": False})
        missing = self.sudo().filtered(lambda r: r.papel == "cliente" and not r.access_token)
        if missing:
            missing._rotate_client_token(clear_approval=False)
        if not self.env.su:
            self._check_client_partner()
        # Aprovação do cliente zerada/linha que entra ou sai de 'cliente':
        # o estado issued/client_approved do relatório é recalculado (mesmo
        # caminho do portal: trava da linha do relatório, sudo + clean_context).
        if changed or rotate or drop:
            rels = (changed | rotate | drop).relatorio_id.sudo().filtered(
                lambda r: r.state in ("issued", "client_approved"))
            if rels:
                rels.with_context(clean_context(self.env.context))._update_client_approval_state()
        return result
