"""Fila da montagem do PDF do Relatório Final (emenda P4 — "Fila + etapas").

A montagem síncrona de um relatório pesado passou de 90 s de CPU; em prefork
`limit_time_cpu` vale por unidade de trabalho para todos os workers, inclusive
o de cron (server.py check_limits). Cada invocação do cron executa unidades
pequenas do pipeline de `afr.relatorio.pdf` (_stage_*) com orçamento de CPU e
se re-agenda com `_trigger`. Gates e aprovações ficam síncronos no clique;
emissão, estado, revisão, reset do cliente e minuta só são gravados no
finalize, depois de todo render.
"""
import json
import logging
import os
import resource
import tempfile
import time
from contextlib import closing, contextmanager
from datetime import timedelta
from urllib.parse import urlparse

import psycopg2
from markupsafe import Markup

from odoo import _, api, fields, http, models
from odoo.exceptions import UserError
from odoo.http import request
from odoo.modules import module as odoo_module
from odoo.tools.misc import clean_context

from .relatorio_editorial import SKIP_CTX
from .relatorio_pdf import (
    CHUNK_PAGES_PARAM, DEFAULT_CHUNK_PAGES, DEFAULT_STEP_CPU, STEP_CPU_PARAM,
    Budget, stage_progress,
)

_logger = logging.getLogger(__name__)

INLINE_CTX = "rq_build_inline"
HIDE_CLIENT_CTX = "rq_hide_client_approval"
# Cookie-jar (arquivo 0600) com a sessão efêmera que o wkhtmltopdf apresenta
# ao baixar /web/assets quando não há request (cron). Só honrado sem request
# (ver ir.actions.report). Arquivo, não argv: o sid não aparece no `ps`.
REPORT_COOKIE_JAR_CTX = "rq_report_cookie_jar"
CRON_XMLID = "afr_qualificacao.ir_cron_relatorio_build_job"
ACTIVE_STATES = ("queued", "running")
# Defaults (D9); os dois primeiros podem ser trocados por ir.config_parameter.
# O intervalo do cron (5 min, rede de segurança) fica no próprio registro.
MAX_ATTEMPTS = 3
MAX_ATTEMPTS_PARAM = "afr_qualificacao.relatorio_build_max_attempts"
JOB_RETENTION_DAYS = 30
RETENTION_PARAM = "afr_qualificacao.relatorio_build_retention_days"
CHAIN_CPU_FRACTION = 0.25
CHAIN_WALL_SECONDS = 30.0
# Folga (s de CPU) antes do RLIMIT_CPU soft do worker: a unidade para aí, antes
# do SIGXCPU (que o Odoo 16 converte em Exception, server.py
# signal_time_expired_handler, e repete a cada ~1 s).
RLIMIT_CPU_MARGIN = 5.0
SESSION_SAVE_TRIES = 5
CPU_LIMIT_MESSAGE = "CPU time limit exceeded."
USER_GROUP = "afr_qualificacao.group_afr_qualificacao_user"
# Fases que renderizam (engc da malha em `sources`, corpo em `body`).
RENDER_PHASES = ("sources", "body")
JOB_KINDS = [("minuta", "Minuta"), ("emissao", "Emissão")]
JOB_STATES = [
    ("queued", "Na fila"), ("running", "Montando"), ("done", "Concluída"),
    ("failed", "Falhou"), ("cancelled", "Cancelada"),
]


def _internal_ctx(env):
    """Contexto de gravação interna: sem default_* (ruling 5.1) e sem gancho
    editorial (SKIP_CTX só vale sob env.su — usar sempre com sudo())."""
    return dict(clean_context(env.context), **{SKIP_CTX: True})


class _AttachmentStore:
    """Blobs do pipeline como ir.attachment privados do job.

    `mimetype` octet-stream: com `attachment_indexation` instalado, um
    `application/pdf` seria indexado (pdfminer) a cada pedaço, dentro do
    orçamento de CPU da unidade. O finalize grava `application/pdf`.
    """

    def __init__(self, job):
        self.job = job

    def _model(self):
        return self.job.env["ir.attachment"].sudo().with_context(_internal_ctx(self.job.env))

    def put(self, name, data):
        att = self._model().create({
            "name": "rq-build-%d-%s" % (self.job.id, name),
            "raw": data,
            "mimetype": "application/octet-stream",
            "res_model": self.job._name,
            "res_id": self.job.id,
            "public": False,
        })
        return str(att.id)

    def get(self, key):
        att = self._model().browse(int(key))
        if att.res_model != self.job._name or att.res_id != self.job.id:
            raise UserError(_("Arquivo intermediário não pertence a esta montagem."))
        return att.with_context(bin_size=False).raw


class AfrRelatorioBuildJob(models.Model):
    _name = "afr.relatorio.build.job"
    _description = "Montagem do PDF do Relatório Final (fila)"
    _order = "id desc"
    _rec_name = "relatorio_id"

    relatorio_id = fields.Many2one("afr.qualificacao.relatorio", required=True,
                                   ondelete="cascade", index=True, readonly=True)
    kind = fields.Selection(JOB_KINDS, required=True, readonly=True)
    state = fields.Selection(JOB_STATES, required=True, default="queued",
                             readonly=True, index=True)
    requested_by = fields.Many2one("res.users", required=True, readonly=True)
    revision = fields.Integer(readonly=True)
    editorial_seq = fields.Integer(readonly=True)
    token = fields.Char(readonly=True, copy=False,
                        groups="afr_qualificacao.group_afr_qualificacao_manager")
    issued_at = fields.Datetime(readonly=True)
    scan_snapshot = fields.Text(readonly=True)
    blocks_snapshot = fields.Text(readonly=True)
    stage_json = fields.Text(readonly=True)
    phase = fields.Char(readonly=True)
    progress = fields.Integer(readonly=True)
    attempts = fields.Integer(readonly=True)
    last_run_at = fields.Datetime(readonly=True)
    error = fields.Text(readonly=True)
    result_attachment_id = fields.Many2one("ir.attachment", readonly=True)
    emissao_id = fields.Many2one("afr.relatorio.emissao", readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS afr_relatorio_build_job_one_active
            ON afr_relatorio_build_job (relatorio_id)
            WHERE state IN ('queued', 'running')
        """)

    # ---------------------------------------------------------------- enqueue
    @api.model
    def _rq_active_for(self, relatorios):
        return self.sudo().search([("relatorio_id", "in", relatorios.ids),
                                   ("state", "in", ACTIVE_STATES)])

    @api.model
    def _rq_check_no_active(self, relatorio):
        if self._rq_active_for(relatorio):
            raise UserError(_(
                "Já existe uma montagem de PDF em andamento para %s. Aguarde a "
                "conclusão ou cancele-a."
            ) % relatorio.name)

    @api.model
    def _rq_enqueue(self, relatorio, kind, **extra):
        relatorio.ensure_one()
        self._rq_check_no_active(relatorio)
        vals = {
            "relatorio_id": relatorio.id, "kind": kind, "state": "queued",
            "requested_by": self.env.user.id, "revision": relatorio.revision,
            "editorial_seq": relatorio.rq_editorial_seq,
            "stage_json": json.dumps(self.env["afr.relatorio.pdf"]._stage_init(kind == "minuta")),
            "phase": "sources", "progress": 0, "attempts": 0,
            "last_run_at": fields.Datetime.now(), "error": False,
            "result_attachment_id": False, "emissao_id": False,
        }
        vals.update(extra)
        try:
            with self.env.cr.savepoint():
                job = self.sudo().with_context(_internal_ctx(self.env)).create(vals)
        except psycopg2.IntegrityError:
            raise UserError(_("Já existe uma montagem de PDF em andamento para %s.")
                            % relatorio.name)
        self.env.ref(CRON_XMLID).sudo()._trigger()
        return job

    # ------------------------------------------------------------------- cron
    @api.model
    def _rq_param(self, key, default, cast, minimum):
        try:
            value = cast(self.env["ir.config_parameter"].sudo().get_param(key, default))
        except (TypeError, ValueError):
            value = default
        return max(value, minimum)

    @api.model
    def _cron_process(self):
        """Unidades de montagem dentro de UM orçamento de CPU por invocação:
        o RLIMIT_CPU do WorkerCron só é renovado entre invocações."""
        step_cpu = self._rq_param(STEP_CPU_PARAM, DEFAULT_STEP_CPU, float, 1.0)
        cpu0, wall0 = time.process_time(), time.monotonic()
        cpu_deadline = self._rq_cpu_deadline(cpu0, step_cpu)
        Job = self.sudo()
        while True:
            job = Job.search([("state", "in", ACTIVE_STATES)], order="last_run_at, id", limit=1)
            if not job:
                return
            progressed = job._rq_run_unit(cpu_deadline=cpu_deadline)
            if (not progressed
                    or time.process_time() - cpu0 >= step_cpu * CHAIN_CPU_FRACTION
                    or time.monotonic() - wall0 >= CHAIN_WALL_SECONDS):
                break
        if Job.search_count([("state", "in", ACTIVE_STATES)]):
            now = fields.Datetime.now()
            # "agora" gera o NOTIFY que acorda o WorkerCron; "+1 s" sobrevive ao
            # DELETE de triggers vencidos que o core faz ao fim do job.
            self.env.ref(CRON_XMLID).sudo()._trigger_list([now, now + timedelta(seconds=1)])

    @api.model
    def _rq_cpu_deadline(self, cpu0, step_cpu):
        """Prazo de CPU da invocação: o orçamento, mas nunca além do RLIMIT_CPU
        soft do worker (menos a folga). `process_time()` e o RLIMIT medem a
        mesma coisa: CPU user+sys do processo."""
        deadline = cpu0 + step_cpu
        soft, _hard = resource.getrlimit(resource.RLIMIT_CPU)
        if soft != resource.RLIM_INFINITY and soft > 0:
            deadline = min(deadline, soft - RLIMIT_CPU_MARGIN)
        return deadline

    @staticmethod
    def _rq_resource_exhausted(exc):
        """Estouro de CPU/memória do worker (não é erro do relatório): a
        tentativa já está contada; a próxima volta com fatia menor."""
        if isinstance(exc, MemoryError):
            return True
        if type(exc) is Exception and str(exc) == CPU_LIMIT_MESSAGE:
            return True
        soft, _hard = resource.getrlimit(resource.RLIMIT_CPU)
        if soft == resource.RLIM_INFINITY or soft <= 0:
            return False
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return usage.ru_utime + usage.ru_stime >= soft

    # --------------------------------------------------------------- execução
    def _rq_inline(self):
        return bool(self.env.context.get(INLINE_CTX) or odoo_module.current_test)

    def _rq_commit(self):
        if not self._rq_inline():
            self.env.cr.commit()

    @contextmanager
    def _rq_unit_guard(self):
        if self._rq_inline():
            with self.env.cr.savepoint():
                yield
            return
        try:
            yield
        except Exception:
            # Sem savepoint: o render pode ter dado cr.commit() (commit_assetsbundle).
            # Volta tudo até a reivindicação, que já está commitada.
            self.env.cr.rollback()
            self.env.invalidate_all()
            raise

    def _rq_run_unit(self, cpu_deadline=None):
        """Executa a próxima unidade deste job. True se houve progresso ou desfecho."""
        self.ensure_one()
        job = self.sudo()
        if job.state not in ACTIVE_STATES:
            return False
        max_attempts = job._rq_param(MAX_ATTEMPTS_PARAM, MAX_ATTEMPTS, int, 1)
        if job.attempts >= max_attempts:
            job._rq_fail(_(
                "A etapa \"%(phase)s\" foi interrompida %(n)d vezes seguidas "
                "(provável limite de CPU ou memória do servidor)."
            ) % {"phase": job.phase, "n": job.attempts})
            return True
        # Reivindica e CONTA a tentativa antes do trabalho pesado. Estouro do
        # limite de CPU (o Odoo 16 transforma SIGXCPU em Exception) ou
        # MemoryError chegam ao except abaixo e NÃO falham o job; já o
        # watchdog de tempo real (SIGKILL) e o OOM killer matam o worker sem
        # except nenhum. Nos dois casos a tentativa commitada aqui conta, e
        # a próxima unidade roda com a fatia dividida (Budget retry).
        job.write({"state": "running", "attempts": job.attempts + 1,
                   "last_run_at": fields.Datetime.now()})
        job._rq_commit()
        try:
            with job._rq_unit_guard():
                job._rq_do_unit(cpu_deadline)
        except psycopg2.OperationalError:
            _logger.info("Montagem %s: conflito de concorrência; nova tentativa.", job.id)
            return False
        except Exception as exc:
            if job._rq_resource_exhausted(exc):
                # Rollback já feito pelo guard; sem _rq_fail (o próximo
                # SIGXCPU pode chegar em ~1 s). False: o cron para já.
                _logger.warning(
                    "Montagem %s: limite de CPU/memória do worker na etapa %s "
                    "(tentativa %s); nova tentativa com fatia menor.",
                    job.id, job.phase, job.attempts)
                return False
            _logger.exception("Montagem %s do relatório %s falhou.", job.id,
                              job.relatorio_id.display_name)
            job._rq_fail(_("Erro na etapa \"%(phase)s\": %(err)s") % {
                "phase": job.phase, "err": exc})
        return True

    def _rq_relatorio_env(self):
        """O relatório como o solicitante o vê (acesso, idioma, fuso)."""
        user = self.requested_by
        rel = self.relatorio_id
        company = rel.company_id if rel.company_id in user.company_ids else user.company_id
        ctx = {"lang": user.lang, "tz": user.tz, "allowed_company_ids": company.ids,
               HIDE_CLIENT_CTX: True}
        if self.kind == "emissao":
            ctx.update(rq_emission_token=self.token, rq_emission_date=self.issued_at)
        if self._rq_inline():
            ctx["commit_assetsbundle"] = False  # savepoint não sobrevive a commit
        return rel.with_user(user).with_context(**ctx)

    def _rq_session_store(self):
        return http.root.session_store

    def _rq_save_report_session(self, store, tries=SESSION_SAVE_TRIES):
        """Grava a sessão efêmera e CONFERE o arquivo: o save do
        FilesystemSessionStore engole OSError (rename para o shard `sid[:2]`
        sem permissão de escrita) e o sid ficaria apontando para nada. Um
        sid novo cai noutro shard. None se nenhum save pegou."""
        for _attempt in range(tries):
            session = store.new()
            session.update(http.get_default_session())
            session.db = self.env.cr.dbname
            store.save(session)
            if os.path.isfile(store.get_session_filename(session.sid)):
                return session
        _logger.warning(
            "Montagem %s: sessão efêmera não gravada em %s (permissão dos "
            "subdiretórios?); render sem cookie, o CSS do layout pode faltar.",
            self.id, store.path)
        return None

    @contextmanager
    def _rq_report_session(self, phase):
        """Sessão efêmera (só `db`) para o wkhtmltopdf baixar o CSS do layout.

        Sem request (cron), `_run_wkhtmltopdf` não passa cookie: em
        multi-db sem dbfilter `/web/assets/...` responde 404 e o corpo sai
        sem o CSS dos relatórios (medido no web-1: 404 sem, 200 com). Os
        assets são auth=public, então basta a sessão saber o banco. A URL
        continua sendo `report.url`/`web.base.url`, que precisa ser
        alcançável pelo próprio servidor (e aceita pelo dbfilter).
        """
        if phase not in RENDER_PHASES or request or odoo_module.current_test:
            yield {}
            return
        store = self._rq_session_store()
        session = self._rq_save_report_session(store)
        if session is None:
            yield {}  # render sem cookie (CSS pode faltar em multi-db), mas segue
            return
        jar_path = None
        try:
            # Mesmo formato do core (ir_actions_report._run_wkhtmltopdf).
            domain = urlparse(self.env["ir.actions.report"]._get_report_url()).hostname
            fd, jar_path = tempfile.mkstemp(suffix=".txt", prefix="report.rq_cookie_jar.tmp.")
            with closing(os.fdopen(fd, "wb")) as jar:  # mkstemp: modo 0600
                jar.write(("session_id=%s; HttpOnly; domain=%s; path=/;"
                           % (session.sid, domain)).encode())
            yield {REPORT_COOKIE_JAR_CTX: jar_path}
        finally:
            if jar_path:
                try:
                    os.unlink(jar_path)
                except FileNotFoundError:
                    pass
            store.delete(session)

    def _rq_stale_reason(self):
        """Mensagem se o relatório mudou desde o clique; False se segue válido.

        Na emissão, só invariantes baratos (D4): o gate completo rodou no clique."""
        rel = self.relatorio_id
        if rel.rq_editorial_seq != self.editorial_seq:
            return _("O relatório foi alterado durante a montagem; o PDF foi "
                     "descartado. Gere de novo.")
        if self.kind == "emissao":
            if rel.state != "draft" or rel.revision != self.revision:
                return _("O status ou a revisão do relatório mudou durante a montagem.")
            problems = rel._rq_internal_approval_problems()
            if problems:
                return _("As aprovações internas mudaram durante a montagem: %s") % (
                    "; ".join(problems))
        return False

    def _rq_do_unit(self, cpu_deadline):
        stale = self._rq_stale_reason()
        if stale:
            self._rq_fail(stale)
            return
        st = json.loads(self.stage_json)
        if st["phase"] == "done":
            self._rq_finalize(st)
            return
        rel = self._rq_relatorio_env()
        vals = {}
        budget = Budget(
            max_pages=self._rq_param(CHUNK_PAGES_PARAM, DEFAULT_CHUNK_PAGES, int, 1),
            cpu_deadline=cpu_deadline, retry=self.attempts,
        )
        with self._rq_report_session(st["phase"]) as session_ctx:
            rel = rel.with_context(**session_ctx)
            if st["phase"] == "body" and self.kind == "emissao" and not self.blocks_snapshot:
                vals["blocks_snapshot"] = rel._blocks_snapshot()  # render ANTES de gravar
            rel.env["afr.relatorio.pdf"]._stage_run(rel, st, _AttachmentStore(self), budget)
        # `st` só é persistido depois da unidade inteira (fit/body mexem em
        # avisos e page_cost antes de avançar o cursor).
        vals.update(stage_json=json.dumps(st), phase=st["phase"],
                    progress=stage_progress(st), attempts=0)
        self.write(vals)
        self._rq_commit()

    def _rq_finalize(self, st):
        """Só gravações (nenhum render): minuta ou emissão."""
        attachment = self.env["ir.attachment"].sudo().browse(int(st["final_blob"]))
        rel = self.relatorio_id.sudo().with_context(_internal_ctx(self.env))
        getattr(rel, "_rq_finalize_%s" % self.kind)(self, attachment, st["warnings"])
        self.write({"state": "done", "phase": "done", "progress": 100, "attempts": 0,
                    "result_attachment_id": attachment.id})
        self._rq_cleanup()  # o final já foi re-apontado para o relatório
        self._rq_commit()

    def _rq_fail(self, message):
        """Estado `failed` sempre gravado; limpeza e chatter são best-effort
        (uma falha ali não pode deixar o job ativo e em loop)."""
        self.ensure_one()
        self.write({"state": "failed", "error": message})
        try:
            with self.env.cr.savepoint():
                self._rq_cleanup()
                kind = dict(self._fields["kind"].selection)[self.kind]
                self.relatorio_id.sudo().with_context(_internal_ctx(self.env)).message_post(
                    body=_("Falha na montagem (%(kind)s): %(msg)s") % {
                        "kind": kind, "msg": message},
                    author_id=self.requested_by.partner_id.id,
                )
        except Exception:
            _logger.exception("Montagem %s: falha ao limpar/avisar no chatter.", self.id)
        self._rq_commit()

    def _rq_cancel(self):
        for job in self.sudo().filtered(lambda j: j.state in ACTIVE_STATES):
            job.write({"state": "cancelled", "error": False})
            job._rq_cleanup()
            kind = dict(job._fields["kind"].selection)[job.kind]
            job.relatorio_id.with_context(_internal_ctx(self.env)).message_post(
                body=_("Montagem (%(kind)s) cancelada por %(user)s.") % {
                    "kind": kind, "user": self.env.user.name})

    def _rq_cleanup(self):
        self.env["ir.attachment"].sudo().search([
            ("res_model", "=", self._name), ("res_id", "in", self.ids),
        ]).unlink()

    @api.autovacuum
    def _gc_finished_jobs(self):
        days = self._rq_param(RETENTION_PARAM, JOB_RETENTION_DAYS, int, 1)
        limit = fields.Datetime.now() - timedelta(days=days)
        old = self.sudo().search([("state", "not in", ACTIVE_STATES),
                                  ("write_date", "<", limit)])
        old._rq_cleanup()
        old.unlink()


class IrActionsReportBuildSession(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def _build_wkhtmltopdf_args(self, paperformat_id, landscape,
                                specific_paperformat_args=None, set_viewport_size=False):
        """Sem request, apresenta a sessão efêmera do job (ver
        `_rq_report_session`). Com request o core já passa o cookie da
        sessão do usuário — e o contexto vindo de RPC é ignorado."""
        args = super()._build_wkhtmltopdf_args(
            paperformat_id, landscape,
            specific_paperformat_args=specific_paperformat_args,
            set_viewport_size=set_viewport_size)
        jar = self.env.context.get(REPORT_COOKIE_JAR_CTX)
        if jar and not request:
            args.extend(["--cookie-jar", jar])
        return args


class AfrQualificacaoRelatorioBuild(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    rq_editorial_seq = fields.Integer(string="Versão editorial", readonly=True,
                                      copy=False, default=0)
    build_job_ids = fields.One2many("afr.relatorio.build.job", "relatorio_id",
                                    string="Montagens de PDF", readonly=True)
    # Computados juntos (não `related` num m2o computado não pesquisável, que
    # gerava UserWarning no carregamento do registry). compute_sudo: Técnico e
    # Usuário leem o status sem depender da ACL do job.
    rq_build_job_id = fields.Many2one("afr.relatorio.build.job",
                                      compute="_compute_rq_build_job", compute_sudo=True,
                                      string="Última montagem")
    rq_build_state = fields.Selection(JOB_STATES, compute="_compute_rq_build_job",
                                      compute_sudo=True, string="Montagem")
    rq_build_kind = fields.Selection(JOB_KINDS, compute="_compute_rq_build_job",
                                     compute_sudo=True, string="Tipo de montagem")
    rq_build_progress = fields.Integer(compute="_compute_rq_build_job",
                                       compute_sudo=True, string="Progresso")
    rq_build_error = fields.Text(compute="_compute_rq_build_job",
                                 compute_sudo=True, string="Erro da montagem")

    @api.depends("build_job_ids.state", "build_job_ids.kind",
                 "build_job_ids.progress", "build_job_ids.error")
    def _compute_rq_build_job(self):
        for rel in self:
            job = rel.build_job_ids[:1]  # _order id desc
            rel.rq_build_job_id = job
            rel.rq_build_state = job.state
            rel.rq_build_kind = job.kind
            rel.rq_build_progress = job.progress
            rel.rq_build_error = job.error

    def _rq_bump_editorial_seq(self):
        """+1 na versão editorial (SQL: sem guardas/tracking; o gatilho pode ser
        um Técnico sem write no relatório). Jobs comparam com o valor do clique."""
        if not self.ids:
            return
        self.env.cr.execute(
            "UPDATE afr_qualificacao_relatorio "
            "SET rq_editorial_seq = COALESCE(rq_editorial_seq, 0) + 1 WHERE id IN %s",
            [tuple(self.ids)])
        self.invalidate_recordset(["rq_editorial_seq"])

    def _rq_check_user_group(self, acao):
        if self.env.su or self.env.user.has_group(USER_GROUP):
            return
        raise UserError(_("Apenas usuários do escritório podem %s.") % acao)

    def _rq_enqueued_notification(self, message):
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {
            "title": _("Montagem do PDF enfileirada"), "message": message,
            "type": "info", "sticky": False,
            "next": {"type": "ir.actions.client", "tag": "soft_reload"},
        }}

    def action_gerar_minuta(self):
        """Enfileira a minuta ('MINUTA — SEM VALIDADE'); o resultado sai no chatter."""
        self.ensure_one()
        self._rq_check_user_group(_("gerar a minuta"))
        self.env["afr.relatorio.build.job"]._rq_enqueue(self, "minuta")
        return self._rq_enqueued_notification(_(
            "A minuta está sendo montada em segundo plano. Atualize a página para "
            "acompanhar; o link aparece no histórico ao concluir."))

    def action_baixar_minuta(self):
        self.ensure_one()
        if not self.minuta_attachment_id:
            raise UserError(_("Nenhuma minuta gerada ainda."))
        return {"type": "ir.actions.act_url", "target": "self",
                "url": "/web/content/%d?download=true" % self.minuta_attachment_id.id}

    def action_cancelar_montagem(self):
        self.ensure_one()
        jobs = self.env["afr.relatorio.build.job"]._rq_active_for(self)
        if not jobs:
            raise UserError(_("Não há montagem em andamento para este relatório."))
        if "emissao" in jobs.mapped("kind"):
            self._check_manager_only(_("cancelar a emissão em montagem"))
        else:
            self._rq_check_user_group(_("cancelar a montagem da minuta"))
        jobs._rq_cancel()
        return True

    def _rq_finalize_minuta(self, job, attachment, warnings):
        """Chamado pelo job com sudo + contexto interno; só gravações."""
        self.ensure_one()
        previous = self.minuta_attachment_id
        attachment.with_context(self.env.context).write({
            "res_model": self._name, "res_id": self.id, "public": False,
            "mimetype": "application/pdf",
            "name": "%s-%s-MINUTA.pdf" % (self.name, self.revision_label),
        })
        self.write({"minuta_attachment_id": attachment.id})
        # Só apaga a minuta anterior se ela é DESTE relatório (defesa em
        # profundidade do item 1 da revisão final): um id alheio que tenha
        # chegado ao campo fica onde está.
        if (previous and previous != attachment
                and previous.res_model == self._name and previous.res_id == self.id):
            previous.unlink()
        body = Markup("%s <a href=\"/web/content/%d?download=true\">%s</a>") % (
            _("Minuta gerada."), attachment.id, _("Baixar"))
        if warnings:
            body += Markup("<ul>%s</ul>") % Markup("").join(
                Markup("<li>%s</li>") % w for w in warnings)
        self.message_post(body=body, author_id=job.requested_by.partner_id.id)
