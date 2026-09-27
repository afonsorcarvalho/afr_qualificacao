"""P4 — emissão, revisão, aprovações, verificação pública e portal do Relatório Final."""
from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon
from .relatorio_fakes import RelatorioFixtureMixin, make_user

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
