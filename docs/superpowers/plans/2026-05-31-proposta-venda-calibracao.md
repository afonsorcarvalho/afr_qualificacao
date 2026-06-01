# Proposta de Venda + Calibração — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar o arquétipo de proposta "Venda + Calibração" (block_kind `sales_items` + seções/template seed) e um bloco institucional "Dados Cadastrais – LabQuali" padrão em todas as propostas.

**Architecture:** Reusa o sistema LEGO existente (`afr.proposal.template` → `afr.proposal.block` → relatório `quotation_template.xml`). 1 block_kind novo renderiza tabela de itens das linhas do SO; seções e template via seed XML (`noupdate`); o bloco Dados Cadastrais é retrofitado no template QI/QO/QD existente via helper idempotente chamado pelo `post_init_hook` (fresh) e por migration `16.0.5.7.0` (`-u`).

**Tech Stack:** Odoo 16, Python, QWeb XML, TransactionCase.

---

## Convenções deste módulo

- **`afr_qualificacao` é submodule git.** Commits SEMPRE de dentro de
  `addons/afr_qualificacao`, via agente `git-commit-push` (haiku). Não usar
  `git commit` direto no contexto principal.
- **Rodar testes** (db `odoo_ecm_test`, container `odoo_engenapp-web-1`):

  ```bash
  docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
    --test-enable --test-tags /afr_qualificacao:<TestClass> --stop-after-init \
    --no-http --workers=0 --max-cron-threads=0 \
    --db_host=db --db_user=odoo --db_password=odoo 2>&1 | \
    grep -iE 'FAIL:|tests.stats|failed,.*error|AssertionError'
  ```

  `-u` é necessário p/ recarregar XML seed e o código. "Address already in use"
  no log é inofensivo (instância http ativa); os testes rodam.

---

## File Structure

- **Modify** `models/proposal_template.py` — add `sales_items` em `PROPOSAL_BLOCK_KINDS`.
- **Modify** `reports/quotation_template.xml` — ramo QWeb `sales_items`.
- **Create** `data/proposal_venda_calibracao_seed.xml` — seções institucionais + seção Dados Cadastrais + template TPL-VENDA-CALIB + suas linhas.
- **Modify** `hooks.py` — fn `_ensure_company_data_block(env)` + chamada no `_install_proposal_template_seed`.
- **Create** `migrations/16.0.5.7.0/post-migrate.py` — chama `_ensure_company_data_block`.
- **Modify** `__manifest__.py` — version 16.0.5.7.0 + registrar o seed XML.
- **Create** `tests/test_proposal_venda_calibracao.py` + registrar em `tests/__init__.py`.

---

## Task 1: block_kind `sales_items` + ramo no relatório

**Files:**
- Modify: `models/proposal_template.py:22-31` (constante `PROPOSAL_BLOCK_KINDS`)
- Modify: `reports/quotation_template.xml` (após o ramo `optionals`, ~linha 779)
- Test: `tests/test_proposal_venda_calibracao.py`
- Modify: `tests/__init__.py`

- [ ] **Step 1: Registrar o novo arquivo de teste no `tests/__init__.py`**

Adicionar ao fim de `tests/__init__.py`:

```python

from . import test_proposal_venda_calibracao
```

- [ ] **Step 2: Escrever o teste falhante do ramo `sales_items`**

Criar `tests/test_proposal_venda_calibracao.py`:

```python
"""Proposta Venda + Calibração — block_kind sales_items + template seed."""

from odoo.tests.common import tagged

from .common import AfrQualificacaoTestCommon


@tagged("afr_qualificacao", "post_install", "-at_install")
class TestProposalVendaCalib(AfrQualificacaoTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("sale.action_report_saleorder")

    def _render_block(self, so):
        report = self.env.ref("sale.action_report_saleorder")
        html, _c = report._render_qweb_html(report.report_name, so.ids)
        return html.decode() if isinstance(html, bytes) else html

    def _make_so_with_lines(self):
        """SO com 2 linhas de venda comuns (não-qualif, não-opcional)."""
        so = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qi.id,
            "name": "Venda + Calibração de Termômetro",
            "product_uom_qty": 3,
            "price_unit": 95.0,
        })
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qo.id,
            "name": "Venda + Calibração de Válvula de segurança",
            "product_uom_qty": 2,
            "price_unit": 1350.0,
        })
        return so

    def _render_block(self, so):
        report = self.env.ref("sale.action_report_saleorder")
        html, _c = report._render_qweb_html(report.report_name, so.ids)
        return html.decode() if isinstance(html, bytes) else html

    def test_sales_items_renders_lines(self):
        so = self._make_so_with_lines()
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "sequence": 10,
            "block_kind": "sales_items",
            "title": "Equipamentos a serem Calibrados",
            "included": True,
        })
        html = self._render_block(so)
        self.assertIn("Equipamentos a serem Calibrados", html)
        self.assertIn("Venda + Calibração de Termômetro", html)
        self.assertIn("Venda + Calibração de Válvula de segurança", html)
        # totais por linha presentes (3×95=285, 2×1350=2700)
        self.assertIn("285", html)
        self.assertIn("2.700", html.replace(",", "."))

    def test_sales_items_excludes_sections_and_optionals(self):
        so = self._make_so_with_lines()
        # linha de seção (display_type) e opcional não devem aparecer na tabela
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "display_type": "line_section",
            "name": "SEÇÃO_NAO_LISTAR",
        })
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product_qs.id,
            "name": "OPCIONAL_NAO_LISTAR",
            "product_uom_qty": 1,
            "price_unit": 50.0,
            "is_proposal_optional": True,
        })
        self.env["afr.proposal.block"].create({
            "sale_order_id": so.id,
            "sequence": 10,
            "block_kind": "sales_items",
            "title": "Itens",
            "included": True,
        })
        html = self._render_block(so)
        self.assertNotIn("SEÇÃO_NAO_LISTAR", html)
        self.assertNotIn("OPCIONAL_NAO_LISTAR", html)
```

- [ ] **Step 3: Rodar o teste e ver falhar**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
  --test-enable --test-tags /afr_qualificacao:TestProposalVendaCalib \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 \
  --db_host=db --db_user=odoo --db_password=odoo 2>&1 | \
  grep -iE 'FAIL:|tests.stats|failed,.*error|ValidationError|ParseError'
```

Esperado: falha — `block_kind` `sales_items` inválido na selection (create do
block rejeita) e/ou tabela não renderiza.

- [ ] **Step 4: Adicionar `sales_items` à selection**

Em `models/proposal_template.py`, na constante `PROPOSAL_BLOCK_KINDS` (após
`("optionals", "Serviços Opcionais"),`):

```python
    ("sales_items", "Tabela de Itens (Venda + Calibração)"),
```

- [ ] **Step 5: Adicionar o ramo QWeb no relatório**

Em `reports/quotation_template.xml`, imediatamente após o fechamento do ramo
`optionals` (a tag `</t>` da linha ~779, antes do comentário `<!-- Aceite -->`),
inserir:

```xml
                        <!-- Tabela de itens de venda (Venda + Calibração) -->
                        <t t-if="block.block_kind == 'sales_items'">
                            <t t-set="sale_lines" t-value="doc.order_line.filtered(lambda l: not l.display_type and not l.is_proposal_optional)"/>
                            <div t-att-class="sec_class" t-if="sale_lines">
                                <div t-attf-class="qq-section-title{{ ' qq-section-title-child' if is_child else '' }}"
                                     t-if="block.show_title">
                                    <t t-if="blk_num"><span t-esc="blk_num"/> — </t>
                                    <span t-esc="block.title or 'Equipamentos a serem Calibrados'"/>
                                </div>
                                <table class="qq-table">
                                    <tr>
                                        <th>Descrição</th>
                                        <th style="width: 10%;">Quant.</th>
                                        <th style="width: 20%; text-align: right;">Valor Unitário</th>
                                        <th style="width: 20%; text-align: right;">Valor Total</th>
                                    </tr>
                                    <t t-foreach="sale_lines" t-as="sl">
                                        <tr>
                                            <td><span t-esc="sl.name"/></td>
                                            <td>
                                                <span t-esc="int(sl.product_uom_qty) if sl.product_uom_qty == int(sl.product_uom_qty) else sl.product_uom_qty"/>
                                            </td>
                                            <td style="text-align: right;">
                                                <span t-esc="sl.price_unit"
                                                      t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                                            </td>
                                            <td style="text-align: right;">
                                                <span t-esc="sl.price_subtotal"
                                                      t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                                            </td>
                                        </tr>
                                    </t>
                                </table>
                                <table class="qq-total-table">
                                    <tr>
                                        <td class="qq-tot-label">Subtotal:</td>
                                        <td class="qq-tot-value">
                                            <span t-field="doc.amount_untaxed"
                                                  t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td class="qq-tot-label">Impostos:</td>
                                        <td class="qq-tot-value">
                                            <span t-field="doc.amount_tax"
                                                  t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                                        </td>
                                    </tr>
                                    <tr class="qq-total-grand">
                                        <td class="qq-tot-label">TOTAL GERAL:</td>
                                        <td class="qq-tot-value">
                                            <span t-field="doc.amount_total"
                                                  t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
                                        </td>
                                    </tr>
                                </table>
                            </div>
                        </t>
```

- [ ] **Step 6: Rodar o teste e ver passar**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
  --test-enable --test-tags /afr_qualificacao:TestProposalVendaCalib \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 \
  --db_host=db --db_user=odoo --db_password=odoo 2>&1 | \
  grep -iE 'FAIL:|tests.stats|failed,.*error'
```

Esperado: `test_sales_items_renders_lines` e
`test_sales_items_excludes_sections_and_optionals` passam (0 failed).

- [ ] **Step 7: Commit (via agente git-commit-push, cwd = addons/afr_qualificacao)**

Mensagem sugerida:
`feat(afr_qualificacao): block_kind sales_items (tabela de itens venda+calibração)`
Paths: `models/proposal_template.py reports/quotation_template.xml tests/test_proposal_venda_calibracao.py tests/__init__.py`

---

## Task 2: Seções institucionais + seção Dados Cadastrais + template seed

**Files:**
- Create: `data/proposal_venda_calibracao_seed.xml`
- Modify: `__manifest__.py` (version + data)
- Test: `tests/test_proposal_venda_calibracao.py` (novos métodos)

- [ ] **Step 1: Escrever os testes falhantes (template + render institucional)**

Adicionar à classe `TestProposalVendaCalib`:

```python
    def test_template_seed_structure(self):
        tpl = self.env.ref("afr_qualificacao.proposal_template_venda_calib")
        self.assertTrue(tpl)
        kinds = tpl.line_ids.mapped("block_kind")
        self.assertIn("sales_items", kinds)
        # seção Dados Cadastrais presente
        sec = self.env.ref("afr_qualificacao.sec_dados_cadastrais")
        self.assertIn(sec, tpl.line_ids.mapped("section_id"))
        # sales_items aparece antes do bloco de aceite
        seqs = {l.block_kind: l.sequence for l in tpl.line_ids}
        self.assertLess(seqs["sales_items"], seqs["acceptance"])

    def test_render_contains_institucional(self):
        tpl = self.env.ref("afr_qualificacao.proposal_template_venda_calib")
        so = self._make_so_with_lines()
        so.proposal_template_id = tpl.id
        so._seed_proposal_blocks()
        html = self._render_block(so)
        self.assertIn("NBR 16328", html)
        self.assertIn("SEDEX", html)
        self.assertIn("60 dias", html)
        self.assertIn("52.230.210/0001-70", html)  # CNPJ LabQuali
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
  --test-enable --test-tags /afr_qualificacao:TestProposalVendaCalib \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 \
  --db_host=db --db_user=odoo --db_password=odoo 2>&1 | \
  grep -iE 'FAIL:|tests.stats|failed,.*error|ValueError'
```

Esperado: falha — `external id ... proposal_template_venda_calib` não existe.

- [ ] **Step 3: Criar o seed XML**

Criar `data/proposal_venda_calibracao_seed.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <!--
        Proposta Venda + Calibração (doc 4 LabQuali) + bloco institucional
        Dados Cadastrais. noupdate="1": cliente edita sem perder em upgrade.
        Textos lift de docs/Exemplos diversos/4 - Proposta de Venda + Calibração.doc
        e REFERENCIA_PROPOSTAS_LABQUALI.md (§5, §6, §7).
    -->

    <!-- ===== Seções de texto ===== -->
    <record id="sec_vc_objetivo" model="afr.proposal.section">
        <field name="code">SEC-VC-OBJETIVO</field>
        <field name="name">Objetivo</field>
        <field name="category">objetivo</field>
        <field name="sequence">10</field>
        <field name="body" type="html">
            <div>
                <p>Esta proposta tem por objetivo o fornecimento de serviços de
                Calibração de Instrumentos de Medição, bem como o fornecimento de
                instrumentos e equipamentos destinados ao monitoramento, controle e
                segurança de processos, para <strong>{{ partner.name }}</strong>,
                conforme especificações técnicas e necessidade operacional.</p>
            </div>
        </field>
    </record>

    <record id="sec_vc_metodologia" model="afr.proposal.section">
        <field name="code">SEC-VC-METODOLOGIA</field>
        <field name="name">Metodologia de Execução</field>
        <field name="category">metodologia</field>
        <field name="sequence">20</field>
        <field name="body" type="html">
            <div>
                <p>Os serviços são executados segundo critérios de qualidade e
                princípios organizacionais, atendendo às exigências normativas e
                legislações aplicáveis a cada processo.</p>
                <p>Utilizam-se Padrões de Medição calibrados e rastreados à RBC —
                Rede Brasileira de Calibração / INMETRO, assegurando
                confiabilidade metrológica, rastreabilidade dos resultados e
                conformidade técnica.</p>
            </div>
        </field>
    </record>

    <record id="sec_vc_escopo" model="afr.proposal.section">
        <field name="code">SEC-VC-ESCOPO</field>
        <field name="name">Escopo</field>
        <field name="category">escopo</field>
        <field name="sequence">30</field>
        <field name="body" type="html">
            <div>
                <p>O escopo do fornecimento limita-se aos equipamentos,
                instrumentos, produtos e serviços listados nesta proposta.</p>
                <p>Além dos serviços de calibração, poderão ser contemplados o
                fornecimento de instrumentos calibrados para monitoramento de
                temperatura e umidade, equipamentos para controle de processos e
                válvulas de segurança, conforme especificação técnica e
                necessidade do cliente.</p>
            </div>
        </field>
    </record>

    <record id="sec_vc_procedimento" model="afr.proposal.section">
        <field name="code">SEC-VC-PROCEDIMENTO</field>
        <field name="name">Procedimento de Calibração</field>
        <field name="category">normas</field>
        <field name="sequence">40</field>
        <field name="body" type="html">
            <div>
                <p><strong>Calibração:</strong> operação que estabelece, sob
                condições específicas, em uma primeira etapa, uma relação entre os
                valores e as incertezas de medição fornecidas por padrões e as
                indicações correspondentes com as incertezas associadas; em uma
                segunda etapa, utiliza esta informação para estabelecer uma
                relação visando a obtenção de um resultado de medição a partir de
                uma indicação. (NBR 16328:2014)</p>
                <ul>
                    <li>Serão utilizados Padrões de Medição calibrados e
                    rastreados à RBC — Rede Brasileira de Calibração / INMETRO;</li>
                    <li>Os critérios de aceitação serão determinados pelo cliente
                    e de acordo com os protocolos de calibração formalizados;</li>
                    <li>Os certificados emitidos contêm tabelas com a média dos
                    valores coletados, a incerteza de medição expandida com nível
                    de confiança de 95% e o coeficiente de abrangência (K), além
                    dos dados dos padrões utilizados e cópia de seus respectivos
                    certificados de calibração;</li>
                    <li>Quando aplicável, os instrumentos fornecidos poderão ser
                    entregues acompanhados de Certificado de Calibração, conforme
                    especificação técnica ou requisito do processo.</li>
                </ul>
            </div>
        </field>
    </record>

    <record id="sec_vc_condicoes" model="afr.proposal.section">
        <field name="code">SEC-VC-CONDICOES</field>
        <field name="name">Condições Comerciais</field>
        <field name="category">condicoes</field>
        <field name="sequence">50</field>
        <field name="body" type="html">
            <div>
                <p>Valor total dos serviços com impostos inclusos.</p>
                <p><strong>Opções de Frete (Correios):</strong></p>
                <ul>
                    <li>SEDEX HOJE — entrega no mesmo dia da postagem;</li>
                    <li>SEDEX — dia da postagem + 1 dia útil;</li>
                    <li>Motoboy — aproximadamente 50 minutos.</li>
                </ul>
                <p>Previsão de dias para execução dos serviços conforme acordado.
                Prazo de entrega dos Certificados: 15 dias.</p>
            </div>
        </field>
    </record>

    <record id="sec_vc_documentacao" model="afr.proposal.section">
        <field name="code">SEC-VC-DOCUMENTACAO</field>
        <field name="name">Fornecimento da Documentação</field>
        <field name="category">condicoes</field>
        <field name="sequence">60</field>
        <field name="body" type="html">
            <div>
                <p>O valor total apresentado contempla o envio da documentação em
                formato digital, assinada eletronicamente com certificação digital
                (tecnologia, segurança e integridade).</p>
                <p>Documentação impressa em pastas personalizadas é opcional —
                cobra-se o valor das pastas e o envio pelo correio (Sedex).</p>
            </div>
        </field>
    </record>

    <record id="sec_vc_pagamento" model="afr.proposal.section">
        <field name="code">SEC-VC-PAGAMENTO</field>
        <field name="name">Condições de Pagamento</field>
        <field name="category">financeiro</field>
        <field name="sequence">70</field>
        <field name="body" type="html">
            <div><p>À vista, faturado na aprovação.</p></div>
        </field>
    </record>

    <record id="sec_vc_validade" model="afr.proposal.section">
        <field name="code">SEC-VC-VALIDADE</field>
        <field name="name">Validade da Proposta</field>
        <field name="category">condicoes</field>
        <field name="sequence">80</field>
        <field name="body" type="html">
            <div><p>Esta proposta é válida por 60 dias.</p></div>
        </field>
    </record>

    <record id="sec_vc_observacoes" model="afr.proposal.section">
        <field name="code">SEC-VC-OBSERVACOES</field>
        <field name="name">Observações</field>
        <field name="category">custom</field>
        <field name="sequence">90</field>
        <field name="body" type="html">
            <div>
                <p>O preço apresentado nesta proposta sofrerá alteração caso a
                quantidade de equipamentos seja alterada.</p>
            </div>
        </field>
    </record>

    <!-- ===== Seção institucional Dados Cadastrais (comum a todas) ===== -->
    <record id="sec_dados_cadastrais" model="afr.proposal.section">
        <field name="code">SEC-DADOS-CADASTRAIS</field>
        <field name="name">Dados Cadastrais — LabQuali</field>
        <field name="category">credenciais</field>
        <field name="sequence">200</field>
        <field name="body" type="html">
            <div>
                <p><strong>Nome Fantasia:</strong> LabQuali Qualificações<br/>
                <strong>Razão Social:</strong> LabQuali Qualificações Ltda.<br/>
                <strong>CNPJ:</strong> 52.230.210/0001-70<br/>
                <strong>Inscrição Estadual:</strong> 125.705.737.113<br/>
                <strong>Inscrição Municipal:</strong> 341232<br/>
                <strong>Endereço:</strong> Rua Arujá, nº 47 — Vila Curuçá, Santo
                André — SP — CEP: 09291-250<br/>
                <strong>E-mail comercial:</strong> comercial@labquali.com.br</p>

                <p><strong>Dados Bancários</strong><br/>
                Banco: Itaú · Agência: 666-4 · Conta Corrente: 99108-7<br/>
                Chave PIX: 52.230.210/0001-70 (CNPJ)</p>

                <p><strong>Responsáveis</strong><br/>
                Paulo Neves — Responsável Técnico — Cel.: (11) 99721-0293<br/>
                Bruno Neves — Gerente Técnico — Cel.: (11) 94282-6708<br/>
                Ariel Neves — Administrativo / Financeiro — Cel.: (11) 99461-3056</p>

                <p><strong>Registros Técnicos</strong><br/>
                Registro da Empresa no CREA-SP: 2535551<br/>
                Responsável Técnico: Paulo Rogério das Neves — Engenheiro Mecânico
                — CREA-SP: 0682576030 (Registro Ativo) — Certidão: CI 3381050/2024</p>
            </div>
        </field>
    </record>

    <!-- ===== Template Venda + Calibração ===== -->
    <record id="proposal_template_venda_calib" model="afr.proposal.template">
        <field name="name">Proposta Venda + Calibração</field>
        <field name="code">TPL-VENDA-CALIB</field>
        <field name="sequence">30</field>
    </record>

    <record id="tpl_vc_l01" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">10</field>
        <field name="block_kind">static</field>
        <field name="section_id" ref="sec_vc_objetivo"/>
        <field name="page_break" eval="True"/>
    </record>
    <record id="tpl_vc_l02" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">20</field>
        <field name="block_kind">static</field>
        <field name="section_id" ref="sec_vc_metodologia"/>
    </record>
    <record id="tpl_vc_l03" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">30</field>
        <field name="block_kind">static</field>
        <field name="section_id" ref="sec_vc_escopo"/>
    </record>
    <record id="tpl_vc_l04" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">40</field>
        <field name="block_kind">static</field>
        <field name="section_id" ref="sec_vc_procedimento"/>
    </record>
    <record id="tpl_vc_l05" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">50</field>
        <field name="block_kind">sales_items</field>
        <field name="title">Equipamentos a serem Calibrados</field>
        <field name="page_break" eval="True"/>
    </record>
    <record id="tpl_vc_l06" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">60</field>
        <field name="block_kind">static</field>
        <field name="section_id" ref="sec_vc_condicoes"/>
    </record>
    <record id="tpl_vc_l07" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">70</field>
        <field name="block_kind">static</field>
        <field name="section_id" ref="sec_vc_documentacao"/>
    </record>
    <record id="tpl_vc_l08" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">80</field>
        <field name="block_kind">static</field>
        <field name="section_id" ref="sec_vc_pagamento"/>
    </record>
    <record id="tpl_vc_l09" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">90</field>
        <field name="block_kind">static</field>
        <field name="section_id" ref="sec_vc_validade"/>
    </record>
    <record id="tpl_vc_l10" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">100</field>
        <field name="block_kind">static</field>
        <field name="section_id" ref="sec_vc_observacoes"/>
    </record>
    <record id="tpl_vc_l11" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">110</field>
        <field name="block_kind">static</field>
        <field name="section_id" ref="sec_dados_cadastrais"/>
        <field name="page_break" eval="True"/>
    </record>
    <record id="tpl_vc_l12" model="afr.proposal.template.line">
        <field name="template_id" ref="proposal_template_venda_calib"/>
        <field name="sequence">120</field>
        <field name="block_kind">acceptance</field>
        <field name="section_id" ref="proposal_section_aceite"/>
    </record>
</odoo>
```

- [ ] **Step 4: Registrar no manifest + bump version**

Em `__manifest__.py`:
- `"version": "16.0.5.6.0",` → `"version": "16.0.5.7.0",`
- na lista `data`, após a linha `"data/proposal_optional_seed.xml",`, adicionar:

```python
        "data/proposal_venda_calibracao_seed.xml",
```

- [ ] **Step 5: Rodar e ver passar**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
  --test-enable --test-tags /afr_qualificacao:TestProposalVendaCalib \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 \
  --db_host=db --db_user=odoo --db_password=odoo 2>&1 | \
  grep -iE 'FAIL:|tests.stats|failed,.*error'
```

Esperado: `test_template_seed_structure` e `test_render_contains_institucional`
passam (0 failed).

- [ ] **Step 6: Commit (via git-commit-push, cwd = addons/afr_qualificacao)**

`feat(afr_qualificacao): seções + template Proposta Venda + Calibração + bloco Dados Cadastrais (16.0.5.7.0)`
Paths: `data/proposal_venda_calibracao_seed.xml __manifest__.py tests/test_proposal_venda_calibracao.py`

---

## Task 3: Dados Cadastrais padrão no template QI/QO/QD existente

**Files:**
- Modify: `hooks.py`
- Create: `migrations/16.0.5.7.0/post-migrate.py`
- Test: `tests/test_proposal_venda_calibracao.py` (novo método)

- [ ] **Step 1: Escrever o teste falhante do helper idempotente**

Adicionar à classe `TestProposalVendaCalib`:

```python
    def test_ensure_company_data_block_idempotent(self):
        from ..hooks import _ensure_company_data_block
        tpl = self.env.ref("afr_qualificacao.proposal_template_labquali")
        sec = self.env.ref("afr_qualificacao.sec_dados_cadastrais")

        def _count():
            return len(tpl.line_ids.filtered(lambda l: l.section_id == sec))

        # remove eventuais linhas pré-existentes p/ estado conhecido
        tpl.line_ids.filtered(lambda l: l.section_id == sec).unlink()
        self.assertEqual(_count(), 0)

        _ensure_company_data_block(self.env)
        self.assertEqual(_count(), 1, "deve adicionar exatamente 1 linha")

        _ensure_company_data_block(self.env)
        self.assertEqual(_count(), 1, "2ª chamada não duplica")
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
  --test-enable --test-tags /afr_qualificacao:TestProposalVendaCalib \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 \
  --db_host=db --db_user=odoo --db_password=odoo 2>&1 | \
  grep -iE 'FAIL:|tests.stats|failed,.*error|ImportError'
```

Esperado: falha — `_ensure_company_data_block` não existe (ImportError).

- [ ] **Step 3: Implementar o helper em `hooks.py`**

Adicionar antes de `def _install_proposal_template_seed(cr, registry):`:

```python
def _ensure_company_data_block(env):
    """Garante o bloco institucional 'Dados Cadastrais' no template QI/QO/QD.

    Idempotente: acrescenta 1 linha static (seção SEC-DADOS-CADASTRAIS) ao
    template proposal_template_labquali se ainda não existir, posicionada
    logo antes do bloco de aceite. Chamado pelo post_init (fresh-install) e
    pela migration 16.0.5.7.0 (upgrade na labquali).
    """
    section = env.ref(
        "afr_qualificacao.sec_dados_cadastrais", raise_if_not_found=False
    )
    template = env.ref(
        "afr_qualificacao.proposal_template_labquali", raise_if_not_found=False
    )
    if not section or not template:
        return
    if template.line_ids.filtered(lambda l: l.section_id.id == section.id):
        return  # já tem
    # posiciona logo antes do bloco de aceite (ou no fim)
    acceptance = template.line_ids.filtered(
        lambda l: l.block_kind == "acceptance"
    )
    if acceptance:
        seq = min(acceptance.mapped("sequence")) - 1
    else:
        seq = (max(template.line_ids.mapped("sequence") or [0])) + 10
    env["afr.proposal.template.line"].create({
        "template_id": template.id,
        "sequence": seq,
        "block_kind": "static",
        "section_id": section.id,
    })
```

- [ ] **Step 4: Chamar o helper no post_init_hook (fresh-install)**

Em `hooks.py`, dentro de `_install_proposal_template_seed`, logo após a chamada
existente `_install_qi_qs_type_config(env)`:

```python
    # Bloco institucional Dados Cadastrais padrão no template QI/QO/QD.
    _ensure_company_data_block(env)
```

> Nota: nesse ponto, em fresh-install, a seção `sec_dados_cadastrais` (XML) já
> foi carregada (data load roda antes do post_init) e o template
> `proposal_template_labquali` é criado mais abaixo na mesma função. Mover a
> chamada `_ensure_company_data_block(env)` para o **final** da função
> `_install_proposal_template_seed` (após a criação do template e suas linhas),
> garantindo que o template exista. Se a função retornou cedo (`if template:
> return`), o template já existia → ainda assim chamar antes do return:
> colocar a chamada imediatamente antes de `if template: return` **e** no final,
> protegido pela idempotência do helper.

Implementação concreta: substituir o trecho

```python
    # Seed QI/QS type.config (independente do template; idempotente).
    _install_qi_qs_type_config(env)

    template = env.ref(
        "afr_qualificacao.proposal_template_labquali",
        raise_if_not_found=False,
    )
    if template:
        return  # já instalado
```

por

```python
    # Seed QI/QS type.config (independente do template; idempotente).
    _install_qi_qs_type_config(env)

    template = env.ref(
        "afr_qualificacao.proposal_template_labquali",
        raise_if_not_found=False,
    )
    if template:
        _ensure_company_data_block(env)  # retrofit em template já existente
        return  # já instalado
```

e adicionar, no **final** da função (após a 3ª passagem que propaga `parent_id`):

```python
    # Bloco institucional Dados Cadastrais (após template recém-criado).
    _ensure_company_data_block(env)
```

- [ ] **Step 5: Criar a migration de upgrade**

Criar `migrations/16.0.5.7.0/post-migrate.py`:

```python
"""Retrofit do bloco Dados Cadastrais no template QI/QO/QD em upgrade.

post_init_hook só roda em install; em -u (labquali já instalada) este
post-migrate garante o bloco institucional no template existente.
"""

from odoo import api, SUPERUSER_ID

from odoo.addons.afr_qualificacao.hooks import _ensure_company_data_block


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _ensure_company_data_block(env)
```

- [ ] **Step 6: Rodar e ver passar**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
  --test-enable --test-tags /afr_qualificacao:TestProposalVendaCalib \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 \
  --db_host=db --db_user=odoo --db_password=odoo 2>&1 | \
  grep -iE 'FAIL:|tests.stats|failed,.*error'
```

Esperado: `test_ensure_company_data_block_idempotent` passa (0 failed).

> Nota: o `-u` desta task também dispara a migration `16.0.5.7.0` (a versão foi
> bumpada na Task 2). Conferir no log a ausência de erro na migration.

- [ ] **Step 7: Commit (via git-commit-push, cwd = addons/afr_qualificacao)**

`feat(afr_qualificacao): bloco Dados Cadastrais padrão em todas as propostas (hook + migration)`
Paths: `hooks.py migrations/16.0.5.7.0/post-migrate.py tests/test_proposal_venda_calibracao.py`

---

## Task 4: Validação completa (suite + fresh-install)

**Files:** nenhum (validação).

- [ ] **Step 1: Rodar a suite completa do módulo**

```bash
docker exec odoo_engenapp-web-1 odoo -d odoo_ecm_test -u afr_qualificacao \
  --test-enable --test-tags afr_qualificacao --stop-after-init \
  --no-http --workers=0 --max-cron-threads=0 \
  --db_host=db --db_user=odoo --db_password=odoo 2>&1 | \
  grep -iE 'FAIL:|tests.stats|failed,.*error'
```

Esperado: as falhas conhecidas pré-existentes/ambientais permanecem
(`TestResourcePlan.test_fleet_single_logger_two_temp_standards` por poluição de
db; `TestProposalReport.test_render_equipment_scope_omits_cronograma_footer`
CSS). **Nenhuma falha nova** nos testes `TestProposalVendaCalib`.

- [ ] **Step 2: Validar fresh-install (hook cria o bloco em ambos templates)**

```bash
docker exec odoo_engenapp-db-1 psql -U odoo -c "CREATE DATABASE qualif_vc_smoke;"
docker exec odoo_engenapp-web-1 odoo -d qualif_vc_smoke -i afr_qualificacao \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 \
  --db_host=db --db_user=odoo --db_password=odoo > /tmp/vc_smoke.log 2>&1
echo "EXIT=$?"; tail -3 /tmp/vc_smoke.log
```

Conferir que ambos templates têm o bloco Dados Cadastrais:

```bash
docker exec odoo_engenapp-db-1 psql -U odoo -d qualif_vc_smoke -t -c "
SELECT t.code, COUNT(l.id)
FROM afr_proposal_template t
JOIN afr_proposal_template_line l ON l.template_id = t.id
JOIN afr_proposal_section s ON s.id = l.section_id
WHERE s.code = 'SEC-DADOS-CADASTRAIS'
GROUP BY t.code;"
```

Esperado: 2 linhas — `TPL-LABQUALI` e `TPL-VENDA-CALIB`, cada uma com count 1.

- [ ] **Step 3: Limpar o db smoke**

```bash
docker exec odoo_engenapp-db-1 psql -U odoo -c "DROP DATABASE qualif_vc_smoke;"
```

- [ ] **Step 4: Atualizar handoff** em `.remember/remember.md` com o estado
  entregue (Proposta Venda+Calibração v16.0.5.7.0, aguardando teste/OK do user
  p/ commit final + deploy labquali via `-u`).

---

## Self-Review (preenchido pelo autor do plano)

**Spec coverage:** C1→Task1; C2/C3/C4→Task2; C5→Task3; C6→Task2(manifest);
testes→Tasks 1-3; validação fresh-install→Task4. Todos os itens do spec cobertos.

**Placeholder scan:** sem TODO/TBD. Helper de render único (`_render_block`).

**Type consistency:** `_ensure_company_data_block(env)` (assinatura única, usada
em hooks.py e migration). xmlids consistentes: `sec_dados_cadastrais`,
`proposal_template_venda_calib`, `proposal_template_labquali`. block_kind
`sales_items` idêntico em selection, QWeb, seed e testes.
