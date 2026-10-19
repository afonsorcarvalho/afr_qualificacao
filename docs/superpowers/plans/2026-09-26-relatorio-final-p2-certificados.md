# Relatório Final — P2: Biblioteca de Certificados — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Os certificados dos instrumentos viram uma biblioteca com papel (`antes`/`depois`/`externo`). O relatório final escolhe sozinho, pelas datas dos ensaios, o certificado de cada validador e de cada padrão da OS. Ele também entrega os bytes desses certificados e os certificados das malhas: o PDF do `engc_os` quando a malha tem calibração vinculada, senão os PDFs e imagens anexados à malha. Tudo isso fica visível numa aba só de leitura.

**Architecture:** Só extensões por `_inherit` dentro de `afr_qualificacao` (`engc_os` está congelado). O papel e a regra de seleção por data ficam no instrumento, em `models/calibration_instruments.py`. A composição por relatório fica num arquivo novo, `models/relatorio_certificados.py` (`_inherit = "afr.qualificacao.relatorio"`), com três métodos de contrato consumidos por P4 e P5. A malha ganha o O2M inverso `collect_item_ids`. O formulário do relatório ganha a página `page_certificados`, com um Html computado não armazenado.

**Tech Stack:** Odoo 16.0 (ORM, QWeb reports, views XML), Python 3 (`base64`, `markupsafe`), `odoo.tools.mimetypes.guess_mimetype`, `unittest.mock` nos testes, PIL (já no container) para gerar PNG de teste.

**Spec:** `addons/afr_qualificacao/docs/superpowers/specs/2026-09-26-relatorio-final-qualificacao-design.md` (§4.4, decisões D4 e D5). Índice e contrato: `addons/afr_qualificacao/docs/superpowers/plans/2026-09-26-relatorio-final-00-indice.md`.

## Global Constraints

- Odoo **16.0**. O módulo `afr_qualificacao` é **git submodule** em `addons/afr_qualificacao/`. Trabalhar na branch `feat/relatorio-final` **dentro do submodule** (P1 já a criou).
- Commits sempre de dentro de `addons/afr_qualificacao/`, via agente `git-commit-push` (haiku), com paths relativos ao submodule. **Não** fazer push nem bump do pointer no monorepo sem o usuário pedir. Mensagens em inglês, Conventional Commits.
- Testes: comando base `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init --no-http`. `-u` é obrigatório quando tocar XML e `--no-http` é obrigatório. Falhas pré-existentes conhecidas (ignorar): `TestResourcePlan.test_fleet_single_logger_two_temp_standards`, `TestProposalReport.test_render_equipment_scope_omits_cronograma_footer`, `TestProposalReport.test_render_schedule_block`.
- Novos testes herdam de `tests/common.py::AfrQualificacaoTestCommon`. Registrar cada arquivo novo em `tests/__init__.py`.
- `engc_os` está **congelado**: não editar nada em `engenapp/engc_os/`. Extensões só por `_inherit` dentro de `afr_qualificacao`.
- **Nunca** usar nomes de clientes, pessoas ou números de certificados reais (`dados_sensiveis/`). Usar "Cliente Teste", "Validador Teste", "CERT-TST-…".
- PWA (`pwa/`) **não muda**.
- Versão do manifest ao final de P2: **`16.0.8.1.0`**. P2 não cria model novo (sem ACL) e não cria seed (sem migração).
- Os nomes do contrato são **vinculantes**: `afr_role`, `_afr_select_certificate(role, date_start, date_end)`, `_afr_certificate_selection()`, `_afr_certificate_files(roles)`, `_afr_malha_certificate_files()`, `page_certificados`.
- Textos de UI em pt-BR.

## Review Focus

- **Bases existentes após `-u`:** todo certificado já cadastrado nasce `afr_role='externo'`, então validadores ficam sem antes/depois até alguém reclassificar. O esperado é que a aba mostre "AUSENTE" em vermelho, sem erro. Teste: `test_html_marks_missing_when_validator_only_has_externo` (Task 4).
- **Certificado sem número:** a legenda não pode sair "Certificado False" nem ficar vazia. O esperado é "Certificado s/nº — …". Teste: `test_files_caption_without_number` (Task 2).
- **Certificado sem arquivo nenhum** (binário vazio e sem linhas em `certificate_file_ids`, ou linhas sem `file`): ele é selecionado, mas não gera tupla de arquivo, e nada quebra. Testes: `test_files_skip_certificate_without_any_file` (Task 2) e `test_file_content_fallback_skips_rows_without_file` (Task 1).
- **Duas malhas vinculadas à mesma `engc.calibration`** (medições diferentes da mesma calibração): o certificado do `engc_os` sai uma vez só, não duplicado no anexo. Teste: `test_malha_same_calibration_rendered_once` (Task 3).
- **Instrumento que é validador E padrão na mesma OS:** o esperado são três entradas (antes, depois, externo), não duas e nem cinco. Teste: `test_selection_instrument_with_both_roles` (Task 2).

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `models/calibration_instruments.py` | Modify | `afr_role` no certificado, helper `_afr_file_content()`, regra `_afr_select_certificate` no instrumento |
| `views/calibration_instruments_views.xml` | Modify | `afr_role` na tree/form de certificados dentro do form do instrumento |
| `models/qualificacao_malha.py` | Modify | O2M inverso `collect_item_ids` |
| `models/relatorio_certificados.py` | Create | `_afr_certificate_selection`, `_afr_certificate_files`, `_afr_malha_certificate_files`, `certificados_html` |
| `models/__init__.py` | Modify | importar `relatorio_certificados` **depois** de `relatorio` |
| `views/relatorio_certificados_views.xml` | Create | página `page_certificados` no form do relatório |
| `__manifest__.py` | Modify | versão `16.0.8.1.0`, novo XML em `data` |
| `tests/test_relatorio_certificados.py` | Create | `TestRelatorioCertificados` (todas as tasks acrescentam métodos) |
| `tests/__init__.py` | Modify | registrar o arquivo de teste |

---

### Task 1: Papel do certificado + seleção por data no instrumento

**Files:**
- Modify: `models/calibration_instruments.py` (classes `EngcCalibrationInstrumentsCertificates` e `EngcCalibrationInstruments`; imports no topo)
- Modify: `views/calibration_instruments_views.xml` (novo record antes do bloco "F4.3: liga unit_of_measurement")
- Modify: `__manifest__.py` (`"version"`)
- Create: `tests/test_relatorio_certificados.py`
- Modify: `tests/__init__.py`

**Interfaces:**
- Consumes (P1): model `afr.qualificacao.relatorio` com `os_id`, `equipment_id`, `index`, `data_inicio_ensaios`, `data_fim_ensaios`; SQL `unique(os_id, equipment_id)`. Consome também (engc_os, read-only): `engc.calibration.instruments.certificate_ids` e os campos do certificado `certificate_calibration` (Binary), `certificate_number`, `date_calibration`, `validate_calibration`, `superseded_by_id`, `certificate_file_ids` (`file`, `name`).
- Produces:
  - `engc.calibration.instruments.certificates.afr_role`: Selection `[("antes","Antes da campanha"),("depois","Depois da campanha"),("externo","Certificado externo (padrão)")]`, default `"externo"`.
  - `engc.calibration.instruments.certificates._afr_file_content() -> bytes`: decodifica `certificate_calibration`; se vazio, usa o **primeiro** `certificate_file_ids` que tenha `file`; sem nada, `b""`.
  - `engc.calibration.instruments._afr_select_certificate(role: str, date_start: date|False, date_end: date|False)`: devolve um recordset `engc.calibration.instruments.certificates` com 0 ou 1 registro. `ValueError` se `role` for desconhecido.
  - Constante de módulo `AFR_CERT_ROLES` (lista de tuplas da Selection) em `models/calibration_instruments.py`.

- [ ] **Step 0: Conferir pré-requisitos (P1 presente, branch certa)**

Run:
```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git branch --show-current
grep -n '_name = "afr.qualificacao.relatorio"' models/relatorio.py
grep -n '"version"' __manifest__.py
```
Expected: `feat/relatorio-final`; uma linha em `models/relatorio.py`; versão `16.0.8.0.0`. Se P1 não estiver presente, **parar**: P2 depende de P1.

- [ ] **Step 1: Criar o arquivo de teste com fixtures e testes da seleção no instrumento**

Criar `tests/test_relatorio_certificados.py`:

```python
# -*- coding: utf-8 -*-
"""P2 (16.0.8.1.0) — biblioteca de certificados do relatório final.

Cobre: papel do certificado (afr_role), seleção por data no instrumento
(spec §4.4), seleção/arquivos por relatório e certificados de malha (D4).
"""
import base64
import io
from datetime import date, timedelta
from unittest.mock import patch

from PIL import Image

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon

PDF_BYTES = b"%PDF-1.4\n% afr test\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
ENGC_REPORT = "engc_os.report_engc_os_calibration_certificate"


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _b64(raw):
    return base64.b64encode(raw)


@tagged("afr_qualificacao", "relatorio_final", "post_install", "-at_install")
class TestRelatorioCertificados(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.inicio = date(2026, 7, 10)
        cls.fim = date(2026, 7, 12)

        Inst = cls.env["engc.calibration.instruments"]
        cls.validador = Inst.create({"name": "Validador Teste", "id_number": "VT-01"})
        cls.padrao = Inst.create({"name": "Padrão Teste", "id_number": "PT-01"})
        cls.Cert = cls.env["engc.calibration.instruments.certificates"]

        cls.employee = cls.env["hr.employee"].create({"name": "Téc Relatório Teste"})
        cls.os = cls.env["afr.qualificacao.os"].create({
            "tecnico_default_id": cls.employee.id,
            "date_planned_start": "2026-07-10 08:00:00",
            "date_planned_end": "2026-07-12 17:00:00",
        })
        # Qualif + malhas ANTES do relatório: não depender da ordem de
        # recompute de qualificacao_ids (P1).
        cls.qualif = cls.env["afr.qualificacao"].create({
            "name": "Q Calib Relatório",
            "equipment_id": cls.equip1.id,
            "qualification_type": "calibration",
            "os_id": cls.os.id,
            "responsible_id": cls.env.uid,
        })
        Malha = cls.env["afr.qualificacao.malha"]
        cls.malha_t = Malha.create({
            "qualificacao_id": cls.qualif.id,
            "malha_type_id": cls.malha_temp.id,
        })
        cls.malha_p = Malha.create({
            "qualificacao_id": cls.qualif.id,
            "malha_type_id": cls.malha_press.id,
        })

        cls.os.resource_plan_line_ids.unlink()
        PlanLine = cls.env["afr.qualificacao.resource.plan.line"]
        cls.line_val = PlanLine.create({
            "os_id": cls.os.id,
            "resource_role": "validador",
            "instrument_id": cls.validador.id,
        })
        cls.line_pad = PlanLine.create({
            "os_id": cls.os.id,
            "resource_role": "padrao",
            "instrument_id": cls.padrao.id,
        })

        cls.rel = cls.env["afr.qualificacao.relatorio"].create({
            "os_id": cls.os.id,
            "equipment_id": cls.equip1.id,
            "index": 1,
            "data_inicio_ensaios": cls.inicio,
            "data_fim_ensaios": cls.fim,
        })

    # ------------------------------------------------------------------ helpers
    def _cert(self, instrument, role, date_cal, validate=None, number=None,
              content=PDF_BYTES, **extra):
        vals = {
            "instrument_id": instrument.id,
            "afr_role": role,
            "date_calibration": date_cal,
            "validate_calibration": validate or (date_cal + timedelta(days=365)),
            "certificate_number": number,
        }
        if content:
            vals["certificate_calibration"] = _b64(content)
        vals.update(extra)
        return self.Cert.create(vals)

    # ------------------------------------------------ Task 1: instrumento
    def test_afr_role_default_externo(self):
        cert = self.Cert.create({
            "instrument_id": self.padrao.id,
            "date_calibration": self.inicio,
        })
        self.assertEqual(cert.afr_role, "externo")

    def test_select_antes_latest_on_or_before_start(self):
        self._cert(self.validador, "antes", self.inicio - timedelta(days=30), number="CERT-TST-A1")
        on_start = self._cert(self.validador, "antes", self.inicio, number="CERT-TST-A2")
        self._cert(self.validador, "antes", self.inicio + timedelta(days=1), number="CERT-TST-A3")
        got = self.validador._afr_select_certificate("antes", self.inicio, self.fim)
        self.assertEqual(got, on_start, "data igual ao início conta como 'antes'")

    def test_select_antes_none_before_start(self):
        self._cert(self.validador, "antes", self.inicio + timedelta(days=1))
        got = self.validador._afr_select_certificate("antes", self.inicio, self.fim)
        self.assertFalse(got)

    def test_select_depois_earliest_on_or_after_end(self):
        self._cert(self.validador, "depois", self.fim - timedelta(days=1), number="CERT-TST-D0")
        self._cert(self.validador, "depois", self.fim + timedelta(days=5), number="CERT-TST-D5")
        on_end = self._cert(self.validador, "depois", self.fim, number="CERT-TST-D1")
        got = self.validador._afr_select_certificate("depois", self.inicio, self.fim)
        self.assertEqual(got, on_end, "data igual ao fim conta como 'depois'")

    def test_select_externo_requires_validity_window(self):
        self._cert(self.padrao, "externo", self.inicio - timedelta(days=100),
                   validate=self.inicio - timedelta(days=1), number="CERT-TST-EXP")
        boundary = self._cert(self.padrao, "externo", self.inicio - timedelta(days=30),
                              validate=self.inicio, number="CERT-TST-OK")
        self._cert(self.padrao, "externo", self.inicio + timedelta(days=1),
                   number="CERT-TST-FUT")
        got = self.padrao._afr_select_certificate("externo", self.inicio, self.fim)
        self.assertEqual(got, boundary, "validade igual ao início ainda vale")

    def test_select_externo_calibrated_on_start_counts(self):
        same_day = self._cert(self.padrao, "externo", self.inicio, number="CERT-TST-SD")
        got = self.padrao._afr_select_certificate("externo", self.inicio, self.fim)
        self.assertEqual(got, same_day)

    def test_select_externo_without_validity_is_ignored(self):
        cert = self._cert(self.padrao, "externo", self.inicio - timedelta(days=5))
        cert.validate_calibration = False
        got = self.padrao._afr_select_certificate("externo", self.inicio, self.fim)
        self.assertFalse(got)

    def test_select_ignores_superseded(self):
        older = self._cert(self.validador, "antes", self.inicio - timedelta(days=20), number="CERT-TST-OLD")
        newer = self._cert(self.validador, "antes", self.inicio - timedelta(days=2), number="CERT-TST-NEW")
        newer.superseded_by_id = older.id
        got = self.validador._afr_select_certificate("antes", self.inicio, self.fim)
        self.assertEqual(got, older)

    def test_select_ignores_other_roles(self):
        self._cert(self.validador, "externo", self.inicio - timedelta(days=1))
        self._cert(self.validador, "depois", self.inicio - timedelta(days=1))
        got = self.validador._afr_select_certificate("antes", self.inicio, self.fim)
        self.assertFalse(got)

    def test_select_missing_dates_returns_empty(self):
        self._cert(self.validador, "antes", self.inicio - timedelta(days=1))
        self._cert(self.validador, "depois", self.fim + timedelta(days=1))
        self._cert(self.padrao, "externo", self.inicio - timedelta(days=1))
        self.assertFalse(self.validador._afr_select_certificate("antes", False, self.fim))
        self.assertFalse(self.validador._afr_select_certificate("depois", self.inicio, False))
        self.assertFalse(self.padrao._afr_select_certificate("externo", None, None))

    def test_select_unknown_role_raises(self):
        with self.assertRaises(ValueError):
            self.validador._afr_select_certificate("durante", self.inicio, self.fim)

    def test_file_content_prefers_binary(self):
        cert = self._cert(self.padrao, "externo", self.inicio)
        self.assertEqual(cert._afr_file_content(), PDF_BYTES)

    def test_file_content_fallback_skips_rows_without_file(self):
        cert = self._cert(self.padrao, "externo", self.inicio, content=None)
        cert.certificate_file_ids = [
            (0, 0, {"name": "Sem arquivo"}),
            (0, 0, {"name": "EN", "file": _b64(b"%PDF-1.4 english"),
                    "filename": "cert_en.pdf"}),
        ]
        self.assertEqual(cert._afr_file_content(), b"%PDF-1.4 english")

    def test_file_content_empty_when_nothing(self):
        cert = self._cert(self.padrao, "externo", self.inicio, content=None)
        self.assertEqual(cert._afr_file_content(), b"")

    def test_instrument_form_shows_afr_role(self):
        form = self.env.ref("engc_os.calibration_instruments_form")
        arch = self.env["engc.calibration.instruments"].get_view(
            form.id, "form")["arch"]
        self.assertIn('name="afr_role"', arch)
```

Em `tests/__init__.py`, acrescentar no fim:

```python

# Relatório final — P2 (16.0.8.1.0): biblioteca de certificados
from . import test_relatorio_certificados
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioCertificados --stop-after-init --no-http`
Expected: FAIL/ERROR. Os `create` com `afr_role` levantam `ValueError: Invalid field 'afr_role' on model 'engc.calibration.instruments.certificates'`, e as chamadas levantam `AttributeError: ... '_afr_select_certificate'` / `'_afr_file_content'`.

- [ ] **Step 3: Implementar papel, helper de arquivo e seleção**

Em `models/calibration_instruments.py`, trocar o bloco de imports do topo:

```python
from odoo import api, fields, models
```

por:

```python
import base64

from odoo import api, fields, models

# P2 (16.0.8.1.0) — papel do certificado na biblioteca do relatório final.
AFR_CERT_ROLES = [
    ("antes", "Antes da campanha"),
    ("depois", "Depois da campanha"),
    ("externo", "Certificado externo (padrão)"),
]
```

Acrescentar ao docstring do módulo, logo após a linha do F10:

```
P2   (16.0.8.1.0): biblioteca de certificados do relatório final — papel
                    (antes/depois/externo) por certificado e seleção por
                    data de ensaio (spec relatório final §4.4).
```

Na classe `EngcCalibrationInstrumentsCertificates` (a que já tem o hotfix `_compute_is_valid`), acrescentar depois do método `_compute_is_valid`:

```python
    afr_role = fields.Selection(
        AFR_CERT_ROLES,
        string="Papel no relatório",
        default="externo",
        required=True,
        help=(
            "Como este certificado entra no relatório final de qualificação: "
            "'Antes'/'Depois' = calibração do validador pré/pós campanha; "
            "'Externo' = certificado de terceiro do padrão (vigência na data "
            "dos ensaios)."
        ),
    )

    def _afr_file_content(self):
        """Bytes do certificado: binário principal; senão o primeiro arquivo
        de idioma que tenha conteúdo; senão b"". `bin_size=False` garante
        conteúdo e não o tamanho."""
        self.ensure_one()
        rec = self.with_context(bin_size=False)
        if rec.certificate_calibration:
            return base64.b64decode(rec.certificate_calibration)
        for file_rec in rec.certificate_file_ids:
            if file_rec.file:
                return base64.b64decode(file_rec.file)
        return b""
```

Na classe `EngcCalibrationInstruments`, acrescentar antes de `def name_get(self):`:

```python
    # ------------------------------------------------------------------
    # P2 (16.0.8.1.0) — seleção de certificado por data de ensaio
    # ------------------------------------------------------------------
    def _afr_select_certificate(self, role, date_start, date_end):
        """Certificado (0 ou 1) do papel `role` para ensaios em
        [date_start, date_end] — spec §4.4:

        - antes:   afr_role='antes', maior date_calibration <= date_start;
        - depois:  afr_role='depois', menor date_calibration >= date_end;
        - externo: afr_role='externo', date_calibration <= date_start <=
                   validate_calibration (o mais recente).

        Bordas: data igual conta. Substituídos (superseded_by_id) e
        certificados sem date_calibration são ignorados. Data de referência
        ausente → vazio. Empate de data → maior id (cadastro mais recente).
        """
        self.ensure_one()
        empty = self.env["engc.calibration.instruments.certificates"]
        if role not in dict(AFR_CERT_ROLES):
            raise ValueError("Papel de certificado desconhecido: %r" % (role,))
        certs = self.certificate_ids.filtered(
            lambda c: c.afr_role == role
            and not c.superseded_by_id
            and c.date_calibration
        )
        if role == "antes":
            if not date_start:
                return empty
            cands = certs.filtered(lambda c: c.date_calibration <= date_start)
            return cands.sorted(
                key=lambda c: (c.date_calibration, c.id), reverse=True)[:1]
        if role == "depois":
            if not date_end:
                return empty
            cands = certs.filtered(lambda c: c.date_calibration >= date_end)
            return cands.sorted(key=lambda c: (c.date_calibration, -c.id))[:1]
        # externo
        if not date_start:
            return empty
        cands = certs.filtered(
            lambda c: c.validate_calibration
            and c.date_calibration <= date_start <= c.validate_calibration
        )
        return cands.sorted(
            key=lambda c: (c.date_calibration, c.id), reverse=True)[:1]
```

Em `views/calibration_instruments_views.xml`, inserir este record logo **antes** do comentário `<!-- F4.3: liga unit_of_measurement à grandeza (sensor_kind) -->`:

```xml
    <!-- ============================================================== -->
    <!-- P2 (16.0.8.1.0): papel do certificado no relatório final        -->
    <!-- ============================================================== -->
    <record id="view_engc_calibration_instruments_form_afr_role" model="ir.ui.view">
        <field name="name">engc.calibration.instruments.form.afr_role</field>
        <field name="model">engc.calibration.instruments</field>
        <field name="inherit_id" ref="engc_os.calibration_instruments_form"/>
        <field name="priority">97</field>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='certificate_ids']/tree/field[@name='certificate_number']" position="after">
                <field name="afr_role"/>
            </xpath>
            <xpath expr="//field[@name='certificate_ids']/form//field[@name='certificate_partner']" position="after">
                <field name="afr_role"/>
            </xpath>
        </field>
    </record>
```

> `superseded_by_id` já é exibido pelo form do `engc_os`; não duplicar.

Em `__manifest__.py`, trocar `"version": "16.0.8.0.0",` por `"version": "16.0.8.1.0",`.

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioCertificados --stop-after-init --no-http`
Expected: todos os testes de `TestRelatorioCertificados` PASS (15 testes), sem `ERROR` no log de carga das views.

- [ ] **Step 5: Commit**

Commit via agente `git-commit-push`, cwd `addons/afr_qualificacao`, sem push:
- Files: `models/calibration_instruments.py`, `views/calibration_instruments_views.xml`, `__manifest__.py`, `tests/test_relatorio_certificados.py`, `tests/__init__.py`
- Message:
```
feat(relatorio): add certificate role and date-based selection per instrument

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 2: Seleção e arquivos de certificados por relatório

**Files:**
- Create: `models/relatorio_certificados.py`
- Modify: `models/__init__.py` (import **depois** de `from . import relatorio`)
- Modify: `tests/test_relatorio_certificados.py` (acrescentar métodos ao fim da classe)

**Interfaces:**
- Consumes (Task 1): `engc.calibration.instruments._afr_select_certificate(role, date_start, date_end)`, `engc.calibration.instruments.certificates._afr_file_content() -> bytes`, `AFR_CERT_ROLES`. Consumes (P1): `afr.qualificacao.relatorio.os_id`, `data_inicio_ensaios`, `data_fim_ensaios`. Consumes (existente): `afr.qualificacao.os.resource_plan_line_ids` (`resource_role` ∈ `validador`/`padrao`, `instrument_id`, `equipment_ids`). Consumes (P1): `equipment_id`.
- Produces:
  - `afr.qualificacao.relatorio._afr_certificate_selection() -> list[dict]`. Chaves: `instrument` (record), `resource_role` (`"validador"`/`"padrao"`), `role` (`"antes"`/`"depois"`/`"externo"`), `certificate` (record, possivelmente vazio). Ordem: todos os validadores (antes, depois), depois todos os padrões (externo), cada grupo na ordem das linhas do plano. Dedupe por (instrumento, `resource_role`). Só entram linhas com `instrument_id` **e** (`equipment_ids` vazio **ou** `relatorio.equipment_id in equipment_ids`).
  - `afr.qualificacao.relatorio._afr_certificate_files(roles) -> list[tuple[bytes, str, str]]` = `(conteúdo, mimetype, legenda)`, na ordem da seleção, só para `role in roles` com certificado e arquivo presentes. Legenda: `"Certificado <nº|s/nº> — <instrumento> (<rótulo do papel>)"`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim da classe `TestRelatorioCertificados`:

```python
    # ------------------------------------------------ Task 2: relatório
    def _by_key(self, selection):
        return {(s["instrument"].id, s["role"]): s for s in selection}

    def test_selection_shape_and_order(self):
        sel = self.rel._afr_certificate_selection()
        self.assertEqual(
            [(s["instrument"], s["resource_role"], s["role"]) for s in sel],
            [
                (self.validador, "validador", "antes"),
                (self.validador, "validador", "depois"),
                (self.padrao, "padrao", "externo"),
            ],
        )
        for s in sel:
            self.assertEqual(set(s), {"instrument", "resource_role", "role", "certificate"})
            self.assertFalse(s["certificate"], "sem certificados cadastrados → vazio")

    def test_selection_picks_certificates_by_date(self):
        antes = self._cert(self.validador, "antes", self.inicio, number="CERT-TST-A")
        depois = self._cert(self.validador, "depois", self.fim, number="CERT-TST-D")
        externo = self._cert(self.padrao, "externo", self.inicio - timedelta(days=10),
                             number="CERT-TST-E")
        by = self._by_key(self.rel._afr_certificate_selection())
        self.assertEqual(by[(self.validador.id, "antes")]["certificate"], antes)
        self.assertEqual(by[(self.validador.id, "depois")]["certificate"], depois)
        self.assertEqual(by[(self.padrao.id, "externo")]["certificate"], externo)

    def test_selection_skips_lines_without_instrument(self):
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id, "resource_role": "padrao",
        })
        self.assertEqual(len(self.rel._afr_certificate_selection()), 3)

    def test_selection_dedupes_instrument(self):
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id, "resource_role": "validador",
            "instrument_id": self.validador.id,
        })
        self.assertEqual(len(self.rel._afr_certificate_selection()), 3)

    def test_selection_instrument_with_both_roles(self):
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id, "resource_role": "padrao",
            "instrument_id": self.validador.id,
        })
        sel = self.rel._afr_certificate_selection()
        roles_validador = [s["role"] for s in sel if s["instrument"] == self.validador]
        self.assertEqual(roles_validador, ["antes", "depois", "externo"])
        self.assertEqual(len(sel), 4)

    def test_selection_without_dates_all_empty(self):
        self._cert(self.validador, "antes", self.inicio - timedelta(days=1))
        self._cert(self.validador, "depois", self.fim + timedelta(days=1))
        self._cert(self.padrao, "externo", self.inicio - timedelta(days=1))
        self.rel.write({"data_inicio_ensaios": False, "data_fim_ensaios": False})
        sel = self.rel._afr_certificate_selection()
        self.assertEqual(len(sel), 3)
        self.assertFalse(any(s["certificate"] for s in sel))

    def test_selection_excludes_instrument_of_other_equipment(self):
        outro = self.env["engc.calibration.instruments"].create(
            {"name": "Validador Outro Equip", "id_number": "VT-02"})
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id, "resource_role": "validador",
            "instrument_id": outro.id,
            "equipment_ids": [(6, 0, [self.equip2.id])],
        })
        sel = self.rel._afr_certificate_selection()
        self.assertNotIn(outro, [s["instrument"] for s in sel])
        self.assertEqual(len(sel), 3)

    def test_selection_includes_line_for_this_equipment(self):
        proprio = self.env["engc.calibration.instruments"].create(
            {"name": "Padrão Deste Equip", "id_number": "PT-02"})
        self.env["afr.qualificacao.resource.plan.line"].create({
            "os_id": self.os.id, "resource_role": "padrao",
            "instrument_id": proprio.id,
            "equipment_ids": [(6, 0, [self.equip1.id, self.equip2.id])],
        })
        sel = self.rel._afr_certificate_selection()
        self.assertIn(proprio, [s["instrument"] for s in sel])
        self.assertEqual(len(sel), 4)

    def test_selection_includes_line_with_empty_equipment_ids(self):
        # line_val/line_pad do setUpClass não têm equipment_ids → entram.
        self.assertFalse(self.line_val.equipment_ids)
        self.assertFalse(self.line_pad.equipment_ids)
        sel = self.rel._afr_certificate_selection()
        self.assertEqual({s["instrument"] for s in sel}, {self.validador, self.padrao})

    def test_selection_empty_plan(self):
        self.os.resource_plan_line_ids.unlink()
        self.assertEqual(self.rel._afr_certificate_selection(), [])

    def test_files_filter_by_roles(self):
        self._cert(self.validador, "antes", self.inicio, number="CERT-TST-A")
        depois = self._cert(self.validador, "depois", self.fim, number="CERT-TST-D",
                            content=None)
        depois.certificate_file_ids = [
            (0, 0, {"name": "EN", "file": _b64(b"%PDF-1.4 depois")}),
        ]
        self._cert(self.padrao, "externo", self.inicio, number="CERT-TST-E")

        files = self.rel._afr_certificate_files(["antes", "depois"])
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0][0], PDF_BYTES)
        self.assertEqual(files[0][1], "application/pdf")
        self.assertIn("CERT-TST-A", files[0][2])
        self.assertIn("Validador Teste", files[0][2])
        self.assertIn("Antes da campanha", files[0][2])
        self.assertEqual(files[1][0], b"%PDF-1.4 depois")
        self.assertIn("Depois da campanha", files[1][2])

        ext = self.rel._afr_certificate_files(["externo"])
        self.assertEqual(len(ext), 1)
        self.assertIn("CERT-TST-E", ext[0][2])
        self.assertIn("Padrão Teste", ext[0][2])

    def test_files_image_mimetype(self):
        self._cert(self.padrao, "externo", self.inicio, number="CERT-TST-IMG",
                   content=_png_bytes())
        files = self.rel._afr_certificate_files(["externo"])
        self.assertEqual(files[0][1], "image/png")

    def test_files_skip_certificate_without_any_file(self):
        self._cert(self.padrao, "externo", self.inicio, number="CERT-TST-NF",
                   content=None)
        self.assertEqual(self.rel._afr_certificate_files(["externo"]), [])
        # antes/depois ausentes também não geram tupla
        self.assertEqual(self.rel._afr_certificate_files(["antes", "depois"]), [])

    def test_files_caption_without_number(self):
        self._cert(self.padrao, "externo", self.inicio, number=False)
        files = self.rel._afr_certificate_files(["externo"])
        self.assertTrue(files[0][2].startswith("Certificado s/nº — Padrão Teste"))
        self.assertNotIn("False", files[0][2])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioCertificados --stop-after-init --no-http`
Expected: os testes novos dão ERROR com `AttributeError: 'afr.qualificacao.relatorio' object has no attribute '_afr_certificate_selection'` (e `_afr_certificate_files`); os 15 da Task 1 continuam PASS.

- [ ] **Step 3: Implementar o arquivo novo**

Criar `models/relatorio_certificados.py`:

```python
# -*- coding: utf-8 -*-
"""Relatório final — P2 (16.0.8.1.0): biblioteca de certificados.

Seleção automática, por data de ensaio, do certificado de cada instrumento
do plano de recursos da OS (validador → antes + depois; padrão → externo) e
fornecimento dos bytes para a montagem do PDF (P4). Certificados de malha
seguem D4: PDF do report engc_os quando a malha tem calibração vinculada,
senão os arquivos anexados à malha.
"""
import base64

from odoo import models
from odoo.tools.mimetypes import guess_mimetype

from .calibration_instruments import AFR_CERT_ROLES

# resource_role do plano → papéis de certificado exigidos, na ordem do anexo.
_ROLES_BY_RESOURCE = (
    ("validador", ("antes", "depois")),
    ("padrao", ("externo",)),
)


def _mimetype_of(content):
    return guess_mimetype(content, default="application/octet-stream")


class AfrQualificacaoRelatorio(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    # ------------------------------------------------------------------
    # Instrumentos (validador / padrão)
    # ------------------------------------------------------------------
    def _afr_certificate_selection(self):
        """Uma entrada por (instrumento, papel exigido). Validadores
        primeiro, depois padrões, cada grupo na ordem das linhas do plano.
        Só entram linhas com instrumento e que atendem este equipamento
        (equipment_ids vazio = linha da OS inteira); (instrumento,
        resource_role) repetido conta uma vez."""
        self.ensure_one()
        equipment = self.equipment_id
        lines = self.os_id.resource_plan_line_ids.filtered(
            lambda l: l.instrument_id
            and (not l.equipment_ids or equipment in l.equipment_ids)
        )
        result = []
        seen = set()
        for resource_role, cert_roles in _ROLES_BY_RESOURCE:
            for line in lines.filtered(lambda l: l.resource_role == resource_role):
                instrument = line.instrument_id
                key = (instrument.id, resource_role)
                if key in seen:
                    continue
                seen.add(key)
                for role in cert_roles:
                    result.append({
                        "instrument": instrument,
                        "resource_role": resource_role,
                        "role": role,
                        "certificate": instrument._afr_select_certificate(
                            role,
                            self.data_inicio_ensaios,
                            self.data_fim_ensaios,
                        ),
                    })
        return result

    def _afr_certificate_files(self, roles):
        """(bytes, mimetype, legenda) dos certificados selecionados com
        role em `roles` e arquivo presente, na ordem da seleção."""
        self.ensure_one()
        role_labels = dict(AFR_CERT_ROLES)
        files = []
        for entry in self._afr_certificate_selection():
            cert = entry["certificate"]
            if entry["role"] not in roles or not cert:
                continue
            content = cert._afr_file_content()
            if not content:
                continue
            caption = "Certificado %s — %s (%s)" % (
                cert.certificate_number or "s/nº",
                entry["instrument"].display_name,
                role_labels[entry["role"]],
            )
            files.append((content, _mimetype_of(content), caption))
        return files
```

Em `models/__init__.py`, localizar a linha `from . import relatorio` (adicionada por P1) e inserir **logo abaixo** dela:

```python
from . import relatorio_certificados    # Relatório final P2 (16.0.8.1.0)
```

> A ordem importa: dentro do mesmo módulo, a classe com `_name = "afr.qualificacao.relatorio"` precisa ser registrada antes da classe `_inherit`. Senão o load falha com `TypeError: Model 'afr.qualificacao.relatorio' does not exist in registry`.

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioCertificados --stop-after-init --no-http`
Expected: PASS (29 testes).

- [ ] **Step 5: Commit**

Commit via agente `git-commit-push`, cwd `addons/afr_qualificacao`, sem push:
- Files: `models/relatorio_certificados.py`, `models/__init__.py`, `tests/test_relatorio_certificados.py`
- Message:
```
feat(relatorio): select instrument certificates and expose their files

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 3: Certificados das malhas (híbrido engc_os / anexos)

**Files:**
- Modify: `models/qualificacao_malha.py` (campo novo, logo após `collected_without_relatorio`)
- Modify: `models/relatorio_certificados.py` (constante + método novo)
- Modify: `tests/test_relatorio_certificados.py` (acrescentar métodos)

**Interfaces:**
- Consumes (P1): `afr.qualificacao.relatorio.qualificacao_ids`. Consumes (existente): `afr.qualificacao.malha.engc_calibration_measurement_id` → `engc.calibration.measurement.calibration_id`; `afr.qualificacao.collect.item` (`malha_id`, `file`, `mimetype`, `name`, `sequence`); report xmlid `engc_os.report_engc_os_calibration_certificate` (model `engc.calibration`).
- Produces:
  - `afr.qualificacao.malha.collect_item_ids`: O2M `afr.qualificacao.collect.item` por `malha_id`. **Não existia**, e o contrato o pressupõe.
  - `afr.qualificacao.relatorio._afr_malha_certificate_files() -> list[tuple[bytes, str, str]]`. Para cada malha de `qualificacao_ids.malha_ids` (na ordem): se tem calibração `engc_os`, gera o PDF do report dela (**uma vez por calibração**, legenda `"Certificado de calibração <cal.name> — <malha>"`); senão usa os `collect_item_ids` com `file` e mimetype PDF ou `image/*`, ordenados por `(sequence, id)`, com legenda `"<item> — <malha>"`. Outros mimetypes são ignorados.
  - Constante de módulo `ENGC_CALIBRATION_REPORT = "engc_os.report_engc_os_calibration_certificate"` em `models/relatorio_certificados.py`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim da classe `TestRelatorioCertificados`:

```python
    # ------------------------------------------------ Task 3: malhas
    def _engc_calibration(self):
        # Obrigatórios do engc_os: client_id, equipment_id, technician_id,
        # date_calibration, measurement_procedure (M2O required) e
        # instruments_ids (M2M required; o domínio do instrumento da medição
        # sai daqui).
        procedure = self.env["engc.calibration.measurement.procedure"].create({
            "codigo": "PROC-TST",
            "description": "Procedimento Teste",
        })
        return self.env["engc.calibration"].create({
            "client_id": self.partner.id,
            "equipment_id": self.equip1.id,
            "technician_id": self.employee.id,
            "date_calibration": self.inicio,
            "measurement_procedure": procedure.id,
            "instruments_ids": [(6, 0, [self.padrao.id])],
        })

    def _link_malha(self, malha, calibration):
        meas = self.env["engc.calibration.measurement"].create({
            "calibration_id": calibration.id,
            "instrument_id": self.padrao.id,
        })
        malha.engc_calibration_measurement_id = meas.id
        return meas

    def _item(self, malha, name, content, mimetype, sequence=10):
        vals = {
            "qualif_id": self.qualif.id,
            "malha_id": malha.id,
            "name": name,
            "kind": "pdf",
            "sequence": sequence,
            "mimetype": mimetype,
        }
        if content:
            vals["file"] = _b64(content)
        return self.env["afr.qualificacao.collect.item"].create(vals)

    def _patch_report(self):
        Report = type(self.env["ir.actions.report"])
        return patch.object(
            Report, "_render_qweb_pdf",
            return_value=(b"%PDF-1.4 engc-cert", "pdf"),
        )

    def test_engc_report_xmlid_exists(self):
        report = self.env.ref(ENGC_REPORT)
        self.assertEqual(report.model, "engc.calibration")

    def test_malha_collect_item_ids_inverse(self):
        item = self._item(self.malha_t, "Cert malha T", PDF_BYTES, "application/pdf")
        self.assertIn(item, self.malha_t.collect_item_ids)
        self.assertNotIn(item, self.malha_p.collect_item_ids)

    def test_malha_files_from_engc_calibration(self):
        cal = self._engc_calibration()
        self._link_malha(self.malha_t, cal)
        with self._patch_report() as render:
            files = self.rel._afr_malha_certificate_files()
        render.assert_called_once()
        self.assertEqual(render.call_args.args, (ENGC_REPORT, [cal.id]))
        self.assertEqual(len(files), 1, "malha_p sem calibração e sem arquivo → nada")
        content, mimetype, caption = files[0]
        self.assertEqual(content, b"%PDF-1.4 engc-cert")
        self.assertEqual(mimetype, "application/pdf")
        self.assertIn(cal.name, caption)
        self.assertIn(self.malha_t.display_name, caption)

    def test_malha_same_calibration_rendered_once(self):
        cal = self._engc_calibration()
        self._link_malha(self.malha_t, cal)
        self._link_malha(self.malha_p, cal)
        with self._patch_report() as render:
            files = self.rel._afr_malha_certificate_files()
        render.assert_called_once()
        self.assertEqual(len(files), 1)

    def test_malha_engc_wins_over_collect_items(self):
        cal = self._engc_calibration()
        self._link_malha(self.malha_t, cal)
        self._item(self.malha_t, "PDF anexado", PDF_BYTES, "application/pdf")
        with self._patch_report():
            files = self.rel._afr_malha_certificate_files()
        self.assertEqual([f[0] for f in files], [b"%PDF-1.4 engc-cert"])

    def test_malha_files_fallback_collect_items(self):
        png = _png_bytes()
        self._item(self.malha_t, "Foto certificado", png, "image/png", sequence=20)
        self._item(self.malha_t, "PDF certificado", PDF_BYTES, "application/pdf", sequence=10)
        self._item(self.malha_t, "Planilha", b"a;b\n1;2\n", "text/csv", sequence=5)
        self._item(self.malha_t, "Pendente", None, "application/pdf", sequence=1)
        with self._patch_report() as render:
            files = self.rel._afr_malha_certificate_files()
        render.assert_not_called()
        self.assertEqual([f[1] for f in files], ["application/pdf", "image/png"])
        self.assertEqual(files[0][0], PDF_BYTES)
        self.assertEqual(files[1][0], png)
        self.assertIn("PDF certificado", files[0][2])
        self.assertIn(self.malha_t.display_name, files[0][2])

    def test_malha_files_guess_mimetype_when_missing(self):
        self._item(self.malha_p, "Sem mimetype", PDF_BYTES, False)
        with self._patch_report():
            files = self.rel._afr_malha_certificate_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0][1], "application/pdf")

    def test_malha_files_empty_without_malhas_data(self):
        with self._patch_report() as render:
            self.assertEqual(self.rel._afr_malha_certificate_files(), [])
        render.assert_not_called()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioCertificados --stop-after-init --no-http`
Expected: os testes novos dão ERROR. `test_malha_collect_item_ids_inverse` falha com `AttributeError: 'afr.qualificacao.malha' object has no attribute 'collect_item_ids'`, e os demais com `AttributeError: ... '_afr_malha_certificate_files'`. `test_engc_report_xmlid_exists` já passa.

- [ ] **Step 3: Implementar**

Em `models/qualificacao_malha.py`, logo após a definição do campo `collected_without_relatorio` (o bloco `collected_without_relatorio = fields.Boolean(...)`), acrescentar:

```python
    # Relatório final P2 (16.0.8.1.0) — inverso de collect.item.malha_id;
    # fonte dos certificados de malha quando não há calibração engc_os.
    collect_item_ids = fields.One2many(
        "afr.qualificacao.collect.item",
        "malha_id",
        string="Itens de Coleta",
    )
```

Em `models/relatorio_certificados.py`, logo abaixo de `_ROLES_BY_RESOURCE = (...)`, acrescentar:

```python
# Report QWeb do certificado de calibração do engc_os (model engc.calibration).
ENGC_CALIBRATION_REPORT = "engc_os.report_engc_os_calibration_certificate"
```

E, ao fim da classe `AfrQualificacaoRelatorio`, acrescentar:

```python
    # ------------------------------------------------------------------
    # Malhas de controle (D4 — híbrido)
    # ------------------------------------------------------------------
    def _afr_malha_certificate_files(self):
        """Por malha dos qualificacao_ids: PDF do certificado engc_os quando
        há calibração vinculada (uma vez por calibração); senão PDFs/imagens
        dos itens de coleta da malha."""
        self.ensure_one()
        Report = self.env["ir.actions.report"].sudo()
        files = []
        rendered = set()
        for malha in self.qualificacao_ids.mapped("malha_ids"):
            calibration = malha.engc_calibration_measurement_id.calibration_id
            if calibration:
                if calibration.id in rendered:
                    continue
                rendered.add(calibration.id)
                pdf, _fmt = Report._render_qweb_pdf(
                    ENGC_CALIBRATION_REPORT, [calibration.id])
                caption = "Certificado de calibração %s — %s" % (
                    calibration.name, malha.display_name)
                files.append((pdf, "application/pdf", caption))
                continue
            items = malha.collect_item_ids.with_context(bin_size=False).sorted(
                key=lambda i: (i.sequence, i.id))
            for item in items:
                if not item.file:
                    continue
                content = base64.b64decode(item.file)
                mimetype = item.mimetype or _mimetype_of(content)
                if mimetype != "application/pdf" and not mimetype.startswith("image/"):
                    continue
                caption = "%s — %s" % (item.name, malha.display_name)
                files.append((content, mimetype, caption))
        return files
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioCertificados --stop-after-init --no-http`
Expected: PASS (37 testes). Rodar também a classe vizinha que toca malha, para garantir que nada regrediu: `--test-tags /afr_qualificacao:TestAuthorizationScope` → PASS.

- [ ] **Step 5: Commit**

Commit via agente `git-commit-push`, cwd `addons/afr_qualificacao`, sem push:
- Files: `models/qualificacao_malha.py`, `models/relatorio_certificados.py`, `tests/test_relatorio_certificados.py`
- Message:
```
feat(relatorio): provide malha certificates from engc_os report or collect files

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 4: Aba "Certificados" no form do relatório

**Files:**
- Modify: `models/relatorio_certificados.py` (imports + campo computado + helper HTML)
- Create: `views/relatorio_certificados_views.xml`
- Modify: `__manifest__.py` (`data`)
- Modify: `tests/test_relatorio_certificados.py` (acrescentar métodos)

**Interfaces:**
- Consumes (Task 2): `_afr_certificate_selection()`. Consumes (P1): form `afr_qualificacao.view_afr_qualificacao_relatorio_form` (em `views/relatorio_views.xml`) com `<notebook>` e página `name="page_ciclos"`.
- Produces:
  - `afr.qualificacao.relatorio.certificados_html`: Html computado, não armazenado, `sanitize=False`.
  - `afr.qualificacao.relatorio._afr_certificados_html() -> Markup`.
  - Página `name="page_certificados"` (só leitura), inserida depois de `page_ciclos`. Planos seguintes podem usar xpath nesse `name`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim da classe `TestRelatorioCertificados`:

```python
    # ------------------------------------------------ Task 4: aba
    def _html(self):
        self.rel.invalidate_recordset(["certificados_html"])
        return str(self.rel.certificados_html or "")

    def test_html_lists_selection(self):
        self._cert(self.validador, "antes", self.inicio, number="CERT-TST-HA",
                   validate=date(2027, 7, 10))
        html = self._html()
        self.assertIn("Validador Teste", html)
        self.assertIn("Padrão Teste", html)
        self.assertIn("CERT-TST-HA", html)
        self.assertIn("Antes da campanha", html)
        self.assertIn("10/07/2026", html)
        self.assertIn("10/07/2027", html)
        self.assertIn("AUSENTE", html, "depois/externo sem certificado")

    def test_html_marks_missing_when_validator_only_has_externo(self):
        # Base existente após -u: certificado antigo nasce 'externo'.
        self._cert(self.validador, "externo", self.inicio - timedelta(days=5),
                   number="CERT-TST-LEGADO")
        html = self._html()
        self.assertEqual(html.count("AUSENTE"), 3)
        self.assertNotIn("CERT-TST-LEGADO", html)

    def test_html_empty_plan(self):
        self.os.resource_plan_line_ids.unlink()
        self.assertIn("Nenhum instrumento", self._html())

    def test_html_escapes_names(self):
        self.validador.name = "<b>Val</b>"
        html = self._html()
        self.assertIn("&lt;b&gt;Val&lt;/b&gt;", html)
        self.assertNotIn("<b>Val</b>", html)

    def test_form_has_page_certificados(self):
        form = self.env.ref("afr_qualificacao.view_afr_qualificacao_relatorio_form")
        arch = self.env["afr.qualificacao.relatorio"].get_view(form.id, "form")["arch"]
        self.assertIn('name="page_certificados"', arch)
        self.assertIn('name="certificados_html"', arch)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioCertificados --stop-after-init --no-http`
Expected: os testes novos falham. Os de HTML dão `AttributeError: ... 'certificados_html'`, e `test_form_has_page_certificados` dá `AssertionError: 'name="page_certificados"' not found`.

- [ ] **Step 3: Implementar campo, HTML e view**

Em `models/relatorio_certificados.py`, trocar os imports:

```python
import base64

from odoo import models
from odoo.tools.mimetypes import guess_mimetype
```

por:

```python
import base64

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.tools.mimetypes import guess_mimetype
```

Dentro da classe `AfrQualificacaoRelatorio`, logo após `_inherit = "afr.qualificacao.relatorio"`, acrescentar:

```python
    certificados_html = fields.Html(
        string="Certificados",
        compute="_compute_certificados_html",
        sanitize=False,
        help=(
            "Certificados escolhidos automaticamente pelas datas dos ensaios "
            "para os instrumentos do plano de recursos da OS."
        ),
    )

    @api.depends(
        "data_inicio_ensaios",
        "data_fim_ensaios",
        "os_id.resource_plan_line_ids.instrument_id",
        "os_id.resource_plan_line_ids.resource_role",
        "os_id.resource_plan_line_ids.instrument_id.certificate_ids.afr_role",
        "os_id.resource_plan_line_ids.instrument_id.certificate_ids.date_calibration",
        "os_id.resource_plan_line_ids.instrument_id.certificate_ids.validate_calibration",
        "os_id.resource_plan_line_ids.instrument_id.certificate_ids.superseded_by_id",
    )
    def _compute_certificados_html(self):
        for rel in self:
            rel.certificados_html = rel._afr_certificados_html()

    def _afr_certificados_html(self):
        """Tabela só de leitura da seleção; 'AUSENTE' em vermelho quando
        não há certificado para o papel exigido."""
        self.ensure_one()
        selection = self._afr_certificate_selection() if self.os_id else []
        if not selection:
            return Markup(
                '<p class="text-muted">Nenhum instrumento no plano de recursos '
                'da OS. Gere/ajuste o plano de recursos para listar os '
                'certificados.</p>')
        role_labels = dict(AFR_CERT_ROLES)
        resource_labels = dict(
            self.env["afr.qualificacao.resource.plan.line"]
            ._fields["resource_role"].selection)

        def fmt(value):
            return value.strftime("%d/%m/%Y") if value else "—"

        rows = Markup("")
        for entry in selection:
            cert = entry["certificate"]
            if cert:
                number = escape(cert.certificate_number or "s/nº")
                cal_date = escape(fmt(cert.date_calibration))
                validity = escape(fmt(cert.validate_calibration))
            else:
                number = Markup(
                    '<span style="color:#c00;font-weight:bold;">AUSENTE</span>')
                cal_date = validity = Markup("—")
            rows += (
                Markup("<tr><td>") + escape(entry["instrument"].display_name)
                + Markup("</td><td>")
                + escape(resource_labels.get(entry["resource_role"], ""))
                + Markup("</td><td>") + escape(role_labels[entry["role"]])
                + Markup("</td><td>") + number
                + Markup("</td><td>") + cal_date
                + Markup("</td><td>") + validity
                + Markup("</td></tr>")
            )
        return (
            Markup(
                '<table class="table table-sm table-bordered o_afr_cert_table">'
                "<thead><tr><th>Instrumento</th><th>Papel no plano</th>"
                "<th>Certificado exigido</th><th>Nº</th><th>Calibração</th>"
                "<th>Validade</th></tr></thead><tbody>")
            + rows
            + Markup("</tbody></table>")
        )
```

Criar `views/relatorio_certificados_views.xml` (herda `afr_qualificacao.view_afr_qualificacao_relatorio_form`, de P1):

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Relatório final P2 (16.0.8.1.0): aba de certificados (só leitura) -->
    <record id="view_afr_qualificacao_relatorio_form_certificados" model="ir.ui.view">
        <field name="name">afr.qualificacao.relatorio.form.certificados</field>
        <field name="model">afr.qualificacao.relatorio</field>
        <field name="inherit_id" ref="afr_qualificacao.view_afr_qualificacao_relatorio_form"/>
        <field name="arch" type="xml">
            <xpath expr="//page[@name='page_ciclos']" position="after">
                <page string="Certificados" name="page_certificados">
                    <field name="certificados_html" readonly="1" nolabel="1"/>
                    <div class="text-muted small">
                        Seleção automática pelas datas dos ensaios:
                        <b>antes</b> = último certificado do validador até o
                        início; <b>depois</b> = primeiro certificado do
                        validador a partir do fim; <b>padrão</b> = certificado
                        externo vigente no início. Para corrigir, ajuste o
                        papel e as datas dos certificados no cadastro do
                        instrumento.
                    </div>
                </page>
            </xpath>
        </field>
    </record>
</odoo>
```

Em `__manifest__.py`, na lista `data`, inserir **logo após** a linha `"views/relatorio_views.xml",` (views do relatório, de P1):

```python
        # Relatório final P2 — aba Certificados
        "views/relatorio_certificados_views.xml",
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioCertificados --stop-after-init --no-http`
Expected: PASS (42 testes), sem erro de validação de view no log.

Depois, a suíte inteira do módulo, via agente `test-runner`: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao --stop-after-init --no-http`
Expected: só as 3 falhas pré-existentes conhecidas (ver Global Constraints).

- [ ] **Step 5: Validar a UI via agent-browser**

Reiniciar o container para os assets, fazer login (logout antes de re-logar) em `http://localhost:8083`, abrir um relatório final e conferir que a aba **Certificados** aparece depois de **Ciclos**, mostrando a tabela ou a mensagem "Nenhum instrumento…". Abrir um instrumento em Qualificações › Configurações › Padrões Metrológicos e conferir a coluna/campo **Papel no relatório** na lista e no form de certificado.

- [ ] **Step 6: Commit**

Commit via agente `git-commit-push`, cwd `addons/afr_qualificacao`, sem push:
- Files: `models/relatorio_certificados.py`, `views/relatorio_certificados_views.xml`, `__manifest__.py`, `tests/test_relatorio_certificados.py`
- Message:
```
feat(relatorio): show selected certificates tab on final report form

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

## Self-Review (feito na escrita)

- **Cobertura do contrato P2:** `afr_role` (T1), `_afr_select_certificate` (T1), `_afr_certificate_selection` (T2), `_afr_certificate_files` (T2), `_afr_malha_certificate_files` (T3), `page_certificados` (T4), manifest `16.0.8.1.0` (T1). Spec §4.4: regras antes/depois/externo com borda igual (T1); instrumentos de `os_id.resource_plan_line_ids.instrument_id`, filtrados pelo equipamento do relatório (`equipment_ids` vazio ou contendo o equipamento) (T2). D4 híbrido (T3). D5 "emissão bloqueada sem depois" fica em P5 (`CERT_DEPOIS_AUSENTE`), que consome `_afr_certificate_selection`.
- **Placeholders:** nenhum.
- **Consistência de nomes:** `AFR_CERT_ROLES`, `_afr_file_content`, `ENGC_CALIBRATION_REPORT`, `_afr_certificados_html` e `certificados_html` são usados com o mesmo nome em todas as tasks.
- **Review Focus:** as 5 linhas têm teste na task dona do código.

## Notas para P4/P5

- `_afr_certificate_files` e `_afr_malha_certificate_files` não fazem sudo nos certificados, porque o ACL do `engc_os` libera `base.group_user`. Só o render do report `engc_os` roda com `sudo()`.
- A seleção considera só linhas do plano com instrumento e com `equipment_ids` vazio ou contendo `relatorio.equipment_id` (decisão do contrato atualizado). As regras `CERT_*` do P5 herdam esse recorte.
