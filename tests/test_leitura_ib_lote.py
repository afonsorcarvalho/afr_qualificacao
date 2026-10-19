# -*- coding: utf-8 -*-
"""Testes do wizard de preenchimento em lote de leituras de IB (F11 P6).

Cobre: cria só ciclos sem leitura, pula os que já têm (e informa quantos),
quantidade gravada por leitura, default do indicador biológico único,
indicador de outro relatório barrado pela constraint existente, quantidade
<= 0 barrada, permissão (Usuário consegue, Técnico não) e trava de rascunho.
"""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common_relatorio import RelatorioTestCommon


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestLeituraIbLote(RelatorioTestCommon):

    def _wizard(self, cycle_ids, **vals):
        base = {
            "relatorio_id": self.rel.id,
            "cycle_ids": [(6, 0, cycle_ids)],
            "resultado": "negativo",
            "controle_positivo_ok": True,
            "quantidade": 1,
        }
        base.update(vals)
        return self.env["afr.relatorio.leitura.ib.lote"].create(base)

    def test_cria_apenas_ciclos_sem_leitura(self):
        c1 = self._cycle(seq=1)
        c2 = self._cycle(seq=2)
        existente = self.env["afr.relatorio.leitura.ib"].create({
            "relatorio_id": self.rel.id,
            "cycle_id": c1.id,
            "resultado": "positivo",
        })
        wiz = self._wizard([c1.id, c2.id])
        wiz.action_confirm()
        self._refresh()
        self.assertEqual(len(self.rel.leitura_ib_ids), 2)
        # a leitura existente do c1 não foi sobrescrita
        leitura_c1 = self.rel.leitura_ib_ids.filtered(lambda l: l.cycle_id == c1)
        self.assertEqual(leitura_c1, existente)
        self.assertEqual(leitura_c1.resultado, "positivo")
        leitura_c2 = self.rel.leitura_ib_ids.filtered(lambda l: l.cycle_id == c2)
        self.assertTrue(leitura_c2)
        self.assertEqual(leitura_c2.resultado, "negativo")

    def test_pula_existentes_notifica_quantidade(self):
        c1 = self._cycle(seq=1)
        c2 = self._cycle(seq=2)
        self.env["afr.relatorio.leitura.ib"].create({
            "relatorio_id": self.rel.id, "cycle_id": c1.id, "resultado": "negativo",
        })
        wiz = self._wizard([c1.id, c2.id])
        result = wiz.action_confirm()
        msg = result["params"]["message"]
        self.assertIn("1", msg)
        self.assertIn("pulad", msg)

    def test_quantidade_gravada(self):
        c1 = self._cycle(seq=1)
        wiz = self._wizard([c1.id], quantidade=3)
        wiz.action_confirm()
        self._refresh()
        leitura = self.rel.leitura_ib_ids.filtered(lambda l: l.cycle_id == c1)
        self.assertEqual(leitura.quantidade, 3)

    def test_default_indicador_unico(self):
        ind = self.env["afr.relatorio.indicador"].create({
            "relatorio_id": self.rel.id, "tipo": "biologico", "lote": "L1",
        })
        self._refresh()
        wiz = self.env["afr.relatorio.leitura.ib.lote"].new({
            "relatorio_id": self.rel.id,
        })
        wiz._onchange_relatorio_id()
        self.assertEqual(wiz.indicador_id.id, ind.id)

    def test_indicador_de_outro_relatorio_barrado(self):
        outro_qd = self.env["afr.qualificacao"].create({
            "name": "QD Outro Relatório",
            "equipment_id": self.equip2.id,
            "qualification_type": "performance",
            "company_id": self.company.id,
            "os_id": self.os.id,
        })
        rels = self.os.action_generate_relatorios()
        outro_rel = rels.filtered(lambda r: r.equipment_id == self.equip2)[:1]
        ind_outro = self.env["afr.relatorio.indicador"].create({
            "relatorio_id": outro_rel.id, "tipo": "biologico", "lote": "OUTRO",
        })
        c1 = self._cycle(seq=1)
        wiz = self._wizard([c1.id], indicador_id=ind_outro.id)
        with self.assertRaises(ValidationError):
            wiz.action_confirm()

    def test_quantidade_menor_igual_zero_barrada(self):
        c1 = self._cycle(seq=1)
        wiz = self._wizard([c1.id], quantidade=0)
        with self.assertRaises(ValidationError):
            wiz.action_confirm()

    def test_usuario_consegue(self):
        c1 = self._cycle(seq=1)
        wiz = self._wizard([c1.id]).with_user(self.user_qualif)
        wiz.action_confirm()
        self._refresh()
        self.assertTrue(self.rel.leitura_ib_ids.filtered(lambda l: l.cycle_id == c1))

    def test_tecnico_nao_consegue(self):
        c1 = self._cycle(seq=1)
        with self.assertRaises(AccessError):
            self.env["afr.relatorio.leitura.ib.lote"].with_user(
                self.user_technician
            ).create({
                "relatorio_id": self.rel.id,
                "cycle_ids": [(6, 0, [c1.id])],
                "resultado": "negativo",
                "quantidade": 1,
            })

    def test_fora_de_rascunho_recusado(self):
        c1 = self._cycle(seq=1)
        wiz = self._wizard([c1.id])
        self.rel.state = "issued"
        with self.assertRaises(Exception):
            wiz.action_confirm()
