# Opcionais Aceitos — Fase 1 (Núcleo) Design Spec
Date: 2026-06-04
Module: afr_qualificacao

## Contexto e problema

Hoje uma linha `is_proposal_optional=True` em `sale.order.line`:
- NÃO gera qualificação no confirm (filtrada em `_create_qualificacoes_from_lines`)
- aparece em secção "Serviços Opcionais" no PDF/portal
- **MAS soma ao `amount_total`** (sem filtro de exclusão)

Objetivo: opcional = **oferta**. Só conta (total/fatura/geração) se **aceito**. Decisões do utilizador:
- Não-aceito **não soma** ao total (fica como referência).
- Opcionais podem ser **serviços** (pasta/viagem/diária) **ou qualificações** (equip/ciclo/malha extra).
- **Seleção do cliente já conta** (1 estado `optional_accepted`; comercial revê/ajusta no form).
- Não-aceitos após confirm **ficam como referência** (linha qty=0).

Faseamento global: **Fase 1 (núcleo, esta spec)** → Fase 2 (aba opcionais no wizard) → Fase 3 (PDF caixas) → Fase 4 (portal interativo). Esta spec cobre só a Fase 1.

## Escopo Fase 1

O núcleo de estado + total + confirm + form, suficiente para criar/aceitar opcionais manualmente (no form) e ver o efeito correto. Wizard/PDF/portal ficam para fases seguintes.

## 1. Campos novos (`sale.order.line`)

```python
optional_accepted = fields.Boolean(
    string="Opcional Aceito",
    default=False,
    copy=True,
    help="Opcional autorizado pelo cliente. Quando aceito, soma ao total, "
         "vai à fatura e — se for qualificação — gera afr.qualificacao + OS.",
)
optional_qty = fields.Float(
    string="Qtd. do Opcional",
    default=1.0,
    copy=True,
    help="Quantidade pretendida do opcional. Guardada enquanto não aceito "
         "(product_uom_qty fica 0); aplicada quando aceito.",
)
```

> `is_proposal_optional` já existe (não mexer na definição).

## 2. Sincronização da quantidade — não soma até aceito

Regra: numa linha `is_proposal_optional`, `product_uom_qty = optional_qty se optional_accepted senão 0`.
Reusa o padrão de `part01_declined` (qty=0 não soma ao `amount_total` nem é faturada).

```python
@api.onchange("optional_accepted", "optional_qty", "is_proposal_optional")
def _onchange_optional_sync_qty(self):
    """Linha opcional: qty efetiva = optional_qty se aceito, senão 0."""
    for line in self:
        if not line.is_proposal_optional:
            continue
        line.product_uom_qty = line.optional_qty if line.optional_accepted else 0.0
```

Para gravação programática (portal Fase 4, testes, confirm), um helper idempotente reutilizável:

```python
def _sync_optional_qty(self):
    """Aplica a regra de qty dos opcionais (chamável fora de onchange)."""
    for line in self:
        if not line.is_proposal_optional:
            continue
        target = line.optional_qty if line.optional_accepted else 0.0
        if line.product_uom_qty != target:
            line.product_uom_qty = target
    return True
```

> Decisão: NÃO sobrescrever `write`/`create` (risco de efeitos colaterais em fluxos nativos do SO). A UI usa o onchange; portal/testes/confirm chamam `_sync_optional_qty()` explicitamente. O `action_confirm` (override existente em sale.order) chama `self.order_line._sync_optional_qty()` antes de gerar, garantindo consistência mesmo se a linha foi gravada por via não-UI.

## 3. Geração no confirm — opcionais aceitos entram

Hoje (`models/sale_order.py`, `_create_qualificacoes_from_lines`, ~linha 949):
```python
managed = self.order_line.filtered(
    lambda l: l.is_qualificacao_managed
    and not l.display_type
    and not l.is_proposal_optional
    and not l.part01_declined
)
```

Novo:
```python
managed = self.order_line.filtered(
    lambda l: l.is_qualificacao_managed
    and not l.display_type
    and not l.part01_declined
    and not (l.is_proposal_optional and not l.optional_accepted)
    and not (l.is_proposal_optional and not l.qualification_type)
)
```

Efeito:
- Opcional **não aceito** → excluído (não gera).
- Opcional aceito **sem** `qualification_type` (serviço: pasta/viagem) → excluído da geração de qualif, MAS soma/fatura (qty>0 via sync).
- Opcional aceito **com** `qualification_type` (qualif opcional) → **gera** `afr.qualificacao` + cycles/malhas + entra na OS, como qualquer linha de qualificação.

Antes do filtro, o override de `action_confirm` (em sale.order) chama `self.order_line._sync_optional_qty()` para garantir qty coerente.

> Verificar: o `action_confirm` override existente está em sale_order.py. Adicionar a chamada `_sync_optional_qty()` no início (antes de `_create_qualificacoes_from_lines`). Ler o método antes de editar para inserir no ponto certo.

## 4. Constraint de consistência

`_check_qualificacao_consistency` (sale_order_line.py ~186) hoje **pula** todos os `is_proposal_optional`. Com opcionais-qualificação, ajustar:

```python
            # Opcional de SERVIÇO (sem qualification_type) — não é linha de
            # qualificação, pula consistência. Opcional de QUALIFICAÇÃO
            # (com qualification_type) segue as regras normais abaixo.
            if line.is_proposal_optional and not line.qualification_type:
                continue
```
(substitui o `if line.is_proposal_optional: continue` atual)

Assim um opcional-qualificação aceito exige equipment_id + qualification_type + cycle/malha conforme o tipo (igual às linhas normais).

## 5. View do form (`sale_order_views.xml`)

A tree de `order_line` já tem o toggle `is_proposal_optional` (linha ~48). Adicionar ao lado, visíveis quando a linha é opcional:
```xml
<field name="optional_qty" string="Qtd Opc."
       attrs="{'invisible': [('is_proposal_optional', '=', False)]}"
       optional="show"/>
<field name="optional_accepted" string="Aceito"
       attrs="{'invisible': [('is_proposal_optional', '=', False)]}"
       widget="boolean_toggle" optional="show"/>
```

> Ler a view atual à volta da linha 48 para inserir na coluna certa e confirmar o nome exato dos campos vizinhos.

## 6. Migração / dados existentes

- Campos novos com default (`optional_accepted=False`, `optional_qty=1.0`). Linhas opcionais existentes nascem **não aceitas** → passam a NÃO somar ao total após `-u`. **Mudança de comportamento intencional**, alinhada ao objetivo.
- ⚠️ Nota de deploy: cotações em aberto com opcionais que hoje somam vão deixar de somar até serem aceitas. Documentar no commit/changelog. (labquali está em DEV — aceitável.)

## 7. Fora de âmbito (Fase 1)

- Aba "Opcionais" no wizard configurador (Fase 2).
- Caixas ☐/☑ e exclusão do total no PDF (Fase 3) — nota: na Fase 1 o opcional já não soma (qty=0), mas o PDF ainda os lista na secção atual; o ajuste visual das caixas é Fase 3.
- Portal interativo + controller de seleção (Fase 4).
- Catálogo `afr.proposal.optional` (já existe; integração via wizard é Fase 2).

## 8. Testes (TDD)

`tests/test_optional_accepted.py`:
1. `test_optional_not_accepted_qty_zero` — linha opcional não aceita → `_sync_optional_qty` deixa product_uom_qty=0; não soma ao amount_total.
2. `test_optional_accepted_sums` — aceito → product_uom_qty=optional_qty; soma ao amount_total.
3. `test_confirm_optional_service_no_qualif` — opcional aceito sem qualification_type → confirma, fatura, NÃO gera afr.qualificacao.
4. `test_confirm_optional_qualif_generates` — opcional aceito com qualification_type (ex performance + cycle_type) → confirma e gera afr.qualificacao + cycle + entra na OS.
5. `test_confirm_optional_not_accepted_skipped` — opcional não aceito com qualification_type → NÃO gera (referência).
6. `test_constraint_optional_qualif_requires_equipment` — opcional com qualification_type sem equipment_id → ValidationError.
