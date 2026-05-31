"""F10 — Testes do plano de recursos metrológicos (bin-packing), na OS.

O plano vive em `afr.qualificacao.os` (operacional/PCP) e lê demanda dos
SUB-RECORDS reais materializados no confirm do SO:
  - pontos QD → snapshot `qd_point_snapshot_ids` da qualif performance
  - horas QD → Σ horas dos ciclos QD reais (afr.qualificacao.cycle)
  - malhas   → registros afr.qualificacao.malha reais

Cenário núcleo: 2 equipamentos no MESMO grupo paralelo, cada um com QD
(12 pontos temp + 1 press, do template) e 3 malhas de temperatura.

Demanda simultânea no grupo:
  - pontos QD: temp = 12+12 = 24 ; press = 1+1 = 2
  - janela QD do grupo = máx das horas QD por equip = 2 ciclos × 1h = 2.0 h
  - padrões temp simultâneos = 1 (por equip) × 2 equips = 2

Frota esperada:
  - 1 validador (logger cobre temp=28, press=2 → cobre 24/2 numa caixa só)
  - 2 padrões de temperatura
Instrumentos com certificado vencido são ignorados.
"""

from datetime import timedelta

from odoo import fields

from .common import AfrQualificacaoTestCommon


class TestResourcePlan(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Instr = cls.env["engc.calibration.instruments"]
        Func = cls.env["afr.qualificacao.instrument.function"]
        today = fields.Date.today()
        future = today + timedelta(days=200)
        past = today - timedelta(days=30)

        # Reusa tags semeadas; cria só se ausente (unique de code).
        cls.func_validador = Func.search(
            [("code", "=", "VALIDADOR")], limit=1
        ) or Func.create({"name": "Validador", "code": "VALIDADOR"})
        cls.func_padrao = Func.search(
            [("code", "=", "PADRAO")], limit=1
        ) or Func.create({"name": "Padrão", "code": "PADRAO"})

        def _make(name, functions, caps, setup, cert_valid=True):
            instr = Instr.create({
                "name": name,
                "function_ids": [(6, 0, functions.ids)],
                "setup_hours": setup,
                "measurement_capacity_ids": [
                    (0, 0, {"sensor_kind_id": k.id, "qty": q}) for k, q in caps
                ],
            })
            cls.env["engc.calibration.instruments.certificates"].create({
                "instrument_id": instr.id,
                "validate_calibration": future if cert_valid else past,
            })
            return instr

        cls.logger1 = _make(
            "Logger 28ch", cls.func_validador,
            [(cls.sensor_temp, 28), (cls.sensor_press, 2)], 2.0,
        )
        cls.logger_expired = _make(
            "Logger Vencido", cls.func_validador,
            [(cls.sensor_temp, 28), (cls.sensor_press, 2)], 2.0,
            cert_valid=False,
        )
        cls.std_temp_1 = _make(
            "Padrão Temp 1", cls.func_padrao, [(cls.sensor_temp, 1)], 1.0,
        )
        cls.std_temp_2 = _make(
            "Padrão Temp 2", cls.func_padrao, [(cls.sensor_temp, 1)], 1.0,
        )
        cls.std_press_1 = _make(
            "Padrão Press 1", cls.func_padrao, [(cls.sensor_press, 1)], 1.0,
        )

        # Template com pontos QD: temp=12, press=1 (vira snapshot no confirm).
        cls.tpl = cls.env["afr.qualificacao.config.template"].create({
            "name": "Pacote QD Test",
            "equipment_category_id": cls.category.id,
            "qd_point_ids": [
                (0, 0, {"sensor_kind_id": cls.sensor_temp.id, "points": 12}),
                (0, 0, {"sensor_kind_id": cls.sensor_press.id, "points": 1}),
            ],
        })

    def _build_os(self, parallel_group="G1"):
        """Configura SO (2 equips, QD 2 ciclos + 3 malhas temp), confirma e
        define o grupo paralelo nas qualifs da OS (PCP) → retorna a OS.

        F10.4 — parallel_group é definido na OS (não na cotação)."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        wiz = self.env["afr.qualificacao.configurator"].create(
            {"sale_order_id": so.id}
        )
        specs = []
        for equip in (self.equip1, self.equip2):
            specs.append({
                "equipment_id": equip.id,
                "config_template_id": self.tpl.id,
                "qd_line_ids": [(0, 0, {
                    "cycle_type_id": self.cycle_cmax.id,
                    "qty": 2,
                    "estimated_hours": 1.0,
                })],
                "calib_line_ids": [(0, 0, {
                    "malha_type_id": self.malha_temp.id,
                    "qty": 3,
                    "estimated_hours": 1.0,
                })],
            })
        wiz.equipment_line_ids = [(0, 0, s) for s in specs]
        wiz.action_apply()
        so.action_confirm()
        os = so.qualificacao_os_ids
        if parallel_group:
            os.qualificacao_ids.write({"parallel_group": parallel_group})
        return os

    def test_qd_point_snapshot_on_confirm(self):
        """Snapshot QD copiado do template no confirm (independe do template)."""
        os = self._build_os(parallel_group="")
        perf = os.qualificacao_ids.filtered(
            lambda q: q.qualification_type == "performance"
        )
        self.assertTrue(perf)
        for q in perf:
            snap = {s.sensor_kind_id: s.points for s in q.qd_point_snapshot_ids}
            self.assertEqual(snap.get(self.sensor_temp), 12)
            self.assertEqual(snap.get(self.sensor_press), 1)

    def test_fleet_single_logger_two_temp_standards(self):
        os = self._build_os(parallel_group="G1")
        os.action_compute_resource_plan()
        lines = os.resource_plan_line_ids

        validadores = lines.filtered(lambda l: l.resource_role == "validador")
        padroes = lines.filtered(lambda l: l.resource_role == "padrao")

        self.assertEqual(len(validadores), 1, "esperado 1 validador")
        self.assertEqual(validadores.instrument_id, self.logger1)
        self.assertNotIn(self.logger_expired, lines.mapped("instrument_id"))

        self.assertEqual(len(padroes), 2, "esperado 2 padrões temp")
        self.assertTrue(all(
            p.sensor_kind_id == self.sensor_temp for p in padroes
        ))
        self.assertEqual(
            set(padroes.mapped("instrument_id").ids),
            {self.std_temp_1.id, self.std_temp_2.id},
        )
        self.assertNotIn(self.std_press_1, padroes.mapped("instrument_id"))

        # validador = janela(2) + setup(2) = 4.0
        self.assertAlmostEqual(validadores.hours_resource_usage, 4.0, places=2)
        # padrão temp = (6 std-horas / 2) + setup(1)×1 grupo = 4.0
        for p in padroes:
            self.assertAlmostEqual(p.hours_resource_usage, 4.0, places=2)

        self.assertFalse(os.resource_plan_dirty)

    def test_singleton_groups_when_no_parallel_label(self):
        """Sem rótulo, cada equip roda sozinho → 1 padrão temp simultâneo."""
        os = self._build_os(parallel_group="")
        os.action_compute_resource_plan()
        padroes = os.resource_plan_line_ids.filtered(
            lambda l: l.resource_role == "padrao"
        )
        self.assertEqual(len(padroes), 1)

    def test_compute_preserves_overridden_lines(self):
        os = self._build_os(parallel_group="G1")
        os.action_compute_resource_plan()
        a_line = os.resource_plan_line_ids[0]
        a_line.write({"is_overridden": True, "hours_resource_usage": 99.0})
        before = len(os.resource_plan_line_ids)
        os.action_compute_resource_plan()
        self.assertIn(a_line, os.resource_plan_line_ids)
        self.assertAlmostEqual(a_line.hours_resource_usage, 99.0, places=2)
        self.assertTrue(a_line.is_overridden)
        self.assertEqual(len(os.resource_plan_line_ids), before)
