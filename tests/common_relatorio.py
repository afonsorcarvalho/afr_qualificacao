"""Fixtures do Relatório Final para os testes de P5 (varredura + gate).

Monta: OS sem SO (datas 01–03/07/2026) + qualificação QD do equip1 +
relatório gerado por `action_generate_relatorios()`. `_apply_template()` NÃO
é chamado (P3 não aplica no create): o relatório nasce sem blocos, anexos,
checklist nem aprovações, e cada teste cria só o que exercita.
`_approve_internal` cria elaborador/emissor quando faltarem. Dados editoriais
sempre ANTES de aprovar (P4 zera aprovações em edição editorial).
"""
import base64
import io
from datetime import date, datetime, timedelta

from reportlab.pdfgen import canvas

from odoo.tests.common import new_test_user

from .common import AfrQualificacaoTestCommon


def make_pdf(text="Pagina de teste"):
    """PDF de 1 página com `text` (extraível pelo pdfminer)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    return buf.getvalue()


class RelatorioTestCommon(AfrQualificacaoTestCommon):

    D_INI = date(2026, 7, 1)
    D_FIM = date(2026, 7, 3)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cycle_cmax.load_type = "com_carga"
        Func = cls.env["afr.qualificacao.instrument.function"]
        cls.func_validador = Func.search([("code", "=", "VALIDADOR")], limit=1) or Func.create(
            {"name": "Validador", "code": "VALIDADOR"}
        )
        cls.func_padrao = Func.search([("code", "=", "PADRAO")], limit=1) or Func.create(
            {"name": "Padrão", "code": "PADRAO"}
        )
        cls.os = cls.env["afr.qualificacao.os"].create({
            "date_planned_start": datetime(2026, 7, 1, 8, 0, 0),
            "date_planned_end": datetime(2026, 7, 3, 17, 0, 0),
        })
        cls.qd = cls.env["afr.qualificacao"].create({
            "name": "QD Relatório Teste",
            "equipment_id": cls.equip1.id,
            "qualification_type": "performance",
            "company_id": cls.company.id,
            "os_id": cls.os.id,
        })
        rels = cls.os.action_generate_relatorios()
        cls.rel = rels.filtered(lambda r: r.equipment_id == cls.equip1)
        cls.rel.write({
            "data_inicio_ensaios": cls.D_INI,
            "data_fim_ensaios": cls.D_FIM,
            "amb_temperatura": "22 a 25 °C",
            "amb_umidade": "41 %UR",
        })
        cls.user_qualif = new_test_user(
            cls.env,
            login="p5_rel_user",
            name="Eng. Responsável",
            groups="base.group_user,afr_qualificacao.group_afr_qualificacao_user",
        )
        # P5 final fix wave (itens 3 e 8): usuários para os testes de
        # permissão do action_verificar (Técnico) e do unlink de achado
        # (Gestor — tem unlink=1 na ACL por convenção CRUD completo, mas o
        # model restringe a remoção a env.su).
        cls.user_technician = new_test_user(
            cls.env,
            login="p5_rel_tech",
            name="Técnico Teste",
            groups="base.group_user,afr_qualificacao.group_afr_qualificacao_technician",
        )
        cls.user_manager = new_test_user(
            cls.env,
            login="p5_rel_manager",
            name="Gestor Teste",
            groups="base.group_user,afr_qualificacao.group_afr_qualificacao_manager",
        )

    def setUp(self):
        super().setUp()
        # Item 6 (P5 final fix wave): garante IA desligada por padrão em
        # TODA classe desta base — TestRelatorioAi (test_relatorio_ai.py)
        # liga de novo no próprio setUp quando precisa mockar requests.post.
        # Sem isto, um teste que ligasse o parâmetro e não desfizesse
        # poderia deixar outra classe fazendo HTTP real por engano.
        self.env["ir.config_parameter"].sudo().set_param(
            "afr_qualificacao.ai_enabled", "False")

    # ------------------------------------------------------------ helpers
    def _refresh(self):
        self.rel.invalidate_recordset()

    def _cycle(self, state="passed", seq=1, cycle_type=None, **extra):
        vals = {
            "qualificacao_id": self.qd.id,
            "cycle_type_id": (cycle_type or self.cycle_cmax).id,
            "sequence": seq,
        }
        vals.update(extra)
        cycle = self.env["afr.qualificacao.cycle"].create(vals)
        if state != "pending":
            cycle.state = state
        self._refresh()
        return cycle

    def _instrument(self, name, function, channels):
        return self.env["engc.calibration.instruments"].create({
            "name": name,
            "function_ids": [(6, 0, function.ids)],
            "measurement_capacity_ids": [
                (0, 0, {"sensor_kind_id": self.sensor_temp.id, "qty": channels})
            ],
        })

    def _validator(self, name="Logger Teste", channels=28):
        instr = self._instrument(name, self.func_validador, channels)
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id,
            "resource_role": "validador",
            "instrument_id": instr.id,
        })
        return instr

    def _padrao(self, name="Padrão Teste"):
        instr = self._instrument(name, self.func_padrao, 1)
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id,
            "resource_role": "padrao",
            "instrument_id": instr.id,
        })
        return instr

    def _cert(self, instr, role, date_cal, validate=None):
        return self.env["engc.calibration.instruments.certificates"].create({
            "instrument_id": instr.id,
            "afr_role": role,
            "date_calibration": date_cal,
            "validate_calibration": validate or (date_cal + timedelta(days=365)),
        })

    def _anexo(self, code="dados", title="Dados", slot_kind="upload",
               included=True, pdfs=()):
        anexo = self.env["afr.relatorio.anexo"].create({
            "relatorio_id": self.rel.id,
            "code": code,
            "title": title,
            "slot_kind": slot_kind,
            "included": included,
            "sequence": 10,
        })
        att_ids = []
        for i, data in enumerate(pdfs):
            att_ids.append(self.env["ir.attachment"].create({
                "name": "%s-%d.pdf" % (code, i),
                "datas": base64.b64encode(data),
                "mimetype": "application/pdf",
                "res_model": "afr.relatorio.anexo",
                "res_id": anexo.id,
            }).id)
        if att_ids:
            anexo.attachment_ids = [(6, 0, att_ids)]
        self._refresh()
        return anexo

    def _block(self, body, title="Bloco Teste", kind="static", included=True):
        block = self.env["afr.relatorio.block"].create({
            "relatorio_id": self.rel.id,
            "block_kind": kind,
            "title": title,
            "body": body,
            "included": included,
            "sequence": 10,
        })
        self._refresh()
        return block

    def _mk_achado(self, **vals):
        base = {
            "relatorio_id": self.rel.id,
            "origem": "regra",
            "codigo": "TESTE",
            "gravidade": "alerta",
            "mensagem": "Mensagem de teste",
            "onde": "Teste",
        }
        base.update(vals)
        return self.env["afr.relatorio.achado"].with_context(
            afr_scan_internal=True
        ).create(base)

    def _achado(self, codigo):
        self._refresh()
        return self.rel.achado_ids.filtered(lambda a: a.codigo == codigo)

    def _approve_internal(self):
        """Elaborador+emissor com user_id = env.user, aprovados numa única
        chamada de `action_aprovar_interno()` (P4 aprova todas as linhas
        pendentes do usuário de uma vez)."""
        Aprov = self.env["afr.relatorio.aprovacao"]
        for papel in ("elaborador", "emissor"):
            line = self.rel.aprovacao_ids.filtered(lambda a, p=papel: a.papel == p)[:1]
            if not line:
                line = Aprov.create({"relatorio_id": self.rel.id, "papel": papel, "sequence": 10})
            line.user_id = self.env.user
        self._refresh()
        self.rel.action_aprovar_interno()
        self._refresh()
        internas = self.rel.aprovacao_ids.filtered(
            lambda a: a.papel in ("elaborador", "emissor"))
        self.assertTrue(internas and all(a.approved_at for a in internas))

    def _make_clean(self):
        """Validador com certificados antes/depois válidos — sem nenhum
        achado de regra no relatório base."""
        v = self._validator()
        self._cert(v, "antes", self.D_INI - timedelta(days=30))
        self._cert(v, "depois", self.D_FIM + timedelta(days=5))
        self._refresh()
        return v
