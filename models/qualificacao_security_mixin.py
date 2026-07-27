# -*- coding: utf-8 -*-
"""Mixin de segurança compartilhado entre `afr.qualificacao.os` e
`afr.qualificacao` (Task 10 — fecho do bypass do certificado).

`_check_manager_only` nasceu em `qualificacao_os.py` (Task 9) para os guards
de `action_approve`/`action_done`/`action_cancel`. A Task 10 encontrou o
mesmo buraco em `afr.qualificacao` (cascata de certificado alcançável sem
Gestor) e precisa do MESMO guard — extraído aqui para não duplicar o check
`has_group` em dois arquivos.
"""
from odoo import _, models
from odoo.exceptions import UserError


class AfrQualificacaoManagerGuardMixin(models.AbstractModel):
    """Guard servidor reutilizável: só o grupo Gestor pode executar `acao`."""

    _name = "afr.qualificacao.manager.guard.mixin"
    _description = "Mixin: guard servidor 'apenas Gestor'"

    def _check_manager_only(self, acao):
        """Levanta `UserError` se o usuário atual não é Gestor.

        O `groups=` nos botões da view é só UI — qualquer chamada RPC direta
        (ex.: técnico com write no modelo) contornaria isso sem este check.
        `self.env.su` cobre chamadas internas/sudo (crons, migrações, testes
        no `env` default), que são código confiável, não RPC externo.

        :param acao: frase completa a compor a mensagem, ex.:
            "aprovar a OS" ou "aprovar a qualificação".
        """
        if self.env.su:
            return
        if not self.env.user.has_group(
            "afr_qualificacao.group_afr_qualificacao_manager"
        ):
            raise UserError(_("Apenas o Gestor pode %s.") % acao)
