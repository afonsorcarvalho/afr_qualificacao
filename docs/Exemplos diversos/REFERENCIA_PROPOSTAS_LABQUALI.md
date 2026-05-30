# Referência — Propostas LabQuali (modelos reais do cliente)

> **Origem:** extraído dos 3 `.doc` em `docs/Exemplos diversos/` (modelos que a
> LabQuali usa hoje, fora do Odoo). Este arquivo consolida toda informação útil
> para desenvolver os templates do módulo `afr_qualificacao` — **não é mais
> preciso reabrir os `.doc`**.
>
> ⚠️ Acentuação: os `.doc` são OLE binário; a extração via `strings` quebrou
> acentos e tabelas. O texto abaixo foi **reconstruído em PT-BR limpo**. Valores
> numéricos, nomes, CNPJ, telefones e e-mails vieram legíveis e são fiéis ao
> original. Texto corrido institucional pode precisar de revisão final do cliente.

---

## 1. Os três arquétipos de proposta

| # | Arquivo | Tipo | Complexidade |
|---|---------|------|--------------|
| 2 | `2 - Proposta LabQuali de QI - QO - QD` | **Qualificação Térmica + Calibração** (QI/QO/QD) | Alta — escopo por equipamento com tabelas de ciclos |
| 3 | `3 - Proposta de Calibração - LabQuali` | **Calibração de Instrumentos** | Baixa — tabela simples Qtd × Unitário |
| 4 | `4 - Proposta de Venda + Calibração` | **Venda + Calibração** | Baixa — tabela de produtos + frete |

Os três compartilham a **mesma capa, condições comerciais, dados cadastrais e
aceite**. Diferem no miolo técnico/escopo.

---

## 2. Estrutura comum (capa + cabeçalho)

Campos do cabeçalho (preenchidos por cotação):

- Cidade + data (ex: "Santo André, __ de Abril de 202_")
- **Solicitante/Cliente**
- **Endereço de execução** + CEP
- **Contatos** / Dpto / E-mail / Telefones
- **Razão Social** / CNPJ

Título varia por tipo:
- Doc 2: *"Orçamento de Qualificação Térmica e Calibração"*
- Doc 3: *"Orçamento de Calibração de Instrumentos"*
- Doc 4: *"Orçamento de Venda + Calibração de Instrumentos"*

---

## 3. Seções institucionais (texto corrido — comuns)

### 3.1 Objetivo
Fornecimento de serviços de Qualificação Térmica e Calibração de instrumentos
(doc 2) / Calibração de Instrumentos de Medição (doc 3/4) para o cliente citado.

### 3.2 Metodologia de execução
"Nossa estratégia de execução incorpora metodologias comprovadas, sendo
realizadas de acordo com critérios de qualidade e princípios organizacionais,
atendendo às exigências normativas e legislações aplicadas conforme cada
processo, visando atender as necessidades dos nossos clientes."

### 3.3 Escopo
"O escopo do fornecimento proposto está limitado aos equipamentos listados nesta
proposta, conforme mostrado na relação de serviços a serem executados."

### 3.4 Qualificação Térmica — conceitos (doc 2)
A Qualificação Térmica é parte integrante do processo de validação, contendo:

- **QI — Qualificação da Instalação:** evidências documentadas de que a
  instalação foi finalizada de forma satisfatória. Itens avaliados:
  Documentação de Instalação, Elementos de Controle, Software Utilizado
  (validável), Principais componentes, Materiais de construção, Instrumentação,
  Certificados de Calibração, Utilidades, Equipamentos Críticos, Alimentação e
  proteção, Conexões, Módulos de entradas/saída (I/O).
- **QO — Qualificação de Operação:** evidências de que utilidades, sistemas e
  componentes operam conforme especificações. Itens avaliados: Perda de
  energia/comunicação, Validação do software, Requisitos operacionais/parâmetros
  de operação, Alarmes/Mensagens de erro, Controle de acesso/Senhas/Operações
  não permitidas, Inter travamento (segurança), Requisitos de auditoria,
  Segurança da informação, Sistema de backups dos dados, Falta de
  utilidades/suprimentos, Execução dos ciclos sem carga, Interface com operador.
- **QD — Qualificação de Desempenho:** evidências de desempenho consistente em
  rotina. Resultados coletados por período para comprovar consistência. Para
  ciclos com tempo finito → replicados; para tempo infinito → monitoramento de
  amostragem representativa (normalmente 24 h).

### 3.5 Recursos utilizados — Validadores (doc 2)
Sistema de Aquisição de Dados (Validadores):

| Validador | Canais |
|-----------|--------|
| Yokogawa DX-2030 | 30 |
| Yokogawa DX-2030-s-4-2 | 30 |
| Yokogawa DX1006-3-4-2 | 12 |
| Yokogawa GP10 | 20 |
| Yokogawa GM1020 | 20 |

### 3.6 Rastreabilidade dos padrões
"Os padrões utilizados nas Qualificações e Calibrações são calibrados anualmente
pela Rede Brasileira de Calibração — RBC-INMETRO, atendendo a todos os requisitos
nacionais (ANVISA) e internacionais."

### 3.7 Segurança da Informação
"Nossos Validadores atendem aos mais rigorosos critérios de segurança da
informação, gerando os dados coletados de forma criptografada, conforme
**FDA 21 CFR Part 11 Compliant**."

### 3.8 Documentação entregue (doc 2)
Relatório de Qualificação Térmica contendo:
- Protocolo de Qualificação Térmica
- Resultados dos valores obtidos em tabelas e gráficos
- Relatórios gerados pelo equipamento qualificado (fitas de impressão), quando aplicável
- Laudo de Qualificação Microbiológica, ou de limpeza, quando aplicável
- Resultados do Cálculo de Letalidade **F0, A0, FH**, quando aplicável
- Certificados de Calibração dos instrumentos de controle do equipamento
- Certificados de Calibração do validador (**antes e depois** da qualificação)
- Documentos complementares — certificados dos padrões com rastreabilidade INMETRO

### 3.9 Procedimento de Calibração (doc 3/4)
"Calibração: operação que estabelece, sob condições específicas, em uma primeira
etapa, uma relação entre os valores e as incertezas de medição fornecidos por
padrões e as indicações correspondentes; em uma segunda etapa, utiliza esta
informação para estabelecer uma relação visando a obtenção de um resultado de
medição a partir de uma indicação. **(NBR 16328:2014)**"

Os certificados contêm: tabelas com a média dos valores coletados (padrão ×
instrumento), incerteza expandida com **nível de confiança de 95%** e coeficiente
de abrangência (**K**), dados dos padrões utilizados e cópia de seus certificados.

---

## 4. Escopo por equipamento (doc 2 — o coração da proposta QI/QO/QD)

Cada equipamento é um bloco com a estrutura:
- **QI (primeira parte)** — checklist de itens avaliados + "Previsão de N dia(s)" + `Subtotal QI: A SER SOLICITADO`
- **QO (primeira parte)** — checklist + previsão + `Subtotal QO: A SER SOLICITADO`
- **QI (segunda parte) — Calibração** dos equipamentos de controle (malhas)
- **QO (segunda parte)** — tabela "Execução dos ciclos **sem carga**" (Qtd | Ciclo | Temperatura | Tempo)
- **QD** — tabela "Execução dos ciclos **com carga**" + "Previsão de N dia(s)" + `Subtotal QD: R$ X` + **`Valor Unitário: R$ Y`**

> Nota: o checklist QI/QO (itens avaliados) **repete-se idêntico** sob cada
> equipamento no .doc — é verbosidade manual do Word. No módulo isso já está
> fatorado em seções compartilhadas (§3.4) + escopo por equipamento. **Adaptar,
> não copiar** a repetição.

### Catálogo de equipamentos + ciclos + preços (exemplos reais)

| Equipamento | Malhas (calibração) | Ciclos sem carga (QO) | Ciclos com carga (QD) | Dias | Subtotal QD | Valor Unit. |
|---|---|---|---|---|---|---|
| **Autoclave a Vapor** | Temperatura, Pressão, Temporizador | Bowie Dick 3,5 min; Vazio 20 min | Carga Mista 7 min; Carga sensível 20 min | 1,5 | R$ 1.300,00 | **R$ 2.400,00** |
| **Termodesinfectora** | Temperatura, Temporizador | Vazio 10 min; Vazio 2 min | Carga Instrumental 2 min; Carga Inalat. 10 min | 2,5 | R$ 1.800,00 | **R$ 2.900,00** |
| **Lavadora Ultrassônica** | Temperatura, Temporizador | Vazio 15 min | Carga de Instrumental e Canulados 15 min | 1,0 | R$ 1.800,00 | **R$ 2.900,00** |
| **Refrigerador/Freezer/Estufa Incubadora/Banho Maria/Câmara Climática** | Temperatura, Temporizador | Vazios 24 h | Com Carga 24 h + Estudo Abertura de Porta + Estudo Queda de Energia | 2,5 | R$ 1.600,00 | **R$ 2.700,00** |
| **Estufa de Esterilização / Despirogenização** | Temperatura, Temporizador | Vazios 60 min | Com Carga 60 min | 1,5 | R$ 1.400,00 | **R$ 2.500,00** |
| **Autoclave a Gás (ETO)** | Temperatura, Pressão, Umidade, Temporizador | Vazio 180 min | Carga ½ tempo esteril. 90 min; Carga rotina 180 min; tempo curto exposição gás (resistência micro-org.) 5 min | 2,5 (dias e noites) | R$ 2.800,00 | **R$ 4.300,00** |
| **Autoclave a Gás — validação carga industrial (EXTERIMAX)** | Temperatura, Umidade, Pressão, Temporizador | 03 ciclos câmara vazia 180 min | QDF: 1 ciclo carga tempo total 180 min; QDM: 3 ciclos carga ½ tempo 90 min + 1 ciclo tempo curto gás 15 min | 3,0 (Total 8 estudos) | — | **R$ 6.500,00** |
| **Seladora** | Temperatura | 1 medição temperatura máx. recomendada pelo fabricante da embalagem | QD: teste tração da selagem; uniformidade (SEAL TEST); estanqueidade com líquido penetrante | 0,5 | — | **R$ 800,00** |
| **Secadora (Sercon)** | Temperatura, Temporizador | 03 estudos câmara vazia | 03 estudos câmara cheia (Instrumentais) — Total 06 estudos | 0,5 | — | **R$ 600,00** |

Observação (Refrigerador/Freezer etc.): *"Não há necessidade de realizar o estudo
em vazio (QO) nas requalificações. Esta só é exigida na instalação do
equipamento."*

Equipamentos a gás (ETO): QD separa **QDF (físico)** e **QDM (microbiológico)**.

---

## 5. Calibração pura (doc 3) e Venda+Calibração (doc 4)

### Doc 3 — Calibração de Instrumentos
Tabela: **Descrição | Quant. | Valor Unitário R$ | Valor Total R$**

| Descrição | Unit. |
|---|---|
| Calibração de Centrífuga | R$ 250,00 |
| Calibração de Liofilizador | R$ 250,00 |

### Doc 4 — Venda + Calibração
Mesma tabela + **Condições de Frete** (Correios SEDEX HOJE / SEDEX D+1 / Motoboy 50 min):

| Descrição | Unit. | Total (exemplo) |
|---|---|---|
| Venda + Calibração de Termômetro | R$ 95,00 | R$ 285,00 |
| Venda + Calibração de Termo-higrômetros | R$ 130,00 | R$ 260,00 |
| Venda + Calibração de Válvulas de segurança | R$ 1.350,00 | R$ 2.700,00 |

---

## 6. Condições Comerciais (comum aos três)

- **Valor total dos serviços** (impostos já inclusos): R$ ___
- **Previsão de despesa de viagem** na NF da LabQuali (impostos inclusos, gera
  bitributação): ex. R$ 1.095,00
  - No ato da aprovação, cliente solicita data; após agendamento, aguarda-se
    reserva de HOTEL e PASSAGENS (aéreas/rodoviárias). Demais gastos (UBER,
    alimentação) pagos a princípio pela LabQuali e **reembolsados** depois via
    relatório de gastos do financeiro.
- **Previsão de dias para execução:** N dia(s)
- **Prazo de entrega dos Relatórios/Certificados:**
  - Qualificação (doc 2): **25 dias**
  - Calibração (doc 3): **15 dias** · Validade **60 dias**
  - Venda+Calib (doc 4): **15 dias**
- **Fornecimento da documentação:** apenas digital (assinada eletronicamente).
  Versão **impressa em pastas personalizadas é OPCIONAL** — cobra-se valor das
  pastas + correio (Sedex). Campo: "Total de N pasta(s) + envio — VALOR OPCIONAL: R$ ___"
- **Condições de Pagamento:** faturado em **7/35 dias** (doc 2) ou **7 dias**
  (doc 3) a contar do início dos trabalhos.
- **Validade da proposta:** **30 dias** (doc 2) / **60 dias** (doc 3).

### Observações importantes (cláusulas)
- Despesas com viagens fora da Grande São Paulo (transporte aéreo/terrestre,
  refeições, hospedagem) por conta do cliente (vide Condições Comerciais).
- O valor sofre alteração caso quantidade de ciclos (cargas) ou equipamentos mude.
- Cancelamento após agendamento: comunicar com **≥ 3 dias** de antecedência, senão
  cobra-se **uma (01) diária técnica**.
- **IMPORTANTE — Diária técnica adicional:** atrasos por causa do cliente, não
  previstos, geram cobrança de diária técnica adicional de **R$ 1.000,00**
  (impostos inclusos) por dia excedente + despesas de viagem se fora da Grande SP.

---

## 7. Dados Cadastrais — LabQuali (institucional fixo)

- **Razão Social:** LabQuali Qualificações Ltda.
- **Nome Fantasia:** LabQuali Qualificação
- **CNPJ:** 52.230.210/0001-70
- **Inscrição Estadual:** 125.705.737.113
- **Inscrição Municipal:** 341232
- **Endereço:** Rua Arujá, 47 — Vila Curuçá — Santo André/SP — CEP 09291-250
- **E-mail comercial:** comercial@labquali.com.br
- **E-mail assinaturas:** assinaturas.relatorios@labquali.com.br

**Dados Bancários:**
- Banco: Itaú · Agência: 666-4 · Conta Corrente: 99108-7
- Chave PIX: 52.230.210/0001-70 (CNPJ)

**Responsáveis:**
| Nome | Cargo | Celular |
|---|---|---|
| Paulo Neves | Responsável Técnico | (11) 99721-0293 |
| Bruno Neves | Gerente Técnico | (11) 94282-6708 |
| Ariel Neves | Administrativo / Financeiro | (11) 99461-3056 |

**Registros Técnicos:**
- Registro da Empresa no CREA-SP: **2535551**
- Responsável Técnico: Paulo Rogério das Neves — Engenheiro Mecânico —
  CREA-SP **0682576030** (Registro Ativo) — Certidão CI 3381050/2024
- Renzo Loris Filippi — Engenheiro Mecânico — CREA-SP **5060361951** /
  CONFEA Nacional 260415235-5
- Credenciado conforme Decisão Normativa DN 29/1988 e DN 45/1992 do CREA-SP/CONFEA
  e Lei nº 6.514 — Ministério do Trabalho (Art. 188).

---

## 8. Responsabilidades do Cliente (doc 2 — cláusulas a–e)

- **a) Indicação de responsáveis:** informar previamente o responsável pelo
  acompanhamento (disponível durante a execução), o responsável pela aprovação/
  assinatura da documentação (com autonomia) e contatos operacionais
  (e-mail/telefone atualizados). Alterações comunicadas previamente.
- **b) Condições dos equipamentos e preparo das cargas:** equipamentos em pleno
  funcionamento, manutenção em dia; disponibilizar cargas, materiais e insumos
  para os ciclos conforme escopo.
- **c) Fornecimento de insumos:** indicadores biológicos e químicos, testes
  específicos, materiais de carga e demais insumos aplicáveis.
- **d) Despesas de viagem:** fora da Grande SP por conta do cliente. Cliente opta
  por (i) comprar/enviar passagens e reservar hospedagem, ou (ii) autorizar a
  LabQuali a fazê-lo (cobrado conforme proposta, com impostos).
- **e) Impactos no cronograma:** ausência/divergência/atraso no fornecimento de
  informações, insumos, cargas ou definições impacta agendamento, execução e
  prazos de liberação/emissão da documentação.

---

## 9. Aceite da Proposta Comercial

"Declaro que li, compreendi e estou de acordo com os termos técnicos e comerciais
descritos nesta proposta comercial, referente à prestação de serviços de [tipo],
conforme o escopo apresentado."

Campos: Assinatura do responsável + data. Confirma concordância com escopo
técnico, prazos de execução, valores, forma de fornecimento da documentação
(digital inclusa, impressa opcional) e condições comerciais. Validade vinculada
ao preenchimento e assinatura. (Doc 3/4 incluem aceite digital via portal/e-mail
`assinaturas.relatorios@labquali.com.br`.)

---

## 10. Gap analysis — docs reais × módulo `afr_qualificacao` (estado 16.0.4.19.0)

| Elemento da proposta real | Estado no módulo | Ação sugerida |
|---|---|---|
| Template QI/QO/QD | ✅ 1 template seed ("LabQuali QI/QO/QD") | Enriquecer conteúdo |
| Template Calibração pura (doc 3) | ❌ ausente | **Criar seed** |
| Template Venda+Calibração (doc 4) | ❌ ausente | **Criar seed** |
| Seções institucionais (objetivo/metodologia/QI/QO/QD/normas/etc.) | ✅ existem, mas **abreviadas/genéricas** com tokens `{{ partner.name }}`/`{{ company.name }}` | Revisar/enriquecer vs texto real |
| Escopo por equipamento (QI/QO 1ª+2ª parte, ciclos sem/com carga) | ✅ `equipment_scope` + `cycle_specs` | Validar alinhamento com layout real |
| Checklist itens QI/QO por equipamento | ⚠️ fatorado em seções (não repetido) | Confirmar com cliente (decisão "adaptar") |
| "Previsão N dias" + Subtotal por fase + Valor Unitário | ✅ cronograma (F8.14) + `financial` | Validar |
| Validadores Yokogawa | ✅ seção `validadores` | OK |
| Dados Cadastrais LabQuali (CNPJ, banco, PIX, sócios) | ❌ **não seedado** (depende de `res.company`) | Decidir: company config vs bloco fixo |
| Registros Técnicos (CREA, engenheiros) | ⚠️ `credenciais` abreviado com token | Enriquecer com dados reais (§7) |
| Responsabilidades cliente a–e | ⚠️ `responsabilidades` resumido (5 bullets) | Expandir vs §8 |
| Condições comerciais (valores exatos R$1.000 diária, R$1.095 viagem, frete) | ⚠️ `condicoes` genérico | Tornar configurável / enriquecer |
| Aceite + assinatura digital portal | ✅ `acceptance` + F9.4 portal | OK |
| Pastas impressas opcionais (VALOR OPCIONAL) | ✅ `optionals` | Validar |
| Condições de Frete (doc 4) | ❌ ausente | Avaliar p/ template Venda+Calib |

### North star (objetivo do cliente)
Deixar a cotação **fácil e rápida para o time de vendas**: vendedor cria SO →
escolhe template (QI/QO/QD · Calibração · Venda+Calib) → escolhe equipamento(s) →
ciclos/preços/escopo auto-preenchidos via `afr.config.template` → PDF/portal 90%
pronto. O lever está em **integrar `proposal.template` (documento) com
`config.template` (pacote de equipamento)**.

---

_Gerado a partir dos `.doc` em 2026-05-30. Atualizar se os modelos do cliente mudarem._
