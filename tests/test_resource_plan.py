"""F10 — Testes do plano de recursos metrológicos (bin-packing).

Cenário núcleo: 2 equipamentos no MESMO grupo paralelo, cada um com QD
(12 pontos temp + 1 press, do template) e 3 malhas de temperatura.

Demanda simultânea no grupo:
  - pontos QD: temp = 12+12 = 24 ; press = 1+1 = 2
  - janela QD do grupo = máx das horas QD por equip = 2.0 h
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

        # Reusa as tags semeadas (data/instrument_function_seed.xml); cria só
        # se ausente (evita violar o unique de code).
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

        # Template com pontos QD: temp=12, press=1
        cls.tpl = cls.env["afr.qualificacao.config.template"].create({
            "name": "Pacote QD Test",
            "equipment_category_id": cls.category.id,
            "qd_point_ids": [
                (0, 0, {"sensor_kind_id": cls.sensor_temp.id, "points": 12}),
                (0, 0, {"sensor_kind_id": cls.sensor_press.id, "points": 1}),
            ],
        })

        cls.so = cls._build_so(cls, parallel_group="G1")

    def _build_so(self, parallel_group=""):
        """Cria SO com 2 equips no mesmo grupo: QD (2 ciclos) + 3 malhas temp."""
        SO = self.env["sale.order"]
        SOL = self.env["sale.order.line"]
        order = SO.create({"partner_id": self.partner.id})
        for equip in (self.equip1, self.equip2):
            # section line do equipamento (carrega template + grupo paralelo)
            SOL.create({
                "order_id": order.id,
                "display_type": "line_section",
                "name": equip.display_name,
                "is_qualificacao_managed": True,
                "equipment_id": equip.id,
                "config_template_id": self.tpl.id,
                "parallel_group": parallel_group,
            })
            # QD: 2 ciclos × 1h
            SOL.create({
                "order_id": order.id,
                "product_id": self.product_qd_cmax.id,
                "is_qualificacao_managed": True,
                "equipment_id": equip.id,
                "qualification_type": "performance",
                "cycle_type_id": self.cycle_cmax.id,
                "estimated_hours": 1.0,
                "qualif_cycle_qty": 2,
                "product_uom_qty": 2,
            })
            # Calib: 3 malhas temp × 1h
            SOL.create({
                "order_id": order.id,
                "product_id": self.product_malha_temp.id,
                "is_qualificacao_managed": True,
                "equipment_id": equip.id,
                "qualification_type": "calibration",
                "malha_type_id": self.malha_temp.id,
                "estimated_hours": 1.0,
                "qualif_cycle_qty": 3,
                "product_uom_qty": 3,
            })
        return order

    def test_fleet_single_logger_two_temp_standards(self):
        self.so.action_compute_resource_plan()
        lines = self.so.resource_plan_line_ids

        validadores = lines.filtered(lambda l: l.resource_role == "validador")
        padroes = lines.filtered(lambda l: l.resource_role == "padrao")

        # 1 validador cobre tudo (temp 24/28, press 2/2)
        self.assertEqual(len(validadores), 1, "esperado 1 validador")
        self.assertEqual(validadores.instrument_id, self.logger1)
        # vencido jamais sugerido
        self.assertNotIn(self.logger_expired, lines.mapped("instrument_id"))

        # 2 padrões de temperatura
        self.assertEqual(len(padroes), 2, "esperado 2 padrões temp")
        self.assertTrue(all(
            p.sensor_kind_id == self.sensor_temp for p in padroes
        ))
        self.assertEqual(
            set(padroes.mapped("instrument_id").ids),
            {self.std_temp_1.id, self.std_temp_2.id},
        )

        # nenhum padrão de pressão (não há malha press)
        self.assertNotIn(self.std_press_1, padroes.mapped("instrument_id"))

        # horas de utilização: validador = janela(2) + setup(2) = 4.0
        self.assertAlmostEqual(validadores.hours_resource_usage, 4.0, places=2)
        # padrão temp = (6 std-horas / 2) + setup(1)×1 grupo = 4.0
        for p in padroes:
            self.assertAlmostEqual(p.hours_resource_usage, 4.0, places=2)

        # dirty limpo após compute
        self.assertFalse(self.so.resource_plan_dirty)

    def test_singleton_groups_when_no_parallel_label(self):
        """Sem rótulo de grupo, cada equip roda sozinho → demanda QD por grupo
        cai p/ 12 temp; 1 logger ainda cobre. Padrões temp simultâneos = 1."""
        so = self._build_so(parallel_group="")
        so.action_compute_resource_plan()
        padroes = so.resource_plan_line_ids.filtered(
            lambda l: l.resource_role == "padrao"
        )
        # cada grupo singleton tem 1 malha temp simultânea → máx = 1 padrão
        self.assertEqual(len(padroes), 1)

    def test_compute_preserves_overridden_lines(self):
        so = self._build_so(parallel_group="G1")
        so.action_compute_resource_plan()
        # técnico ajusta uma linha
        a_line = so.resource_plan_line_ids[0]
        a_line.write({"is_overridden": True, "hours_resource_usage": 99.0})
        before = len(so.resource_plan_line_ids)
        so.action_compute_resource_plan()
        # linha overridden permanece intacta
        self.assertIn(a_line, so.resource_plan_line_ids)
        self.assertAlmostEqual(a_line.hours_resource_usage, 99.0, places=2)
        self.assertTrue(a_line.is_overridden)
        # plano não duplica (regenera apenas as não-overridden)
        self.assertEqual(len(so.resource_plan_line_ids), before)
