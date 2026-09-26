# Relatório Final — P5: Varredura (regras + IA) + Gate de Emissão — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Antes de emitir um Relatório Final, rodar uma varredura de inconsistências (17 regras determinísticas + revisão assistiva por IA via OpenRouter), registrar os achados com decisão humana e impedir a emissão enquanto houver bloqueio ou alerta (de regra ou de IA) sem decisão.

**Architecture:** Um model persistente `afr.relatorio.achado` guarda cada achado com a decisão. As regras são funções puras em `models/relatorio_rules.py`, reunidas no registro `RULES` e executadas por `run_rules()`, que isola cada regra num savepoint e trata falha como bloqueio. A IA fica num AbstractModel `afr.relatorio.ai`, com cliente HTTP `requests`, chunking e parse tolerante. Ela só entra quando está ligada e nunca gera `bloqueia`, mas seus alertas precisam de decisão como os de regra. `afr.qualificacao.relatorio` ganha `action_verificar()`, que recria os achados pendentes e herda as decisões já tomadas, e estende `_check_emission_gate()`/`_scan_snapshot()` de P4. Quem emite roda de novo a verificação, só com as regras, antes de decidir.

**Tech Stack:** Odoo 16.0 (Python 3.9 no container), `requests`, `pdfminer.six 20200726` (`pdfminer.high_level.extract_text`), `reportlab 3.5` (só em testes, para gerar PDFs sintéticos), `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-09-26-relatorio-final-qualificacao-design.md` (§7 inteiro, §4.6, §9, §10, §11). **Índice + contrato:** `docs/superpowers/plans/2026-09-26-relatorio-final-00-indice.md`. Os nomes do contrato são obrigatórios.

## Global Constraints

- Odoo **16.0**. Módulo `afr_qualificacao` é **git submodule** em `addons/afr_qualificacao/`. Trabalhar na branch `feat/relatorio-final` **dentro do submodule** (já existe, criada em P1).
- P1–P4 já estão implementados e verdes antes de começar P5. Os únicos pontos de apoio são os nomes do contrato do índice: `_afr_certificate_selection()`, `afr.relatorio.anexo._resolve_files()` / `_check_files()`, `_render_block_body(block)`, `_anexo_number(code)`, `_check_emission_gate()`, `_scan_snapshot()`, `action_emitir()`, `action_aprovar_interno()`, `PROBLEM_EMPTY` (`models/relatorio_anexo_files.py`), `tests/relatorio_fakes.py::FakeCorpo`, `cycle_ids`, `janela_inicio/fim`, `sensor_pos_ids`, `leitura_ib_ids`, `indicador_ids`, `checklist_ids`, `aprovacao_ids`, `anexo_ids`, `block_ids`.
- **Fatos de P4 (plano `2026-09-26-relatorio-final-p4-montagem-emissao.md`, confirmados — não redescobrir):**
  - Form do relatório: xmlid `afr_qualificacao.view_afr_qualificacao_relatorio_form`; P4 adiciona `page_revisoes` no fim do notebook e os botões do header antes do statusbar.
  - `action_emitir()` falha no gate com **`UserError`** `"Não é possível emitir o relatório <name>:\n- <problema>…"`; é manager-only via `_check_manager_only` (passa com `env.su`).
  - `action_aprovar_interno()` aprova **todas** as linhas elaborador/emissor pendentes com `user_id == env.user` numa única chamada (UserError se não houver nenhuma).
  - `afr.relatorio.anexo._check_files()` → itens `PROBLEM_EMPTY` (constante em `models/relatorio_anexo_files.py`) **ou** `"<legenda>: <motivo>"`. `ANEXO_VAZIO` ⇔ `PROBLEM_EMPTY` na lista; `ANEXO_ILEGIVEL` ⇔ qualquer outro item (anexo com todos os arquivos ilegíveis → ILEGIVEL, não VAZIO).
  - `slot_kind='bloco'` → `_resolve_files()` devolve `[]` por design (conteúdo sai no corpo): as regras **pulam** anexos `bloco`.
  - `_invalidate_internal_approvals()` dispara em `write` do relatório nos campos `equipment_id, template_id, data_inicio_ensaios, data_fim_ensaios, amb_temperatura, amb_umidade, tolerancia_acima, criterio_f0_fator, block_ids, anexo_ids, checklist_ids, indicador_ids, leitura_ib_ids`, em create/write/unlink de block/anexo/checklist/indicador/leitura.ib/sensor.pos e em write de `janela_inicio/janela_fim/sensor_pos_ids` do ciclo; **não** em `achado_ids` nem `minuta_attachment_id`. Nas fixtures: montar os dados **antes** de aprovar.
  - Testes que emitem fazem patch de `ir.actions.report._render_qweb_pdf` com `tests/relatorio_fakes.py::FakeCorpo` (`with FakeCorpo().patch(self.env): ...`), como os testes de P4 — em modo teste o `_render_qweb_pdf` real devolve HTML. **Não** mockar `afr.relatorio.pdf.build`.
  - `_apply_template()` não roda no create: a fixture de P5 não o chama (parte de relatório sem blocos/anexos/aprovações e cria só o que cada teste exercita).
- Commits sempre de dentro de `addons/afr_qualificacao/`, via agente `git-commit-push` (haiku), com paths relativos ao submodule. **Não** fazer push nem bump do pointer no monorepo sem o usuário pedir. Mensagens em inglês, Conventional Commits, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Testes do orquestrador rodam pelo agente `test-runner` (sonnet). Comando base: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:<Classe> --stop-after-init --no-http`. `-u` é obrigatório (P5 cria model e XML); `--no-http` também. Falhas pré-existentes conhecidas, que devem ser ignoradas: `TestResourcePlan.test_fleet_single_logger_two_temp_standards`, `TestProposalReport.test_render_equipment_scope_omits_cronograma_footer`, `TestProposalReport.test_render_schedule_block`.
- Novos testes herdam de `tests/common.py::AfrQualificacaoTestCommon`, via a nova base `tests/common_relatorio.py::RelatorioTestCommon`. Cada arquivo novo é registrado em `tests/__init__.py`.
- Todo model novo entra em `models/__init__.py` e em `security/ir.model.access.csv`. **Exceção deliberada** para `afr.relatorio.achado`: user fica em `1,1,1,0` (sem unlink), e a troca de achados dentro de `action_verificar()` roda em `sudo()`.
- Grupos: `afr_qualificacao.group_afr_qualificacao_technician`, `..._user`, `..._manager`.
- **Nunca** usar nomes de clientes, pessoas ou números de certificado reais de `dados_sensiveis/`. Usar "Cliente Teste", "Eng. Responsável", "Logger Teste".
- **Nunca** gravar chave de API em arquivo versionado: código, testes, docs, checklist, seeds. Nos testes, a chave é o literal `"sk-test"`.
- `engc_os` está **congelado**; P5 não toca em `engenapp/engc_os/`. O PWA (`pwa/`) não muda.
- Não adicionar dependência pip. `requests` e `pdfminer.six` já estão no container.
- Manifest ao final de P5: `"version": "16.0.8.4.0"`. P5 não cria seed, então não há `migrations/16.0.8.4.0/`.
- Textos de UI e mensagens de achado em pt-BR.
- Parâmetros de IA em `ir.config_parameter`, exatamente como na spec §7.2: `afr_qualificacao.ai_enabled` (default `False`), `afr_qualificacao.ai_api_key`, `afr_qualificacao.ai_model` (default `google/gemma-4-31b-it`), `afr_qualificacao.ai_timeout` (default `60`). Endpoint `https://openrouter.ai/api/v1/chat/completions`, com headers `Authorization: Bearer <key>` e `Content-Type: application/json`, igual ao PWA (`pwa/lib/llm/client.ts`).
- Limite de chunk para a IA: **12000** caracteres por trecho (`MAX_CHUNK_CHARS`).

### Decisões de interpretação da spec (valem para todas as tasks)

1. **Achado `bloqueia` não aceita decisão.** Uma constraint impede `procede`/`descartado` quando `gravidade='bloqueia'`, e a única saída é corrigir o dado e verificar de novo. Esta é a leitura de §7.3 ("nenhum bloqueia pendente") que não permite descartar `CERT_DEPOIS_AUSENTE` e furar D5.
2. **Carry-over literal.** Ao verificar de novo, um achado já decidido (`procede` ou `descartado`) cuja chave `(origem, codigo, onde)` volta a aparecer mantém a decisão, e só `mensagem`/`gravidade` são atualizadas. Se a nova gravidade for `bloqueia`, a decisão volta para `pendente`. Um achado decidido que não se repete é apagado. Os pendentes são sempre recriados.
3. **Todo `alerta` precisa de decisão antes de emitir, venha de regra ou de IA** (§7.3). O gate ignora apenas `info`. A IA nunca gera `bloqueia` (§7.2): gravidade vinda da IA é forçada para `alerta`/`info`. Na prática, um alerta de IA pendente segura a emissão até ser decidido (procede, ou descartado com motivo).
4. **Na emissão, a verificação roda só com as regras** (contexto `afr_skip_ai`), para ser determinística. Os achados de IA que já existem ficam intactos (com a decisão), continuam valendo no gate e entram no `scan_snapshot`.
5. **`APROVACAO_INTERNA`** só roda com o contexto `afr_emission_check`. No gate ela é ignorada ao montar a lista de impedimentos, porque o `super()` de P4 já relata aprovações internas faltantes.
6. **Regra que lança exceção** vira achado `bloqueia` com o próprio código da regra ("Falha ao executar a regra…"). A exceção é registrada no log e a regra roda num savepoint, para não abortar o cursor.
7. **`CANAL_SEM_CERT`, heurística:** extrai o primeiro grupo de dígitos do `canal` (`"CH006"` → 6, `"CH0106"` → 106) e marca o canal quando esse número é maior que a **capacidade total de canais dos validadores do plano de recursos** (soma de `measurement_capacity_ids.qty` dos instrumentos nas linhas `resource_role='validador'`). Canal sem dígitos é ignorado, e sem validador no plano a regra fica silenciosa (quem cobre esse caso é `CERT_DEPOIS_AUSENTE`). A notação módulo+canal do Yokogawa (`CH0106` = módulo 01 canal 06) pode gerar falso alerta. Como é só `alerta`, basta decidir, e o ponto fica registrado no TODO.
8. **`CERT_DEPOIS_AUSENTE` sem validador no plano** gera um único achado bloqueante ("Nenhum validador no plano de recursos"), senão uma OS sem plano emitiria sem comprovar calibração (D5).
9. **Datas de ensaio vazias:** `CERT_ANTES_AUSENTE` gera um bloqueio "Datas de início/fim dos ensaios não preenchidas". `CERT_DEPOIS_AUSENTE`, `PADRAO_VENCIDO` e `DATA_FORA_JANELA` ficam silenciosas nesse caso, para não repetir a causa.
10. **Chave de carry-over:** `onde` é estável e identifica o objeto. Onde um rótulo pode se repetir (ciclo, bloco, coleta, linha de checklist), inclui `[#<id>]`.

## Review Focus

- **Captura perto da meia-noite (fuso):** um item capturado às 22:30 de Brasília no último dia de ensaio (01:30 UTC do dia seguinte) **não** pode gerar `DATA_FORA_JANELA`. A data é comparada no fuso do usuário (`context_timestamp`). O teste fica na Task 3.
- **Decidir um achado pelo form** (`rel.write({"achado_ids": [(1, id, {...})]})`) **não** pode zerar aprovações internas já dadas, que P4 zera em escrita editorial. O teste fica na Task 6.
- **Uma regra com bug** não pode derrubar o botão Verificar nem passar em silêncio: vira achado bloqueante e as demais regras seguem rodando. O teste fica na Task 2.
- **OS sem validador no plano de recursos** tem que bloquear a emissão, e não passar por falta de linhas para checar. O teste fica na Task 2.
- **IA fora do ar com vários anexos:** a primeira falha de rede interrompe as chamadas seguintes (sem somar N × timeout) e gera um único `IA_INDISPONIVEL`. O teste fica na Task 5.

Também foi verificado, sem virar item do Review Focus: referência `anexo('x')` gravada com aspas escapadas em HTML (`&#39;`) continua sendo detectada (teste na Task 3). `procede` não exige motivo, por decisão da spec, que só exige motivo em `descartado`, e isso fica registrado aqui para o revisor.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `models/relatorio_achado.py` | Create | Model `afr.relatorio.achado`: campos, guard de create/write, carimbo de decisão, constraints |
| `models/relatorio_rules.py` | Create | Funções puras das 17 regras, registro `RULES`, `run_rules()`, helper `cycle_counts()` |
| `models/relatorio_ai.py` | Create | AbstractModel `afr.relatorio.ai`: config, chunking, prompt, `_call`, parse tolerante, `review()` |
| `models/relatorio_verificacao.py` | Create | `_inherit` de `afr.qualificacao.relatorio`: `achado_ids`, `has_blocking`, `blocking_summary`, `action_verificar`, overrides de gate/snapshot |
| `models/res_config_settings.py` | Modify | 4 campos de IA |
| `models/__init__.py` | Modify | imports |
| `security/ir.model.access.csv` | Modify | ACL do achado |
| `views/relatorio_verificacao_views.xml` | Create | botão Verificar, banner "Aguardando", página `page_verificacao` |
| `views/res_config_settings_views.xml` | Modify | bloco "Verificação por IA" |
| `__manifest__.py` | Modify | versão `16.0.8.4.0` e view nova |
| `tests/common_relatorio.py` | Create | fixtures compartilhadas (OS, QD, relatório, validador, certificado, anexo, bloco, PDF sintético) |
| `tests/test_relatorio_rules.py` | Create | regras: positivo e negativo de cada uma |
| `tests/test_relatorio_ai.py` | Create | IA com `requests.post` mockado + settings |
| `tests/test_relatorio_gate.py` | Create | model achado, verificar/carry-over, gate, snapshot na emissão |
| `tests/__init__.py` | Modify | registra os 3 arquivos |
| `TODO.md` | Modify | itens fora de escopo da §11 |
| `docs/RELATORIO_FINAL_TEST_CHECKLIST.md` | Create | aceite manual via agent-browser |

---

### Task 1: Model `afr.relatorio.achado` + ACL + fixtures de teste

**Files:**
- Create: `models/relatorio_achado.py`
- Create: `models/relatorio_verificacao.py` (só `achado_ids` e os computes de bloqueio nesta task)
- Modify: `models/__init__.py` (fim do arquivo)
- Modify: `security/ir.model.access.csv` (fim do arquivo)
- Modify: `__manifest__.py` (`version`)
- Create: `tests/common_relatorio.py`
- Create: `tests/test_relatorio_gate.py` (classe `TestAchadoModel`)
- Modify: `tests/__init__.py`

**Interfaces:**
- Consumes (P1–P4): `afr.qualificacao.os.action_generate_relatorios()` → recordset; campos do relatório `state`, `block_ids`, `anexo_ids`, `checklist_ids`, `aprovacao_ids`, `data_inicio_ensaios`, `data_fim_ensaios`, `amb_temperatura`, `amb_umidade`; models `afr.relatorio.block`, `afr.relatorio.anexo`, `afr.relatorio.aprovacao`; `engc.calibration.instruments.certificates.afr_role` (P2).
- Produces:
  - `afr.relatorio.achado` com campos `relatorio_id`, `origem` (`regra`/`ia`), `codigo`, `gravidade` (`bloqueia`/`alerta`/`info`), `gravidade_order`, `mensagem`, `onde`, `decisao` (`pendente`/`procede`/`descartado`), `motivo`, `decidido_por`, `decidido_em`, `relatorio_state`.
  - Constantes em `models/relatorio_achado.py`: `SCAN_CTX = "afr_scan_internal"`, `USER_WRITABLE_FIELDS`.
  - `afr.qualificacao.relatorio.achado_ids` (O2M), `has_blocking` (Boolean, compute não armazenado), `blocking_summary` (Text, compute), `achado_pendente_count` (Integer, compute).
  - `tests/common_relatorio.py::RelatorioTestCommon` com `make_pdf(text) -> bytes` e os helpers `_cycle`, `_validator`, `_padrao`, `_cert`, `_anexo`, `_block`, `_mk_achado`, `_approve_internal`, `_make_clean`, `_achado(codigo)`.

- [ ] **Step 1: Confirmar branch e versão**

Run:
```bash
cd /home/afonso/docker/odoo_engenapp/addons/afr_qualificacao
git branch --show-current
grep -n '"version"' __manifest__.py
```
Esperado: branch `feat/relatorio-final` e versão `16.0.8.3.0` (P4 concluído e verde).

- [ ] **Step 2: Escrever a fixture compartilhada `tests/common_relatorio.py`**

```python
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
```

- [ ] **Step 3: Escrever os testes do model em `tests/test_relatorio_gate.py`**

```python
"""P5 — achado (model), verificação/carry-over, gate de emissão, snapshot."""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common_relatorio import RelatorioTestCommon


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestAchadoModel(RelatorioTestCommon):

    def test_usuario_nao_cria_achado_fora_da_varredura(self):
        Achado = self.env["afr.relatorio.achado"].with_user(self.user_qualif)
        with self.assertRaises(AccessError):
            Achado.create({
                "relatorio_id": self.rel.id, "origem": "regra", "codigo": "X",
                "gravidade": "alerta", "mensagem": "forjado", "onde": "X",
                "decisao": "descartado", "motivo": "plantado",
            })

    def test_contexto_scan_nao_autoriza_usuario(self):
        """SCAN_CTX vem do cliente RPC — não pode abrir o guard."""
        Achado = self.env["afr.relatorio.achado"].with_user(
            self.user_qualif).with_context(afr_scan_internal=True)
        with self.assertRaises(AccessError):
            Achado.create({
                "relatorio_id": self.rel.id, "origem": "regra", "codigo": "X",
                "gravidade": "alerta", "mensagem": "forjado", "onde": "X",
            })
        a = self._mk_achado().with_user(self.user_qualif).with_context(
            afr_scan_internal=True)
        with self.assertRaises(AccessError):
            a.write({"decidido_por": self.env.ref("base.user_admin").id})

    def test_descartado_exige_motivo(self):
        a = self._mk_achado()
        with self.assertRaises(ValidationError):
            a.write({"decisao": "descartado", "motivo": "   "})

    def test_decisao_carimba_e_limpa(self):
        a = self._mk_achado()
        a.write({"decisao": "descartado", "motivo": "Falso positivo conferido."})
        self.assertEqual(a.decidido_por, self.env.user)
        self.assertTrue(a.decidido_em)
        a.write({"decisao": "pendente"})
        self.assertFalse(a.decidido_por)
        self.assertFalse(a.decidido_em)

    def test_bloqueia_nao_aceita_decisao(self):
        a = self._mk_achado(gravidade="bloqueia")
        with self.assertRaises(ValidationError):
            a.write({"decisao": "procede"})

    def test_usuario_so_grava_decisao_e_motivo(self):
        a = self._mk_achado().with_user(self.user_qualif)
        a.write({"decisao": "descartado", "motivo": "Conferido em campo."})
        self.assertEqual(a.decisao, "descartado")
        with self.assertRaises(AccessError):
            a.write({"gravidade": "info"})

    def test_has_blocking_e_resumo(self):
        self.assertFalse(self.rel.has_blocking)
        self._mk_achado(gravidade="bloqueia", mensagem="Falta certificado depois")
        self._mk_achado(gravidade="alerta", mensagem="Ambiente vazio")
        self._refresh()
        self.assertTrue(self.rel.has_blocking)
        self.assertIn("Falta certificado depois", self.rel.blocking_summary)
        self.assertNotIn("Ambiente vazio", self.rel.blocking_summary)
        self.assertEqual(self.rel.achado_pendente_count, 2)
```

Registre em `tests/__init__.py` (no fim):
```python

# Relatório Final P5 — varredura (regras + IA) + gate de emissão
from . import test_relatorio_gate
```

- [ ] **Step 4: Rodar e confirmar que falha**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestAchadoModel --stop-after-init --no-http`
Esperado: erro de carga/KeyError, `afr.relatorio.achado` ainda não existe.

- [ ] **Step 5: Implementar `models/relatorio_achado.py`**

```python
# -*- coding: utf-8 -*-
"""Achado da varredura de inconsistência do Relatório Final (spec §7).

Só a varredura (`action_verificar`, em sudo) cria achados e grava
origem/código/gravidade/mensagem/onde/decidido_por. O contexto SCAN_CTX é só
um marcador legível — nunca autoriza nada (cliente RPC controla o contexto). O usuário grava apenas a
decisão (`decisao`, `motivo`) — e só com o relatório em rascunho.
Achado `bloqueia` não aceita decisão: sai corrigindo o dado e verificando
de novo (evita descartar CERT_DEPOIS_AUSENTE e furar D5).
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

SCAN_CTX = "afr_scan_internal"
USER_WRITABLE_FIELDS = frozenset({"decisao", "motivo"})

ORIGEM_SELECTION = [("regra", "Regra"), ("ia", "IA — verificar")]
GRAVIDADE_SELECTION = [
    ("bloqueia", "Bloqueia"),
    ("alerta", "Alerta"),
    ("info", "Info"),
]
DECISAO_SELECTION = [
    ("pendente", "Pendente"),
    ("procede", "Procede"),
    ("descartado", "Descartado"),
]
GRAVIDADE_ORDER = {"bloqueia": 0, "alerta": 1, "info": 2}


class AfrRelatorioAchado(models.Model):
    _name = "afr.relatorio.achado"
    _description = "Achado da Verificação do Relatório Final"
    _order = "relatorio_id, gravidade_order, origem, codigo, id"

    relatorio_id = fields.Many2one(
        "afr.qualificacao.relatorio",
        string="Relatório",
        required=True,
        ondelete="cascade",
        index=True,
    )
    relatorio_state = fields.Selection(related="relatorio_id.state", string="Estado do relatório")
    origem = fields.Selection(ORIGEM_SELECTION, required=True, default="regra")
    codigo = fields.Char(string="Código", required=True)
    gravidade = fields.Selection(GRAVIDADE_SELECTION, required=True, default="alerta")
    gravidade_order = fields.Integer(compute="_compute_gravidade_order", store=True)
    mensagem = fields.Text(required=True)
    onde = fields.Char(string="Onde")
    decisao = fields.Selection(DECISAO_SELECTION, string="Decisão", required=True, default="pendente")
    motivo = fields.Text()
    decidido_por = fields.Many2one("res.users", string="Decidido por", readonly=True)
    decidido_em = fields.Datetime(string="Decidido em", readonly=True)

    @api.depends("gravidade")
    def _compute_gravidade_order(self):
        for r in self:
            r.gravidade_order = GRAVIDADE_ORDER.get(r.gravidade, 3)

    def _is_internal(self):
        # Só sudo conta como interno. SCAN_CTX é apenas um marcador: contexto
        # é controlado pelo cliente via JSON-RPC, então NÃO é confiável.
        return bool(self.env.su)

    @api.model_create_multi
    def create(self, vals_list):
        if not self._is_internal():
            raise AccessError(_(
                "Achados são criados apenas pela verificação (botão Verificar)."
            ))
        return super().create(vals_list)

    def write(self, vals):
        if not self._is_internal():
            extra = set(vals) - USER_WRITABLE_FIELDS
            if extra:
                raise AccessError(_(
                    "Só a decisão e o motivo de um achado podem ser alterados "
                    "(campos recusados: %s)."
                ) % ", ".join(sorted(extra)))
            if any(r.relatorio_id.state != "draft" for r in self):
                raise UserError(_(
                    "Decisões só podem ser alteradas com o relatório em rascunho."
                ))
        if "decisao" in vals:
            vals = dict(vals)
            if vals["decisao"] in ("procede", "descartado"):
                vals["decidido_por"] = self.env.uid
                vals["decidido_em"] = fields.Datetime.now()
            else:
                vals["decidido_por"] = False
                vals["decidido_em"] = False
        return super().write(vals)

    @api.constrains("decisao", "motivo", "gravidade")
    def _check_decisao(self):
        for r in self:
            if r.gravidade == "bloqueia" and r.decisao != "pendente":
                raise ValidationError(_(
                    "Achado bloqueante não aceita decisão: corrija o dado e "
                    "clique em Verificar novamente (%s)."
                ) % r.codigo)
            if r.decisao == "descartado" and not (r.motivo or "").strip():
                raise ValidationError(_(
                    "Informe o motivo para descartar o achado %s."
                ) % r.codigo)
```

- [ ] **Step 6: Implementar `models/relatorio_verificacao.py` (parte inicial)**

```python
# -*- coding: utf-8 -*-
"""Relatório Final — varredura de inconsistência e gate de emissão (P5)."""
from odoo import api, fields, models


class AfrQualificacaoRelatorio(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    achado_ids = fields.One2many(
        "afr.relatorio.achado",
        "relatorio_id",
        string="Achados da verificação",
    )
    has_blocking = fields.Boolean(compute="_compute_blocking", string="Tem bloqueio")
    blocking_summary = fields.Text(compute="_compute_blocking", string="Aguardando")
    achado_pendente_count = fields.Integer(
        compute="_compute_blocking", string="Achados pendentes"
    )

    @api.depends("achado_ids.gravidade", "achado_ids.decisao", "achado_ids.mensagem")
    def _compute_blocking(self):
        for r in self:
            blocking = r.achado_ids.filtered(
                lambda a: a.gravidade == "bloqueia" and a.decisao == "pendente"
            )
            r.has_blocking = bool(blocking)
            r.blocking_summary = "\n".join("• %s" % a.mensagem for a in blocking)
            r.achado_pendente_count = len(r.achado_ids.filtered(
                lambda a: a.decisao == "pendente" and a.gravidade != "info"
            ))
```

No fim de `models/__init__.py` (depois do import de P1 `from . import relatorio` e dos de P2–P4):
```python
from . import relatorio_achado          # Relatório Final P5 (16.0.8.4.0)
from . import relatorio_verificacao     # P5 — _inherit afr.qualificacao.relatorio
```

No fim de `security/ir.model.access.csv`:
```csv
access_afr_relatorio_achado_technician,afr_relatorio_achado_technician,model_afr_relatorio_achado,afr_qualificacao.group_afr_qualificacao_technician,1,0,0,0
access_afr_relatorio_achado_user,afr_relatorio_achado_user,model_afr_relatorio_achado,afr_qualificacao.group_afr_qualificacao_user,1,1,1,0
access_afr_relatorio_achado_manager,afr_relatorio_achado_manager,model_afr_relatorio_achado,afr_qualificacao.group_afr_qualificacao_manager,1,1,1,1
```

Em `__manifest__.py`: `"version": "16.0.8.3.0",` → `"version": "16.0.8.4.0",`.

- [ ] **Step 7: Rodar e confirmar que passa**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestAchadoModel --stop-after-init --no-http`
Esperado: 7 testes, 0 falhas.

- [ ] **Step 8: Commit**

Via agente `git-commit-push` (cwd `/home/afonso/docker/odoo_engenapp/addons/afr_qualificacao`), paths `models/relatorio_achado.py models/relatorio_verificacao.py models/__init__.py security/ir.model.access.csv __manifest__.py tests/common_relatorio.py tests/test_relatorio_gate.py tests/__init__.py`, mensagem:
```
feat(relatorio): add verification finding model with decision guard

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 2: Regras bloqueantes + registro + `run_rules`

**Files:**
- Create: `models/relatorio_rules.py`
- Create: `tests/test_relatorio_rules.py` (classe `TestRelatorioRulesBloqueia`)
- Modify: `tests/__init__.py`

**Interfaces:**
- Consumes: `rel._afr_certificate_selection()` → `list[dict(instrument, resource_role, role, certificate)]` (P2); `anexo._check_files()` → `list[str]` e `PROBLEM_EMPTY` de `models/relatorio_anexo_files.py` (P4); `rel._render_block_body(block)` → `Markup` (P3); `cycle.cycle_type_id.load_type`; `rel.leitura_ib_ids.cycle_id/resultado`; `rel.indicador_ids.validade/lote/tipo`.
- Produces (módulo puro `odoo.addons.afr_qualificacao.models.relatorio_rules`):
  - `EMISSION_CTX = "afr_emission_check"`
  - `finding(codigo, gravidade, mensagem, onde="") -> dict`
  - uma função `rule_<codigo_minusculo>(rel) -> list[dict]` por regra
  - `RULES: OrderedDict[str, callable]`, com 8 regras nesta task e 17 na Task 3
  - `run_rules(rel) -> list[dict]`, que isola cada regra num savepoint e troca exceção por achado `bloqueia`
  - helpers `cycle_label(cycle)`, `block_label(block)`

- [ ] **Step 1: Escrever os testes**

`tests/test_relatorio_rules.py`:
```python
"""P5 — regras determinísticas da varredura: positivo + negativo por regra."""
from datetime import timedelta
from unittest.mock import patch

from odoo.tests import tagged

from ..models import relatorio_rules
from ..models.relatorio_rules import RULES, run_rules
from .common_relatorio import RelatorioTestCommon, make_pdf


class _RulesMixin:
    def _run(self, code, ctx=None):
        self._refresh()
        rel = self.rel.with_context(**ctx) if ctx else self.rel
        return RULES[code](rel)


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestRelatorioRulesBloqueia(_RulesMixin, RelatorioTestCommon):

    # --- certificados -------------------------------------------------
    def test_cert_depois_sem_validador_no_plano(self):
        out = self._run("CERT_DEPOIS_AUSENTE")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "bloqueia")
        self.assertIn("Nenhum validador", out[0]["mensagem"])

    def test_cert_depois(self):
        v = self._validator()
        self.assertEqual(len(self._run("CERT_DEPOIS_AUSENTE")), 1)
        self._cert(v, "depois", self.D_FIM + timedelta(days=2))
        self.assertEqual(self._run("CERT_DEPOIS_AUSENTE"), [])

    def test_cert_depois_anterior_ao_fim_nao_serve(self):
        v = self._validator()
        self._cert(v, "depois", self.D_FIM - timedelta(days=1))
        self.assertEqual(len(self._run("CERT_DEPOIS_AUSENTE")), 1)

    def test_cert_antes(self):
        v = self._validator()
        self.assertEqual(len(self._run("CERT_ANTES_AUSENTE")), 1)
        self._cert(v, "antes", self.D_INI - timedelta(days=30))
        self.assertEqual(self._run("CERT_ANTES_AUSENTE"), [])

    def test_cert_datas_vazias(self):
        self._validator()
        self.rel.write({"data_inicio_ensaios": False})
        out = self._run("CERT_ANTES_AUSENTE")
        self.assertEqual(len(out), 1)
        self.assertIn("Datas", out[0]["mensagem"])
        self.assertEqual(self._run("CERT_DEPOIS_AUSENTE"), [])
        self.assertEqual(self._run("PADRAO_VENCIDO"), [])

    def test_padrao_vencido(self):
        p = self._padrao()
        self._cert(p, "externo", self.D_INI - timedelta(days=400), self.D_INI - timedelta(days=1))
        out = self._run("PADRAO_VENCIDO")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "bloqueia")
        self._cert(p, "externo", self.D_INI - timedelta(days=10), self.D_FIM + timedelta(days=300))
        self.assertEqual(self._run("PADRAO_VENCIDO"), [])

    # --- indicadores biológicos -------------------------------------------
    def test_ib_sem_leitura(self):
        c = self._cycle()
        self._cycle(cycle_type=self.cycle_qo_test, seq=2)  # sem carga: ignorado
        out = self._run("IB_SEM_LEITURA")
        self.assertEqual(len(out), 1)
        self.assertIn("[#%d]" % c.id, out[0]["onde"])
        self.env["afr.relatorio.leitura.ib"].create({
            "relatorio_id": self.rel.id, "cycle_id": c.id,
            "resultado": "negativo", "data_leitura": self.D_FIM,
        })
        self.assertEqual(self._run("IB_SEM_LEITURA"), [])

    def test_ib_vencido(self):
        ind = self.env["afr.relatorio.indicador"].create({
            "relatorio_id": self.rel.id, "tipo": "biologico", "lote": "L-TESTE",
            "validade": self.D_FIM - timedelta(days=1),
        })
        out = self._run("IB_VENCIDO")
        self.assertEqual(len(out), 1)
        self.assertIn("L-TESTE", out[0]["mensagem"])
        ind.validade = self.D_FIM
        self.assertEqual(self._run("IB_VENCIDO"), [])

    # --- anexos -------------------------------------------------------------
    def test_anexo_vazio(self):
        a = self._anexo(code="dados")
        out = self._run("ANEXO_VAZIO")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "bloqueia")
        a.included = False
        self.assertEqual(self._run("ANEXO_VAZIO"), [])

    def test_anexo_vazio_ignora_slot_bloco(self):
        self._anexo(code="protocolo", title="Protocolo", slot_kind="bloco")
        self.assertEqual(self._run("ANEXO_VAZIO"), [])

    def test_anexo_ilegivel(self):
        self._anexo(code="dados", pdfs=[make_pdf("ok"), b"%PDF-1.4 lixo corrompido"])
        out = self._run("ANEXO_ILEGIVEL")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "bloqueia")
        self.assertEqual(self._run("ANEXO_VAZIO"), [])

    def test_anexo_todo_ilegivel_e_ilegivel_nao_vazio(self):
        self._anexo(code="dados", pdfs=[b"%PDF-1.4 lixo corrompido"])
        self.assertEqual(len(self._run("ANEXO_ILEGIVEL")), 1)
        self.assertEqual(self._run("ANEXO_VAZIO"), [])

    def test_anexo_legivel_sem_achado(self):
        self._anexo(code="dados", pdfs=[make_pdf("ok")])
        self.assertEqual(self._run("ANEXO_ILEGIVEL"), [])
        self.assertEqual(self._run("ANEXO_VAZIO"), [])

    # --- tokens -------------------------------------------------------------
    def test_token_nao_resolvido(self):
        self._block("<p>Valor: {{ relatorio.name</p>", title="Objetivo")
        out = self._run("TOKEN_NAO_RESOLVIDO")
        self.assertEqual(len(out), 1)
        self.assertIn("Objetivo", out[0]["onde"])

    def test_token_resolvido(self):
        self._block("<p>Nº {{ relatorio.name }}</p>", title="Objetivo")
        self.assertEqual(self._run("TOKEN_NAO_RESOLVIDO"), [])

    # --- runner -------------------------------------------------------------
    def test_run_rules_regra_quebrada_vira_bloqueio(self):
        def boom(rel):
            raise RuntimeError("falha simulada")

        with patch.dict(relatorio_rules.RULES, {"CERT_ANTES_AUSENTE": boom}):
            out = run_rules(self.rel)
        broken = [f for f in out if f["codigo"] == "CERT_ANTES_AUSENTE"]
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0]["gravidade"], "bloqueia")
        self.assertIn("falha simulada", broken[0]["mensagem"])
        # as demais regras continuaram rodando
        self.assertTrue(any(f["codigo"] == "CERT_DEPOIS_AUSENTE" for f in out))
```

Em `tests/__init__.py`, logo abaixo de `from . import test_relatorio_gate`:
```python
from . import test_relatorio_rules
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioRulesBloqueia --stop-after-init --no-http`
Esperado: `ImportError`/`ModuleNotFoundError: relatorio_rules`.

- [ ] **Step 3: Implementar `models/relatorio_rules.py`**

```python
# -*- coding: utf-8 -*-
"""Regras determinísticas da varredura do Relatório Final (spec §7.1).

Cada regra é uma função pura `rule(relatorio) -> list[dict]`; o dict tem
`codigo`, `gravidade` (bloqueia/alerta/info), `mensagem`, `onde`. Nenhuma
regra grava nada. `onde` é estável entre verificações (chave de carry-over
das decisões) e inclui `[#id]` quando o rótulo pode repetir.

`RULES` é o registro (ordem = execução). `run_rules` isola cada regra num
savepoint e converte exceção em achado bloqueante com o código da regra.
"""
import logging
import re
from collections import OrderedDict
from html import unescape

from odoo import fields

from .relatorio_anexo_files import PROBLEM_EMPTY

_logger = logging.getLogger(__name__)

EMISSION_CTX = "afr_emission_check"
ANEXO_REF_RE = re.compile(r"""anexo\(\s*['"]([\w\-]+)['"]\s*\)""")
CANAL_NUM_RE = re.compile(r"(\d+)")


def finding(codigo, gravidade, mensagem, onde=""):
    return {
        "codigo": codigo,
        "gravidade": gravidade,
        "mensagem": mensagem,
        "onde": onde or "",
    }


def _fmt(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def cycle_label(cycle):
    return "%s [#%d]" % (cycle.display_name, cycle.id)


def block_label(block):
    name = block.title or block.section_id.display_name or block.block_kind
    return "%s [#%d]" % (name, block.id)


def _anexo_label(anexo):
    return anexo.title or anexo.code or ("Anexo #%d" % anexo.id)


def _dates_missing(rel):
    return not rel.data_inicio_ensaios or not rel.data_fim_ensaios


def _cert_rows(rel, resource_role, role):
    return [
        row for row in rel._afr_certificate_selection()
        if row["resource_role"] == resource_role and row["role"] == role
    ]


# ------------------------------------------------------------ bloqueia
def rule_cert_depois_ausente(rel):
    if _dates_missing(rel):
        return []
    rows = _cert_rows(rel, "validador", "depois")
    if not rows and not _cert_rows(rel, "validador", "antes"):
        return [finding(
            "CERT_DEPOIS_AUSENTE", "bloqueia",
            "Nenhum validador no plano de recursos da OS — impossível "
            "comprovar a calibração pós-campanha.",
            "Plano de recursos",
        )]
    out = []
    for row in rows:
        if not row["certificate"]:
            name = row["instrument"].display_name
            out.append(finding(
                "CERT_DEPOIS_AUSENTE", "bloqueia",
                "Validador %s sem certificado 'depois' com data ≥ %s."
                % (name, _fmt(rel.data_fim_ensaios)),
                "Validador: %s" % name,
            ))
    return out


def rule_cert_antes_ausente(rel):
    if _dates_missing(rel):
        return [finding(
            "CERT_ANTES_AUSENTE", "bloqueia",
            "Datas de início/fim dos ensaios não preenchidas — a seleção de "
            "certificados depende delas.",
            "Campo: Datas dos ensaios",
        )]
    out = []
    for row in _cert_rows(rel, "validador", "antes"):
        if not row["certificate"]:
            name = row["instrument"].display_name
            out.append(finding(
                "CERT_ANTES_AUSENTE", "bloqueia",
                "Validador %s sem certificado 'antes' com data ≤ %s."
                % (name, _fmt(rel.data_inicio_ensaios)),
                "Validador: %s" % name,
            ))
    return out


def rule_padrao_vencido(rel):
    if _dates_missing(rel):
        return []
    out = []
    for row in _cert_rows(rel, "padrao", "externo"):
        if not row["certificate"]:
            name = row["instrument"].display_name
            out.append(finding(
                "PADRAO_VENCIDO", "bloqueia",
                "Padrão %s sem certificado vigente em %s."
                % (name, _fmt(rel.data_inicio_ensaios)),
                "Padrão: %s" % name,
            ))
    return out


def rule_ib_sem_leitura(rel):
    lidos = set(rel.leitura_ib_ids.filtered(lambda l: l.resultado).mapped("cycle_id").ids)
    out = []
    for cycle in rel.cycle_ids:
        if cycle.cycle_type_id.load_type == "com_carga" and cycle.id not in lidos:
            out.append(finding(
                "IB_SEM_LEITURA", "bloqueia",
                "Ciclo com carga %s sem leitura de indicador biológico registrada."
                % cycle.display_name,
                "Ciclo: %s" % cycle_label(cycle),
            ))
    return out


def rule_ib_vencido(rel):
    ref = rel.data_fim_ensaios or rel.data_inicio_ensaios
    if not ref:
        return []
    out = []
    for ind in rel.indicador_ids:
        if ind.validade and ind.validade < ref:
            out.append(finding(
                "IB_VENCIDO", "bloqueia",
                "Indicador %s lote %s vencido em %s (ensaios até %s)."
                % (ind.modelo_tipo or ind.tipo, ind.lote or "—",
                   _fmt(ind.validade), _fmt(ref)),
                "Indicador: lote %s [#%d]" % (ind.lote or "—", ind.id),
            ))
    return out


def _anexos_com_arquivo(rel):
    # slot 'bloco' não tem arquivo por design (conteúdo sai no corpo) — P4.
    return rel.anexo_ids.filtered(lambda a: a.included and a.slot_kind != "bloco")


def rule_anexo_vazio(rel):
    """P4: `_check_files()` contém PROBLEM_EMPTY ⇔ anexo sem nenhum arquivo."""
    out = []
    for anexo in _anexos_com_arquivo(rel):
        if PROBLEM_EMPTY in anexo._check_files():
            out.append(finding(
                "ANEXO_VAZIO", "bloqueia",
                "Anexo '%s' incluído sem arquivo." % _anexo_label(anexo),
                "Anexo: %s" % _anexo_label(anexo),
            ))
    return out


def rule_anexo_ilegivel(rel):
    """P4: todo item de `_check_files()` diferente de PROBLEM_EMPTY é
    "<legenda>: <motivo>" (ilegível, criptografado, sem páginas, tipo não
    suportado). Anexo com todos os arquivos ilegíveis → ILEGIVEL, não VAZIO."""
    out = []
    for anexo in _anexos_com_arquivo(rel):
        for problema in anexo._check_files():
            if problema == PROBLEM_EMPTY:
                continue
            out.append(finding(
                "ANEXO_ILEGIVEL", "bloqueia",
                "Anexo '%s': %s" % (_anexo_label(anexo), problema),
                "Anexo: %s — %s" % (_anexo_label(anexo), problema),
            ))
    return out


def rule_token_nao_resolvido(rel):
    out = []
    for block in rel.block_ids.filtered("included"):
        label = block_label(block)
        try:
            html = str(rel._render_block_body(block) or "")
        except Exception as exc:  # noqa: BLE001 — erro de render é o achado
            out.append(finding(
                "TOKEN_NAO_RESOLVIDO", "bloqueia",
                "Erro ao renderizar o bloco: %s" % exc,
                "Bloco: %s" % label,
            ))
            continue
        if "{{" in html:
            out.append(finding(
                "TOKEN_NAO_RESOLVIDO", "bloqueia",
                "Token '{{' não resolvido após a renderização do bloco.",
                "Bloco: %s" % label,
            ))
    return out


RULES = OrderedDict([
    ("CERT_DEPOIS_AUSENTE", rule_cert_depois_ausente),
    ("CERT_ANTES_AUSENTE", rule_cert_antes_ausente),
    ("PADRAO_VENCIDO", rule_padrao_vencido),
    ("IB_SEM_LEITURA", rule_ib_sem_leitura),
    ("IB_VENCIDO", rule_ib_vencido),
    ("ANEXO_VAZIO", rule_anexo_vazio),
    ("ANEXO_ILEGIVEL", rule_anexo_ilegivel),
    ("TOKEN_NAO_RESOLVIDO", rule_token_nao_resolvido),
])


def run_rules(rel):
    """Executa todas as regras do registro. Regra que falha vira bloqueio."""
    out = []
    for code, fn in list(RULES.items()):
        try:
            with rel.env.cr.savepoint():
                found = fn(rel) or []
        except Exception as exc:  # noqa: BLE001 — fail closed
            _logger.exception("Regra %s falhou no relatório %s", code, rel.id)
            found = [finding(
                code, "bloqueia",
                "Falha ao executar a regra %s: %s" % (code, exc),
                "Regra: %s" % code,
            )]
        out.extend(found)
    return out
```

Observação para quem implementar: `unescape`, `fields` e `ANEXO_REF_RE`/`CANAL_NUM_RE` só são usados na Task 3, mas já ficam declarados aqui para a Task 3 apenas acrescentar funções. Se o lint reclamar de import não usado nesta task, mantenha: a Task 3 usa.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioRulesBloqueia --stop-after-init --no-http`
Esperado: 16 testes, 0 falhas.

- [ ] **Step 5: Commit**

Via `git-commit-push` (cwd do submodule), paths `models/relatorio_rules.py tests/test_relatorio_rules.py tests/__init__.py`, mensagem:
```
feat(relatorio): add blocking verification rules and fail-closed runner

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 3: Regras de alerta + `APROVACAO_INTERNA` (registro completo, 17)

**Files:**
- Modify: `models/relatorio_rules.py` (acrescentar funções e substituir a definição de `RULES`)
- Modify: `tests/test_relatorio_rules.py` (nova classe `TestRelatorioRulesAlerta`)

**Interfaces:**
- Consumes: `rel._anexo_number(code) -> str` (P3); `rel.os_id.sale_order_id`, `sale.order.line.cycle_type_id/qualif_cycle_qty/equipment_id/is_proposal_optional/optional_accepted`; `cycle.sale_order_line_id/state/collect_item_ids/janela_inicio/janela_fim/sensor_pos_ids`; `afr.qualificacao.collect.item.captured_at/qualif_id`; `rel.os_id.resource_plan_line_ids`; `instrument.measurement_capacity_ids.qty`; `rel.aprovacao_ids.papel/approved_at`.
- Produces:
  - `cycle_counts(rel) -> dict[cycle_type_record, list[int, int]]` (`[contratados, executados]`), usado também pela IA na Task 5
  - `validator_channel_capacity(rel) -> int`
  - `RULES` com os 17 códigos da spec §7.1

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_relatorio_rules.py` (imports no topo: `import base64` e `from datetime import datetime, timedelta`):
```python
EXPECTED_CODES = {
    "CERT_DEPOIS_AUSENTE", "CERT_ANTES_AUSENTE", "PADRAO_VENCIDO",
    "IB_SEM_LEITURA", "IB_VENCIDO", "ANEXO_VAZIO", "ANEXO_ILEGIVEL",
    "TOKEN_NAO_RESOLVIDO", "ANEXO_REF_EXCLUIDO", "CICLOS_CONTAGEM",
    "CICLO_SEM_DADOS", "CICLO_SEM_JANELA", "DATA_FORA_JANELA",
    "AMBIENTE_VAZIO", "CHECKLIST_REPROVADO", "CANAL_SEM_CERT",
    "APROVACAO_INTERNA",
}


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestRelatorioRulesAlerta(_RulesMixin, RelatorioTestCommon):

    def test_registro_completo(self):
        self.assertEqual(set(RULES), EXPECTED_CODES)

    def test_anexo_ref_excluido(self):
        self._block("<p>Ver Anexo {{ anexo('micro') }}.</p>", title="Conclusão")
        out = self._run("ANEXO_REF_EXCLUIDO")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "alerta")
        self.assertIn("micro", out[0]["mensagem"])
        self._anexo(code="micro", title="Laudo microbiológico")
        self.assertEqual(self._run("ANEXO_REF_EXCLUIDO"), [])

    def test_anexo_ref_excluido_com_aspas_escapadas(self):
        self._block("<p>Ver Anexo {{ anexo(&#39;f0&#39;) }}.</p>", title="Resultados")
        out = self._run("ANEXO_REF_EXCLUIDO")
        self.assertEqual(len(out), 1)
        self.assertIn("f0", out[0]["mensagem"])

    def test_ciclos_contagem(self):
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qd_cmax.id,
            "cycle_type_id": self.cycle_cmax.id,
            "qualif_cycle_qty": 2,
            "equipment_id": self.equip1.id,
        })
        self.os.sale_order_id = so
        self._cycle(state="passed", seq=1, sale_order_line_id=line.id)
        c2 = self._cycle(state="pending", seq=2, sale_order_line_id=line.id)
        out = self._run("CICLOS_CONTAGEM")
        self.assertEqual(len(out), 1)
        self.assertIn("2 contratado(s), 1 executado(s)", out[0]["mensagem"])
        c2.state = "passed"
        self.assertEqual(self._run("CICLOS_CONTAGEM"), [])

    def test_ciclo_sem_dados(self):
        c = self._cycle()
        self.assertEqual(len(self._run("CICLO_SEM_DADOS")), 1)
        self.env["afr.qualificacao.collect.item"].create({
            "name": "Dados do validador",
            "qualif_id": self.qd.id,
            "cycle_id": c.id,
            "kind": "pdf",
            "state": "collected",
            "file": base64.b64encode(make_pdf("dados")),
            "filename": "dados.pdf",
            "mimetype": "application/pdf",
        })
        self.assertEqual(self._run("CICLO_SEM_DADOS"), [])

    def test_ciclo_sem_janela(self):
        c = self._cycle()
        self.assertEqual(len(self._run("CICLO_SEM_JANELA")), 1)
        c.write({
            "janela_inicio": datetime(2026, 7, 1, 10, 0),
            "janela_fim": datetime(2026, 7, 1, 10, 30),
        })
        self.assertEqual(self._run("CICLO_SEM_JANELA"), [])

    def test_ciclo_janela_invertida(self):
        self._cycle(janela_inicio=datetime(2026, 7, 1, 11, 0),
                    janela_fim=datetime(2026, 7, 1, 10, 0))
        out = self._run("CICLO_SEM_JANELA")
        self.assertEqual(len(out), 1)
        self.assertIn("anterior", out[0]["mensagem"])

    def _coleta(self, captured_at):
        return self.env["afr.qualificacao.collect.item"].create({
            "name": "Foto do painel",
            "qualif_id": self.qd.id,
            "kind": "foto",
            "state": "collected",
            "captured_at": captured_at,
        })

    def test_data_fora_janela(self):
        self._coleta(datetime(2025, 7, 2, 12, 0))
        out = self._run("DATA_FORA_JANELA", {"tz": "UTC"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["gravidade"], "alerta")

    def test_data_dentro_janela(self):
        self._coleta(datetime(2026, 7, 2, 12, 0))
        self.assertEqual(self._run("DATA_FORA_JANELA", {"tz": "UTC"}), [])

    def test_data_fora_janela_respeita_fuso(self):
        # 01:30 UTC de 04/07 = 22:30 de 03/07 em Brasília (último dia de ensaio)
        self._coleta(datetime(2026, 7, 4, 1, 30))
        self.assertEqual(self._run("DATA_FORA_JANELA", {"tz": "America/Sao_Paulo"}), [])
        self.assertEqual(len(self._run("DATA_FORA_JANELA", {"tz": "UTC"})), 1)

    def test_ambiente_vazio(self):
        self.assertEqual(self._run("AMBIENTE_VAZIO"), [])
        self.rel.write({"amb_umidade": " "})
        out = self._run("AMBIENTE_VAZIO")
        self.assertEqual(len(out), 1)
        self.assertIn("Umidade", out[0]["onde"])

    def test_checklist_reprovado(self):
        Check = self.env["afr.relatorio.checklist"]
        Check.create({"relatorio_id": self.rel.id, "grupo": "Instalações elétricas",
                      "descricao": "Aterramento", "status": "aprovado", "sequence": 1})
        self.assertEqual(self._run("CHECKLIST_REPROVADO"), [])
        Check.create({"relatorio_id": self.rel.id, "grupo": "Instalações elétricas",
                      "descricao": "Disjuntor dedicado", "status": "reprovado",
                      "comentario": "Compartilhado", "sequence": 2})
        out = self._run("CHECKLIST_REPROVADO")
        self.assertEqual(len(out), 1)
        self.assertIn("Disjuntor dedicado", out[0]["mensagem"])

    def test_canal_sem_cert(self):
        self._validator(channels=28)
        c = self._cycle()
        Pos = self.env["afr.relatorio.sensor.pos"]
        Pos.create({"cycle_id": c.id, "canal": "CH012", "posicao": "Centro", "sequence": 1})
        self.assertEqual(self._run("CANAL_SEM_CERT"), [])
        Pos.create({"cycle_id": c.id, "canal": "CH030", "posicao": "Dreno", "sequence": 2})
        out = self._run("CANAL_SEM_CERT")
        self.assertEqual(len(out), 1)
        self.assertIn("CH030", out[0]["mensagem"])

    def test_canal_sem_validador_silencioso(self):
        c = self._cycle()
        self.env["afr.relatorio.sensor.pos"].create(
            {"cycle_id": c.id, "canal": "CH099", "posicao": "Topo", "sequence": 1})
        self.assertEqual(self._run("CANAL_SEM_CERT"), [])

    def test_aprovacao_interna_so_na_emissao(self):
        self.assertEqual(self._run("APROVACAO_INTERNA"), [])
        out = self._run("APROVACAO_INTERNA", {relatorio_rules.EMISSION_CTX: True})
        self.assertTrue(out)
        self.assertTrue(all(f["gravidade"] == "bloqueia" for f in out))
        self._approve_internal()
        self.assertEqual(self._run("APROVACAO_INTERNA", {relatorio_rules.EMISSION_CTX: True}), [])
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioRulesAlerta --stop-after-init --no-http`
Esperado: `KeyError: 'ANEXO_REF_EXCLUIDO'` e `test_registro_completo` falha.

- [ ] **Step 3: Implementar as regras**

Em `models/relatorio_rules.py`, acrescente logo **antes** da definição de `RULES`:
```python
# ------------------------------------------------------------ alerta
def rule_anexo_ref_excluido(rel):
    out = []
    for block in rel.block_ids.filtered("included"):
        codes = sorted(set(ANEXO_REF_RE.findall(unescape(block.body or ""))))
        for code in codes:
            if not rel._anexo_number(code):
                out.append(finding(
                    "ANEXO_REF_EXCLUIDO", "alerta",
                    "O texto referencia anexo('%s'), que está excluído ou não existe."
                    % code,
                    "Bloco: %s → anexo('%s')" % (block_label(block), code),
                ))
    return out


def cycle_counts(rel):
    """{cycle_type: [contratados, executados]} do equipamento do relatório.

    Contratados = Σ qualif_cycle_qty das linhas SO (da OS e dos ciclos) com
    cycle_type, do mesmo equipamento, excluindo opcional não aceito; ciclo
    sem linha SO conta 1 contratado. Executados = ciclos com state != pending.
    """
    counts = {}
    lines = rel.cycle_ids.mapped("sale_order_line_id")
    so = rel.os_id.sale_order_id
    if so:
        lines |= so.order_line.filtered(
            lambda l: l.cycle_type_id
            and l.equipment_id == rel.equipment_id
            and not (l.is_proposal_optional and not l.optional_accepted)
        )
    for line in lines:
        ctype = line.cycle_type_id or line.cycle_ids[:1].cycle_type_id
        if ctype:
            counts.setdefault(ctype, [0, 0])[0] += line.qualif_cycle_qty or 0
    for cycle in rel.cycle_ids:
        entry = counts.setdefault(cycle.cycle_type_id, [0, 0])
        if not cycle.sale_order_line_id:
            entry[0] += 1
        if cycle.state != "pending":
            entry[1] += 1
    return counts


def rule_ciclos_contagem(rel):
    out = []
    items = sorted(cycle_counts(rel).items(), key=lambda kv: kv[0].name or "")
    for ctype, (contratados, executados) in items:
        if contratados != executados:
            out.append(finding(
                "CICLOS_CONTAGEM", "alerta",
                "Ciclos '%s': %d contratado(s), %d executado(s)."
                % (ctype.name, contratados, executados),
                "Ciclos: %s" % ctype.name,
            ))
    return out


def _is_pdf(item):
    return (item.mimetype or "").lower() == "application/pdf" or (
        (item.filename or "").lower().endswith(".pdf")
    )


def rule_ciclo_sem_dados(rel):
    out = []
    for cycle in rel.cycle_ids:
        has_pdf = any(
            i.state == "collected" and i.file and _is_pdf(i)
            for i in cycle.collect_item_ids
        )
        if not has_pdf:
            out.append(finding(
                "CICLO_SEM_DADOS", "alerta",
                "Ciclo %s sem PDF de dados do validador." % cycle.display_name,
                "Ciclo: %s" % cycle_label(cycle),
            ))
    return out


def rule_ciclo_sem_janela(rel):
    out = []
    for cycle in rel.cycle_ids:
        if not cycle.janela_inicio or not cycle.janela_fim:
            msg = "Ciclo %s sem janela de esterilização (início/fim)." % cycle.display_name
        elif cycle.janela_fim <= cycle.janela_inicio:
            msg = ("Ciclo %s com fim da janela anterior ou igual ao início."
                   % cycle.display_name)
        else:
            continue
        out.append(finding(
            "CICLO_SEM_JANELA", "alerta", msg, "Ciclo: %s" % cycle_label(cycle),
        ))
    return out


def rule_data_fora_janela(rel):
    if _dates_missing(rel):
        return []
    ini, fim = rel.data_inicio_ensaios, rel.data_fim_ensaios
    items = rel.env["afr.qualificacao.collect.item"].search([
        ("qualif_id", "in", rel.qualificacao_ids.ids),
        ("captured_at", "!=", False),
    ])
    out = []
    for item in items:
        # fuso do usuário/contexto (tz) — evita falso alerta perto da meia-noite
        local = fields.Datetime.context_timestamp(rel, item.captured_at).date()
        if local < ini or local > fim:
            out.append(finding(
                "DATA_FORA_JANELA", "alerta",
                "Item de coleta '%s' capturado em %s, fora do período dos "
                "ensaios (%s a %s)." % (item.name, _fmt(local), _fmt(ini), _fmt(fim)),
                "Coleta: %s [#%d]" % (item.name, item.id),
            ))
    return out


def rule_ambiente_vazio(rel):
    out = []
    for field_name, label in (
        ("amb_temperatura", "Temperatura ambiente"),
        ("amb_umidade", "Umidade ambiente"),
    ):
        if not (rel[field_name] or "").strip():
            out.append(finding(
                "AMBIENTE_VAZIO", "alerta",
                "%s não informada." % label,
                "Campo: %s" % label,
            ))
    return out


def rule_checklist_reprovado(rel):
    out = []
    for line in rel.checklist_ids.filtered(lambda l: l.status == "reprovado"):
        comentario = (" — %s" % line.comentario) if line.comentario else ""
        out.append(finding(
            "CHECKLIST_REPROVADO", "alerta",
            "Item de checklist reprovado: %s — %s%s"
            % (line.grupo or "", line.descricao or "", comentario),
            "Checklist: %s / %s [#%d]" % (line.grupo or "", line.descricao or "", line.id),
        ))
    return out


def validator_channel_capacity(rel):
    instruments = rel.os_id.resource_plan_line_ids.filtered(
        lambda l: l.resource_role == "validador"
    ).mapped("instrument_id")
    return sum(instruments.mapped("measurement_capacity_ids.qty"))


def rule_canal_sem_cert(rel):
    """Heurística (ver plano P5, decisão 7): nº do canal > capacidade total."""
    capacity = validator_channel_capacity(rel)
    if not capacity:
        return []
    out = []
    for cycle in rel.cycle_ids:
        for pos in cycle.sensor_pos_ids:
            match = CANAL_NUM_RE.search(pos.canal or "")
            if not match:
                continue
            if int(match.group(1)) > capacity:
                out.append(finding(
                    "CANAL_SEM_CERT", "alerta",
                    "Canal %s (posição %s) fora da faixa 1–%d dos validadores do "
                    "plano de recursos — sem cobertura de certificado."
                    % (pos.canal, pos.posicao or "—", capacity),
                    "Ciclo: %s / canal %s" % (cycle_label(cycle), pos.canal),
                ))
    return out


def rule_aprovacao_interna(rel):
    if not rel.env.context.get(EMISSION_CTX):
        return []
    out = []
    for papel, label in (("elaborador", "Elaborador"), ("emissor", "Emissor")):
        lines = rel.aprovacao_ids.filtered(lambda a, p=papel: a.papel == p)
        if not lines:
            msg = "Papel %s não definido nas aprovações." % label
        elif any(not a.approved_at for a in lines):
            msg = "%s sem aprovação interna." % label
        else:
            continue
        out.append(finding("APROVACAO_INTERNA", "bloqueia", msg, "Aprovação: %s" % label))
    return out
```

Substitua a definição de `RULES` por:
```python
RULES = OrderedDict([
    ("CERT_DEPOIS_AUSENTE", rule_cert_depois_ausente),
    ("CERT_ANTES_AUSENTE", rule_cert_antes_ausente),
    ("PADRAO_VENCIDO", rule_padrao_vencido),
    ("IB_SEM_LEITURA", rule_ib_sem_leitura),
    ("IB_VENCIDO", rule_ib_vencido),
    ("ANEXO_VAZIO", rule_anexo_vazio),
    ("ANEXO_ILEGIVEL", rule_anexo_ilegivel),
    ("TOKEN_NAO_RESOLVIDO", rule_token_nao_resolvido),
    ("ANEXO_REF_EXCLUIDO", rule_anexo_ref_excluido),
    ("CICLOS_CONTAGEM", rule_ciclos_contagem),
    ("CICLO_SEM_DADOS", rule_ciclo_sem_dados),
    ("CICLO_SEM_JANELA", rule_ciclo_sem_janela),
    ("DATA_FORA_JANELA", rule_data_fora_janela),
    ("AMBIENTE_VAZIO", rule_ambiente_vazio),
    ("CHECKLIST_REPROVADO", rule_checklist_reprovado),
    ("CANAL_SEM_CERT", rule_canal_sem_cert),
    ("APROVACAO_INTERNA", rule_aprovacao_interna),
])
```

(`fields` já está importado desde a Task 2: `from odoo import fields`.)

- [ ] **Step 4: Rodar e confirmar que passa (as duas classes)**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioRulesAlerta,/afr_qualificacao:TestRelatorioRulesBloqueia --stop-after-init --no-http`
Esperado: 31 testes, 0 falhas.

- [ ] **Step 5: Commit**

Via `git-commit-push` (cwd do submodule), paths `models/relatorio_rules.py tests/test_relatorio_rules.py`, mensagem:
```
feat(relatorio): add warning rules and complete the 17-rule registry

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 4: `action_verificar()` com carry-over das decisões

**Files:**
- Modify: `models/relatorio_verificacao.py`
- Modify: `tests/test_relatorio_gate.py` (nova classe `TestVerificar`)

**Interfaces:**
- Consumes: `relatorio_rules.run_rules(rel)`, `SCAN_CTX` (Task 1).
- Produces:
  - `afr.qualificacao.relatorio.action_verificar() -> True` (UserError se `state != 'draft'`)
  - `_run_verificacao()`: executa a varredura em qualquer estado, usada pelo gate da Task 6
  - `_ai_findings() -> list[dict]`: nesta task devolve `[]`, e a Task 5 substitui pela chamada ao serviço de IA
  - constante `AI_SKIP_CTX = "afr_skip_ai"` em `models/relatorio_verificacao.py`

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_relatorio_gate.py` (import no topo: `from odoo.exceptions import AccessError, UserError, ValidationError`):
```python
@tagged("post_install", "-at_install", "afr_qualificacao")
class TestVerificar(RelatorioTestCommon):

    def test_verificar_grava_achados_de_regra(self):
        self.rel.action_verificar()
        a = self._achado("CERT_DEPOIS_AUSENTE")
        self.assertEqual(len(a), 1)
        self.assertEqual(a.origem, "regra")
        self.assertEqual(a.decisao, "pendente")
        self.assertTrue(self.rel.has_blocking)

    def test_pendente_some_quando_corrigido(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        self.assertTrue(self._achado("AMBIENTE_VAZIO"))
        self.rel.write({"amb_umidade": "45 %UR"})
        self.rel.action_verificar()
        self.assertFalse(self._achado("AMBIENTE_VAZIO"))
        self.assertFalse(self.rel.has_blocking)

    def test_decisao_carregada_quando_repete(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        a = self._achado("AMBIENTE_VAZIO")
        a.write({"decisao": "descartado", "motivo": "Sala sem higrômetro."})
        self.rel.action_verificar()
        b = self._achado("AMBIENTE_VAZIO")
        self.assertEqual(b.id, a.id)
        self.assertEqual(b.decisao, "descartado")
        self.assertEqual(b.motivo, "Sala sem higrômetro.")

    def test_procede_carregado_quando_repete(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        self._achado("AMBIENTE_VAZIO").write({"decisao": "procede"})
        self.rel.action_verificar()
        self.assertEqual(self._achado("AMBIENTE_VAZIO").decisao, "procede")

    def test_decidido_apagado_quando_nao_repete(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        self._achado("AMBIENTE_VAZIO").write({"decisao": "descartado", "motivo": "x"})
        self.rel.write({"amb_umidade": "45 %UR"})
        self.rel.action_verificar()
        self.assertFalse(self._achado("AMBIENTE_VAZIO"))

    def test_verificar_como_usuario(self):
        self.rel.with_user(self.user_qualif).action_verificar()
        self.assertTrue(self._achado("CERT_DEPOIS_AUSENTE"))
        # regra que quebra (ex.: ACL faltando p/ o grupo user) vira bloqueio
        # com o próprio código — não pode passar por achado legítimo
        self._refresh()
        self.assertFalse(self.rel.achado_ids.filtered(
            lambda a: a.mensagem.startswith("Falha ao executar a regra")))

    def test_skip_ai_preserva_achados_de_ia(self):
        ia = self._mk_achado(origem="ia", codigo="IA_ACHADO", onde="Corpo: capa")
        self.rel.with_context(afr_skip_ai=True).action_verificar()
        self.assertTrue(ia.exists())
        self.rel.action_verificar()  # sem skip: IA (desligada) recria só o que vier
        self.assertFalse(ia.exists())
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestVerificar --stop-after-init --no-http`
Esperado: `AttributeError: ... 'action_verificar'`.

- [ ] **Step 3: Implementar**

Substitua `models/relatorio_verificacao.py` inteiro por:
```python
# -*- coding: utf-8 -*-
"""Relatório Final — varredura de inconsistência e gate de emissão (P5)."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import relatorio_rules
from .relatorio_achado import SCAN_CTX

AI_SKIP_CTX = "afr_skip_ai"


class AfrQualificacaoRelatorio(models.Model):
    _inherit = "afr.qualificacao.relatorio"

    achado_ids = fields.One2many(
        "afr.relatorio.achado",
        "relatorio_id",
        string="Achados da verificação",
    )
    has_blocking = fields.Boolean(compute="_compute_blocking", string="Tem bloqueio")
    blocking_summary = fields.Text(compute="_compute_blocking", string="Aguardando")
    achado_pendente_count = fields.Integer(
        compute="_compute_blocking", string="Achados pendentes"
    )

    @api.depends("achado_ids.gravidade", "achado_ids.decisao", "achado_ids.mensagem")
    def _compute_blocking(self):
        for r in self:
            blocking = r.achado_ids.filtered(
                lambda a: a.gravidade == "bloqueia" and a.decisao == "pendente"
            )
            r.has_blocking = bool(blocking)
            r.blocking_summary = "\n".join("• %s" % a.mensagem for a in blocking)
            r.achado_pendente_count = len(r.achado_ids.filtered(
                lambda a: a.decisao == "pendente" and a.gravidade != "info"
            ))

    # ------------------------------------------------------------ varredura
    def action_verificar(self):
        for rel in self:
            if rel.state != "draft":
                raise UserError(_("Só é possível verificar um relatório em rascunho."))
            rel._run_verificacao()
        return True

    def _ai_findings(self):
        """Achados da IA (dicts sem `origem`). Substituído na Task 5."""
        return []

    def _run_verificacao(self):
        """Recria achados pendentes; herda decisões de achados que se repetem.

        Chave de carry-over: (origem, codigo, onde). Decidido que se repete →
        mantém decisão, atualiza mensagem/gravidade (volta a pendente se virar
        bloqueia). Decidido que não se repete → apagado. Com AI_SKIP_CTX os
        achados de IA existentes não são tocados.
        """
        self.ensure_one()
        skip_ai = bool(self.env.context.get(AI_SKIP_CTX))
        Achado = self.env["afr.relatorio.achado"].sudo().with_context(**{SCAN_CTX: True})

        findings = [dict(f, origem="regra") for f in relatorio_rules.run_rules(self)]
        origens = ["regra"]
        if not skip_ai:
            origens.append("ia")
            findings += [dict(f, origem="ia") for f in self._ai_findings()]

        existing = Achado.search([
            ("relatorio_id", "=", self.id),
            ("origem", "in", origens),
        ])
        pending = existing.filtered(lambda a: a.decisao == "pendente")
        decided_recs = existing - pending
        pending.unlink()
        decided = {(a.origem, a.codigo, a.onde or ""): a for a in decided_recs}

        kept = Achado.browse()
        to_create = []
        seen = set()
        for f in findings:
            key = (f["origem"], f["codigo"], f.get("onde") or "")
            if key in seen:
                continue
            seen.add(key)
            rec = decided.get(key)
            if rec:
                vals = {"mensagem": f["mensagem"], "gravidade": f["gravidade"]}
                if f["gravidade"] == "bloqueia":
                    vals.update(decisao="pendente", motivo=False)
                rec.write(vals)
                kept |= rec
            else:
                to_create.append({
                    "relatorio_id": self.id,
                    "origem": f["origem"],
                    "codigo": f["codigo"],
                    "gravidade": f["gravidade"],
                    "mensagem": f["mensagem"],
                    "onde": f.get("onde") or "",
                    "decisao": "pendente",
                })
        (decided_recs - kept).unlink()
        if to_create:
            Achado.create(to_create)
        self.invalidate_recordset(["achado_ids"])

        if not self.env.context.get(relatorio_rules.EMISSION_CTX):
            grav = [f["gravidade"] for f in findings]
            self.message_post(body=_(
                "Verificação executada: %(b)s bloqueio(s), %(a)s alerta(s), "
                "%(i)s informativo(s).",
                b=grav.count("bloqueia"), a=grav.count("alerta"), i=grav.count("info"),
            ))
        return True
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestVerificar,/afr_qualificacao:TestAchadoModel --stop-after-init --no-http`
Esperado: 14 testes, 0 falhas.

- [ ] **Step 5: Commit**

Via `git-commit-push` (cwd do submodule), paths `models/relatorio_verificacao.py tests/test_relatorio_gate.py`, mensagem:
```
feat(relatorio): add verify action with decision carry-over

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 5: Serviço de IA `afr.relatorio.ai` + configurações

**Files:**
- Create: `models/relatorio_ai.py`
- Modify: `models/__init__.py`
- Modify: `models/relatorio_verificacao.py` (`_ai_findings`)
- Modify: `models/res_config_settings.py`
- Create: `tests/test_relatorio_ai.py`
- Modify: `tests/__init__.py`

**Interfaces:**
- Consumes: `relatorio_rules.cycle_counts(rel)` (Task 3); `rel._render_block_body(block)` (P3); `anexo._resolve_files()`, `anexo.numero` (P3/P4); `rel.revision_label`, `rel.partner_id`, `rel.equipment_id.tag/serial_number` (P1/engc_os).
- Produces (módulo `odoo.addons.afr_qualificacao.models.relatorio_ai`):
  - constantes `OPENROUTER_URL`, `PARAM_ENABLED`, `PARAM_API_KEY`, `PARAM_MODEL`, `PARAM_TIMEOUT`, `DEFAULT_MODEL = "google/gemma-4-31b-it"`, `DEFAULT_TIMEOUT = 60`, `MAX_CHUNK_CHARS = 12000`, `MAX_PDF_PAGES = 15`, `CODIGO_IA = "IA_ACHADO"`, `CODIGO_INDISPONIVEL = "IA_INDISPONIVEL"`, `SYSTEM_PROMPT`
  - funções puras `parse_ai_json(content) -> list` (lança `ValueError`), `truncate(text, limit=MAX_CHUNK_CHARS) -> str`, `pdf_to_text(data) -> str`
  - `afr.relatorio.ai`: `review(relatorio) -> list[dict]` (dicts `codigo/gravidade/mensagem/onde`, gravidade só `alerta`/`info`), `_call(messages) -> str`, `_build_chunks(relatorio) -> list[dict(label, text)]`, `_identity_card(relatorio) -> dict`, `_is_enabled() -> bool`
  - `res.config.settings`: `afr_ai_enabled`, `afr_ai_api_key`, `afr_ai_model`, `afr_ai_timeout`

- [ ] **Step 1: Escrever os testes**

`tests/test_relatorio_ai.py`:
```python
"""P5 — revisão por IA (OpenRouter) com requests.post mockado."""
from unittest.mock import MagicMock, patch

import requests

from odoo.tests import tagged

from ..models import relatorio_ai
from ..models.relatorio_ai import (
    CODIGO_IA,
    CODIGO_INDISPONIVEL,
    DEFAULT_MODEL,
    MAX_CHUNK_CHARS,
    OPENROUTER_URL,
    parse_ai_json,
    truncate,
)
from .common_relatorio import RelatorioTestCommon, make_pdf

POST = "odoo.addons.afr_qualificacao.models.relatorio_ai.requests.post"

VALID = '{"achados": [{"gravidade": "alerta", "onde": "Capa", "trecho": "TAG AC-99", "explicacao": "TAG diverge do cartão."}]}'


def _resp(content):
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {"choices": [{"message": {"content": content}}]}
    return m


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestRelatorioAiPure(RelatorioTestCommon):

    def test_parse_json_puro(self):
        self.assertEqual(len(parse_ai_json(VALID)), 1)

    def test_parse_json_com_cerca(self):
        self.assertEqual(len(parse_ai_json("Segue:\n```json\n%s\n```\nFim." % VALID)), 1)

    def test_parse_json_com_texto_em_volta(self):
        self.assertEqual(len(parse_ai_json("Resultado: %s obrigado" % VALID)), 1)

    def test_parse_lixo(self):
        with self.assertRaises(ValueError):
            parse_ai_json("não encontrei nada de errado")
        with self.assertRaises(ValueError):
            parse_ai_json('{"resultado": []}')

    def test_truncate(self):
        self.assertEqual(truncate("abc"), "abc")
        long_text = "x" * (MAX_CHUNK_CHARS * 3)
        self.assertEqual(len(truncate(long_text)), MAX_CHUNK_CHARS)
        self.assertIn("truncado", truncate(long_text))


@tagged("post_install", "-at_install", "afr_qualificacao")
class TestRelatorioAi(RelatorioTestCommon):

    def setUp(self):
        super().setUp()
        self.icp = self.env["ir.config_parameter"].sudo()
        self.icp.set_param(relatorio_ai.PARAM_ENABLED, "True")
        self.icp.set_param(relatorio_ai.PARAM_API_KEY, "sk-test")
        self.AI = self.env["afr.relatorio.ai"]

    def test_desligada_nao_chama(self):
        self.icp.set_param(relatorio_ai.PARAM_ENABLED, False)
        with patch(POST) as post:
            self.assertEqual(self.AI.review(self.rel), [])
        post.assert_not_called()

    def test_sem_chave_vira_indisponivel_sem_chamar(self):
        self.icp.set_param(relatorio_ai.PARAM_API_KEY, False)
        with patch(POST) as post:
            out = self.AI.review(self.rel)
        post.assert_not_called()
        self.assertEqual([f["codigo"] for f in out], [CODIGO_INDISPONIVEL])
        self.assertEqual(out[0]["gravidade"], "info")

    def test_json_valido(self):
        with patch(POST, return_value=_resp(VALID)) as post:
            out = self.AI.review(self.rel)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["codigo"], CODIGO_IA)
        self.assertEqual(out[0]["gravidade"], "alerta")
        self.assertTrue(out[0]["mensagem"].startswith("IA — verificar"))
        args, kwargs = post.call_args
        self.assertEqual(args[0], OPENROUTER_URL)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(kwargs["json"]["model"], DEFAULT_MODEL)
        self.assertEqual(kwargs["timeout"], 60)
        user_msg = kwargs["json"]["messages"][1]["content"]
        self.assertIn(self.rel.name, user_msg)  # cartão de identidade

    def test_json_com_cerca(self):
        with patch(POST, return_value=_resp("```json\n%s\n```" % VALID)):
            out = self.AI.review(self.rel)
        self.assertEqual([f["codigo"] for f in out], [CODIGO_IA])

    def test_lixo_vira_indisponivel(self):
        with patch(POST, return_value=_resp("Tudo certo, nada a apontar.")):
            out = self.AI.review(self.rel)
        self.assertEqual([f["codigo"] for f in out], [CODIGO_INDISPONIVEL])

    def test_timeout_interrompe_e_vira_indisponivel(self):
        self._anexo(code="dados", pdfs=[make_pdf("Ciclo 1 dados")])
        with patch(POST, side_effect=requests.Timeout("lento")) as post:
            out = self.AI.review(self.rel)
        self.assertEqual(post.call_count, 1)  # não tenta o 2º trecho
        self.assertEqual([f["codigo"] for f in out], [CODIGO_INDISPONIVEL])

    def test_connection_error_vira_indisponivel(self):
        with patch(POST, side_effect=requests.ConnectionError("offline")):
            out = self.AI.review(self.rel)
        self.assertEqual([f["codigo"] for f in out], [CODIGO_INDISPONIVEL])

    def test_gravidade_bloqueia_da_ia_vira_alerta(self):
        content = '{"achados": [{"gravidade": "bloqueia", "onde": "x", "trecho": "y", "explicacao": "z"}, {"gravidade": "info", "onde": "a", "trecho": "b", "explicacao": "c"}]}'
        with patch(POST, return_value=_resp(content)):
            out = self.AI.review(self.rel)
        self.assertEqual(sorted(f["gravidade"] for f in out), ["alerta", "info"])

    def test_chunk_truncado(self):
        self._block("<p>%s</p>" % ("palavra " * 5000), title="Longo")
        chunks = self.AI._build_chunks(self.rel)
        self.assertTrue(all(len(c["text"]) <= MAX_CHUNK_CHARS for c in chunks))

    def test_chunk_por_anexo_com_texto_do_pdf(self):
        self._anexo(code="dados", title="Dados do validador", pdfs=[make_pdf("Ciclo 1 dados")])
        chunks = self.AI._build_chunks(self.rel)
        self.assertEqual(len(chunks), 2)
        self.assertIn("Ciclo 1", chunks[1]["text"])
        with patch(POST, return_value=_resp('{"achados": []}')) as post:
            self.assertEqual(self.AI.review(self.rel), [])
        self.assertEqual(post.call_count, 2)

    def test_verificar_grava_achado_de_ia(self):
        with patch(POST, return_value=_resp(VALID)):
            self.rel.action_verificar()
        ia = self.rel.achado_ids.filtered(lambda a: a.origem == "ia")
        self.assertEqual(ia.mapped("codigo"), [CODIGO_IA])

    def test_settings_gravam_parametros(self):
        self.env["res.config.settings"].create({
            "afr_ai_enabled": True,
            "afr_ai_model": "provedor/modelo-teste",
            "afr_ai_timeout": 30,
        }).execute()
        self.assertEqual(self.icp.get_param(relatorio_ai.PARAM_MODEL), "provedor/modelo-teste")
        self.assertEqual(self.icp.get_param(relatorio_ai.PARAM_TIMEOUT), "30")
        self.assertTrue(self.AI._is_enabled())
```

Em `tests/__init__.py`, logo abaixo de `from . import test_relatorio_rules`:
```python
from . import test_relatorio_ai
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioAi,/afr_qualificacao:TestRelatorioAiPure --stop-after-init --no-http`
Esperado: `ImportError: relatorio_ai`.

- [ ] **Step 3: Implementar `models/relatorio_ai.py`**

```python
# -*- coding: utf-8 -*-
"""Revisão assistiva por IA (OpenRouter) do Relatório Final — spec §7.2.

Desligada por padrão (`afr_qualificacao.ai_enabled`). Uma chamada para o
corpo (texto dos blocos + dados estruturados JSON) + uma por anexo com texto
extraído (pdfminer), cada uma truncada a MAX_CHUNK_CHARS e acompanhada do
"cartão de identidade". Achados só `alerta`/`info`. Qualquer falha (rede,
HTTP, JSON inválido) vira UM achado IA_INDISPONIVEL (info); falha de rede
interrompe os trechos seguintes.
"""
import io
import json
import logging
import re

import requests

from odoo import _, models
from odoo.tools import html2plaintext

from . import relatorio_rules

_logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PARAM_ENABLED = "afr_qualificacao.ai_enabled"
PARAM_API_KEY = "afr_qualificacao.ai_api_key"
PARAM_MODEL = "afr_qualificacao.ai_model"
PARAM_TIMEOUT = "afr_qualificacao.ai_timeout"
# Mesmo modelo que o PWA usa em produção (variante paga; `:free` devolve 429).
DEFAULT_MODEL = "google/gemma-4-31b-it"
DEFAULT_TIMEOUT = 60
MAX_CHUNK_CHARS = 12000
MAX_PDF_PAGES = 15
CODIGO_IA = "IA_ACHADO"
CODIGO_INDISPONIVEL = "IA_INDISPONIVEL"
TRUNC_MARKER = "\n[... texto truncado ...]"

SYSTEM_PROMPT = """Você é um revisor técnico de relatórios de qualificação térmica de autoclaves (esterilização a vapor), redigidos em português do Brasil. Sua tarefa é apontar INCONSISTÊNCIAS DE DOCUMENTO no trecho recebido, comparando-o com o CARTÃO DE IDENTIDADE do relatório (fonte da verdade) e com ele mesmo.

Procure principalmente:
1. Identificação divergente do cartão: nome do cliente, TAG, número de série, modelo do equipamento, número do relatório ou revisão.
2. Datas incoerentes: datas fora do período de ensaios do cartão, ano diferente, gráficos ou impressões de outro período (arquivo reaproveitado), leitura de indicador biológico antes da incubação.
3. Numeração e contagem: "Página X de Y" com X maior que Y, quantidade de ciclos no texto diferente dos ciclos contratados, anexo citado que não existe.
4. Valores técnicos que se contradizem dentro do trecho: temperatura, tempo, pressão, F0, tolerância e critérios de aceitação.
5. Texto de modelo não preenchido: marcadores como {{ }}, "XXX", "[preencher]", nome de outro cliente.

Regras:
- Não invente problemas. Se não houver inconsistência, devolva a lista vazia.
- Não julgue se o equipamento foi aprovado ou reprovado; aponte apenas inconsistências do documento.
- Use "alerta" para inconsistência provável que pode invalidar o relatório e "info" para observação menor (grafia, formatação).
- Nunca use gravidade diferente de "alerta" ou "info".
- "onde" localiza o problema no trecho (seção, página, tabela ou ciclo). "trecho" copia literalmente o texto problemático (até 200 caracteres). "explicacao" diz, em uma ou duas frases, por que é inconsistente.

Responda SOMENTE com um JSON válido, sem nenhum texto antes ou depois, exatamente neste formato:
{"achados": [{"gravidade": "alerta", "onde": "...", "trecho": "...", "explicacao": "..."}]}"""

FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)


def parse_ai_json(content):
    """Extrai a lista `achados` de uma resposta possivelmente suja."""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("resposta vazia")
    text = content.strip()
    fence = FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("JSON não encontrado na resposta")
        data = json.loads(text[start:end + 1])
    if not isinstance(data, dict) or not isinstance(data.get("achados"), list):
        raise ValueError("JSON sem a lista 'achados'")
    return data["achados"]


def truncate(text, limit=MAX_CHUNK_CHARS):
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - len(TRUNC_MARKER)] + TRUNC_MARKER


def pdf_to_text(data):
    from pdfminer.high_level import extract_text

    return extract_text(io.BytesIO(data), maxpages=MAX_PDF_PAGES) or ""


class AfrRelatorioAi(models.AbstractModel):
    _name = "afr.relatorio.ai"
    _description = "Revisão do Relatório Final por IA"

    # ------------------------------------------------------------ config
    def _param(self, key, default=False):
        return self.env["ir.config_parameter"].sudo().get_param(key, default)

    def _is_enabled(self):
        return str(self._param(PARAM_ENABLED, "False")).strip().lower() in (
            "1", "true", "yes", "on",
        )

    def _timeout(self):
        try:
            return max(5, int(self._param(PARAM_TIMEOUT, DEFAULT_TIMEOUT)))
        except (TypeError, ValueError):
            return DEFAULT_TIMEOUT

    # ------------------------------------------------------------ HTTP
    def _call(self, messages):
        """POST no OpenRouter; devolve o `content` da 1ª escolha."""
        api_key = self._param(PARAM_API_KEY)
        if not api_key:
            raise ValueError("chave de API não configurada")
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": "Bearer %s" % api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": self._param(PARAM_MODEL) or DEFAULT_MODEL,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 2000,
            },
            timeout=self._timeout(),
        )
        resp.raise_for_status()
        data = resp.json()
        content = (((data or {}).get("choices") or [{}])[0].get("message") or {}).get("content")
        if not isinstance(content, str):
            raise ValueError("resposta sem conteúdo")
        return content

    # ------------------------------------------------------------ contexto
    def _identity_card(self, rel):
        eq = rel.equipment_id
        return {
            "relatorio": rel.name,
            "revisao": rel.revision_label,
            "cliente": rel.partner_id.name or "",
            "equipamento": eq.display_name or "",
            "tag": eq.tag or "",
            "numero_serie": eq.serial_number or "",
            "data_inicio_ensaios": str(rel.data_inicio_ensaios or ""),
            "data_fim_ensaios": str(rel.data_fim_ensaios or ""),
            "ciclos_contratados": {
                ctype.name: vals[0]
                for ctype, vals in relatorio_rules.cycle_counts(rel).items()
            },
        }

    def _structured_data(self, rel):
        return {
            "ambiente": {"temperatura": rel.amb_temperatura or "", "umidade": rel.amb_umidade or ""},
            "criterios": {"tolerancia_acima_c": rel.tolerancia_acima, "f0_fator": rel.criterio_f0_fator},
            "checklist": [
                {"grupo": l.grupo or "", "descricao": l.descricao or "",
                 "status": l.status or "", "comentario": l.comentario or ""}
                for l in rel.checklist_ids
            ],
            "indicadores": [
                {"tipo": i.tipo or "", "marca": i.marca or "", "modelo_tipo": i.modelo_tipo or "",
                 "lote": i.lote or "", "validade": str(i.validade or ""),
                 "valor_d": i.valor_d, "populacao": i.populacao or ""}
                for i in rel.indicador_ids
            ],
            "leituras_ib": [
                {"ciclo": l.cycle_id.display_name or "", "resultado": l.resultado or "",
                 "data_leitura": str(l.data_leitura or ""),
                 "controle_positivo_ok": l.controle_positivo_ok}
                for l in rel.leitura_ib_ids
            ],
            "ciclos": [
                {"ciclo": c.display_name, "estado": c.state,
                 "janela_inicio": str(c.janela_inicio or ""), "janela_fim": str(c.janela_fim or ""),
                 "sensores": [{"canal": s.canal or "", "posicao": s.posicao or "", "ib": s.ib_label or ""}
                              for s in c.sensor_pos_ids]}
                for c in rel.cycle_ids
            ],
        }

    def _body_text(self, rel):
        parts = []
        for block in rel.block_ids.filtered("included").sorted(lambda b: (b.sequence, b.id)):
            try:
                html = rel._render_block_body(block)
            except Exception:  # noqa: BLE001 — TOKEN_NAO_RESOLVIDO já reporta
                continue
            text = html2plaintext(str(html or "")).strip()
            if text:
                parts.append("## %s\n%s" % (block.title or block.block_kind, text))
        return "\n\n".join(parts)

    def _build_chunks(self, rel):
        chunks = [{
            "label": "Corpo do relatório",
            "text": truncate("TEXTO DO RELATÓRIO:\n%s\n\nDADOS ESTRUTURADOS (JSON):\n%s" % (
                self._body_text(rel),
                json.dumps(self._structured_data(rel), ensure_ascii=False, indent=1),
            )),
        }]
        for anexo in rel.anexo_ids.filtered("included").sorted(lambda a: (a.sequence, a.id)):
            try:
                files = anexo._resolve_files()
            except Exception:  # noqa: BLE001 — ANEXO_* já reportam
                files = []
            texts = []
            for content, mimetype, legenda in files:
                if (mimetype or "") != "application/pdf":
                    continue
                try:
                    text = pdf_to_text(content)
                except Exception as exc:  # noqa: BLE001
                    _logger.info("pdfminer falhou no anexo %s: %s", anexo.id, exc)
                    continue
                if text.strip():
                    texts.append("### %s\n%s" % (legenda or "", text.strip()))
            if texts:
                chunks.append({
                    "label": "Anexo %s — %s" % (anexo.numero or "", anexo.title or anexo.code),
                    "text": truncate("\n\n".join(texts)),
                })
        return chunks

    def _messages(self, card, chunk):
        user = (
            "CARTÃO DE IDENTIDADE DO RELATÓRIO (fonte da verdade):\n%s\n\n"
            "TRECHO EM ANÁLISE: %s\n\n%s"
        ) % (json.dumps(card, ensure_ascii=False, indent=1), chunk["label"], chunk["text"])
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]

    # ------------------------------------------------------------ saída
    def _indisponivel(self, msg):
        return {"codigo": CODIGO_INDISPONIVEL, "gravidade": "info",
                "mensagem": msg[:1000], "onde": "IA"}

    def _to_findings(self, label, itens):
        out = []
        for it in itens:
            if not isinstance(it, dict):
                continue
            grav = "info" if str(it.get("gravidade") or "").strip().lower() == "info" else "alerta"
            explic = str(it.get("explicacao") or "").strip()
            trecho = str(it.get("trecho") or "").strip()
            if not explic and not trecho:
                continue
            msg = _("IA — verificar: %s") % (explic or trecho)
            if explic and trecho:
                msg += ' — trecho: "%s"' % trecho[:300]
            out.append({
                "codigo": CODIGO_IA,
                "gravidade": grav,
                "mensagem": msg[:2000],
                "onde": "%s: %s" % (label, str(it.get("onde") or "").strip()[:200]),
            })
        return out

    def review(self, relatorio):
        """Lista de achados (dicts) da IA; [] quando desligada."""
        relatorio.ensure_one()
        if not self._is_enabled():
            return []
        if not self._param(PARAM_API_KEY):
            return [self._indisponivel(_("IA ligada, mas sem chave de API configurada."))]
        card = self._identity_card(relatorio)
        out, falhas = [], []
        chunks = self._build_chunks(relatorio)
        for idx, chunk in enumerate(chunks):
            try:
                itens = parse_ai_json(self._call(self._messages(card, chunk)))
            except requests.RequestException as exc:
                _logger.warning("IA: falha de rede no relatório %s: %s", relatorio.id, exc)
                restantes = len(chunks) - idx - 1
                falhas.append("%s (%s)%s" % (
                    chunk["label"], exc,
                    _("; %d trecho(s) não enviados") % restantes if restantes else "",
                ))
                break
            except Exception as exc:  # noqa: BLE001 — resposta inválida
                _logger.warning("IA: resposta inválida no relatório %s: %s", relatorio.id, exc)
                falhas.append("%s (%s)" % (chunk["label"], exc))
                continue
            out.extend(self._to_findings(chunk["label"], itens))
        if falhas:
            out.append(self._indisponivel(
                _("IA indisponível em %d trecho(s): %s") % (len(falhas), "; ".join(falhas))
            ))
        return out
```

Em `models/__init__.py`, logo abaixo de `from . import relatorio_verificacao`:
```python
from . import relatorio_ai              # P5 — revisão assistiva OpenRouter
```

Em `models/relatorio_verificacao.py`, substitua o método `_ai_findings` por:
```python
    def _ai_findings(self):
        """Achados da IA (dicts sem `origem`); [] quando desligada."""
        return self.env["afr.relatorio.ai"].review(self)
```

Em `models/res_config_settings.py`, acrescente o import `from .relatorio_ai import DEFAULT_MODEL, DEFAULT_TIMEOUT` depois de `from odoo import fields, models` e os campos no fim da classe:
```python
    # Relatório Final P5 — revisão por IA (OpenRouter), spec §7.2
    afr_ai_enabled = fields.Boolean(
        string="Revisão por IA no Relatório Final",
        config_parameter="afr_qualificacao.ai_enabled",
        help="Envia o texto do relatório e dos anexos ao OpenRouter na verificação. "
             "Desligado por padrão (dado do cliente sai do servidor).",
    )
    afr_ai_api_key = fields.Char(
        string="Chave de API (OpenRouter)",
        config_parameter="afr_qualificacao.ai_api_key",
    )
    afr_ai_model = fields.Char(
        string="Modelo",
        config_parameter="afr_qualificacao.ai_model",
        default=DEFAULT_MODEL,
        help="Use modelo pago; variantes ':free' devolvem 429 na prática.",
    )
    afr_ai_timeout = fields.Integer(
        string="Timeout (s)",
        config_parameter="afr_qualificacao.ai_timeout",
        default=DEFAULT_TIMEOUT,
    )
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestRelatorioAi,/afr_qualificacao:TestRelatorioAiPure,/afr_qualificacao:TestVerificar --stop-after-init --no-http`
Esperado: 24 testes, 0 falhas. `TestVerificar.test_skip_ai_preserva_achados_de_ia` continua verde porque a IA está desligada por padrão.

- [ ] **Step 5: Commit**

Via `git-commit-push` (cwd do submodule), paths `models/relatorio_ai.py models/__init__.py models/relatorio_verificacao.py models/res_config_settings.py tests/test_relatorio_ai.py tests/__init__.py`, mensagem:
```
feat(relatorio): add OpenRouter assistive review with tolerant parsing

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 6: Gate de emissão + `scan_snapshot`

**Files:**
- Modify: `models/relatorio_verificacao.py` (overrides)
- Modify: `tests/test_relatorio_gate.py` (nova classe `TestGateEmissao`)

**Interfaces:**
- Consumes (P4): `super()._check_emission_gate() -> list[str]` (aprovações internas); `action_emitir()`, que chama o gate (UserError se houver problema), monta o PDF e grava `emissao.scan_snapshot = self._scan_snapshot()`; `current_emissao_id`; `state`; `tests/relatorio_fakes.py::FakeCorpo`.
- Produces:
  - `_check_emission_gate() -> list[str]`: `super()` + bloqueios pendentes (exceto `APROVACAO_INTERNA`) + **todo** alerta pendente, de regra ou de IA. `info` é ignorado. Antes de montar a lista, roda `_run_verificacao()` com `afr_emission_check` e `afr_skip_ai`.
  - `_scan_snapshot() -> str`: JSON (lista ordenada por id) com `origem, codigo, gravidade, mensagem, onde, decisao, motivo, decidido_por, decidido_em`.

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_relatorio_gate.py` (imports no topo: `import json` e `from .relatorio_fakes import FakeCorpo`):
```python
@tagged("post_install", "-at_install", "afr_qualificacao")
class TestGateEmissao(RelatorioTestCommon):

    def _emit(self):
        # mesmo mock dos testes de P4: _render_qweb_pdf devolve HTML em modo teste
        with FakeCorpo().patch(self.env):
            return self.rel.action_emitir()

    def test_gate_bloqueia_com_bloqueio_pendente(self):
        self._approve_internal()
        problems = self.rel._check_emission_gate()
        self.assertTrue(any("CERT_DEPOIS_AUSENTE" in p for p in problems))
        self.assertFalse(any("Falha ao executar a regra" in p for p in problems))
        with self.assertRaises(UserError):
            self._emit()
        self.assertEqual(self.rel.state, "draft")

    def test_alerta_de_regra_precisa_de_decisao(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self._approve_internal()
        problems = self.rel._check_emission_gate()
        self.assertTrue(any("AMBIENTE_VAZIO" in p for p in problems))
        self.assertFalse(any("Falha ao executar a regra" in p for p in problems))
        self._achado("AMBIENTE_VAZIO").write(
            {"decisao": "descartado", "motivo": "Sala sem higrômetro."})
        self.assertFalse(any("AMBIENTE_VAZIO" in p for p in self.rel._check_emission_gate()))

    def test_alerta_de_ia_pendente_bloqueia_ate_decidir(self):
        self._make_clean()
        self._approve_internal()
        ia = self._mk_achado(origem="ia", codigo="IA_ACHADO", gravidade="alerta",
                             onde="Corpo do relatório: capa")
        problems = self.rel._check_emission_gate()
        self.assertTrue(ia.exists())  # re-verificação na emissão não apaga IA
        self.assertTrue(any("IA_ACHADO" in p for p in problems))
        ia.write({"decisao": "descartado", "motivo": "TAG conferida na plaqueta."})
        self.assertEqual(self.rel._check_emission_gate(), [])
        self.assertEqual(ia.decisao, "descartado")

    def test_info_de_ia_nao_bloqueia(self):
        self._make_clean()
        self._approve_internal()
        ia = self._mk_achado(origem="ia", codigo="IA_ACHADO", gravidade="info",
                             onde="Corpo do relatório: grafia")
        indisp = self._mk_achado(origem="ia", codigo="IA_INDISPONIVEL", gravidade="info",
                                 onde="IA")
        self.assertEqual(self.rel._check_emission_gate(), [])
        self.assertTrue(ia.exists() and indisp.exists())

    def test_aprovacao_interna_nao_duplica_mensagem_do_super(self):
        self._make_clean()
        problems = self.rel._check_emission_gate()
        self.assertFalse(any("APROVACAO_INTERNA" in p for p in problems))
        self.assertTrue(problems)  # vêm do super() de P4

    def test_decisao_pelo_form_nao_zera_aprovacoes(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        self._approve_internal()
        a = self._achado("AMBIENTE_VAZIO")
        self.rel.write({"achado_ids": [(1, a.id, {"decisao": "descartado", "motivo": "Sem higrômetro."})]})
        self._refresh()
        internas = self.rel.aprovacao_ids.filtered(lambda x: x.papel in ("elaborador", "emissor"))
        self.assertTrue(all(x.approved_at for x in internas))

    def test_emissao_grava_scan_snapshot(self):
        self._make_clean()
        self.rel.write({"amb_umidade": False})
        self.rel.action_verificar()
        self._achado("AMBIENTE_VAZIO").write(
            {"decisao": "descartado", "motivo": "Sala sem higrômetro; registrado em ata."})
        self._approve_internal()
        self._emit()
        self._refresh()
        self.assertEqual(self.rel.state, "issued")
        snap = json.loads(self.rel.current_emissao_id.scan_snapshot)
        item = [s for s in snap if s["codigo"] == "AMBIENTE_VAZIO"]
        self.assertEqual(len(item), 1)
        self.assertEqual(item[0]["decisao"], "descartado")
        self.assertEqual(item[0]["motivo"], "Sala sem higrômetro; registrado em ata.")
        self.assertTrue(item[0]["decidido_por"])

    def test_verificar_bloqueado_fora_de_rascunho(self):
        self._make_clean()
        self._approve_internal()
        self._emit()
        with self.assertRaises(UserError):
            self.rel.action_verificar()
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestGateEmissao --stop-after-init --no-http`
Esperado: falhas em `test_gate_bloqueia_com_bloqueio_pendente` (gate de P4 não conhece achados) e em `test_emissao_grava_scan_snapshot` (snapshot `"[]"`).

- [ ] **Step 3: Implementar os overrides**

Acrescente `import json` no topo de `models/relatorio_verificacao.py` e estes métodos no fim da classe:
```python
    # ------------------------------------------------------------ gate (§7.3)
    def _check_emission_gate(self):
        """super() (P4: aprovações internas) + achados pendentes (§7.3).

        Re-verifica antes (só regras, determinístico; achados de IA intactos).
        Todo `alerta` pendente — regra OU IA — impede; `info` é ignorado.
        IA nunca gera `bloqueia`. APROVACAO_INTERNA já vem do super().
        """
        problems = list(super()._check_emission_gate())
        self.ensure_one()
        self.with_context(**{
            relatorio_rules.EMISSION_CTX: True,
            AI_SKIP_CTX: True,
        })._run_verificacao()
        self.invalidate_recordset(["achado_ids"])
        for a in self.achado_ids.sorted("id"):
            if a.decisao != "pendente" or a.gravidade == "info":
                continue
            if a.codigo == "APROVACAO_INTERNA":
                continue
            if a.gravidade == "bloqueia":
                problems.append(_("Bloqueio [%s]: %s") % (a.codigo, a.mensagem))
            elif a.gravidade == "alerta":
                problems.append(_("Alerta sem decisão [%s]: %s") % (a.codigo, a.mensagem))
        return problems

    def _scan_snapshot(self):
        self.ensure_one()
        data = [{
            "origem": a.origem,
            "codigo": a.codigo,
            "gravidade": a.gravidade,
            "mensagem": a.mensagem,
            "onde": a.onde or "",
            "decisao": a.decisao,
            "motivo": a.motivo or "",
            "decidido_por": a.decidido_por.name or "",
            "decidido_em": fields.Datetime.to_string(a.decidido_em) if a.decidido_em else "",
        } for a in self.achado_ids.sorted("id")]
        return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao:TestGateEmissao,/afr_qualificacao:TestVerificar,/afr_qualificacao:TestAchadoModel --stop-after-init --no-http`
Esperado: 22 testes, 0 falhas.

- [ ] **Step 5: Commit**

Via `git-commit-push` (cwd do submodule), paths `models/relatorio_verificacao.py tests/test_relatorio_gate.py`, mensagem:
```
feat(relatorio): gate emission on rule findings and snapshot decisions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 7: UI: página Verificação, banner "Aguardando", botão Verificar, configurações de IA

**Files:**
- Create: `views/relatorio_verificacao_views.xml`
- Modify: `views/res_config_settings_views.xml`
- Modify: `__manifest__.py` (`data`)

**Interfaces:**
- Consumes: form `afr_qualificacao.view_afr_qualificacao_relatorio_form` (P1, confirmado), com `//header`, `//sheet` e a página `page_anexos` (P3); campos das Tasks 1 e 4.
- Produces: view herdada `afr_qualificacao.view_afr_qualificacao_relatorio_form_verificacao`; página `name="page_verificacao"`.

- [ ] **Step 1: Criar `views/relatorio_verificacao_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="view_afr_qualificacao_relatorio_form_verificacao" model="ir.ui.view">
        <field name="name">afr.qualificacao.relatorio.form.verificacao</field>
        <field name="model">afr.qualificacao.relatorio</field>
        <field name="inherit_id" ref="afr_qualificacao.view_afr_qualificacao_relatorio_form"/>
        <field name="arch" type="xml">
            <xpath expr="//header" position="inside">
                <button name="action_verificar" type="object" string="Verificar"
                        icon="fa-search" class="btn-secondary"
                        groups="afr_qualificacao.group_afr_qualificacao_user"
                        attrs="{'invisible': [('state', '!=', 'draft')]}"/>
            </xpath>
            <xpath expr="//sheet" position="before">
                <field name="has_blocking" invisible="1"/>
                <div class="alert alert-danger mb-0" role="alert"
                     attrs="{'invisible': ['|', ('has_blocking', '=', False), ('state', '!=', 'draft')]}">
                    <strong>Aguardando:</strong>
                    <field name="blocking_summary" nolabel="1" readonly="1"/>
                </div>
            </xpath>
            <xpath expr="//page[@name='page_anexos']" position="after">
                <page name="page_verificacao" string="Verificação">
                    <field name="achado_pendente_count" invisible="1"/>
                    <div class="text-muted mb-2">
                        Clique em <strong>Verificar</strong> para rodar as regras (e a IA, se ligada em
                        Configurações). <strong>Bloqueios</strong> só saem corrigindo o dado e verificando de
                        novo. <strong>Alertas</strong> (de regra ou da IA) precisam de decisão antes de emitir:
                        <em>Procede</em> (corrigido) ou <em>Descartado</em> (com motivo). Itens
                        <em>Info</em> não impedem a emissão.
                    </div>
                    <field name="achado_ids" nolabel="1"
                           attrs="{'readonly': [('state', '!=', 'draft')]}">
                        <tree editable="bottom" create="0" delete="0"
                              decoration-danger="gravidade == 'bloqueia'"
                              decoration-warning="gravidade == 'alerta' and decisao == 'pendente'"
                              decoration-info="gravidade == 'info'"
                              decoration-muted="decisao != 'pendente'"
                              decoration-it="origem == 'ia'">
                            <field name="origem" widget="badge" readonly="1"
                                   decoration-info="origem == 'ia'"
                                   decoration-muted="origem == 'regra'"/>
                            <field name="gravidade" widget="badge" readonly="1"
                                   decoration-danger="gravidade == 'bloqueia'"
                                   decoration-warning="gravidade == 'alerta'"
                                   decoration-info="gravidade == 'info'"/>
                            <field name="codigo" readonly="1"/>
                            <field name="mensagem" readonly="1"/>
                            <field name="onde" readonly="1" optional="show"/>
                            <field name="decisao"
                                   attrs="{'readonly': [('gravidade', '=', 'bloqueia')]}"/>
                            <field name="motivo"
                                   attrs="{'required': [('decisao', '=', 'descartado')],
                                           'readonly': [('gravidade', '=', 'bloqueia')]}"/>
                            <field name="decidido_por" readonly="1" optional="show"/>
                            <field name="decidido_em" readonly="1" optional="hide"/>
                        </tree>
                    </field>
                </page>
            </xpath>
        </field>
    </record>

</odoo>
```

- [ ] **Step 2: Bloco de IA nas configurações**

Em `views/res_config_settings_views.xml`, dentro do `<div class="app_settings_block" ... data-key="afr_qualificacao" ...>`, logo **depois** do `</div>` que fecha o `<div class="row mt16 o_settings_container">` existente, insira:
```xml
                    <h2>Relatório Final — Verificação por IA</h2>
                    <div class="row mt16 o_settings_container">
                        <div class="col-12 col-lg-6 o_setting_box">
                            <div class="o_setting_left_pane">
                                <field name="afr_ai_enabled"/>
                            </div>
                            <div class="o_setting_right_pane">
                                <label for="afr_ai_enabled"/>
                                <div class="text-muted">
                                    Na verificação do relatório, envia o texto dos blocos e dos anexos ao
                                    OpenRouter e registra achados "IA — verificar" (alerta ou info; alerta precisa de decisão antes de emitir). O dado do
                                    cliente sai do servidor: ligar é decisão do gestor.
                                </div>
                                <div class="mt8" attrs="{'invisible': [('afr_ai_enabled', '=', False)]}">
                                    <div class="row">
                                        <label for="afr_ai_api_key" class="col-lg-4 o_light_label"/>
                                        <field name="afr_ai_api_key" password="True" class="col-lg-8"/>
                                    </div>
                                    <div class="row">
                                        <label for="afr_ai_model" class="col-lg-4 o_light_label"/>
                                        <field name="afr_ai_model" class="col-lg-8"/>
                                    </div>
                                    <div class="row">
                                        <label for="afr_ai_timeout" class="col-lg-4 o_light_label"/>
                                        <field name="afr_ai_timeout" class="col-lg-8"/>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
```

- [ ] **Step 3: Registrar a view no manifest**

Em `__manifest__.py`, acrescente como **último** item da lista `"data"` (inherit precisa do form de P1 já carregado):
```python
        # Relatório Final P5 — página Verificação + botão Verificar + banner
        "views/relatorio_verificacao_views.xml",
```

- [ ] **Step 4: Upgrade + suíte completa do módulo**

Delegue ao `test-runner`: `docker exec odoo_engenapp-web-1 /entrypoint.sh -d odoo_ecm_test -u afr_qualificacao --test-enable --test-tags /afr_qualificacao --stop-after-init --no-http`
Esperado: o upgrade carrega a view sem `ParseError`. Nenhuma falha nova: só as 3 pré-existentes do Global Constraints podem aparecer.

- [ ] **Step 5: Smoke de UI via agent-browser (dev em 8084)**

Suba o módulo no db de dev e reinicie para os assets:
```bash
docker exec odoo_engenapp-web-qualificacao-1 /entrypoint.sh -d qualificacao-dev -u afr_qualificacao --stop-after-init --no-http
docker restart odoo_engenapp-web-qualificacao-1
```
Depois:
```bash
agent-browser open "http://localhost:8084/web/session/logout"
agent-browser open "http://localhost:8084/web/login?db=qualificacao-dev"
agent-browser snapshot -i          # preencher login/senha do admin de dev e entrar
agent-browser open "http://localhost:8084/web#model=afr.qualificacao.relatorio&view_type=list"
agent-browser snapshot -i          # abrir um relatório em rascunho
```
Valide no form:
1. o botão **Verificar** aparece no header;
2. depois de clicar, a aba **Verificação** lista os achados com cor por gravidade e o banner vermelho "Aguardando:" mostra as mensagens bloqueantes;
3. ao tentar decidir uma linha `bloqueia`, `decisao` fica readonly;
4. escolher "Descartado" num alerta sem motivo mostra o campo obrigatório, e com motivo salva preenchendo "Decidido por";
5. em Configurações → AFR Qualificação, o bloco "Relatório Final — Verificação por IA" mostra a chave como senha.

Tire `agent-browser screenshot` das telas 2 e 5 e anexe o resultado ao relatório da task. **Não** cole chave de API real em lugar nenhum.

- [ ] **Step 6: Commit**

Via `git-commit-push` (cwd do submodule), paths `views/relatorio_verificacao_views.xml views/res_config_settings_views.xml __manifest__.py`, mensagem:
```
feat(relatorio): add verification tab, blocking banner and AI settings

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 8: TODO.md (fora de escopo da §11) + checklist de aceite manual

**Files:**
- Modify: `TODO.md` (seção `## Pendente — outros`)
- Create: `docs/RELATORIO_FINAL_TEST_CHECKLIST.md`

**Interfaces:**
- Consumes: nada de código.
- Produces: documentação.

- [ ] **Step 1: Atualizar `TODO.md`**

No início da lista de `## Pendente — outros` (logo abaixo do cabeçalho), insira:
```markdown
- **Relatório Final — Fase 2 (fora de escopo da Fase 1, spec [2026-09-26](docs/superpowers/specs/2026-09-26-relatorio-final-qualificacao-design.md) §11):**
  - Captura estruturada no PWA (ambiente, checklist, posições de sensores, janelas de esterilização, leituras de IB) — hoje o escritório digita no backend.
  - Extração do arquivo bruto do validador por IA → preencher `afr.qualificacao.cycle.extracted_json` (min/máx/média/F0 por canal) reaproveitando `afr.relatorio.ai`.
  - Certificado de malha com L.E.Adm / Inc.Total / status no `engc_os` (depende de descongelar o `engc_os`).
  - Assinatura digital ICP-Brasil / gov.br no PDF emitido.
  - Montagem assíncrona do PDF (queue_job) — hoje síncrona com aviso no botão.
  - Tabelas de resultado por canal geradas pelo Odoo (hoje vêm no PDF do validador).
  - `CANAL_SEM_CERT`: a heurística atual compara o nº do canal com a capacidade total dos validadores; decodificar a notação módulo+canal do Yokogawa (ex.: `CH0106` = módulo 01, canal 06) para eliminar falso alerta.
```

- [ ] **Step 2: Criar `docs/RELATORIO_FINAL_TEST_CHECKLIST.md`**

```markdown
# Checklist — Relatório Final de Qualificação (P1–P5, 16.0.8.4.0)

## Ambiente
- **URL:** http://localhost:8084/web?db=qualificacao-dev (container `odoo_engenapp-web-qualificacao-1`)
- **Upgrade:** `docker exec odoo_engenapp-web-qualificacao-1 /entrypoint.sh -d qualificacao-dev -u afr_qualificacao --stop-after-init --no-http` + `docker restart odoo_engenapp-web-qualificacao-1`
- **Browser:** `agent-browser` — sempre `open .../web/session/logout` antes de logar de novo; `snapshot -i` após cada mudança de tela.
- **Dados:** usar só "Cliente Teste" / equipamentos de teste. Nunca dados de `dados_sensiveis/`.
- **IA:** chave do OpenRouter é colada **só** em Configurações → AFR Qualificação (nunca em arquivo, chat ou print).

---

## Bloco A — Preparação
- [ ] **A.1** Configurações → AFR Qualificação → bloco "Relatório Final — Verificação por IA" visível; IA desligada por padrão.
- [ ] **A.2** Instrumento validador com certificados `Antes da campanha` (data ≤ início dos ensaios) e `Depois da campanha` (data ≥ fim) na biblioteca; padrão com certificado externo vigente.
- [ ] **A.3** OS de qualificação com QD (≥ 2 ciclos com carga), plano de recursos com o validador e o padrão.

## Bloco B — Gerar relatórios a partir da OS
- [ ] **B.1** OS → smart button **Relatórios Finais** → ação **Gerar relatórios** cria 1 relatório por equipamento (`ReQT-<OS>-<n>`).
- [ ] **B.2** Clicar de novo em Gerar não duplica (idempotente).
- [ ] **B.3** Relatório abre em **Rascunho**, `Rev.00`, com template sugerido pela categoria (blocos, anexos, checklist, aprovações).

## Bloco C — Dados de campo e ciclos
- [ ] **C.1** Aba **Dados de campo**: datas dos ensaios, ambiente (temperatura/umidade), tolerância, fator F0.
- [ ] **C.2** Checklist: marcar itens aprovados; marcar 1 como **reprovado** (para o Bloco E).
- [ ] **C.3** Indicadores: cadastrar IB com lote e validade; leituras de IB por ciclo (resultado negativo).
- [ ] **C.4** Aba **Ciclos**: janela início/fim por ciclo; posições de sensores (canal/posição/IB); "copiar do ciclo anterior" funciona.
- [ ] **C.5** Aba **Certificados**: seleção automática mostra antes/depois/padrão corretos.

## Bloco D — Texto, anexos e minuta
- [ ] **D.1** Aba **Texto**: editar um bloco estático com token `{{ relatorio.name }}` → minuta mostra o nº.
- [ ] **D.2** Aba **Anexos**: numeração 1..N só sobre incluídos; excluir um anexo renumera.
- [ ] **D.3** **Gerar minuta** → PDF com marca "MINUTA — SEM VALIDADE", "Página X de Y" em todas as páginas (anexos incluídos), índice com páginas corretas.

## Bloco E — Verificar (P5)
- [ ] **E.1** Remover temporariamente o certificado "depois" → **Verificar** → aba **Verificação** lista `CERT_DEPOIS_AUSENTE` (vermelho) e banner **"Aguardando: …"** no topo.
- [ ] **E.2** Linha `bloqueia`: coluna Decisão não editável.
- [ ] **E.3** `CHECKLIST_REPROVADO` (amarelo): escolher **Descartado** sem motivo → campo Motivo obrigatório; com motivo salva e mostra "Decidido por".
- [ ] **E.4** Restaurar o certificado "depois" → **Verificar** → bloqueio some, banner some; decisão do checklist **mantida** (mesma linha).
- [ ] **E.5** Esvaziar umidade → Verificar → `AMBIENTE_VAZIO`; preencher → Verificar → some.
- [ ] **E.6** Anexo incluído sem arquivo → `ANEXO_VAZIO`; texto citando `anexo('x')` excluído → `ANEXO_REF_EXCLUIDO`.
- [ ] **E.7** (Opcional, com chave válida) Ligar IA → Verificar → achados "IA — verificar" em itálico; alerta de IA pendente impede Emitir até ser decidido; chave inválida → um único `IA_INDISPONIVEL` (info), sem erro na tela.

## Bloco F — Aprovar e emitir
- [ ] **F.1** Com alerta pendente (de regra ou de IA), **Emitir** → erro listando "Alerta sem decisão [...]".
- [ ] **F.2** Decidir todos os alertas; **Aprovar** como elaborador e como emissor (usuários designados).
- [ ] **F.3** Editar um campo editorial após aprovar → aprovações internas zeradas; decidir achado **não** zera.
- [ ] **F.4** **Emitir** (gestor) → estado **Emitido**, aba **Revisões** mostra emissão com SHA-256 e token; chatter registra.
- [ ] **F.5** PDF emitido sem marca d'água, QR no rodapé da última página do corpo.

## Bloco G — Verificação pública e portal
- [ ] **G.1** Abrir `/qualificacao/relatorio/verify/<token>` em janela anônima → nº, revisão, data, hash, status **Válido**.
- [ ] **G.2** Token inválido → 404.
- [ ] **G.3** Link de aprovação do cliente (`/my/relatorio/<id>?access_token=...`) → PDF + botão **Aprovar** → grava data/IP/nome; com todos os aprovadores → estado **Aprovado pelo cliente**; página pública lista a aprovação.

## Bloco H — Revisar
- [ ] **H.1** **Revisar** → `Rev.01`, estado Rascunho, aprovações internas zeradas; emissão anterior ainda **Válida**.
- [ ] **H.2** Emitir a Rev.01 → emissão anterior vira **Substituída** na página pública; nova emissão válida.
- [ ] **H.3** Emissão anterior continua imutável (tentar editar pela interface não é possível).
```

- [ ] **Step 3: Commit**

Via `git-commit-push` (cwd do submodule), paths `TODO.md docs/RELATORIO_FINAL_TEST_CHECKLIST.md`, mensagem:
```
docs(relatorio): add phase-2 backlog and manual acceptance checklist

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

## Self-Review (feito pelo autor do plano)

**Cobertura da spec:**
- §7 (model do achado com todos os campos) → Task 1.
- §7.1: 17 regras → Tasks 2 e 3, com `test_registro_completo` garantindo o conjunto.
- §7 (`action_verificar` apaga não decididos) → Task 4, com carry-over.
- §7.2: parâmetros exatos, chunking corpo + anexo, pdfminer, truncagem, cartão, JSON exigido, parse tolerante, `IA_INDISPONIVEL`, só `alerta`/`info`, marcação "IA — verificar" → Task 5.
- §7.3 (gate e `scan_snapshot`) → Task 6.
- §9 (aba Verificação, badge "aguardando", botão Verificar, grupo `user` verifica) → Task 7.
- §10 (cada regra com positivo e negativo; IA mockada: contrato, inválido, timeout, desligada) → Tasks 2, 3 e 5.
- §11 → Task 8.
- §12 ("IA desligada por padrão") → Tasks 5 e 7.

**Tipos e nomes:** `SCAN_CTX`/`afr_scan_internal` (Task 1) são usados em `_mk_achado` e `_run_verificacao`. `EMISSION_CTX` (Task 2) é usado nas Tasks 3 e 6. `AI_SKIP_CTX`/`afr_skip_ai` (Task 4) é usado nos testes das Tasks 4 e 6. `cycle_counts` (Task 3) é usado na Task 5. `_ai_findings` é trocado na Task 5. `RULES`/`run_rules`/`finding` batem entre as Tasks 2 e 3.

**Fatos de P4 incorporados** (ver Global Constraints): xmlid do form; `UserError` em `action_emitir`; `action_aprovar_interno` aprova tudo numa chamada; classificação `PROBLEM_EMPTY` → VAZIO / demais → ILEGIVEL; `bloco` sem arquivo por design; campos que zeram aprovações (achado_ids fora — fixado por `test_decisao_pelo_form_nao_zera_aprovacoes`); mock `FakeCorpo` em `_render_qweb_pdf`; `_apply_template()` explícito (não usado nas fixtures de P5).
