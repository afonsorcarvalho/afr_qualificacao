"""Edição editorial do Relatório Final (spec §4.6).

Editar dados, texto ou anexos em rascunho zera as aprovações internas (evita
aprovar uma versão e emitir outra). Fora de rascunho a edição é recusada —
o PDF emitido e os dados não podem divergir até alguém clicar Revisar.
Os ganchos ficam nos models FILHOS também: o form de bloco (modal), anexos,
checklist etc. gravam direto no filho, sem passar por relatorio.write().

A guarda de `approved_at`/`ip`/`access_token` de `afr.relatorio.aprovacao`
NÃO fica aqui: P3 (`relatorio_aprovacao.py`) já a aplica a todos os papéis
(ruling 1.11/4.4 do P4).
"""
from odoo import api, models

SKIP_CTX = "rq_skip_editorial_hook"


class AfrRelatorioEditorialMixin(models.AbstractModel):
    _name = "afr.relatorio.editorial.mixin"
    _description = "Mixin: edição editorial do Relatório Final"

    # True: recusa a edição com relatório fora de rascunho; False: só invalida.
    _rq_lock_when_issued = True
    # None: qualquer campo conta; frozenset: só estes campos contam no write.
    _rq_watched_fields = None

    def _rq_relatorios(self):
        return self.mapped("relatorio_id")

    def _rq_touch(self, vals=None):
        if self.env.context.get(SKIP_CTX) or not self:
            return
        if (vals is not None and self._rq_watched_fields is not None
                and not self._rq_watched_fields.intersection(vals)):
            return
        relatorios = self._rq_relatorios()
        if not relatorios:
            return
        if self._rq_lock_when_issued:
            relatorios._check_editable()
        relatorios._invalidate_internal_approvals()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._rq_touch()
        return records

    def write(self, vals):
        self._rq_touch(vals)
        return super().write(vals)

    def unlink(self):
        self._rq_touch()
        return super().unlink()


def _draft_relatorios_of(env, qualificacoes):
    """Relatórios em rascunho que usam estas qualificações.

    Busca com sudo: quem dispara pode ser um Técnico editando a janela do
    ciclo, sem visibilidade garantida do relatório — deixar de achar o
    relatório aqui manteria aprovações de um conteúdo que mudou.
    """
    Relatorio = env["afr.qualificacao.relatorio"]
    if not qualificacoes:
        return Relatorio
    return Relatorio.sudo().search([
        ("qualificacao_ids", "in", qualificacoes.ids),
        ("state", "=", "draft"),
    ])


class AfrRelatorioBlockEditorial(models.Model):
    _name = "afr.relatorio.block"
    _inherit = ["afr.relatorio.block", "afr.relatorio.editorial.mixin"]


class AfrRelatorioAnexoEditorial(models.Model):
    _name = "afr.relatorio.anexo"
    _inherit = ["afr.relatorio.anexo", "afr.relatorio.editorial.mixin"]


class AfrRelatorioChecklistEditorial(models.Model):
    _name = "afr.relatorio.checklist"
    _inherit = ["afr.relatorio.checklist", "afr.relatorio.editorial.mixin"]


class AfrRelatorioIndicadorEditorial(models.Model):
    _name = "afr.relatorio.indicador"
    _inherit = ["afr.relatorio.indicador", "afr.relatorio.editorial.mixin"]


class AfrRelatorioLeituraIbEditorial(models.Model):
    _name = "afr.relatorio.leitura.ib"
    _inherit = ["afr.relatorio.leitura.ib", "afr.relatorio.editorial.mixin"]


class AfrRelatorioSensorPosEditorial(models.Model):
    _name = "afr.relatorio.sensor.pos"
    _inherit = ["afr.relatorio.sensor.pos", "afr.relatorio.editorial.mixin"]

    # Dado de campo do ciclo: não trava (a qualificação pode seguir
    # sendo usada), só zera aprovações de relatórios em rascunho.
    _rq_lock_when_issued = False

    def _rq_relatorios(self):
        return _draft_relatorios_of(self.env, self.mapped("cycle_id.qualificacao_id"))


class AfrQualificacaoCycleEditorial(models.Model):
    _name = "afr.qualificacao.cycle"
    _inherit = ["afr.qualificacao.cycle", "afr.relatorio.editorial.mixin"]

    _rq_lock_when_issued = False
    _rq_watched_fields = frozenset({"janela_inicio", "janela_fim", "sensor_pos_ids"})

    def _rq_relatorios(self):
        return _draft_relatorios_of(self.env, self.mapped("qualificacao_id"))

    @api.model_create_multi
    def create(self, vals_list):
        # Criar ciclo (confirmação de SO, geração de OS) não é edição
        # editorial: pula o gancho do mixin. O retorno volta ao contexto
        # normal — senão gravações seguintes no mesmo recordset pulariam
        # o gancho.
        return super(
            AfrQualificacaoCycleEditorial, self.with_context(**{SKIP_CTX: True})
        ).create(vals_list).with_context(**{SKIP_CTX: False})

    def unlink(self):
        return super(
            AfrQualificacaoCycleEditorial, self.with_context(**{SKIP_CTX: True})
        ).unlink()
