from unittest.mock import patch

import psycopg2

from odoo import fields, http
from odoo.exceptions import UserError
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from odoo.addons.afr_qualificacao.models import relatorio_build_job as jobmod
from odoo.addons.afr_qualificacao.models import relatorio_pdf as rp

from .common import AfrQualificacaoTestCommon
from .relatorio_fakes import (FakeCorpo, RelatorioFixtureMixin, make_user,
                              pdf_pages_text, run_build_jobs, squash)

USER = "afr_qualificacao.group_afr_qualificacao_user"
TECH = "afr_qualificacao.group_afr_qualificacao_technician"


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioBuildJob(RelatorioFixtureMixin, AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.office = make_user(cls.env, "escritorio.rq.job", USER)
        cls.tech = make_user(cls.env, "tecnico.rq.job", TECH)

    def setUp(self):
        super().setUp()
        self.rel, self.qualif = self._make_relatorio()
        self.blocks, self.anexos = self._standard_layout(self.rel)
        self.Job = self.env["afr.relatorio.build.job"]

    def _enqueue_minuta(self):
        return self.rel.with_user(self.office).action_gerar_minuta()

    def _job(self):
        return self.Job.sudo().search([("relatorio_id", "=", self.rel.id)], limit=1)

    def test_cron_record(self):
        cron = self.env.ref(jobmod.CRON_XMLID)
        self.assertTrue(cron.active)
        self.assertEqual(cron.code.strip(), "model._cron_process()")
        self.assertEqual((cron.interval_number, cron.interval_type), (5, "minutes"))

    def test_minuta_is_queued_and_triggers_cron(self):
        calls = []
        Cron = type(self.env["ir.cron"])
        original = Cron._trigger

        def spy(cron_self, at=None):
            calls.append(cron_self.id)
            return original(cron_self, at)

        with patch.object(Cron, "_trigger", spy):
            action = self._enqueue_minuta()
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(calls, [self.env.ref(jobmod.CRON_XMLID).id])
        job = self._job()
        self.assertEqual((job.state, job.kind, job.requested_by), ("queued", "minuta", self.office))
        self.assertFalse(self.rel.minuta_attachment_id)  # nada antes do job rodar

    def test_minuta_job_in_one_page_units_equals_sync_build(self):
        self.env["ir.config_parameter"].sudo().set_param(rp.CHUNK_PAGES_PARAM, "1")
        rel_as_job = self.rel.with_user(self.office).with_context(
            tz=self.office.tz, lang=self.office.lang, rq_hide_client_approval=True)
        with FakeCorpo().patch(self.env):
            expected, exp_w = self.env["afr.relatorio.pdf"]._build(rel_as_job, watermark=True)
            self._enqueue_minuta()
            units = run_build_jobs(self.env)
        job = self._job()
        self.assertEqual(job.state, "done")
        self.assertEqual(job.progress, 100)
        self.assertGreater(units, 10)
        minuta = self.rel.minuta_attachment_id
        self.assertEqual(pdf_pages_text(minuta.raw), pdf_pages_text(expected))
        self.assertFalse(minuta.public)
        self.assertEqual((minuta.res_model, minuta.res_id), (self.rel._name, self.rel.id))
        self.assertIn("MINUTA—SEMVALIDADE", squash("".join(pdf_pages_text(minuta.raw))))
        # intermediários apagados
        self.assertFalse(self.env["ir.attachment"].sudo().search([
            ("res_model", "=", self.Job._name), ("res_id", "=", job.id)]))

    def test_runs_as_requesting_user(self):
        seen = []
        Pdf = type(self.env["afr.relatorio.pdf"])
        original = Pdf._stage_run

        def spy(pdf_self, relatorio, st, store, budget):
            seen.append((relatorio.env.uid, relatorio.env.su,
                         relatorio.env.context.get("rq_hide_client_approval")))
            return original(pdf_self, relatorio, st, store, budget)

        with FakeCorpo().patch(self.env), patch.object(Pdf, "_stage_run", spy):
            self._enqueue_minuta()
            run_build_jobs(self.env)
        self.assertTrue(seen)
        self.assertTrue(all(s == (self.office.id, False, True) for s in seen), seen)

    def test_one_active_job_per_relatorio(self):
        self._enqueue_minuta()
        with self.assertRaises(UserError):
            self._enqueue_minuta()
        with self.assertRaises(psycopg2.IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.Job.sudo().create({"relatorio_id": self.rel.id, "kind": "minuta",
                                        "requested_by": self.office.id, "state": "queued"})

    def test_second_minuta_replaces_previous(self):
        with FakeCorpo().patch(self.env):
            self._enqueue_minuta(); run_build_jobs(self.env)
            first = self.rel.minuta_attachment_id
            self._enqueue_minuta(); run_build_jobs(self.env)
        self.assertFalse(first.exists())
        second = self.rel.minuta_attachment_id
        self.assertIn("/web/content/%d" % second.id,
                      self.rel.with_user(self.office).action_baixar_minuta()["url"])

    def test_editorial_change_during_build_aborts_minuta(self):
        with FakeCorpo().patch(self.env):
            self._enqueue_minuta()
            run_build_jobs(self.env, until=lambda job: job.phase == "stamp")
            self.blocks["objetivo"].write({"body": "<p>mudou</p>"})
            run_build_jobs(self.env)
        job = self._job()
        self.assertEqual(job.state, "failed")
        self.assertIn("alterado durante a montagem", job.error)
        self.assertFalse(self.rel.minuta_attachment_id)
        self.assertIn("alterado durante a montagem", self.rel.message_ids[0].body)

    def test_crash_after_claim_resumes_same_unit(self):
        with FakeCorpo().patch(self.env):
            self._enqueue_minuta()
            run_build_jobs(self.env, until=lambda job: job.phase == "fit")
            job = self._job()
            # Worker morreu depois da reivindicação (commit) e antes do fim.
            job.write({"state": "running", "attempts": 1})
            run_build_jobs(self.env)
        self.assertEqual(job.state, "done")
        self.assertEqual(job.attempts, 0)
        self.assertTrue(self.rel.minuta_attachment_id)

    def test_repeated_crash_fails_job(self):
        self._enqueue_minuta()
        job = self._job()
        job.write({"state": "running", "attempts": jobmod.MAX_ATTEMPTS})
        run_build_jobs(self.env)
        self.assertEqual(job.state, "failed")
        self.assertIn("vezes seguidas", job.error)

    def test_exception_in_unit_fails_and_cleans(self):
        Pdf = type(self.env["afr.relatorio.pdf"])
        original = Pdf._stage_run

        def boom(pdf_self, relatorio, st, store, budget):
            if st["phase"] == "body":
                raise ValueError("boom")
            return original(pdf_self, relatorio, st, store, budget)

        with FakeCorpo().patch(self.env), patch.object(Pdf, "_stage_run", boom), \
                mute_logger("odoo.addons.afr_qualificacao.models.relatorio_build_job"):
            self._enqueue_minuta()
            run_build_jobs(self.env)
        job = self._job()
        self.assertEqual(job.state, "failed")
        self.assertIn("boom", job.error)
        self.assertFalse(self.env["ir.attachment"].sudo().search([
            ("res_model", "=", self.Job._name), ("res_id", "=", job.id)]))

    def test_cancel(self):
        with FakeCorpo().patch(self.env):
            self._enqueue_minuta()
            run_build_jobs(self.env, until=lambda job: job.phase == "body")
            self.rel.with_user(self.office).action_cancelar_montagem()
            self.assertEqual(self._job().state, "cancelled")
            self._enqueue_minuta()  # liberado
        with self.assertRaises(UserError):
            self.rel.with_user(self.tech).action_cancelar_montagem()

    def test_cron_process_retriggers_while_jobs_remain(self):
        calls = []
        Cron = type(self.env["ir.cron"])
        original = Cron._trigger_list

        def spy(cron_self, at_list):
            calls.append(list(at_list))
            return original(cron_self, at_list)

        with FakeCorpo().patch(self.env), patch.object(Cron, "_trigger_list", spy), \
                patch.object(jobmod, "CHAIN_CPU_FRACTION", 0.0):
            self._enqueue_minuta()
            calls.clear()
            self.Job.with_context(rq_build_inline=True)._cron_process()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]), 2)
        self.assertLessEqual(calls[0][0], fields.Datetime.now())

    def test_technician_cannot_enqueue_but_reads_status(self):
        with self.assertRaises(UserError):
            self.rel.with_user(self.tech).action_gerar_minuta()
        self._enqueue_minuta()
        self.assertEqual(self.rel.with_user(self.tech).rq_build_state, "queued")

    def test_editorial_seq_bumps_on_editorial_edits_only(self):
        seq = self.rel.rq_editorial_seq
        self.rel.write({"amb_temperatura": "22 °C"})
        self.blocks["objetivo"].write({"body": "<p>x</p>"})
        self.assertEqual(self.rel.rq_editorial_seq, seq + 2)
        self.rel.message_post(body="nota")
        self.assertEqual(self.rel.rq_editorial_seq, seq + 2)
        with self.assertRaises(UserError):
            self.rel.with_user(self.office).write({"rq_editorial_seq": 0})

    def test_autovacuum_removes_old_finished_jobs(self):
        self._enqueue_minuta()
        job = self._job()
        job.write({"state": "failed"})
        job.flush_recordset()  # senão o flush posterior regrava write_date = agora
        self.env.cr.execute("UPDATE afr_relatorio_build_job SET write_date = now() - interval '40 days' WHERE id = %s", [job.id])
        job.invalidate_recordset()
        self.Job._gc_finished_jobs()
        self.assertFalse(job.exists())

    # --- CSS do layout sem request (cron): sessão efêmera p/ o wkhtmltopdf ---
    def test_wkhtmltopdf_cookie_only_with_job_session_and_no_request(self):
        Report = self.env["ir.actions.report"]
        paperformat = self.env.ref("afr_qualificacao.paperformat_relatorio_final")
        plain = Report._build_wkhtmltopdf_args(paperformat, False)
        self.assertNotIn("--cookie", plain)
        args = Report.with_context(**{jobmod.REPORT_SESSION_CTX: "abc"})._build_wkhtmltopdf_args(
            paperformat, False)
        self.assertEqual(args[-3:], ["--cookie", "session_id", "abc"])
        with patch.object(jobmod, "request", object()):  # RPC: contexto do cliente ignorado
            args = Report.with_context(**{jobmod.REPORT_SESSION_CTX: "abc"})._build_wkhtmltopdf_args(
                paperformat, False)
        self.assertNotIn("--cookie", args)

    def test_report_session_is_ephemeral_and_only_for_render_phases(self):
        self._enqueue_minuta()
        job = self._job()
        store = http.root.session_store
        with patch.object(jobmod.odoo_module, "current_test", False):
            with job._rq_report_session("stamp") as ctx:
                self.assertEqual(ctx, {})
            with job._rq_report_session("body") as ctx:
                sid = ctx[jobmod.REPORT_SESSION_CTX]
                self.assertEqual(store.get(sid).db, self.env.cr.dbname)
                self.assertFalse(store.get(sid).uid)
        self.assertIsNone(store.get(sid).db)  # removida do store
