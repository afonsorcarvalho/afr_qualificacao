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


def skip_editorial_hook(env):
    """SKIP_CTX só vale sob `env.su` (fix round 1, achado 1): contexto é
    controlado pelo cliente RPC, então sem su a chave é ignorada — senão
    qualquer chamador furaria a trava do relatório emitido e a invalidação."""
    return bool(env.su and env.context.get(SKIP_CTX))


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
        if not self or skip_editorial_hook(self.env):
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

    def _rq_touch_create(self, vals_list):
        """Gancho pós-create; o ciclo sobrescreve (só campos vigiados)."""
        self._rq_touch()

    def _rq_touch_unlink(self):
        """Gancho pré-unlink; o ciclo sobrescreve (só se tinha dado vigiado)."""
        self._rq_touch()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._rq_touch_create(vals_list)
        return records

    def write(self, vals):
        self._rq_touch(vals)
        return super().write(vals)

    def unlink(self):
        self._rq_touch_unlink()
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

    # Fix round 1, achado 1: criar/apagar ciclo (confirmação de SO, geração
    # de OS) não é edição editorial — decidido aqui, estruturalmente, e não
    # por uma chave de contexto (que o cliente RPC controla).

    def _rq_touch_create(self, vals_list):
        """Só conta se o ciclo já nasce com janela/sensores preenchidos."""
        if any(vals.get(f) for vals in vals_list for f in self._rq_watched_fields):
            self._rq_touch()

    def _rq_touch_unlink(self):
        """Só conta se o ciclo apagado tinha janela/sensores preenchidos."""
        if any(c.janela_inicio or c.janela_fim or c.sensor_pos_ids for c in self):
            self._rq_touch()
