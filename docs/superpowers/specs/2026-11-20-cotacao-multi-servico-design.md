# Cotação multi-serviço com proposta única — Design (Projeto 1 de 2)

Data: 2026-11-20 · Módulo: `afr_qualificacao` (submodule) · Versão alvo: `16.0.9.3.0`

Projeto 2 (execução dos serviços novos + certificados de calibração) terá spec
própria e consome o que este projeto deixa pronto.

## 1. Intenção

A LabQuali não vende só qualificação. Também vende NR-13, verificação de vazão
de exaustores com cálculo de trocas de ar de salas, e calibração avulsa de
sensores de ambiente, câmaras frigoríficas, estufas, incubadoras de indicador
biológico e seladoras de papel grau cirúrgico. O mesmo cliente costuma comprar
vários desses serviços e prefere **um orçamento só**, porque é mais fácil
aprovar na diretoria.

Hoje a cotação só sabe cotar equipamento × tipo de qualificação (QI, Calibração
como malha, QO, QD, QS). Serviço que não é qualificação entra como linha manual
de produto, sem capítulo próprio na proposta e sem nada que a execução possa
herdar.

Sucesso: quem cota adiciona "8 seladoras, 3 incubadoras, 1 NR-13" na mesma
cotação em que configura as qualificações, em poucos cliques, e a proposta sai
como um documento único, com um capítulo por serviço e um resumo financeiro que
soma tudo.

## 2. Decisões do user

1. **Uma cotação só.** Todos os serviços nascem na mesma cotação, na mesma tela.
   Não existe fusão de cotações separadas.
2. **Todo serviço novo é cotado por unidade:** seladora, sensor de ambiente,
   estufa, incubadora de IB por unidade; sala por exaustor; NR-13 por
   equipamento.
3. **Dados de cada unidade vêm depois.** A cotação é por quantidade; os dados de
   identificação de cada unidade são necessários para gerar certificado e
   relatório, não para cotar.
4. **Entrega em dois projetos:** este (cotação + proposta única) e depois a
   execução com certificados. Este tem que ser desenhado já pensando no segundo.
5. **"Template" é o modelo do documento de proposta que sai**, não um
   pré-preenchimento da cotação.
6. **Aceite é sempre total.** A diretoria aprova o pacote inteiro; não há aceite
   por serviço.
7. **Resumo financeiro com total único** que soma serviços, despesas de viagem e
   opcionais, sem subtotal intermediário separando viagem e opcionais.
8. **Abordagem:** catálogo de serviços + passo novo no configurador (seção 5).

## 3. Objetivos, não-objetivos, anti-objetivos

**Objetivos**

- Cadastro de serviços cotáveis por unidade, agrupados em capítulos.
- Passo "Outros serviços" no configurador atual, na mesma cotação.
- Proposta única: um capítulo por grupo de serviço presente, só quando presente.
- Resumo financeiro com uma linha por frente de serviço, viagem e opcionais
  aceitos, e total geral único.
- Lista de unidades por linha de serviço, numerada, pronta para a execução.

**Não-objetivos (ficam para depois)**

- OS, coleta em campo e certificado dos serviços novos (Projeto 2).
- Preço ou template combinado por cliente para os serviços novos. Vale a tabela
  geral; o preço unitário é editável na cotação.
- Cotação pelo celular (PWA / levantamento).
- Aceite parcial por serviço.
- Mudar o comportamento do configurador de qualificação existente.

**Anti-objetivos**

- Obrigar a cadastrar cada equipamento antes de cotar. Cotar 20 sensores tem que
  ser uma linha com quantidade 20.
- Fazer a pessoa escolher template de proposta na mão conforme a combinação de
  serviços.
- Um valor que entra no total da cotação e não aparece no resumo impresso (bug
  C26-06-0005 não pode voltar).

## 4. Estado atual (código, 2026-11-20)

- `sale.order` + wizard `afr.qualificacao.configurator`, passos
  `_STEP_ORDER = ["escopo", "opcionais", "revisao"]`. `action_apply` recria do
  zero as linhas `is_qualificacao_managed` e preserva linhas manuais.
- Linhas de qualificação são equipamento × tipo, com `equipment_id`,
  `cycle_type_id` / `malha_type_id`, horas estimadas.
- Proposta em blocos: `afr.proposal.template` → linhas copiadas para
  `afr.proposal.block` na cotação. Tipos de bloco em `PROPOSAL_BLOCK_KINDS`:
  `static`, `equipment_scope`, `schedule`, `standards_table`, `financial`,
  `optionals`, `sales_items`, `acceptance`. Cada tipo de bloco tem **três**
  implementações que precisam andar juntas: `reports/templates_blocos/block_*.xml`
  (PDF), cópia inline em `views/sale_order_portal_template.xml` (portal) e
  `_snapshot_html` em `models/proposal_block.py` (bloco editável/DOCX).
- O template default (`PROPOSAL_TEMPLATE_LINES` em `hooks.py`) **não** tem
  `financial`, `optionals` nem `schedule`. `financial` é tipo morto desde a
  16.0.7.0.0 (não renderiza; `action_edit_block` o recusa). Os totais saem só no
  fim do bloco `equipment_scope` (`qq_totals_table`, "único emissor de totais").
  Os ciclos também saem dentro de `equipment_scope`; não há bloco de tabela de
  ciclos.
- O configurador exige equipamento em dois pontos (`action_next_step` ao sair de
  "escopo" e `action_apply`). `has_qualif_lines` (que pede `equipment_id`)
  chaveia o portal LabQuali, o painel de totais do form, o template de e-mail e
  os painéis de `sale_order_form_panels.py`.
- Fora de rascunho/enviada, só o configurador e o desconto geral são bloqueados;
  as linhas seguem editáveis pelo padrão do Odoo.
- `action_reload_proposal_blocks` recarrega do `proposal_template_id` da própria
  cotação; o default de cotação nova é o template de menor `sequence`. O hook
  trata o template existente como "utilizador controla 100%".
- Opcionais (`afr.proposal.optional`, kinds incluindo `travel`) viram linhas
  `is_proposal_optional` com `optional_accepted`.
- `sale.order._qualif_proposal_totals()` é a fonte única dos totais (form, PDF,
  portal). Já decompõe `amount_untaxed` em total das qualificações, adicionais
  (viagem, pasta, opcionais aceitos), desconto e residual "Outros", e imprime
  "Valor Geral da Proposta". Ou seja, a decisão 7 já vale para viagem e
  opcionais; falta a quebra por serviço.
- Desconto geral (`is_qualif_discount_line`) incide só sobre os serviços de
  qualificação.
- `engc.equipment` (herdado aqui) já aceita marca, modelo e série opcionais.
- O template default da proposta é semeado por `hooks.py`, não por
  `proposal_template_seed.xml`; mudanças em instalações existentes vão por
  migração por xmlid.
- Exemplos reais em `dados_sensiveis/exemplos_relatorios/`: propostas 074/26,
  080B/26, 252/26 (qualificação + calibração num documento) e certificados
  176-25-NN (seladora, incubadora de IB, termo-higrômetro).

## 5. Abordagens consideradas

**A — Catálogo de serviços + passo novo no configurador (escolhida pelo user).**
Modelo novo de serviço cotável por unidade; passo "Outros serviços" no
configurador; capítulo por grupo na proposta. Custa um modelo e um passo novos.
Cotar fica em dois cliques e a execução herda procedimento e unidades numeradas.

**B — Tudo vira qualificação.** Seladora, incubadora e sensor como categorias de
equipamento, calibração avulsa como malha, NR-13 como tipo novo ao lado de
QI/QO/QD. Reaproveita quase tudo, mas obriga cadastrar cada equipamento antes de
cotar, gera uma linha por equipamento e não acomoda exaustor de sala. Contraria
a usabilidade pedida.

**C — Produtos comuns + linhas manuais**, usando o bloco `sales_items` que já
existe. Quase de graça, mas sem capítulo por serviço, sem lista de unidades, e a
execução teria que ser refeita do zero.

Escolhida a **A** por ser a única que atende usabilidade agora sem travar o
Projeto 2.

## 6. Desenho

Itens marcados **(decisão do desenho)** foram escolhidos por quem escreveu este
documento, não pelo user; podem ser revistos.

### 6.1 Catálogo

**Grupo de serviço** (`afr.servico.grupo`): é o capítulo da proposta e a linha
do resumo financeiro.

- nome (ex.: "Calibração de Instrumentos"), código, sequência, ativo, empresa
- título do capítulo na proposta
- rótulo da unidade no plural/singular para textos ("instrumento", "exaustor",
  "equipamento")

**Serviço** (`afr.servico`), herda `afr.product.service.mixin`:

- nome, código, sequência, ativo, empresa
- grupo (obrigatório)
- produto de serviço (obrigatório); preço padrão = preço de lista do produto
- horas estimadas por unidade
- descrição de escopo (texto curto que aparece na tabela da proposta)
- procedimento de referência: código e revisão (ex.: QPC-008 rev. 00)
- normas (`afr.qualificacao.standard`, M2M)
- categoria de equipamento (opcional), usada ao cadastrar unidades

Edição só pelo grupo Gestor; comercial lê. Menus em Configuração, ao lado de
tipos de ciclo e de malha.

**Seeds** (preço zero, gestor preenche):

| Grupo | Serviços |
|---|---|
| Calibração de Instrumentos | sensor de ambiente (termo-higrômetro), câmara frigorífica, estufa, incubadora de indicador biológico, seladora de papel grau cirúrgico |
| NR-13 | inspeção NR-13 por equipamento |
| Vazão de Exaustores e Trocas de Ar | verificação por exaustor |

Câmara frigorífica não foi confirmada pelo user como "por unidade"; assumida
assim **(decisão do desenho)**.

### 6.2 Linha da cotação

Em `sale.order.line`:

- `service_id` (serviço do catálogo) e `is_service_managed`
- quantidade = número de unidades; preço unitário editável
- horas estimadas da linha = quantidade × horas por unidade do serviço
- uma linha por serviço por cotação **(decisão do desenho)**; se a pessoa quiser
  dois preços para o mesmo serviço, usa linha manual

Linha de serviço nunca tem `equipment_id` nem `qualification_type`, e nunca é
`is_qualificacao_managed`. A constraint de consistência das linhas de
qualificação não pode pegá-la.

### 6.3 Unidades

Modelo `afr.servico.unidade`, filho da linha de serviço:

- número do item (sequencial na cotação, atravessando todos os serviços)
- equipamento (`engc.equipment`, opcional) **(decisão do desenho:** reaproveitar
  o cadastro de equipamento em vez de criar um segundo cadastro**)**
- identificação/TAG, descrição, marca, modelo, série, local de uso, faixa de
  utilização. Preenchidos a partir do equipamento quando ele é escolhido;
  digitáveis direto quando não há equipamento.
- estado calculado: identificada ou pendente (identificada = tem TAG ou série)

Regras:

- Na cotação em rascunho, a lista é opcional. A pessoa pode preencher zero, parte
  ou todas.
- Ao confirmar a cotação, o sistema completa a lista com unidades vazias até a
  quantidade da linha e fixa o número do item. Confirmar **não** bloqueia por
  unidade pendente.
- A cotação mostra "N de M unidades identificadas" por linha e no total.
- Nunca pode haver mais unidades do que a quantidade da linha.
- Identificação completa passa a ser obrigatória só para gerar a execução, que é
  do Projeto 2.

Estabilidade do número depois da confirmação **(decisão do desenho)**:

- Número atribuído nunca muda e nunca é reaproveitado.
- Aumentar a quantidade: unidades novas recebem os próximos números, no fim.
- Reduzir a quantidade: só remove unidades pendentes, das de número mais alto
  para baixo. Se sobrariam menos vagas do que unidades identificadas, bloqueia
  com mensagem; a pessoa remove a unidade identificada à mão. Buracos na
  numeração são aceitos.
- Cancelar → rascunho → reconfirmar preserva unidades e números; só completa o
  que faltar.

Motivo do número do item: os certificados reais são numerados
`<proposta>-<item>` (ex.: 176/25-47, 176/25-54), sequenciais entre serviços. O
Projeto 2 decide como esse número se combina com a numeração dos relatórios de
qualificação; este projeto só garante que cada unidade tem um número estável
depois do aceite.

### 6.4 Configurador

Novo passo **"Outros serviços"** entre "escopo" e "opcionais":

```
Outros serviços
 Serviço                          Qtd   Unitário    Total
 Calibração de seladora             8   R$ 120,00   R$ 960,00
 Calibração de incubadora de IB     3   R$ 180,00   R$ 540,00
 Inspeção NR-13                     1   R$ 2.400    R$ 2.400,00
 [+ adicionar serviço]
                                  Subtotal outros serviços  R$ 3.900,00
```

- Escolher o serviço preenche unitário e horas a partir do catálogo.
- Serviços agrupados visualmente por grupo.
- A lista de unidades é editada na linha da cotação (aba própria no form), não
  dentro do wizard **(decisão do desenho:** manter o wizard leve**)**.
- O passo de revisão mostra as frentes de serviço e o total.
- **Cotação só de outros serviços, sem nenhum equipamento de qualificação, tem
  que funcionar.** As duas exigências de equipamento do configurador caem quando
  há pelo menos um serviço. Tudo que hoje é chaveado por `has_qualif_lines`
  (portal LabQuali, painel de totais do form, template de e-mail, painéis do
  form) passa a valer também para cotação que só tem linhas de serviço, por um
  indicador novo "cotação gerenciada" = tem qualificação ou tem serviço.
- Ao aplicar: as linhas de qualificação continuam sendo recriadas do zero como
  hoje. As linhas de serviço **não** são recriadas: são atualizadas por
  `service_id` (cria as novas, ajusta qtd/preço das existentes, remove as que
  saíram), para não perder a lista de unidades. Reduzir a quantidade segue a
  mesma regra da seção 6.3 em qualquer estado: remove primeiro as unidades
  pendentes; se ainda sobrarem mais identificadas do que a nova quantidade,
  bloqueia com mensagem e a pessoa remove a unidade identificada à mão. Remover
  do configurador um serviço que tem unidade identificada bloqueia do mesmo
  jeito.
- Depois de confirmada a cotação, o configurador fica bloqueado como hoje; a
  quantidade da linha de serviço segue editável direto na linha, com as regras
  de numeração da seção 6.3.

O botão do configurador continua um só. O rótulo deixa de falar só em
qualificações (ex.: "Configurar Serviços") **(decisão do desenho)**.

### 6.5 Proposta

**Capítulos condicionais.** Cada linha de template e cada bloco ganham um campo
"aparece quando": sempre, quando há qualificação, ou quando há serviço de um
grupo específico. Na renderização, bloco cuja condição não se cumpre é pulado e
a numeração é calculada só sobre os blocos visíveis **(decisão do desenho)**.

Com isso existe **um template de proposta multi-serviço** que contém todos os
capítulos. Ele é copiado inteiro para a cotação e o documento se ajusta sozinho
ao que foi cotado, sem a pessoa trocar de template e sem sincronizar blocos a
cada mudança. A pessoa continua podendo reordenar, desligar e editar o texto de
cada bloco na cotação. Na lista de blocos do form, bloco oculto pela condição
aparece esmaecido com o motivo.

Alternativa descartada: inserir e remover blocos na cotação conforme os serviços
entram e saem. Dá o mesmo resultado, mas exige sincronização e perde edição de
texto quando um grupo sai e volta.

**Bloco novo `service_group`** (um por grupo no template), que renderiza:

```
4. Calibração de Instrumentos
   4.1 <texto descritivo do grupo: o que é, procedimento, o que é entregue>
   4.2 Serviços
       Item  Serviço                         Qtd   Unitário    Total
       1     Calibração de seladora            8   R$ 120,00   R$   960,00
       2     Calibração de incubadora de IB    3   R$ 180,00   R$   540,00
                                                   Subtotal    R$ 1.500,00
   4.3 Relação de instrumentos            ← só se houver unidade identificada
       Item  Identificação  Descrição  Marca / Modelo  Série  Local
```

O texto descritivo é um bloco estático normal (`afr.proposal.section`) com a
condição do grupo, posicionado antes do bloco `service_group`.

O rodapé do bloco mostra também "Previsão de N dia(s) de serviço" quando as
linhas do grupo têm horas estimadas. O bloco `service_group` precisa das três
implementações (PDF, portal, snapshot editável).

**Condição de cada bloco do template** **(decisão do desenho)**:

| Bloco | Aparece |
|---|---|
| Objetivo, metodologia, rastreabilidade, condições, dados cadastrais, credenciais, responsabilidades, aceite | sempre |
| Texto estático "normas" e tabela de normas (`standards_table`) | sempre |
| Descrição QI/QO/QD, validadores, entregáveis (falam de relatório de qualificação térmica), escopo por equipamento | quando há qualificação |
| Texto do grupo + `service_group` | quando há serviço do grupo |

A tabela de normas passa a agregar também as normas dos serviços cotados, além
das de ciclos e malhas. O que cada grupo entrega (certificado, laudo) vai no
texto do próprio grupo.

**Objetivo e título do orçamento** citam os serviços presentes. Um helper na
cotação devolve a lista dos títulos das frentes presentes ("Qualificação
Térmica, Calibração de Instrumentos e NR-13") para uso nas expressões dos
textos.

**Esqueleto do documento:**

```
PROPOSTA COMERCIAL Nº ...
 1. Objetivo                         (cita as frentes presentes)
 2. Metodologia, rastreabilidade, segurança da informação
 3. Qualificação Térmica             (se houver qualificação)
 4. Calibração de Instrumentos       (se houver)
 5. NR-13                            (se houver)
 6. Vazão de Exaustores e Trocas de Ar (se houver)
 7. Resumo financeiro                (bloco novo de totais, seção 6.6)
 8. Condições comerciais
 9. Dados cadastrais, responsabilidades do cliente, aceite
```

Cronograma (`schedule`) e Opcionais (`optionals`) continuam fora do template
default, como hoje; quem quiser adiciona o bloco na cotação.

**Textos.** O capítulo de Calibração parte dos textos que já existem das
propostas de venda + calibração (`SEC-VC-*`). Para NR-13 e Vazão/Trocas de Ar
não há texto institucional da LabQuali no repositório: entram textos-rascunho
marcados como "revisar", para o cliente substituir. Isso é dependência externa,
não bloqueia a construção.

**Template default** **(decisão do desenho)**. O template multi-serviço é um
**registro novo** (ex.: `TPL-MULTI`), com a menor `sequence`, e por isso vira o
default de cotações novas. `TPL-LABQUALI` e `TPL-VENDA-CALIB` não são tocados
(o primeiro é controlado pelo usuário e pode ter sido editado à mão no remoto);
continuam escolhíveis no seletor do configurador. Cotações existentes ficam com
o template que têm; para migrar uma, a pessoa troca o template na cotação e usa
"Recarregar blocos". Seed pelo `hooks.py` (instalação nova) mais migração que
cria o registro por xmlid se não existir (instalação existente).

### 6.6 Resumo financeiro e cronograma

`_qualif_proposal_totals()` continua a fonte única e passa a devolver também as
frentes de serviço:

```
Qualificação Térmica ........................ R$ 12.400,00   (se houver)
Calibração de Instrumentos .................. R$  1.500,00
NR-13 ....................................... R$  2.400,00
Despesas de viagem (estimativa) ............. R$  4.714,02
Pasta impressa .............................. R$    190,00
Descontos ................................... -R$   500,00   (se houver)
VALOR GERAL DA PROPOSTA ..................... R$ 20.704,02
```

- Uma linha por grupo presente, valor = soma das linhas de serviço do grupo.
- Linhas de serviço saem do cálculo de "adicionais" (senão contam duas vezes).
- Viagem e opcionais só aparecem quando aceitos/incluídos, como hoje; os não
  aceitos não entram no total nem no resumo.
- A linha residual "Outros" continua existindo como rede de segurança: a soma
  das linhas impressas tem que fechar com `amount_untaxed`.
- Com uma frente só e sem adicionais, imprime só o total geral, como hoje.
- Desconto geral continua incidindo só sobre qualificação **(decisão do
  desenho:** não ampliar a base do desconto neste projeto**)**.
- Mesmo resumo no form, no PDF e no portal.

**Onde o resumo imprime** **(decisão do desenho)**. Hoje a tabela de totais sai
só no fim de `equipment_scope`. Numa cotação sem qualificação esse bloco fica
oculto e o total sumiria. Então:

- Entra um bloco próprio de totais (reaproveitando o tipo `financial`, hoje
  morto, ou um tipo novo; escolha de quem constrói), presente no template
  multi-serviço depois do último capítulo de serviço, condição "sempre".
- `equipment_scope` só imprime a tabela de totais quando a cotação **não** tem
  um bloco de totais ativo. Assim propostas dos templates antigos saem
  idênticas às de hoje e nenhuma proposta imprime o total duas vezes ou zero
  vezes.
- Regra a testar: toda proposta com valor imprime a tabela de totais exatamente
  uma vez.

As horas das linhas de serviço entram na previsão total de dias de execução da
cotação e, se o bloco de cronograma for adicionado, aparecem com uma linha por
grupo.

### 6.7 O que este projeto deixa pronto para o Projeto 2

- Serviço com procedimento de referência, normas e categoria de equipamento.
- Cada unidade cotada como registro numerado, com identificação e vínculo
  opcional a equipamento.
- Linha de cotação que distingue serviço de catálogo de qualificação e de item
  manual.

O wizard "Gerar OS de Qualificação" ignora linhas de serviço neste projeto.

## 7. Restrições

- Odoo 16.0; nada de editar `engc_os` (terceiro), só `_inherit`.
- Submodule: commit e push de dentro de `addons/afr_qualificacao`, depois bump do
  pointer no monorepo.
- Bump de versão no manifest.
- Remoto labquali está em desenvolvimento, sem produção: migração de dados não
  é exigida, exceto a do template default da proposta.
- Testes pelo padrão do módulo (suíte atual ~1500 testes tem que continuar
  verde); UI validada no navegador antes de entregar.

## 8. Deixado para quem constrói

- Nomes técnicos finais de modelos e campos.
- Layout exato do passo do configurador e da aba de unidades no form.
- Como marcar visualmente blocos ocultos pela condição.
- Estilo das tabelas novas no PDF, seguindo as classes já usadas (`qq-table`).
- Divisão em tarefas e ordem de entrega.
