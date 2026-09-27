"""P4 — emissão, revisão, aprovações, verificação pública e portal do Relatório Final."""
import hashlib
import json
from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from odoo.addons.afr_qualificacao.controllers.relatorio import (
    _portal_aprovacao,
    _portal_page_values,
    _portal_pdf_headers,
    _relatorio_verify_values,
)
from odoo.addons.afr_qualificacao.models import relatorio_pdf as rp

from .common import AfrQualificacaoTestCommon
from .relatorio_fakes import (FakeCorpo, RelatorioFixtureMixin, make_user,
                              pdf_pages_text, run_build_jobs, squash)

MANAGER = "afr_qualificacao.group_afr_qualificacao_manager"
USER = "afr_qualificacao.group_afr_qualificacao_user"
TECH = "afr_qualificacao.group_afr_qualificacao_technician"


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioEmissaoModel(RelatorioFixtureMixin, AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = make_user(cls.env, "gestor.rq.emissao", MANAGER)
        cls.usuario = make_user(cls.env, "usuario.rq.emissao", USER)

    def setUp(self):
        super().setUp()
        self.rel, _q = self._make_relatorio()
        self.att = self._attachment(b"%PDF-1.4 teste", "r.pdf", "application/pdf")

    def _internal_create(self, **vals):
        base = {
            "relatorio_id": self.rel.id, "revision": 0,
            "pdf_attachment_id": self.att.id, "sha256": "0" * 64,
            "token": "a" * 32,
        }
        base.update(vals)
        return self.env["afr.relatorio.emissao"].sudo().with_context(
            rq_emissao_internal=True
        ).create(base)

    def test_create_without_internal_flag_is_blocked(self):
        with self.assertRaises(UserError):
            self.env["afr.relatorio.emissao"].create({
                "relatorio_id": self.rel.id, "token": "b" * 32,
            })
        with self.assertRaises(UserError):
            self.env["afr.relatorio.emissao"].with_user(self.manager).create({
                "relatorio_id": self.rel.id, "token": "c" * 32,
            })

    def test_internal_create_and_supersede(self):
        emissao = self._internal_create()
        self.assertEqual(emissao.name, "%s Rev.00" % self.rel.name)
        emissao.sudo().with_context(rq_emissao_internal=True).write({"superseded": True})
        self.assertTrue(emissao.superseded)

    def test_internal_create_ignores_context_defaults(self):
        """Ruling 5.1: `default_superseded`/`default_token` no contexto não

        podem "vazar" para dentro do registro criado pelo caminho interno —
        o Odoo aplica `context['default_<campo>']` a campos AUSENTES de
        `vals` dentro do próprio `super().create()`, depois do pre-check do
        override (mesmo raciocínio de `relatorio_aprovacao.py::create()`,
        P3). `token` fica de fora de `vals` de propósito, para provar que o
        `default_token` do contexto não o preenche.
        """
        emissao = self.env["afr.relatorio.emissao"].sudo().with_context(
            rq_emissao_internal=True,
            default_superseded=True,
            default_token="z" * 32,
        ).create({
            "relatorio_id": self.rel.id, "revision": 0,
            "pdf_attachment_id": self.att.id, "sha256": "1" * 64,
        })
        self.assertFalse(emissao.superseded)
        self.assertFalse(emissao.token)

    def test_write_is_blocked_even_for_superuser(self):
        emissao = self._internal_create()
        with self.assertRaises(UserError):
            emissao.write({"sha256": "f" * 64})
        with self.assertRaises(UserError):
            emissao.sudo().with_context(rq_emissao_internal=True).write({"sha256": "f" * 64})
        emissao.sudo().with_context(rq_emissao_internal=True).write({"superseded": True})
        with self.assertRaises(UserError):
            emissao.sudo().with_context(rq_emissao_internal=True).write({"superseded": False})
        with self.assertRaises(UserError):
            emissao.with_user(self.manager).write({"superseded": True})

    def test_unlink_is_blocked(self):
        emissao = self._internal_create()
        with self.assertRaises(UserError):
            emissao.unlink()

    def test_verify_url_prefers_context_token_then_current_emissao(self):
        self.assertFalse(self.rel.verify_url)
        url = self.rel.with_context(rq_emission_token="d" * 32).verify_url
        self.assertIn("/qualificacao/relatorio/verify/" + "d" * 32, url)
        emissao = self._internal_create(token="e" * 32)
        self.rel.write({"current_emissao_id": emissao.id})  # env admin (su)
        self.assertIn("/qualificacao/relatorio/verify/" + "e" * 32, self.rel.verify_url)

    def test_internal_fields_not_writable_by_users(self):
        rel_mgr = self.rel.with_user(self.manager)
        for vals in ({"state": "issued"}, {"revision": 3}):
            with self.assertRaises(UserError):
                rel_mgr.write(vals)
        self.rel.write({"revision": 2})  # su pode (migrações, código interno)
        self.assertEqual(self.rel.revision, 2)

    # ─────────────────────────────────────────────────────────────
    # Fix round 1 — create() de afr.qualificacao.relatorio estava aberto:
    # só o write() guardava _RQ_INTERNAL_FIELDS (state, revision,
    # current_emissao_id). Usuário (create=1 na ACL) conseguia nascer o
    # registro já emitido/revisado, sem passar pela ação Emitir/Revisar.
    # ─────────────────────────────────────────────────────────────
    def _give_equip2_qualif_on(self, os_rec):
        """`afr.qualificacao.relatorio` exige que o equipamento já tenha
        qualificação na OS (guard pré-existente, não relacionado a este fix)
        — sem isto, o `create()` falharia por esse motivo, não pelo guard
        de `_RQ_INTERNAL_FIELDS` que este teste quer exercitar."""
        self.env["afr.qualificacao"].create({
            "name": "Qualif equip2 p/ teste do guard de create",
            "equipment_id": self.equip2.id,
            "qualification_type": "installation",
            "company_id": self.company.id,
            "os_id": os_rec.id,
        })

    def test_create_with_internal_fields_is_blocked_for_usuario(self):
        other_rel, _q = self._make_relatorio(equipment=self.equip2)
        emissao = self._internal_create(relatorio_id=other_rel.id, token="f" * 32)
        self._give_equip2_qualif_on(self.rel.os_id)
        with self.assertRaises(UserError):
            self.env["afr.qualificacao.relatorio"].with_user(self.usuario).create({
                "os_id": self.rel.os_id.id,
                "equipment_id": self.equip2.id,
                "state": "issued",
                "revision": 5,
                "current_emissao_id": emissao.id,
            })

    def test_create_with_context_default_state_is_blocked_for_usuario(self):
        """Pós-check: o pré-check só vê o `vals` recebido — `context
        ['default_state']` é aplicado pelo ORM DENTRO do `super().create()`,
        depois do pré-check (mesmo raciocínio de `qualificacao.py`
        Task 13/14). Sem `state` no vals, só o pós-check no registro
        efetivo pega isso."""
        self._give_equip2_qualif_on(self.rel.os_id)
        with self.assertRaises(UserError):
            self.env["afr.qualificacao.relatorio"].with_user(
                self.usuario
            ).with_context(default_state="issued").create({
                "os_id": self.rel.os_id.id,
                "equipment_id": self.equip2.id,
            })

    def test_manager_with_internal_context_but_no_sudo_still_blocked(self):
        """O contexto `rq_emissao_internal` por si só não basta — precisa de
        `env.su`. Gestor sem `sudo()` não passa, mesmo com a flag no
        contexto (a única diferença deste teste em relação a
        `test_create_without_internal_flag_is_blocked` é a presença
        explícita da flag)."""
        with self.assertRaises(UserError):
            self.env["afr.relatorio.emissao"].with_user(
                self.manager
            ).with_context(rq_emissao_internal=True).create({
                "relatorio_id": self.rel.id, "token": "g" * 32,
            })

    def test_action_generate_relatorios_still_works_for_usuario(self):
        """Regressão: o guard novo do create() não pode quebrar o caminho
        legítimo (vals sem nenhum campo de `_RQ_INTERNAL_FIELDS`)."""
        self._give_equip2_qualif_on(self.rel.os_id)
        rels = self.rel.os_id.with_user(self.usuario).action_generate_relatorios()
        novo = rels.filtered(lambda r: r.equipment_id == self.equip2)
        self.assertTrue(novo)
        self.assertEqual(novo.state, "draft")
        self.assertEqual(novo.revision, 0)

    # ─── Task 9 fix round 2, achado 1: âncoras (cliente/empresa/OS/equipamento) ───

    def _foreign_partner(self):
        return self.env["res.partner"].create({
            "name": "Terceiro Teste", "email": "terceiro@example.test"})

    def test_anchor_fields_not_writable_outside_su(self):
        foreign = self._foreign_partner()
        other_company = self.env["res.company"].create({"name": "Empresa Teste 2"})
        partner0, os_partner0 = self.rel.partner_id, self.rel.os_id.partner_id
        other_rel, _q = self._make_relatorio(equipment=self.equip2)
        for user in (self.usuario, self.manager):
            for vals in ({"partner_id": foreign.id}, {"company_id": other_company.id},
                         {"os_id": other_rel.os_id.id}, {"equipment_id": self.equip2.id}):
                with self.assertRaises(UserError, msg=(user.login, vals)):
                    self.rel.with_user(user).write(vals)
        self.assertEqual(self.rel.partner_id, partner0)
        self.assertEqual(self.rel.os_id.partner_id, os_partner0)
        # Regravar o mesmo valor não é troca.
        self.rel.with_user(self.usuario).write({"partner_id": partner0.id})

    def test_create_cannot_set_anchor_partner_or_company(self):
        self._give_equip2_qualif_on(self.rel.os_id)
        foreign = self._foreign_partner()
        Rel = self.env["afr.qualificacao.relatorio"].with_user(self.usuario)
        with self.assertRaises(UserError):
            Rel.create({"os_id": self.rel.os_id.id, "equipment_id": self.equip2.id,
                        "partner_id": foreign.id})
        rel = Rel.with_context(default_partner_id=foreign.id).create(
            {"os_id": self.rel.os_id.id, "equipment_id": self.equip2.id})
        self.assertEqual(rel.partner_id, self.rel.os_id.partner_id)
        self.assertEqual(self.rel.os_id.partner_id, self.partner)

    def test_anchor_constraint_matches_os(self):
        with self.assertRaises(ValidationError):
            self.rel.sudo().write({"partner_id": self._foreign_partner().id})

    def test_current_emissao_must_belong_to_relatorio(self):
        other_rel, _q = self._make_relatorio(equipment=self.equip2)
        other_emissao = self._internal_create(relatorio_id=other_rel.id, token="h" * 32)
        with self.assertRaises(ValidationError):
            self.rel.write({"current_emissao_id": other_emissao.id})


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioAprovacoes(RelatorioFixtureMixin, AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.elab = make_user(cls.env, "elab.rq.aprov", USER)
        cls.emis = make_user(cls.env, "emis.rq.aprov", MANAGER)
        cls.tech = make_user(cls.env, "tec.rq.aprov", TECH)

    def setUp(self):
        super().setUp()
        self.rel, self.qualif = self._make_relatorio()
        self.block = self._block(self.rel, "static", "Objetivo", 10)
        Aprov = self.env["afr.relatorio.aprovacao"]
        self.line_elab = Aprov.create({"relatorio_id": self.rel.id, "papel": "elaborador",
                                       "user_id": self.elab.id, "nome_exibicao": "Eng. Elaborador"})
        self.line_emis = Aprov.create({"relatorio_id": self.rel.id, "papel": "emissor",
                                       "user_id": self.emis.id, "nome_exibicao": "Eng. Responsável"})
        self.line_cli = Aprov.create({"relatorio_id": self.rel.id, "papel": "cliente",
                                      "partner_id": self.partner.id, "nome_exibicao": "Cliente Teste"})

    def _approve_internal(self):
        (self.line_elab | self.line_emis).sudo().write({"approved_at": fields.Datetime.now()})

    def _internal_approved(self):
        return bool(self.line_elab.approved_at or self.line_emis.approved_at)

    def test_aprovar_interno_marks_only_my_lines(self):
        self.rel.with_user(self.elab).action_aprovar_interno()
        self.assertTrue(self.line_elab.approved_at)
        self.assertFalse(self.line_emis.approved_at)

    def test_aprovar_interno_approves_all_my_pending_lines(self):
        """Mesmo usuário designado como elaborador E emissor: uma chamada
        aprova as duas linhas."""
        self.line_emis.write({"user_id": self.elab.id})
        self.rel.with_user(self.elab).action_aprovar_interno()
        self.assertTrue(self.line_elab.approved_at)
        self.assertTrue(self.line_emis.approved_at)
        self.assertEqual(self.rel._check_emission_gate(), [])

    def test_aprovar_interno_ignores_context_defaults(self):
        """Ruling 5.1: a gravação via sudo() usa clean_context — `default_*`
        do contexto do chamador não vaza para a aprovação nem cria linhas."""
        n_lines = len(self.rel.aprovacao_ids)
        self.rel.with_user(self.elab).with_context(
            default_ip="6.6.6.6", default_papel="cliente",
            default_nome_exibicao="Forjado", default_relatorio_id=self.rel.id,
        ).action_aprovar_interno()
        self.assertTrue(self.line_elab.approved_at)
        self.assertNotEqual(self.line_elab.ip, "6.6.6.6")
        self.assertEqual(self.line_elab.nome_exibicao, "Eng. Elaborador")
        self.assertEqual(len(self.rel.aprovacao_ids), n_lines)

    def test_aprovar_interno_requires_designation(self):
        self.rel.with_user(self.emis).action_aprovar_interno()  # 1ª vez: ok
        with self.assertRaises(UserError):
            self.rel.with_user(self.emis).action_aprovar_interno()  # já aprovou
        with self.assertRaises(UserError):
            self.rel.with_user(self.tech).action_aprovar_interno()

    def test_aprovar_interno_refused_outside_draft(self):
        self.rel.write({"state": "issued"})  # su
        with self.assertRaises(UserError):
            self.rel.with_user(self.elab).action_aprovar_interno()
        self.assertFalse(self.line_elab.approved_at)

    def test_cycle_edit_by_technician_invalidates_without_access_error(self):
        # Técnico só escreve ciclo da própria OS (rule_cycle_technician_write_own).
        employee = self.env["hr.employee"].create({"name": "Téc Campo", "user_id": self.tech.id})
        self.rel.os_id.tecnico_default_id = employee
        cycle = self.env["afr.qualificacao.cycle"].create({
            "qualificacao_id": self.qualif.id, "cycle_type_id": self.cycle_cmax.id,
        })
        self._approve_internal()
        cycle.with_user(self.tech).write({"janela_fim": fields.Datetime.now()})
        self.assertFalse(self._internal_approved())

    def test_gate_lists_missing_internal_approvals(self):
        problems = self.rel._check_emission_gate()
        self.assertEqual(len(problems), 2)
        self.assertTrue(any("Elaborador" in p for p in problems))
        self.assertTrue(any("Emissor" in p for p in problems))
        self._approve_internal()
        self.assertEqual(self.rel._check_emission_gate(), [])

    def test_gate_requires_designated_roles(self):
        self.line_emis.unlink()
        problems = self.rel._check_emission_gate()
        self.assertTrue(any("Nenhum emissor" in p for p in problems), problems)

    def test_gate_flags_line_without_user(self):
        self.line_elab.write({"user_id": False})
        problems = self.rel._check_emission_gate()
        self.assertTrue(any("sem usuário designado" in p for p in problems), problems)

    def test_editing_relatorio_field_invalidates_internal_approvals(self):
        self._approve_internal()
        self.rel.write({"amb_temperatura": "22 a 25 °C"})
        self.assertFalse(self._internal_approved())
        self.assertIn("Aprovações internas zeradas", self.rel.message_ids[0].body)

    def test_invalidation_by_usuario_clears_approved_at_and_ip(self):
        """O guard de write do P3 bloqueia approved_at/ip fora de su: a
        invalidação disparada por um Usuário comum precisa passar por sudo."""
        (self.line_elab | self.line_emis).sudo().write({
            "approved_at": fields.Datetime.now(), "ip": "10.0.0.1"})
        self.rel.with_user(self.elab).write({"amb_umidade": "40 %UR"})
        self.assertFalse(self._internal_approved())
        self.assertFalse(self.line_elab.ip or self.line_emis.ip)

    def test_editing_child_models_directly_invalidates(self):
        edits = [
            ("bloco", lambda: self.block.write({"body": "<p>novo texto</p>"})),
            ("anexo", lambda: self._anexo(self.rel, "dados", "Dados", 10)),
            ("checklist", lambda: self.env["afr.relatorio.checklist"].create({
                "relatorio_id": self.rel.id, "grupo": "Instalações elétricas",
                "descricao": "Tomada dedicada", "status": "aprovado", "sequence": 10})),
            ("indicador", lambda: self.env["afr.relatorio.indicador"].create({
                "relatorio_id": self.rel.id, "tipo": "biologico", "marca": "Marca T",
                "lote": "L-01"})),
            ("bloco removido", lambda: self._block(self.rel, "static", "X", 99).unlink()),
        ]
        for label, edit in edits:
            with self.subTest(edit=label):
                self._approve_internal()
                edit()
                self.assertFalse(self._internal_approved(), label)

    def test_non_editorial_write_keeps_approvals(self):
        self._approve_internal()
        att = self._attachment(b"%PDF-1.4", "m.pdf", "application/pdf")
        self.rel.write({"minuta_attachment_id": att.id})
        self.rel.message_post(body="comentário")
        self.assertTrue(self.line_elab.approved_at and self.line_emis.approved_at)

    def test_cycle_window_edit_invalidates_but_other_cycle_fields_do_not(self):
        cycle = self.env["afr.qualificacao.cycle"].create({
            "qualificacao_id": self.qualif.id, "cycle_type_id": self.cycle_cmax.id,
        })
        self._approve_internal()
        cycle.write({"notes": "sem efeito editorial"})
        self.assertTrue(self._internal_approved())
        cycle.write({"janela_inicio": fields.Datetime.now()})
        self.assertFalse(self._internal_approved())

    def test_edit_blocked_outside_draft(self):
        self.rel.write({"state": "issued"})  # su
        with self.assertRaises(UserError):
            self.block.write({"body": "<p>depois de emitido</p>"})
        with self.assertRaises(UserError):
            self.rel.write({"amb_umidade": "41 %UR"})
        with self.assertRaises(UserError):
            self.env["afr.relatorio.checklist"].create({
                "relatorio_id": self.rel.id, "grupo": "G", "descricao": "D",
                "status": "na", "sequence": 1})
        cycle = self.env["afr.qualificacao.cycle"].create({
            "qualificacao_id": self.qualif.id, "cycle_type_id": self.cycle_cmax.id,
        })
        cycle.write({"janela_fim": fields.Datetime.now()})  # ciclo não trava

    def test_users_cannot_forge_approval_fields(self):
        now = fields.Datetime.now()
        with self.assertRaises(UserError):
            self.line_elab.with_user(self.elab).write({"approved_at": now})
        Aprov = self.env["afr.relatorio.aprovacao"].with_user(self.elab)
        with self.assertRaises(UserError):
            Aprov.create({"relatorio_id": self.rel.id, "papel": "cliente",
                          "partner_id": self.partner.id, "approved_at": now})
        with self.assertRaises(UserError):
            Aprov.with_context(default_approved_at=now).create({
                "relatorio_id": self.rel.id, "papel": "emissor", "user_id": self.elab.id})
        # Ruling 1.11/4.4 + P3 final I-3: o guard de P3 vale para todos os
        # papéis — nem o executor nasce aprovado fora de su.
        with self.assertRaises(AccessError):
            Aprov.create({"relatorio_id": self.rel.id, "papel": "executor",
                          "nome_exibicao": "Téc. Campo", "approved_at": now})

    # ───────── Fix round 1 (review Task 7) ─────────

    def test_skip_ctx_ignored_without_su_on_issued_report(self):
        """Achado 1: `rq_skip_editorial_hook` só vale sob env.su — um
        chamador RPC comum não fura a trava do relatório emitido."""
        self.rel.write({"state": "issued"})  # su
        skip = {"rq_skip_editorial_hook": True}
        with self.assertRaises(UserError):
            self.block.with_user(self.elab).with_context(**skip).write(
                {"body": "<p>furando a trava</p>"})
        with self.assertRaises(UserError):
            self.rel.with_user(self.emis).with_context(**skip).write(
                {"amb_umidade": "41 %UR"})
        # sudo + SKIP_CTX (fluxo interno) continua passando.
        self.block.sudo().with_context(**skip).write({"body": "<p>interno</p>"})

    def test_skip_ctx_ignored_without_su_in_draft_still_invalidates(self):
        skip = {"rq_skip_editorial_hook": True}
        self._approve_internal()
        self.block.with_user(self.elab).with_context(**skip).write(
            {"body": "<p>editado</p>"})
        self.assertFalse(self._internal_approved())
        self._approve_internal()
        self.rel.with_user(self.elab).with_context(**skip).write(
            {"amb_temperatura": "20 °C"})
        self.assertFalse(self._internal_approved())

    def test_cycle_creation_does_not_invalidate_unless_window_given(self):
        self._approve_internal()
        Cycle = self.env["afr.qualificacao.cycle"].with_user(self.emis)
        cycle = Cycle.create({
            "qualificacao_id": self.qualif.id, "cycle_type_id": self.cycle_cmax.id,
        })
        self.assertTrue(self._internal_approved())
        cycle.write({"notes": "nada editorial"})
        self.assertTrue(self._internal_approved())
        Cycle.create({
            "qualificacao_id": self.qualif.id, "cycle_type_id": self.cycle_cmax.id,
            "janela_inicio": fields.Datetime.now(),
        })
        self.assertFalse(self._internal_approved())

    def test_usuario_cannot_reassign_emissor_and_self_approve(self):
        """Achado 2: Usuário não se designa emissor para se autoaprovar."""
        with self.assertRaises(AccessError):
            self.line_emis.with_user(self.elab).write({"user_id": self.elab.id})
        self.assertEqual(self.line_emis.user_id, self.emis)
        with self.assertRaises(AccessError):
            self.line_emis.with_user(self.elab).write({"user_id": False})
        # Nem trocando o papel da própria linha de elaborador para emissor.
        with self.assertRaises(AccessError):
            self.line_elab.with_user(self.elab).write({"papel": "emissor"})
        self.rel.with_user(self.elab).action_aprovar_interno()
        self.assertTrue(self.line_elab.approved_at)
        self.assertFalse(self.line_emis.approved_at)
        self.assertTrue(any("Emissor" in p for p in self.rel._check_emission_gate()))

    def test_usuario_cannot_create_emissor_line_with_user(self):
        Aprov = self.env["afr.relatorio.aprovacao"].with_user(self.elab)
        with self.assertRaises(AccessError):
            Aprov.create({"relatorio_id": self.rel.id, "papel": "emissor",
                          "user_id": self.elab.id})
        with self.assertRaises(AccessError):
            Aprov.with_context(default_user_id=self.elab.id).create({
                "relatorio_id": self.rel.id, "papel": "emissor"})
        # Sem usuário (o Gestor designa depois) continua permitido.
        line = Aprov.create({"relatorio_id": self.rel.id, "papel": "emissor"})
        self.assertFalse(line.user_id)

    def test_manager_designates_emissor_and_elaborador_self_assigns(self):
        self.line_emis.with_user(self.emis).write({"user_id": self.elab.id})
        self.assertEqual(self.line_emis.user_id, self.elab)
        Aprov = self.env["afr.relatorio.aprovacao"].with_user(self.emis)
        Aprov.create({"relatorio_id": self.rel.id, "papel": "emissor",
                      "user_id": self.emis.id})
        self.line_elab.write({"user_id": False})
        self.line_elab.with_user(self.elab).write({"user_id": self.elab.id})
        self.assertEqual(self.line_elab.user_id, self.elab)
        self.env["afr.relatorio.aprovacao"].with_user(self.elab).create({
            "relatorio_id": self.rel.id, "papel": "elaborador",
            "user_id": self.elab.id})


class RelatorioEmissaoBase(RelatorioFixtureMixin, AfrQualificacaoTestCommon):
    """Relatório pronto para emitir: layout padrão + elaborador/emissor = gestor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = make_user(cls.env, "gestor.rq.flow", MANAGER)
        cls.office = make_user(cls.env, "escritorio.rq.flow", USER)
        cls.tech = make_user(cls.env, "tecnico.rq.flow", TECH)
        cls.partner.email = "cliente@example.test"

    def setUp(self):
        super().setUp()
        self.rel, self.qualif = self._make_relatorio()
        self.blocks, self.anexos = self._standard_layout(self.rel)
        Aprov = self.env["afr.relatorio.aprovacao"]
        self.line_elab = Aprov.create({"relatorio_id": self.rel.id, "papel": "elaborador",
                                       "user_id": self.manager.id, "nome_exibicao": "Eng. Elaborador"})
        self.line_emis = Aprov.create({"relatorio_id": self.rel.id, "papel": "emissor",
                                       "user_id": self.manager.id, "nome_exibicao": "Eng. Responsável"})
        self.line_cli = Aprov.create({"relatorio_id": self.rel.id, "papel": "cliente",
                                      "partner_id": self.partner.id, "nome_exibicao": "Cliente Teste"})

    def _approve(self):
        self.rel.with_user(self.manager).action_aprovar_interno()

    def _emit(self, user=None, fake=None, rel=None):
        fake = fake or FakeCorpo()
        with fake.patch(self.env):
            result = (rel or self.rel).with_user(user or self.manager).action_emitir()
            run_build_jobs(self.env)
        return result

    def _approve_and_emit(self):
        self._approve()
        self._emit()
        return self.rel.current_emissao_id

    def _revise_and_emit(self):
        self.rel.with_user(self.manager).action_revisar()
        return self._approve_and_emit()


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioEmissaoFlow(RelatorioEmissaoBase):

    def test_aprovar_interno_approves_all_my_lines_in_one_call(self):
        self._approve()
        self.assertTrue(self.line_elab.approved_at and self.line_emis.approved_at)

    def test_emitir_blocked_by_gate_lists_problems(self):
        with self.assertRaises(UserError) as ctx:
            self._emit()
        self.assertIn("Não é possível emitir", str(ctx.exception))
        self.assertIn("Elaborador", str(ctx.exception))
        self.assertEqual(self.rel.state, "draft")
        self.assertFalse(self.rel.emissao_ids)

    def test_emitir_requires_manager(self):
        self._approve()
        with self.assertRaises(UserError):
            self._emit(user=self.office)
        self.assertEqual(self.rel.state, "draft")

    def test_emitir_creates_emission_with_hash_of_attachment_bytes(self):
        emissao = self._approve_and_emit()
        self.assertEqual(self.rel.state, "issued")
        self.assertEqual(emissao.revision, 0)
        self.assertEqual(emissao.issued_by, self.manager)
        self.assertEqual(len(emissao.token), 32)
        self.assertEqual(emissao.sha256, hashlib.sha256(emissao.pdf_attachment_id.raw).hexdigest())
        self.assertEqual(emissao.pdf_attachment_id.mimetype, "application/pdf")
        self.assertEqual(json.loads(emissao.scan_snapshot), [])
        snapshot = json.loads(emissao.blocks_snapshot)
        self.assertIn(str(self.blocks["objetivo"].id), snapshot)
        self.assertIn("__corpo__", snapshot)
        message = self.rel.message_ids.filtered(lambda m: m.attachment_ids)[:1]
        self.assertEqual(message.attachment_ids, emissao.pdf_attachment_id)

    def test_emitted_pdf_has_qr_for_new_token_and_no_watermark(self):
        seen = []
        Pdf = type(self.env["afr.relatorio.pdf"])
        original = Pdf._stamp

        def spy(pdf_self, content, header, watermark):
            seen.append(dict(header, watermark=watermark))
            return original(pdf_self, content, header, watermark)

        with patch.object(Pdf, "_stamp", spy):
            emissao = self._approve_and_emit()
        self.assertIn(emissao.token, seen[0]["verify_url"])
        self.assertFalse(seen[0]["watermark"])
        self.assertNotEqual(seen[0]["date"], "MINUTA")
        text = squash("".join(pdf_pages_text(emissao.pdf_attachment_id.raw)))
        self.assertNotIn("SEMVALIDADE", text)

    def test_emitir_twice_is_blocked(self):
        self._approve_and_emit()
        with self.assertRaises(UserError):
            self._emit()

    def test_revision_flow_supersedes_only_on_new_emission(self):
        e0 = self._approve_and_emit()
        self.rel.with_user(self.manager).action_revisar()
        self.assertEqual(self.rel.state, "draft")
        self.assertEqual(self.rel.revision, 1)
        self.assertEqual(self.rel.revision_label, "Rev.01")
        self.assertFalse(self.line_elab.approved_at or self.line_emis.approved_at)
        self.assertFalse(e0.superseded)
        self.assertEqual(self.rel.current_emissao_id, e0)
        e1 = self._approve_and_emit()
        self.assertEqual(e1.revision, 1)
        self.assertTrue(e0.superseded)
        self.assertFalse(e1.superseded)
        self.assertEqual(self.rel.current_emissao_id, e1)
        self.assertNotEqual(e0.token, e1.token)

    def test_revisar_only_from_issued_and_by_manager(self):
        with self.assertRaises(UserError):
            self.rel.with_user(self.manager).action_revisar()  # rascunho
        self._approve_and_emit()
        with self.assertRaises(UserError):
            self.rel.with_user(self.office).action_revisar()

    def test_client_approvals_reset_on_new_emission(self):
        self._approve_and_emit()
        token_rev0 = self.line_cli.access_token
        self.line_cli.sudo().write({"approved_at": fields.Datetime.now(), "ip": "203.0.113.9"})
        self._revise_and_emit()
        self.assertFalse(self.line_cli.approved_at)
        self.assertFalse(self.line_cli.ip)
        self.assertNotEqual(self.line_cli.access_token, token_rev0)

    def test_proxima_qualificacao_follows_emission_date(self):
        self.rel.write({"data_fim_ensaios": date(2026, 7, 1)})
        self.assertEqual(self.rel.proxima_qualificacao, date(2027, 7, 1))
        emissao = self._approve_and_emit()
        issued_local = fields.Datetime.context_timestamp(self.rel, emissao.issued_at).date()
        self.assertEqual(self.rel.proxima_qualificacao, issued_local + relativedelta(months=12))

    def test_minuta_forbidden_for_technician(self):
        with self.assertRaises(UserError):
            self.rel.with_user(self.tech).action_gerar_minuta()

    # ───────── Emissão enfileirada (emenda P4, Task 8 revisado) ─────────

    def test_emitir_enqueues_and_writes_nothing_until_finalize(self):
        self._approve()
        self.line_cli.sudo().write({"approved_at": fields.Datetime.now()})
        action = self.rel.with_user(self.manager).action_emitir()
        self.assertEqual(action["tag"], "display_notification")
        job = self.env["afr.relatorio.build.job"].sudo().search(
            [("relatorio_id", "=", self.rel.id)])
        self.assertEqual((job.kind, job.state), ("emissao", "queued"))
        self.assertEqual(len(job.token), 32)
        self.assertEqual(job.scan_snapshot, "[]")
        self.assertEqual(self.rel.state, "draft")
        self.assertFalse(self.rel.emissao_ids)
        self.assertTrue(self.line_cli.approved_at)  # reset só no finalize (D3)

    def test_gate_failure_creates_no_job(self):
        with self.assertRaises(UserError):
            self._emit()
        self.assertFalse(self.env["afr.relatorio.build.job"].sudo().search(
            [("relatorio_id", "=", self.rel.id)]))

    def test_emission_uses_click_token_and_date(self):
        self._approve()
        with FakeCorpo().patch(self.env):
            self.rel.with_user(self.manager).action_emitir()
            job = self.env["afr.relatorio.build.job"].sudo().search(
                [("relatorio_id", "=", self.rel.id)])
            token, issued_at = job.token, job.issued_at
            run_build_jobs(self.env)
        emissao = self.rel.current_emissao_id
        self.assertEqual((emissao.token, emissao.issued_at), (token, issued_at))
        self.assertEqual(job.emissao_id, emissao)
        self.assertFalse(emissao.pdf_attachment_id.public)

    def test_default_context_is_not_injected(self):  # ruling 5.1
        self._approve()
        self._emit(rel=self.rel.with_context(default_public=True, default_superseded=True,
                                            default_state="issued"))
        e = self.rel.current_emissao_id
        self.assertFalse(e.superseded)
        self.assertFalse(e.pdf_attachment_id.public)

    def test_emission_in_one_page_units_equals_sync_build(self):
        self.env["ir.config_parameter"].sudo().set_param(rp.CHUNK_PAGES_PARAM, "1")
        self._approve()
        with FakeCorpo().patch(self.env):
            self.rel.with_user(self.manager).action_emitir()
            job = self.env["afr.relatorio.build.job"].sudo().search(
                [("relatorio_id", "=", self.rel.id)])
            rel_ctx = self.rel.with_user(self.manager).with_context(
                tz=self.manager.tz, lang=self.manager.lang, rq_hide_client_approval=True,
                rq_emission_token=job.token, rq_emission_date=job.issued_at)
            expected = self.env["afr.relatorio.pdf"].build(rel_ctx, watermark=False)
            run_build_jobs(self.env)
        self.assertEqual(pdf_pages_text(self.rel.current_emissao_id.pdf_attachment_id.raw),
                         pdf_pages_text(expected))

    def test_emission_job_locks_editorial_edits_and_cancel_unlocks(self):
        self._approve()
        self.rel.with_user(self.manager).action_emitir()
        with self.assertRaises(UserError) as ctx:
            self.blocks["objetivo"].write({"body": "<p>durante</p>"})
        self.assertIn("emissão em montagem", str(ctx.exception))
        self.rel.with_user(self.manager).action_cancelar_montagem()
        self.blocks["objetivo"].write({"body": "<p>depois</p>"})  # liberado

    def test_change_during_emission_aborts_and_keeps_previous_client_approval(self):
        e0 = self._approve_and_emit()
        self.line_cli.sudo().write({"approved_at": fields.Datetime.now()})
        self.rel.with_user(self.manager).action_revisar()
        self._approve()
        cycle = self.env["afr.qualificacao.cycle"].create({
            "qualificacao_id": self.qualif.id, "cycle_type_id": self.cycle_cmax.id})
        with FakeCorpo().patch(self.env):
            self.rel.with_user(self.manager).action_emitir()
            run_build_jobs(self.env, until=lambda job: job.phase == "stamp")
            cycle.write({"janela_inicio": fields.Datetime.now()})  # não trava; incrementa o seq
            run_build_jobs(self.env)
        job = self.rel.build_job_ids[:1]
        self.assertEqual(job.state, "failed")
        self.assertEqual(self.rel.state, "draft")
        self.assertEqual(self.rel.current_emissao_id, e0)
        self.assertFalse(e0.superseded)
        self.assertTrue(self.line_cli.approved_at)  # nota 86: reset não persistiu

    def test_emission_pdf_hides_previous_client_approval(self):
        self._approve_and_emit()
        self.line_cli.sudo().write({"approved_at": fields.Datetime.now()})
        rows = self.rel.with_context(rq_hide_client_approval=True)._report_signature_rows()
        cli = [r for r in rows if r["nome"] == "Cliente Teste"]
        self.assertEqual(cli[0]["approved_at"], "")
        self.assertTrue([r for r in self.rel._report_signature_rows()
                         if r["nome"] == "Cliente Teste"][0]["approved_at"])
        self.rel.with_user(self.manager).action_revisar()
        fake = FakeCorpo()
        self._approve()
        self._emit(fake=fake)
        self.assertTrue(fake.calls)
        self.assertTrue(all(c["context"].get("rq_hide_client_approval") for c in fake.calls))


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioPublicoPortal(RelatorioEmissaoBase):

    def test_verify_not_found(self):
        self.assertEqual(_relatorio_verify_values(self.env, "curto")["status"], "not_found")
        self.assertEqual(_relatorio_verify_values(self.env, "f" * 32)["status"], "not_found")
        self.assertEqual(_relatorio_verify_values(self.env, None)["status"], "not_found")

    def test_verify_valid_then_superseded_only_after_new_emission(self):
        e0 = self._approve_and_emit()
        values = _relatorio_verify_values(self.env, e0.token)
        self.assertEqual(values["status"], "valid")
        self.assertEqual(values["emissao"], e0)
        self.assertFalse(values["under_revision"])
        self.rel.with_user(self.manager).action_revisar()
        values = _relatorio_verify_values(self.env, e0.token)
        self.assertEqual(values["status"], "valid")
        self.assertTrue(values["under_revision"])
        e1 = self._approve_and_emit()
        self.assertEqual(_relatorio_verify_values(self.env, e0.token)["status"], "superseded")
        self.assertEqual(_relatorio_verify_values(self.env, e0.token)["current"], e1)
        self.assertEqual(_relatorio_verify_values(self.env, e1.token)["status"], "valid")

    def test_verify_detects_tampered_stored_pdf(self):
        e0 = self._approve_and_emit()
        e0.pdf_attachment_id.sudo().write({"raw": b"%PDF-1.4 outro conteudo"})
        self.assertEqual(_relatorio_verify_values(self.env, e0.token)["status"], "tampered")

    def test_verify_works_for_public_user_env(self):
        e0 = self._approve_and_emit()
        pub = self.env(user=self.env.ref("base.public_user"))
        values = _relatorio_verify_values(pub, e0.token)
        self.assertEqual(values["status"], "valid")
        self.assertEqual(values["emissao"].id, e0.id)

    def test_portal_token_check(self):
        self._approve_and_emit()
        token = self.line_cli.access_token
        self.assertEqual(_portal_aprovacao(self.env, self.line_cli.id, token), self.line_cli)
        self.assertIsNone(_portal_aprovacao(self.env, self.line_cli.id, "errado"))
        self.assertIsNone(_portal_aprovacao(self.env, self.line_cli.id, None))
        self.assertIsNone(_portal_aprovacao(self.env, self.line_cli.id, [token]))
        self.assertIsNone(_portal_aprovacao(self.env, self.line_elab.id, token))
        self.assertIsNone(_portal_aprovacao(self.env, 999999999, token))
        self.assertIsNone(_portal_aprovacao(self.env, 2 ** 40, token))

    def test_portal_approve_records_data_and_moves_state(self):
        emissao = self._approve_and_emit()
        self.assertTrue(self.line_cli._portal_approve("Cliente Teste Aprovador", "203.0.113.5"))
        self.assertTrue(self.line_cli.approved_at)
        self.assertEqual(self.line_cli.ip, "203.0.113.5")
        self.assertEqual(self.line_cli.nome_exibicao, "Cliente Teste Aprovador")
        self.assertEqual(self.rel.state, "client_approved")
        self.assertFalse(self.line_cli._portal_approve("De novo", "203.0.113.6"))
        # Aprovação do cliente não altera o PDF: hash preservado.
        self.assertEqual(emissao.sha256,
                         hashlib.sha256(emissao.pdf_attachment_id.raw).hexdigest())
        values = _relatorio_verify_values(self.env, emissao.token)
        self.assertEqual(values["client_approvals"], self.line_cli)

    def test_portal_approve_through_public_user_env(self):
        """Caminho real do controller: env do usuário público + registro sudo."""
        self._approve_and_emit()
        pub = self.env(user=self.env.ref("base.public_user"))
        line = _portal_aprovacao(pub, self.line_cli.id, self.line_cli.access_token)
        self.assertTrue(line._portal_approve("Cliente Teste", "203.0.113.5"))
        self.assertTrue(self.line_cli.approved_at)
        self.assertEqual(self.rel.state, "client_approved")
        msg = self.rel.message_ids.filtered(lambda m: "pelo portal" in (m.body or ""))
        self.assertTrue(msg)
        self.assertEqual(msg[0].author_id, self.partner)

    def test_portal_approve_ignores_context_defaults(self):
        self._approve_and_emit()
        line = self.line_cli.with_context(
            default_state="draft", default_approved_at=False, default_model="res.partner",
            default_res_id=self.partner.id,
        )
        self.assertTrue(line._portal_approve("Cliente Teste", "203.0.113.5"))
        self.assertEqual(self.rel.state, "client_approved")
        self.assertFalse(self.env["mail.message"].search([
            ("model", "=", "res.partner"), ("res_id", "=", self.partner.id),
            ("body", "ilike", "pelo portal"),
        ]))

    def test_portal_approve_waits_for_every_client_approver(self):
        second = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": self.rel.id, "papel": "cliente",
            "partner_id": self.partner.id, "nome_exibicao": "Cliente Teste 2",
        })
        self._approve_and_emit()
        self.line_cli._portal_approve("Cliente Teste", "203.0.113.5")
        self.assertEqual(self.rel.state, "issued")
        second._portal_approve("Cliente Teste 2", "203.0.113.7")
        self.assertEqual(self.rel.state, "client_approved")

    def test_portal_approve_refused_before_emission(self):
        with self.assertRaises(UserError):
            self.line_cli._portal_approve("Cliente Teste", "203.0.113.5")
        self.assertFalse(self.line_cli.approved_at)

    def test_portal_approve_refused_while_under_revision(self):
        self._approve_and_emit()
        self.rel.with_user(self.manager).action_revisar()
        with self.assertRaises(UserError):
            self.line_cli._portal_approve("Cliente Teste", "203.0.113.5")
        self.assertFalse(self.line_cli.approved_at)
        self.assertEqual(self.rel.state, "draft")

    def test_portal_approve_refused_for_non_client_line(self):
        self._approve_and_emit()
        with self.assertRaises(UserError):
            self.line_elab._portal_approve("Eng. Elaborador", "203.0.113.5")

    def test_portal_url_manager_only(self):
        self._approve_and_emit()
        url = self.line_cli.with_user(self.manager).portal_url
        self.assertIn("/my/relatorio/%d?access_token=%s" % (
            self.line_cli.id, self.line_cli.access_token), url)
        self.assertFalse(self.line_elab.with_user(self.manager).portal_url)
        with self.assertRaises(AccessError):
            self.line_cli.with_user(self.office).read(["portal_url"])

    def test_send_to_client_creates_mail_with_portal_link(self):
        self._approve_and_emit()
        self.rel.with_user(self.manager).action_enviar_aprovacao_cliente()
        mail = self.env["mail.mail"].search([
            ("model", "=", "afr.relatorio.aprovacao"), ("res_id", "=", self.line_cli.id),
        ], limit=1)
        self.assertTrue(mail)
        self.assertIn("/my/relatorio/%d?access_token=%s" % (
            self.line_cli.id, self.line_cli.access_token), mail.body_html)
        # Fix round 4 (R3): destinatário é o contato da linha (recipient_ids).
        self.assertEqual(mail.recipient_ids, self.partner)

    def test_send_to_client_ignores_context_defaults(self):
        self._approve_and_emit()
        self.rel.with_user(self.manager).with_context(
            default_model="res.partner", default_res_id=self.partner.id,
            default_state="exception",
        ).action_enviar_aprovacao_cliente()
        mail = self.env["mail.mail"].search([
            ("model", "=", "afr.relatorio.aprovacao"), ("res_id", "=", self.line_cli.id),
        ], limit=1)
        self.assertTrue(mail)
        self.assertEqual(mail.state, "outgoing")
        self.assertFalse(self.env["mail.mail"].search([
            ("model", "=", "res.partner"), ("res_id", "=", self.partner.id),
        ]))

    def test_send_to_client_only_when_issued(self):
        with self.assertRaises(UserError):
            self.rel.with_user(self.manager).action_enviar_aprovacao_cliente()

    def test_send_to_client_forbidden_for_usuario(self):  # fix round 3
        """O e-mail entrega o token do cliente: só o Gestor envia (check no
        método, não só no botão) — mesmo com o relatório emitido e o contato
        válido, um Usuário via RPC é barrado e nenhum e-mail sai."""
        self._approve_and_emit()
        with self.assertRaises(UserError):
            self.rel.with_user(self.office).action_enviar_aprovacao_cliente()
        self.assertFalse(self.env["mail.mail"].search([
            ("model", "=", "afr.relatorio.aprovacao"), ("res_id", "=", self.line_cli.id),
        ]))

    def test_send_to_client_forbidden_for_technician(self):
        self._approve_and_emit()
        with self.assertRaises(UserError):
            self.rel.with_user(self.tech).action_enviar_aprovacao_cliente()

    def test_public_templates_exist(self):
        self.assertTrue(self.env.ref("afr_qualificacao.relatorio_verify_template"))
        self.assertTrue(self.env.ref("afr_qualificacao.portal_relatorio_aprovacao"))
        self.assertTrue(self.env.ref("afr_qualificacao.mail_body_relatorio_aprovacao"))

    # ─────────── Fix round 1 (review do Task 9) ───────────

    def _contact(self, name="Contato Cliente Teste", parent=None, email=None):
        return self.env["res.partner"].create({
            "name": name, "parent_id": (parent or self.partner).id if parent is not False else False,
            "email": email or "contato@example.test",
        })

    def test_partner_change_rotates_client_token(self):  # achado 1a
        self._approve_and_emit()
        old = self.line_cli.access_token
        contato = self._contact()
        self.line_cli.with_user(self.office).write({"partner_id": contato.id})
        self.assertTrue(self.line_cli.access_token)
        self.assertNotEqual(self.line_cli.access_token, old)
        self.assertIsNone(_portal_aprovacao(self.env, self.line_cli.id, old))
        self.assertEqual(
            _portal_aprovacao(self.env, self.line_cli.id, self.line_cli.access_token),
            self.line_cli)

    def test_partner_change_clears_client_approval(self):  # achado 1a
        self._approve_and_emit()
        self.line_cli._portal_approve("Cliente Teste", "203.0.113.5")
        self.line_cli.sudo().write({"partner_id": self._contact().id})
        self.assertFalse(self.line_cli.approved_at)
        self.assertFalse(self.line_cli.ip)

    def test_same_partner_write_keeps_token(self):  # achado 1a
        old = self.line_cli.access_token
        self.line_cli.with_user(self.office).write({"partner_id": self.partner.id})
        self.assertEqual(self.line_cli.access_token, old)

    def test_line_turned_cliente_gets_token(self):  # achado 1a
        line = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": self.rel.id, "papel": "elaborador", "nome_exibicao": "Outro",
        })
        self.assertFalse(line.access_token)
        line.with_user(self.office).write({"papel": "cliente", "partner_id": self.partner.id})
        self.assertTrue(line.access_token)
        line.with_user(self.office).write({"papel": "elaborador"})
        self.assertFalse(line.access_token)

    def test_client_line_without_token_gets_one_on_write(self):  # achado 1a
        self.line_cli.sudo().write({"access_token": False})
        self.line_cli.with_user(self.office).write({"nome_exibicao": "Cliente Teste B"})
        self.assertTrue(self.line_cli.access_token)

    def test_usuario_cannot_point_client_line_to_foreign_partner(self):  # achado 1b
        estranho = self._contact("Terceiro Teste", parent=False, email="terceiro@example.test")
        with self.assertRaises(ValidationError):
            self.line_cli.with_user(self.office).write({"partner_id": estranho.id})
        with self.assertRaises(ValidationError):
            self.env["afr.relatorio.aprovacao"].with_user(self.office).create({
                "relatorio_id": self.rel.id, "papel": "cliente", "partner_id": estranho.id,
            })
        line = self.env["afr.relatorio.aprovacao"].create({
            "relatorio_id": self.rel.id, "papel": "elaborador", "partner_id": estranho.id,
        })
        with self.assertRaises(ValidationError):
            line.with_user(self.office).write({"papel": "cliente"})
        # Contato do cliente do relatório e o próprio cliente: permitidos.
        contato = self._contact()
        self.env["afr.relatorio.aprovacao"].with_user(self.office).create({
            "relatorio_id": self.rel.id, "papel": "cliente", "partner_id": contato.id,
        })
        # Fluxo interno (su) não é barrado.
        self.line_cli.sudo().write({"partner_id": estranho.id})

    def test_portal_approve_locks_report_row(self):  # achado 2
        self._approve_and_emit()
        Rel = type(self.rel)
        calls = []
        orig = Rel._rq_lock_for_update

        def spy(recs):
            calls.append((recs.ids, bool(self.line_cli.sudo().approved_at)))
            return orig(recs)

        with patch.object(Rel, "_rq_lock_for_update", spy):
            self.line_cli._portal_approve("Cliente Teste", "203.0.113.5")
        self.assertIn((self.rel.ids, False), calls)

    def test_lock_for_update_issues_row_lock(self):  # achado 2
        queries = []
        cr = self.env.cr
        orig = cr.execute

        def spy(query, params=None, log_exceptions=True):
            queries.append(str(query))
            return orig(query, params, log_exceptions)

        with patch.object(cr, "execute", spy):
            self.rel._rq_lock_for_update()
        # UPDATE (trava + versão nova da linha) — ver _rq_lock_for_update.
        self.assertTrue(any(q.startswith("UPDATE afr_qualificacao_relatorio") for q in queries))

    def test_portal_pdf_is_inline(self):  # achado 3
        emissao = self._approve_and_emit()
        headers = dict(_portal_pdf_headers(emissao.pdf_attachment_id))
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertTrue(headers["Content-Disposition"].startswith("inline"))

    def _render(self, xmlid, values, env=None):
        html = (env or self.env)["ir.qweb"]._render(xmlid, values)
        return str(html)

    def test_render_verify_valid_uses_company_tz(self):  # achados 4 e 5
        emissao = self._approve_and_emit()
        self.rel.company_id.partner_id.tz = False
        self.line_cli._portal_approve("Cliente Teste", "203.0.113.5")
        env_tokyo = self.env(context=dict(self.env.context, tz="Asia/Tokyo"))
        values = _relatorio_verify_values(env_tokyo, emissao.token)
        self.assertEqual(values["tz"], "America/Sao_Paulo")
        html = self._render("afr_qualificacao.relatorio_verify_content", values, env_tokyo)
        self.assertIn("Relatório válido", html)
        self.assertIn(emissao.sha256, html)
        self.assertIn(self.rel.company_id.name, html)
        self.assertIn("Cliente Teste", html)  # aprovação do cliente
        self.assertNotIn(self.rel.equipment_id.display_name, html)
        local = fields.Datetime.context_timestamp(
            self.rel.with_context(tz="America/Sao_Paulo"), emissao.issued_at)
        self.assertIn(local.strftime("%H:%M"), html)

    def test_render_verify_superseded_and_not_found(self):  # achado 5
        e0 = self._approve_and_emit()
        e1 = self._revise_and_emit()
        html = self._render("afr_qualificacao.relatorio_verify_content",
                            _relatorio_verify_values(self.env, e0.token))
        self.assertIn("Revisão substituída", html)
        self.assertIn(e1.name, html)
        html = self._render("afr_qualificacao.relatorio_verify_content",
                            _relatorio_verify_values(self.env, "f" * 32))
        self.assertIn("Relatório não encontrado", html)
        e1.pdf_attachment_id.sudo().write({"raw": b"%PDF-1.4 outro"})
        html = self._render("afr_qualificacao.relatorio_verify_content",
                            _relatorio_verify_values(self.env, e1.token))
        self.assertIn("Arquivo divergente", html)

    def test_render_portal_page(self):  # achados 4 e 5
        emissao = self._approve_and_emit()
        self.rel.company_id.partner_id.tz = False
        token = self.line_cli.access_token
        line = _portal_aprovacao(self.env, self.line_cli.id, token)
        values = dict(_portal_page_values(line, token, None), csrf_token="csrf-teste")
        self.assertEqual(values["tz"], "America/Sao_Paulo")
        html = self._render("afr_qualificacao.portal_relatorio_aprovacao_content", values)
        self.assertIn("/my/relatorio/%d/aprovar" % line.id, html)
        self.assertIn("/my/relatorio/%d/pdf?access_token=%s" % (line.id, token), html)
        self.assertIn(emissao.sha256, html)
        self.assertIn("csrf-teste", html)
        line._portal_approve("Cliente Teste", "203.0.113.5")
        html = self._render("afr_qualificacao.portal_relatorio_aprovacao_content",
                            dict(_portal_page_values(line, token, "ok"), csrf_token="x"))
        self.assertIn("Aprovação registrada", html)
        self.assertIn("Aprovado por", html)
        self.assertNotIn("/aprovar", html)
        self.assertEqual(_portal_page_values(line, token, "<script>")["message"], None)

    def test_client_partner_change_after_client_approved_reverts_to_issued(self):
        self._approve_and_emit()
        self.line_cli._portal_approve("Cliente Teste", "203.0.113.5")
        self.assertEqual(self.rel.state, "client_approved")
        old = self.line_cli.access_token
        self.line_cli.with_user(self.office).write({"partner_id": self._contact().id})
        self.assertFalse(self.line_cli.approved_at)
        self.assertNotEqual(self.line_cli.access_token, old)
        self.assertEqual(self.rel.state, "issued")

    # ─── Fix round 2, achados 2 e 3 ───

    def test_approval_line_cannot_move_between_reports(self):
        self._approve_and_emit()
        other_rel, _q = self._make_relatorio(equipment=self.equip2)
        for line in (self.line_cli, self.line_elab):
            with self.assertRaises(AccessError):
                line.with_user(self.office).write({"relatorio_id": other_rel.id})
            with self.assertRaises(AccessError):
                line.with_user(self.manager).write({"relatorio_id": other_rel.id})
        self.assertEqual(self.line_cli.relatorio_id, self.rel)
        self.line_elab.sudo().write({"relatorio_id": self.rel.id})  # mesmo valor / su

    def test_default_papel_cliente_gets_token(self):
        Aprov = self.env["afr.relatorio.aprovacao"]
        for env_aprov in (Aprov.with_user(self.office), Aprov.sudo()):
            line = env_aprov.with_context(default_papel="cliente").create({
                "relatorio_id": self.rel.id, "partner_id": self.partner.id})
            self.assertEqual(line.papel, "cliente")
            self.assertTrue(line.sudo().access_token)

    # ─── Fix round 3: nenhum caminho entrega o token a não-Gestor ───

    TPL = "afr_qualificacao.mail_template_relatorio_aprovacao"  # legado (removido)

    def test_non_manager_cannot_search_or_group_by_token(self):
        token = self.line_cli.access_token
        Aprov = self.env["afr.relatorio.aprovacao"].with_user(self.office)
        for domain in ([("access_token", "=", token)],
                       [("access_token", "=like", token[:1] + "%")],
                       ["|", ("id", "=", 0), ("access_token", "!=", False)]):
            with self.assertRaises(AccessError, msg=domain):
                Aprov.search_count(domain)
        with self.assertRaises(AccessError):
            self.env["afr.qualificacao.relatorio"].with_user(self.office).search_count(
                [("aprovacao_ids.access_token", "=", token)])
        # Fix round 4 (R2): campo não armazenado — agrupar é recusado pelo ORM.
        with self.assertRaises(UserError):  # AccessError é subclasse
            Aprov.read_group([], ["papel"], ["access_token"])
        # Não pesquisável para ninguém fora do servidor (nem o Gestor).
        with self.assertRaises(AccessError):
            self.env["afr.relatorio.aprovacao"].with_user(self.manager).search_count(
                [("access_token", "=", token)])

    # ─── Fix round 4: segredo fora do modelo legível (rulings R1–R5) ───

    def _no_token(self, token, fn, msg=None):
        """Chamada que ou é recusada ou não devolve o token."""
        try:
            result = fn()
        except (AccessError, UserError, ValueError):
            return
        self.assertNotIn(token, repr(result), msg)

    def test_r4_token_lives_in_secret_model_without_acl(self):  # R1
        token = self.line_cli.access_token
        Secret = self.env["afr.relatorio.aprovacao.secret"]
        secret = Secret.search([("aprovacao_id", "=", self.line_cli.id)])
        self.assertEqual(len(secret), 1)
        self.assertEqual(secret.token, token)
        self.assertFalse(Secret.search([("aprovacao_id", "=", self.line_elab.id)]))
        for user in (self.office, self.tech, self.manager):
            with self.assertRaises(AccessError):
                Secret.with_user(user).search([])
            with self.assertRaises(AccessError):
                secret.with_user(user).read(["token"])

    def test_r4_read_group_aggregate_alias_gives_no_token(self):  # R5
        token = self.line_cli.access_token
        Aprov = self.env["afr.relatorio.aprovacao"]
        for user in (self.office, self.tech):
            for spec in (["t:array_agg(access_token)"], ["t:max(access_token)"],
                         ["access_token:max"], ["access_token:array_agg"]):
                self._no_token(token, lambda: Aprov.with_user(user).read_group(
                    [], spec, ["papel"]), msg=(user.login, spec))

    def test_r4_usuario_authored_template_gets_no_token(self):  # R5
        self._approve_and_emit()
        token = self.line_cli.access_token
        model = self.env["ir.model"]._get("afr.relatorio.aprovacao")
        try:
            tpl = self.env["mail.template"].with_user(self.office).create({
                "name": "Modelo do Usuário",
                "model_id": model.id,
                "subject": "{{ object.access_token }}",
                "body_html": '<p><t t-out="object.access_token"/> <t t-out="object.portal_url"/></p>',
            })
        except AccessError:
            return  # base restringe a edição de modelos dinâmicos: sem vetor
        self._no_token(token, lambda: tpl.generate_email(
            self.line_cli.id, ["subject", "body_html"]))
        self._no_token(token, lambda: self.env["mail.mail"].browse(tpl.send_mail(
            self.line_cli.id, email_values={"email_to": "atacante@example.test"})
        ).sudo().read(["subject", "body_html", "body"]))

    def test_r4_onchange_subfield_gives_no_token(self):  # R5
        token = self.line_cli.access_token
        spec = {"aprovacao_ids": "1", "aprovacao_ids.access_token": "",
                "aprovacao_ids.papel": "", "aprovacao_ids.portal_url": ""}
        rel = self.rel.with_user(self.office)
        # Linha alterada ⇒ o onchange devolve TODOS os subcampos dela (Command.update).
        values = {"aprovacao_ids": [[1, line.id, {"nome_exibicao": "Nome alterado"}]
                                    for line in self.rel.aprovacao_ids]}
        for field_name in (False, "aprovacao_ids"):
            self._no_token(token, lambda: rel.onchange(values, field_name, spec),
                           msg=field_name)

    def test_r4_client_email_has_no_editable_template_and_one_recipient(self):  # R3
        legacy = self.env.ref(self.TPL, raise_if_not_found=False)
        if legacy:  # base antiga: modelo noupdate órfão até a migração 16.0.8.3.0
            legacy.with_user(self.office).write({
                "email_cc": "atacante@example.test",
                "body_html": "<p>modelo adulterado</p>"})
        self._approve_and_emit()
        self.rel.with_user(self.manager).action_enviar_aprovacao_cliente()
        mail = self.env["mail.mail"].search([
            ("model", "=", "afr.relatorio.aprovacao"), ("res_id", "=", self.line_cli.id),
        ])
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.recipient_ids, self.partner)
        self.assertFalse(mail.email_cc)
        self.assertIn(mail.email_to or self.partner.email, self.partner.email)
        token = self.line_cli.access_token
        self.assertIn("/my/relatorio/%d?access_token=%s" % (self.line_cli.id, token),
                      mail.body_html)
        self.assertNotIn("adulterado", mail.body_html)
        with self.assertRaises(AccessError):
            self.env["mail.mail"].with_user(self.office).search_read(
                [("res_id", "=", self.line_cli.id)], ["body_html"])
        # A mensagem-base (legível por quem lê a linha) não carrega o token.
        msgs = self.env["mail.message"].with_user(self.office).search([
            ("model", "=", "afr.relatorio.aprovacao"), ("res_id", "=", self.line_cli.id)])
        self.assertNotIn(token, repr(msgs.read(["body", "subject"])))
        # Nota no chatter do relatório sem o token.
        self.assertNotIn(token, repr(self.rel.message_ids.mapped("body")))

    def test_r4_rotation_updates_secret(self):  # R1
        self._approve_and_emit()
        Secret = self.env["afr.relatorio.aprovacao.secret"]
        old = self.line_cli.access_token
        self.line_cli.with_user(self.office).write({"partner_id": self._contact().id})
        new = Secret.search([("aprovacao_id", "=", self.line_cli.id)]).token
        self.assertNotEqual(new, old)
        self.assertEqual(self.line_cli.access_token, new)
        self.rel.with_user(self.manager).action_revisar()
        self._approve_and_emit()
        newer = Secret.search([("aprovacao_id", "=", self.line_cli.id)]).token
        self.assertNotEqual(newer, new)
        self.assertEqual(_portal_aprovacao(self.env, self.line_cli.id, newer), self.line_cli)
        self.assertIsNone(_portal_aprovacao(self.env, self.line_cli.id, new))

    def test_r4_migration_copies_legacy_column(self):  # R4
        from odoo.modules.module import get_module_path
        from odoo.modules.migration import load_script
        mig = load_script(get_module_path("afr_qualificacao")
                          + "/migrations/16.0.8.3.0/post-migrate.py", "afr_qualificacao_r4_mig")
        cr = self.env.cr
        cr.execute("ALTER TABLE afr_relatorio_aprovacao ADD COLUMN IF NOT EXISTS access_token varchar")
        Secret = self.env["afr.relatorio.aprovacao.secret"]
        Secret.search([("aprovacao_id", "=", self.line_cli.id)]).unlink()
        cr.execute("UPDATE afr_relatorio_aprovacao SET access_token = %s WHERE id = %s",
                   ["a" * 32, self.line_cli.id])
        mig.migrate(cr, "16.0.8.2.0")
        mig.migrate(cr, "16.0.8.2.0")  # idempotente
        self.env.invalidate_all()
        secret = Secret.search([("aprovacao_id", "=", self.line_cli.id)])
        self.assertEqual(secret.token, "a" * 32)
        self.assertEqual(_portal_aprovacao(self.env, self.line_cli.id, "a" * 32), self.line_cli)
        cr.execute("SELECT access_token FROM afr_relatorio_aprovacao WHERE id = %s",
                   [self.line_cli.id])
        self.assertFalse(cr.fetchone()[0])
        self.assertFalse(self.env.ref(self.TPL, raise_if_not_found=False))


@tagged("post_install", "-at_install", "afr_relatorio_final")
class TestRelatorioViews(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Como Gestor: botões com groups= somem do arch para quem não tem o grupo
        # (o usuário padrão do teste, OdooBot, não está nos grupos do módulo).
        cls.manager = make_user(cls.env, "gestor.rq.views", MANAGER)

    def test_form_has_p4_buttons_and_revisoes_page(self):
        arch = self.env["afr.qualificacao.relatorio"].with_user(self.manager).get_views(
            [(False, "form")])["views"]["form"]["arch"]
        for name in ("action_gerar_minuta", "action_aprovar_interno", "action_emitir",
                     "action_revisar", "action_enviar_aprovacao_cliente",
                     "action_baixar_minuta", "action_cancelar_montagem"):
            self.assertIn('name="%s"' % name, arch)
        self.assertIn('name="page_revisoes"', arch)
        self.assertIn('name="emissao_ids"', arch)
        self.assertIn('name="rq_build_progress"', arch)

    def test_emission_views_are_read_only(self):
        arch = self.env["afr.relatorio.emissao"].with_user(self.manager).get_views(
            [(False, "form")])["views"]["form"]["arch"]
        self.assertIn('create="0"', arch)
        self.assertIn('edit="0"', arch)

    def test_manifest_version_at_least_p4(self):
        # Piso, não igualdade: P5 sobe para 16.0.8.4.0 e este teste continua verde.
        module = self.env["ir.module.module"].search([("name", "=", "afr_qualificacao")])
        version = tuple(int(part) for part in module.latest_version.split("."))
        self.assertGreaterEqual(version, (16, 0, 8, 3, 0))
