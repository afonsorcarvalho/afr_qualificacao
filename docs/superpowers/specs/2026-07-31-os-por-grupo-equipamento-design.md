# OS de Qualificação por grupo de equipamentos (1 cotação : N OS)

Data: 2026-07-31
Módulo: `afr_qualificacao`
Versão alvo: `16.0.6.13.0` (feat → bump MINOR)

## Problema

Hoje `sale.order.action_confirm()` gera automaticamente **1 OS de qualificação
por cotação**, agregando todos os equipamentos. Na prática uma cotação com
vários equipamentos costuma ser executada em visitas separadas — por setor,
andar ou disponibilidade do cliente — e cada visita precisa da sua própria OS,
com plano de recursos, procedimento e relatórios independentes.

## Solução

Geração passa a ser **manual e incremental, após a confirmação da cotação**:

1. Confirmar a cotação não cria mais nenhuma OS nem qualificação.
2. Na cotação confirmada aparece o botão **Gerar OS de Qualificação**.
3. Cada clique abre um wizard que lista **apenas os equipamentos ainda sem OS**;
   o usuário seleciona um subconjunto e o sistema cria 1 OS já completa
   (qualificações + ciclos/malhas + itens de coleta).
4. Repete-se até acabar. O botão some quando todo equipamento da cotação já
   tem OS.

Invariante central: **um equipamento nunca está em duas OS da mesma cotação**.

## Arquitetura

### Remoção

`action_confirm()` deixa de chamar `_create_qualificacoes_from_lines()`.
O override permanece só pelo `_sync_optional_qty()` das linhas.

### Refatoração

O corpo de materialização (hoje ~80 linhas dentro de
`_create_qualificacoes_from_lines`: `by_equipment` → `by_type` → cycles/malhas
→ snapshot QD → `_explode_collect_items`) é extraído para:

```python
def _materialize_qualificacoes(self, lines, os):
    """Cria afr.qualificacao + sub-records para `lines`, dentro de `os`."""
```

Recebe as linhas e a OS de destino; **não** resolve OS sozinho.

A resolução atual `os = self.qualificacao_os_ids[:1]` com fallback por busca de
nome é **removida**. Com N OS por cotação ela rotearia qualificações para
"a primeira OS que ordenar", silenciosamente errado.

### Adições

**`sale.order`**

- `equipamentos_sem_os_ids` (`Many2many` compute, não armazenado) — equipamentos
  das linhas managed cujo `afr_qualificacao_id` está vazio. Depende de
  `order_line.afr_qualificacao_id` e `order_line.equipment_id`.
- `pode_gerar_os` (`Boolean` compute) — `state == 'sale' and
  equipamentos_sem_os_ids`. Controla a visibilidade do botão.
- `action_open_generate_os_wizard()` — abre o wizard com
  `default_sale_order_id`.

**Wizard `afr.qualificacao.os.generate.wizard` (`TransientModel`)**

| Campo | Tipo | Nota |
|---|---|---|
| `sale_order_id` | Many2one `sale.order`, required, readonly | contexto |
| `equipment_ids` | Many2many `engc.equipment`, required | domínio = pendentes; default = todos os pendentes |

`action_generate()`:

1. Valida `sale_order_id.state == 'sale'` (defesa server-side — botão escondido
   não é garantia).
2. Valida `equipment_ids` não vazio.
3. Revalida contra o pool de pendentes **no momento da execução** (outra aba
   pode ter gerado nesse meio-tempo). Se algum selecionado já tem OS →
   `UserError` listando-os. Se sobrou nada → `UserError`.
4. Cria a OS (`_prepare_qualificacao_os_values(selected, pending)`).
5. Chama `_materialize_qualificacoes(linhas dos equipamentos selecionados, os)`.
6. Retorna `ir.actions.act_window` abrindo a OS criada em form.

**Constraint em `afr.qualificacao`**

```python
@api.constrains("os_id", "equipment_id", "sale_order_id")
def _check_um_equipamento_uma_os_por_so(self):
    """Para cada (sale_order_id, equipment_id): len(set(os_id)) == 1."""
```

Vale para qualquer caminho de criação, não só o wizard — é a invariante que
sobrevive a criação manual, import ou script.

`afr.qualificacao.os.equipment_ids` continua computed a partir de
`qualificacao_ids` — não há segunda m2m para manter em sincronia.

### Nomenclatura

`afr.qualificacao.os` tem `_sql_constraints = [("name_company_uniq",
"unique(name, company_id)", ...)]`. O nome atual `"OS" + so_name[1:]`
(C26-06-0001 → OS26-06-0001) colidiria com N OS.

Regra nova, decidida **no momento da criação**, sem rename retroativo:

```python
existentes = len(so.qualificacao_os_ids)
if existentes == 0 and set(selecionados) == set(pendentes):
    name = "OS26-06-0001"            # cobre a cotação inteira de uma vez
else:
    name = "OS26-06-0001-%d" % (existentes + 1)   # -1, -2, -3…
```

| Cenário | Nomes |
|---|---|
| 1 clique cobrindo todos os equipamentos | `OS26-06-0001` |
| 3 equipamentos, cliques de 2 + 1 | `OS26-06-0001-1`, `OS26-06-0001-2` |
| 3 cliques | `-1`, `-2`, `-3` |

Um primeiro clique parcial já nasce `-1` porque se sabe de antemão que virá
pelo menos `-2` (sobrou equipamento pendente). Invariantes resultantes:

- nome sem sufixo ⇒ a cotação tem OS única;
- existe `-1` ⇒ existe `-2`.

Fallback preservado: cotações cujo `name` não começa com `C` continuam usando a
`ir.sequence` `afr.qualificacao.os.sequence` no `create()`.

**Caso não tratado (explícito):** se as OS forem apagadas manualmente e sobrar
só a `-2`, o nome não volta a ficar sem sufixo. Deleção de OS é rara e manual.

## Fluxo de dados

```
SO confirmada (state=sale)
  └─ botão "Gerar OS de Qualificação"
       └─ wizard: [x] Autoclave 01  [x] Autoclave 02  [ ] Termodesinfectora
            └─ create afr.qualificacao.os (name, partner, company, sale_order_id)
                 └─ _materialize_qualificacoes(linhas dos equips selecionados, os)
                      ├─ 1 afr.qualificacao por (equipamento, qualification_type)
                      ├─ cycles (QD/QO com cycle_type) / malhas (Calib) por qty
                      ├─ snapshot dos pontos QD (qd_point_snapshot_ids)
                      └─ collect.items via procedimento da categoria
            └─ linhas SO recebem afr_qualificacao_id → saem do pool de pendentes
       └─ abre a OS criada em form
```

## Efeitos colaterais aceitos

- **Escopo de recursos muda.** `action_compute_resource_plan`,
  `action_apply_procedimento` e `_resource_demand_by_equipment` são por-OS.
  Com a cotação dividida, passam a calcular por grupo — que é o objetivo
  (visitas separadas), mas altera número de instrumentos e horas por OS em
  relação ao comportamento antigo.
- **Stat button.** `action_view_qualificacao_os` passa a abrir tree quando
  `count > 1` e form quando `count == 1`.

## Segurança

- OS nasce em `draft`; os guards `_MANAGER_ONLY_STATES_ON_CREATE` /
  `_STATE_LOCKED_ONCE_REACHED` do modelo continuam valendo sem alteração.
- `_explode_collect_items` permanece em `sudo()` — mesma justificativa de hoje
  (quem opera a cotação pode não ter os grupos de qualificação).
- A `@api.constrains` da invariante roda sem `sudo`, então vale para todos os
  caminhos.
- O wizard exige os grupos de qualificação normais para criar OS/qualificação
  (sem `sudo` na criação da OS).

## Retrocompatibilidade

Cotações já confirmadas antes desta versão têm OS e linhas com
`afr_qualificacao_id` preenchido → o pool de pendentes fica vazio → o botão não
aparece. Nenhuma migração de dados é necessária.

O nome da OS não vaza para documentos: `grep` em `reports/`, `static/` e
`controllers/` não retorna nenhuma referência a `os.name`; o relatório de OS usa
sequência própria (`afr.qualificacao.os.relatorio`), o certificado usa a OS só
para técnico e instrumentos, e o nome da qualificação deriva do número da
cotação (`Q-C26-06-0001-<eq>-<tipo>`).

## Testes

Novo arquivo `tests/test_os_por_grupo.py`:

1. 3 equipamentos, cliques de 2 + 1 → 2 OS com `equipment_ids` disjuntos.
2. Invariante: criar qualificação de equipamento já coberto por outra OS da
   mesma cotação → `ValidationError`.
3. Nomes: clique único cobrindo tudo → `OS26-06-0001` sem sufixo.
4. Nomes: parcial → `-1`, `-2`, `-3`; sem violar `unique(name, company_id)`.
5. `action_confirm()` sozinho **não** cria OS nem qualificação.
6. Wizard com equipamento já gerado (corrida entre abas) → `UserError`.
7. Sub-records por grupo: ciclos QD, malhas de calibração e collect.items
   apenas dos equipamentos daquele grupo.
8. Pool de pendentes esvazia progressivamente; `pode_gerar_os` vira `False`.
9. Wizard bloqueia cotação não confirmada (`state != 'sale'`).

### Migração dos testes existentes

13 arquivos de teste dependem de `action_confirm()` gerar a estrutura:
`test_qo_cycles`, `test_procedimento_explosion`, `test_hours_vs_cycles`,
`test_partes_qi_qo`, `test_resource_plan`, `test_certificate`,
`test_quote_first_os`, `test_optional_accepted`, `test_sequence_naming`,
`test_so_confirm_generation`, `test_qty_delivered_propagation`,
`test_optional_wizard`, `test_proposal_builder`.

Mitigação: helper compartilhado `_confirm_and_generate_os(so)` (base class de
teste) que confirma a cotação e gera uma OS única com todos os equipamentos,
substituindo `so.action_confirm()` nesses testes. Alteração mecânica, mas ampla
— deve ser uma task própria do plano.

`test_so_confirm_generation` precisa de revisão de conteúdo, não só de chamada:
seu objeto passa a ser "confirm não gera nada".
