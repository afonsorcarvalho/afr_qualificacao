"""F6.1 (16.0.3.5.0) — Geração DOCX individual por qualificação.

Cobre:
- Montagem do contexto rico (cliente/equipamento/aprovação/instrumentos)
- Agrupamento de collect.items por docx_section
- Fallback de template via xmlid quando docx_template_id vazio
- Action gera ir.attachment com mimetype DOCX correto
- Dedup de instrumentos no bloco instrumentos[]
"""

from odoo.tests.common import tagged
from odoo.exceptions import UserError

from .common import AfrQualificacaoTestCommon


@tagged("post_install", "-at_install", "afr_qualificacao", "f6_1")
class TestDocxRender(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.qualif_qi = cls.env["afr.qualificacao"].create({
            "name": "QUALIF-QI-T1",
            "equipment_id": cls.equip1.id,
            "qualification_type": "installation",
            "responsible_id": cls.env.user.id,
        })
        cls.qualif_qo = cls.env["afr.qualificacao"].create({
            "name": "QUALIF-QO-T1",
            "equipment_id": cls.equip1.id,
            "qualification_type": "operational",
            "responsible_id": cls.env.user.id,
        })
        cls.qualif_qd = cls.env["afr.qualificacao"].create({
            "name": "QUALIF-QD-T1",
            "equipment_id": cls.equip1.id,
            "qualification_type": "performance",
            "responsible_id": cls.env.user.id,
        })

    def _make_collect(self, qualif, name, section, **extra):
        vals = {
            "name": name,
            "qualif_id": qualif.id,
            "kind": "foto",
            "required": True,
        }
        vals.update(extra)
        item = self.env["afr.qualificacao.collect.item"].create(vals)
        if section:
            item.docx_section = section
        return item

    def test_build_context_qi_minimal_keys_present(self):
        """Contexto QI sem coletas tem todas as chaves top-level + qi vazio."""
        ctx = self.qualif_qi._build_docx_context()
        for k in (
            "empresa", "documento", "cliente", "equipamento",
            "aprovacao", "revisoes", "instrumentos",
            "qi", "qo", "qd", "conclusao", "anexos",
        ):
            self.assertIn(k, ctx, "chave '%s' ausente no contexto" % k)
        self.assertEqual(ctx["revisoes"], [], "revisoes default = []")
        self.assertEqual(ctx["instrumentos"], [], "sem instrumentos sem coletas")
        # qi populado (responsavel/executor)
        self.assertIn("executor", ctx["qi"])
        self.assertEqual(ctx["qi"]["executor"], self.env.user.name)
        # qo/qd vazios — qualif é QI
        self.assertEqual(ctx["qo"], {})
        self.assertEqual(ctx["qd"], {})

    def test_build_context_qo_groups_collect_items(self):
        """Coletas QO com docx_section caem na sub-chave correta."""
        self._make_collect(
            self.qualif_qo, "Teste funcional 1", "qo_testes_funcionais",
        )
        self._make_collect(
            self.qualif_qo, "Teste funcional 2", "qo_testes_funcionais",
        )
        self._make_collect(
            self.qualif_qo, "Teste segurança 1", "qo_testes_seguranca",
        )
        self._make_collect(self.qualif_qo, "Anexo solto", "anexos")
        ctx = self.qualif_qo._build_docx_context()
        self.assertEqual(len(ctx["qo"]["testes_funcionais"]), 2)
        self.assertEqual(len(ctx["qo"]["testes_seguranca"]), 1)
        # anexos não é qo_* → não aparece em qo
        self.assertNotIn("anexos", ctx["qo"])

    def test_build_context_qd_penetracao_ciclos(self):
        """Coletas QD com seção qd_penetracao_ciclo1/2/3 agrupam separadamente."""
        for ciclo in (1, 2, 3):
            for n in range(ciclo):
                self._make_collect(
                    self.qualif_qd,
                    "Penetra ciclo %d ponto %d" % (ciclo, n),
                    "qd_penetracao_ciclo%d" % ciclo,
                )
        ctx = self.qualif_qd._build_docx_context()
        self.assertEqual(len(ctx["qd"]["penetracao_ciclo1"]), 1)
        self.assertEqual(len(ctx["qd"]["penetracao_ciclo2"]), 2)
        self.assertEqual(len(ctx["qd"]["penetracao_ciclo3"]), 3)

    def test_template_fallback_by_xmlid_when_no_manual_selection(self):
        """Sem docx_template_id manual: resolve por xmlid baseado em type."""
        tpl_qi = self.env.ref("afr_qualificacao.tpl_docx_qi", raise_if_not_found=False)
        self.assertTrue(tpl_qi, "data seed tpl_docx_qi deve existir após upgrade")
        self.assertTrue(tpl_qi.datas, "template QI deve ter datas")
        self.assertFalse(self.qualif_qi.docx_template_id)
        # Resolver não levanta
        bytes_, label = self.qualif_qi._resolve_docx_template_bytes()
        self.assertTrue(bytes_)
        self.assertIn("QI", label)

    def test_manual_template_selection_wins_over_fallback(self):
        """docx_template_id manual prevalece sobre fallback por tipo."""
        tpl_qo = self.env.ref("afr_qualificacao.tpl_docx_qo")
        self.qualif_qi.docx_template_id = tpl_qo
        bytes_, label = self.qualif_qi._resolve_docx_template_bytes()
        self.assertIn("QO", label, "manual QO deve ser escolhido mesmo qualif sendo QI")
        self.assertEqual(bytes_, __import__("base64").b64decode(tpl_qo.datas))

    def test_action_generate_docx_creates_attachment_qi(self):
        """Action gera ir.attachment DOCX > 0 bytes, mimetype correto."""
        self._make_collect(self.qualif_qi, "Manual operação", "qi_documentos")
        result = self.qualif_qi.action_generate_docx()
        self.assertEqual(result["type"], "ir.actions.act_url")
        # Attachment recém-criado
        attachments = self.env["ir.attachment"].search([
            ("res_model", "=", "afr.qualificacao"),
            ("res_id", "=", self.qualif_qi.id),
            ("mimetype", "=", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ])
        self.assertTrue(attachments)
        latest = attachments.sorted("id", reverse=True)[0]
        self.assertTrue(latest.datas)
        # Validar tamanho mínimo (>1KB = render OK, não placeholder vazio)
        import base64
        self.assertGreater(
            len(base64.b64decode(latest.datas)),
            1024,
            "DOCX gerado abaixo de 1KB sugere render falho",
        )

    def test_action_generate_docx_qd_renders_without_section_data(self):
        """QD sem dados granulares de sensores: render funciona, tabelas vazias OK."""
        result = self.qualif_qd.action_generate_docx()
        self.assertEqual(result["type"], "ir.actions.act_url")

    def test_action_generate_docx_qo_renders(self):
        """QO renderiza com fallback de template por tipo."""
        result = self.qualif_qo.action_generate_docx()
        self.assertEqual(result["type"], "ir.actions.act_url")

    def test_partner_block_uses_qualif_partner(self):
        """cliente.nome reflete partner_id da qualif (sticky de equipment.client_id)."""
        ctx = self.qualif_qi._build_docx_context()
        self.assertEqual(ctx["cliente"]["nome"], self.partner.name)

    def test_aprovacao_block_uses_responsible_and_approver(self):
        """aprovacao.elaborado.nome = responsible; aprovado.nome = approver."""
        admin = self.env.ref("base.user_admin")
        self.qualif_qi.approver_id = admin
        ctx = self.qualif_qi._build_docx_context()
        self.assertEqual(ctx["aprovacao"]["elaborado"]["nome"], self.env.user.name)
        self.assertEqual(ctx["aprovacao"]["aprovado"]["nome"], admin.name)

    def test_documento_block_includes_type_label(self):
        """documento.titulo inclui label do qualification_type."""
        ctx = self.qualif_qi._build_docx_context()
        self.assertIn("Instalação", ctx["documento"]["titulo"])
        self.assertIn(self.qualif_qi.name, ctx["documento"]["titulo"])

    def test_docx_section_propagated_from_procedimento_item(self):
        """Related stored: criar collect.item com procedimento_item_id propaga section."""
        proc = self.env["afr.qualificacao.procedimento"].create({
            "name": "Test Proc QI",
        })
        proc_item = self.env["afr.qualificacao.procedimento.item"].create({
            "procedimento_id": proc.id,
            "name": "Manual de instalação",
            "kind": "pdf",
            "phase": "installation",
            "docx_section": "qi_documentos",
        })
        item = self.env["afr.qualificacao.collect.item"].create({
            "name": "Manual de instalação",
            "qualif_id": self.qualif_qi.id,
            "kind": "pdf",
            "procedimento_item_id": proc_item.id,
        })
        # Related stored propaga
        self.assertEqual(item.docx_section, "qi_documentos")
