# Plano — Cor configurável por técnico e por instrumento

Data: 2026-09-20
Repos envolvidos (atenção, são DOIS):
- `addons/afr_qualificacao` — **submodule** (git próprio). PWA + modelo dos instrumentos.
- `addons/afr_qualificacao_agendamento` — **parte do monorepo** `engenapp`. Visitas, RPCs da agenda, formulário do empregado.

Branch: criar `feat/cor-por-recurso` em cada repo.

## Contexto

Na agenda do PWA, cada técnico vira uma bolinha e cada instrumento um triângulo.
A cor sai hoje de `corDoTecnico(id)` / `corDoInstrumento(id)`
(`pwa/app/tecnico/qualificacao/agenda/mes.ts`): `PALETA[id % 12]`, uma paleta de
12 tons **medidos** contra quatro fundos (card claro/escuro e o fundo sólido do
dia selecionado, nos dois temas) — há guarda de contraste em `mes.test.ts`.

O usuário quer **escolher** a cor de cada técnico e de cada instrumento no Odoo,
e que a agenda respeite essa escolha.

## Decisões tomadas com o usuário (não reabrir)

- A escolha é numa **paleta fixa**: o seletor de cores nativo do Odoo (índice
  inteiro), mapeado para os 12 tons já validados. Nada de cor livre em hex —
  perderia a garantia de legibilidade.
- **Não** repintar as amostras do seletor do Odoo. A cor na agenda é a da nossa
  paleta; o quadradinho do Odoo fica parecido, não idêntico.
- Índice **0** ("sem cor" no Odoo) = comportamento atual, cor derivada do id.
  Quem não configurar nada não vê diferença.
- Consequência aceita: o seletor do Odoo oferece 11 posições de cor, e a paleta
  tem 12 tons — um dos tons não é alcançável pela configuração manual.

## Global Constraints

1. **Nunca ler o relógio do aparelho** no front: `Date.UTC`/ISO/`Intl` com
   `timeZone:'UTC'`.
2. **Sem dependência nova** em nenhum dos dois repos.
3. **A11y:** cor nunca é o único portador — os nomes continuam em texto nos
   rótulos e chips. A guarda de contraste da `PALETA` continua valendo e **não
   pode ser afrouxada**.
4. **UI e comentários em pt-BR**, explicando o PORQUÊ.
5. **TDD** nos dois lados.
6. Backend: rodar a suíte do módulo no container local (NUNCA `odoo-bin`; o
   entrypoint é custom):
   `docker exec odoo_engenapp-web-qualificacao-1 /entrypoint.sh odoo -d qualificacao-dev -u <modulo> --test-enable --test-tags /<modulo> --stop-after-init --no-http`
7. Front: `npm run test` e `npx tsc --noEmit` a partir de `pwa/`. Baseline
   **518 testes verdes**.
8. Dev server Next em `:3010` em uso: não derrubar, não subir outro, não rodar
   `npm run build`, **não usar `git stash`/`git checkout`** para provar vermelho.
9. Bump de versão nos `__manifest__.py` dos dois módulos tocados.

## Task 1 — Backend: o campo e as RPCs

### 1a. Técnico (`afr_qualificacao_agendamento`, monorepo)

- `hr.employee` **já tem** o campo `color` (inteiro, core do Odoo). Não criar
  campo novo: expor o existente no formulário do empregado, junto da marcação
  "Técnico de Qualificação" que o módulo já adiciona
  (`views/hr_employee_views.xml`), com o widget de seleção de cor nativo.
- `pwa_tecnico_options` (`models/os_visita.py`) passa a devolver o índice junto
  de `id` e `name`. Nome do campo no payload: `color`.
- `hr.employee.public`: conferir se o índice precisa ser espelhado para o
  Gestor sem permissão de RH, como `is_tecnico` já é
  (`models/hr_employee_public.py`) — a RPC roda em `sudo()`, então
  provavelmente não; **verifique e registre no relatório** em vez de assumir.

### 1b. Instrumento (`afr_qualificacao`, submodule)

- `engc.calibration.instruments` (`models/calibration_instruments.py`) ganha um
  `color` inteiro, mesmo papel, exposto no formulário e na lista.
- `pwa_instrumento_options` — **mora no outro módulo**
  (`afr_qualificacao_agendamento/models/os_visita.py`) e lê este modelo. Passa a
  devolver `color` junto de `id`, `name` e `validade`.

### Testes

Nos dois módulos, no estilo das suítes que já existem:
- `pwa_tecnico_options` devolve `color` de um técnico configurado e `0` de um
  não configurado.
- `pwa_instrumento_options` idem.
- O campo do instrumento existe, aceita o índice e nasce em 0.
- Nada quebra para usuário sem permissão de RH (há teste desse tipo em
  `test_pwa_agenda.py`).

## Task 2 — Front: a cor configurada vence a automática

Em `addons/afr_qualificacao/pwa`:

- Os tipos `Opcao` e `InstrumentoOpcao` (`lib/odoo/agenda.ts`) ganham `color`.
- `mes.ts`: `corDoTecnico` e `corDoInstrumento` passam a aceitar o índice
  configurado e devolver o tom correspondente da `PALETA`; índice ausente, 0 ou
  fora da faixa cai na cor derivada do id (comportamento atual). Mantenha as
  funções puras e testáveis, e **não mude a `PALETA` nem a guarda de contraste**.
- Propagação: `rosterTecnicos` (`carga.ts`) preserva o `color` das opções ao
  unir com os técnicos vindos das visitas; `tecnicosPorDia` e
  `instrumentosPorDia` (`mes.ts`) usam a cor configurada quando houver. Isso
  cobre de uma vez as bolinhas, os triângulos, os chips das duas faixas de
  legenda e a seção "Instrumentos do dia", que já leem dessas fontes.
- O painel de recursos do modo Semana: verificar se usa cor e, se usar, seguir a
  mesma regra.

### Testes

- Técnico com índice configurado desenha no tom correspondente da paleta.
- Índice 0 / ausente mantém exatamente a cor de hoje (teste de não-regressão
  comparando com `corDoTecnico` sem configuração).
- Índice fora da faixa não quebra e cai na cor automática.
- Instrumento idem.
- Dois técnicos com o MESMO índice configurado ficam com a mesma cor — é o que
  a configuração manual permite; o teste existe para fixar que isso é esperado,
  não defeito.
- A guarda de contraste da `PALETA` continua verde, sem alteração.

## Task 3 — Validação no navegador (o controlador faz, não subagente)

Configurar cor para um técnico e um instrumento no Odoo de dev, recarregar o
PWA em `:3010` e conferir bolinha, triângulo, chips das duas faixas e a lista do
dia, nos temas claro e escuro.
