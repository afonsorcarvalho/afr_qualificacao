# -*- coding: utf-8 -*-
"""Achado da varredura de inconsistência do Relatório Final (spec §7).

Só a varredura (`action_verificar`, em sudo) cria achados e grava
origem/código/gravidade/mensagem/onde/decidido_por. O contexto SCAN_CTX é só
um marcador legível — nunca autoriza nada (cliente RPC controla o contexto). O usuário grava apenas a
decisão (`decisao`, `motivo`) — e só com o relatório em rascunho.
Achado `bloqueia` não aceita decisão: sai corrigindo o dado e verificando
de novo (evita descartar CERT_DEPOIS_AUSENTE e furar D5).
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

SCAN_CTX = "afr_scan_internal"
USER_WRITABLE_FIELDS = frozenset({"decisao", "motivo"})

ORIGEM_SELECTION = [("regra", "Regra"), ("ia", "IA — verificar")]
GRAVIDADE_SELECTION = [
    ("bloqueia", "Bloqueia"),
    ("alerta", "Alerta"),
    ("info", "Info"),
]
DECISAO_SELECTION = [
    ("pendente", "Pendente"),
    ("procede", "Procede"),
    ("descartado", "Descartado"),
]
GRAVIDADE_ORDER = {"bloqueia": 0, "alerta": 1, "info": 2}


class AfrRelatorioAchado(models.Model):
    _name = "afr.relatorio.achado"
    _description = "Achado da Verificação do Relatório Final"
    _order = "relatorio_id, gravidade_order, origem, codigo, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio",
        string="Relatório",
        required=True,
        ondelete="cascade",
        index=True,
    )
    relatorio_state = fields.Selection(related="relatorio_id.state", string="Estado do relatório")
    origem = fields.Selection(ORIGEM_SELECTION, required=True, default="regra")
    codigo = fields.Char(string="Código", required=True)
    gravidade = fields.Selection(GRAVIDADE_SELECTION, required=True, default="alerta")
    gravidade_order = fields.Integer(compute="_compute_gravidade_order", store=True)
    mensagem = fields.Text(required=True)
    onde = fields.Char(string="Onde")
    decisao = fields.Selection(DECISAO_SELECTION, string="Decisão", required=True, default="pendente")
    motivo = fields.Text()
    decidido_por = fields.Many2one("res.users", string="Decidido por", readonly=True)
    decidido_em = fields.Datetime(string="Decidido em", readonly=True)

    @api.depends("gravidade")
    def _compute_gravidade_order(self):
        for r in self:
            r.gravidade_order = GRAVIDADE_ORDER.get(r.gravidade, 3)

    def _is_internal(self):
        # Só sudo conta como interno. SCAN_CTX é apenas um marcador: contexto
        # é controlado pelo cliente via JSON-RPC, então NÃO é confiável.
        return bool(self.env.su)

    @api.model_create_multi
    def create(self, vals_list):
        if not self._is_internal():
            raise AccessError(_(
                "Achados são criados apenas pela verificação (botão Verificar)."
            ))
        return super().create(vals_list)

    def unlink(self):
        # Item 8 (P5 final fix wave): a ACL do Gestor tem unlink=1 (mesma
        # convenção de CRUD completo dos demais modelos do módulo), mas
        # apagar um achado manualmente contornaria o gate — ex.: um alerta
        # de IA pendente que simplesmente desaparece sem decisão. Só a
        # varredura interna (sudo) remove achados; a ACL fica como está.
        if not self._is_internal():
            raise AccessError(_(
                "Achados são removidos apenas pela verificação (botão Verificar)."
            ))
        return super().unlink()

    def write(self, vals):
        if not self._is_internal():
            extra = set(vals) - USER_WRITABLE_FIELDS
            if extra:
                raise AccessError(_(
                    "Só a decisão e o motivo de um achado podem ser alterados "
                    "(campos recusados: %s)."
                ) % ", ".join(sorted(extra)))
            if any(r.relatorio_id.state != "draft" for r in self):
                raise UserError(_(
                    "Decisões só podem ser alteradas com o relatório em rascunho."
                ))
        if "decisao" in vals:
            vals = dict(vals)
            if vals["decisao"] in ("procede", "descartado"):
                vals["decidido_por"] = self.env.uid
                vals["decidido_em"] = fields.Datetime.now()
            else:
                vals["decidido_por"] = False
                vals["decidido_em"] = False
        return super().write(vals)

    @api.constrains("decisao", "motivo", "gravidade")
    def _check_decisao(self):
        for r in self:
            if r.gravidade == "bloqueia" and r.decisao != "pendente":
                raise ValidationError(_(
                    "Achado bloqueante não aceita decisão: corrija o dado e "
                    "clique em Verificar novamente (%s)."
                ) % r.codigo)
            if r.decisao == "descartado" and not (r.motivo or "").strip():
                raise ValidationError(_(
                    "Informe o motivo para descartar o achado %s."
                ) % r.codigo)
