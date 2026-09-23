# Validação empírica do modelo — chat de agendamento

Gerado por `scripts/validacao-chat/run.live.ts` em 2026-09-22T03:18:34.779Z.

`server_today` **injetado**: `2026-09-14` (segunda-feira, deliberadamente diferente do hoje real da máquina — é assim que "derivou do servidor" se distingue de "deduziu do relógio").

Janela na tela: 2026-09-14 a 2026-09-20.

> **Leia junto com `TODO.md`.** Este arquivo é evidência crua, gerada: cada
> linha é o que aconteceu naquela execução, não a conclusão. Toda fixture de
> data é pontuada contra o `SERVER_TODAY` que ELA espera: as da lista padrão
> contra `2026-09-14`, e a `F04b` contra `2026-09-21`. Rodar uma delas na
> data da outra reprova por construção — é assim de propósito, para que o
> placar nunca dê ✅ a uma execução que ninguém conferiu. A leitura dos
> resultados mora no `TODO.md`.

## Placar

| Fixture | Grupo | Ferramenta | Data | Encadeamento | Resultado | Wall-clock | Modelo |
|---|---|---|---|---|---|---|---|
| F01 | nucleo | ✅ | ✅ | — | text | 5.4s | google/gemma-4-31b-it |
| F02 | nucleo | ❌ | — | — | text | 1.7s | google/gemma-4-31b-it |
| F03 | nucleo | ✅ | — | — | text | 5.4s | google/gemma-4-31b-it |
| F04 | semana-relativa | ✅ | ✅ | — | text | 4.6s | google/gemma-4-31b-it |
| F05 | nucleo | ✅ | ✅ | ✅ | proposal | 6.8s | google/gemma-4-31b-it |
| F06 | nucleo | ✅ | — | — | text | 2.8s | google/gemma-4-31b-it |
| F07 | nucleo | ❌ | ❌ | — | text | 2.9s | google/gemma-4-31b-it |
| F08 | nucleo | ✅ | — | — | text | 4.0s | google/gemma-4-31b-it |
| F09 | nucleo | ✅ | — | — | text | 2.3s | google/gemma-4-31b-it |
| F10 | semana-relativa | ✅ | ✅ | — | text | 2.4s | google/gemma-4-31b-it |

## Detalhe por fixture

### F01 — "me mostra a agenda de amanhã"

*O caso mais simples de data absoluta: "amanhã" só vira 15/09 se o modelo partiu do server_today injetado.*

- grupo: `nucleo` · desfecho: `text` · 5.4s · 2 volta(s) · modelo: google/gemma-4-31b-it
- ✅ **ferramenta** — esperada buscar_agenda, veio buscar_agenda
- ✅ **data derivada do server_today** — vistas [2026-09-15]
- · **id alucinado barrado** — nenhuma trava disparou

Argumentos crus, exatamente como o modelo mandou:

```
buscar_agenda {"date_from":"2026-09-15","date_to":"2026-09-15"}
```

> A agenda de amanhã (15/09) tem a seguinte visita: - OS26-08-0005-2 · ter, 15/09/2026 · Paulo Neves 08:00–12:00

### F02 — "quais técnicos a gente tem?"

*Ferramenta de consulta pura, sem data nem id. Se falhar aqui, o parser de tool call da stack de serving é o problema, não o prompt.*

- grupo: `nucleo` · desfecho: `text` · 1.7s · 1 volta(s) · modelo: google/gemma-4-31b-it
- ❌ **ferramenta** — esperada listar_tecnicos, veio (nenhuma)
- · **id alucinado barrado** — nenhuma trava disparou

> Temos os seguintes técnicos: - Afonso Carvalho (id 441) - Ariel Neves (id 3) - Bruno Neves (id 4) - Paulo Neves (id 2)

### F03 — "lista pra mim as OS que dá pra agendar"

*Escolha entre duas ferramentas de listagem parecidas (OS x técnicos).*

- grupo: `nucleo` · desfecho: `text` · 5.4s · 2 volta(s) · modelo: google/gemma-4-31b-it
- ✅ **ferramenta** — esperada listar_os, veio listar_os
- · **id alucinado barrado** — nenhuma trava disparou

Argumentos crus, exatamente como o modelo mandou:

```
listar_os {}
```

> As OSs disponíveis para agendamento são: - **QOS00014**: A F R DE CARVALHO LTDA (São Luís) - **QOS00013**: BRITO & SOARES LTDA (Maracanaú) - **QOS00012**: FUNDAÇÃO PARA O DESENVOLVIMENTO MÉDICO E HOSPITALAR (Bauru) - **QOS00011**: BRAILE BIOMÉDICA (São José do Rio Preto) - **QOS00010**: OXIMED (São José do Rio Preto) - **QOS00009**: PLASTIC DAY HOSPITAL LTDA (Santos) - **QOS00008**: HOSPITAL ALBER

### F04 — "como tá a agenda da semana que vem?"

*O defeito já conhecido do item 1 do TODO: o modelo tende a segunda-a-domingo errado (dom–sáb). Falha aqui é RE-OBSERVAÇÃO, não achado novo.*

- grupo: `semana-relativa` · desfecho: `text` · 4.6s · 2 volta(s) · modelo: google/gemma-4-31b-it
- ✅ **ferramenta** — esperada buscar_agenda, veio buscar_agenda
- ✅ **data derivada do server_today** — vistas [2026-09-21, 2026-09-27]
- · **id alucinado barrado** — nenhuma trava disparou

Argumentos crus, exatamente como o modelo mandou:

```
buscar_agenda {"date_from":"2026-09-21","date_to":"2026-09-27"}
```

> A agenda para a semana que vem (21/09 a 27/09) tem as seguintes visitas: - **OS26-06-0002**: ter, 22/09, Afonso Carvalho (09:00–11:00) - **OS26-08-0005-2**: qua, 23/09, Bruno Neves (08:00–12:00) - **OS26-08-0005-2**: qui, 24/09, Bruno Neves (08:00–12:00) - **QOS00004**: qui, 24/09, Paulo Neves (13:00–17:00) - **OS26-08-0005-2**: qui, 24/09, Bruno Neves (13:00–17:00) - **OS26-08-0005-2**: sex, 25/0

### F05 — "agenda a QOS00011 pro Bruno na quarta-feira"

*Caminho completo de escrita: consultar OS e técnico, pegar equipamento/instrumento do resultado, e só então propor. Nenhum id pode ser inventado.*

- grupo: `nucleo` · desfecho: `proposal` · 6.8s · 3 volta(s) · modelo: google/gemma-4-31b-it
- ✅ **ferramenta** — esperada listar_os, veio listar_os
- ✅ **data derivada do server_today** — vistas [2026-09-16]
- · **id alucinado barrado** — nenhuma trava disparou
- ✅ **segunda chamada consome a primeira** — 4 chamada(s): listar_os → listar_tecnicos → listar_instrumentos → criar_visita
- ✅ **terminou em proposta de escrita** — kind=proposal

Argumentos crus, exatamente como o modelo mandou:

```
listar_os {}
listar_tecnicos {}
listar_instrumentos {}
criar_visita {"date":"2026-09-16","equipment_ids":[4823],"instrument_ids":[1],"os_id":9121,"tecnico_id":4}
```

> Criar visita para a OS 9121 em 2026-09-16, técnico 4, equipamentos [4823], instrumentos [1].

### F06 — "quantas horas a QOS00013 precisa? cabe num dia só?"

*Usa horas_previstas/jornada_horas_dia do resultado da ferramenta — o campo novo do pwa_os_options — para responder em texto.*

- grupo: `nucleo` · desfecho: `text` · 2.8s · 2 volta(s) · modelo: google/gemma-4-31b-it
- ✅ **ferramenta** — esperada listar_os, veio listar_os
- · **id alucinado barrado** — nenhuma trava disparou

Argumentos crus, exatamente como o modelo mandou:

```
listar_os {}
```

> A QOS00013 precisa de 12 horas. Não cabe em um dia só, pois a jornada diária é de 8 horas (previstos 2 dias).

### F07 — "tem alguma visita do Paulo essa semana?"

*Filtro por pessoa sobre resultado de ferramenta, e a regra de citar visita por OS+data na prosa (nunca pelo id interno).*

- grupo: `nucleo` · desfecho: `text` · 2.9s · 1 volta(s) · modelo: google/gemma-4-31b-it
- ❌ **ferramenta** — esperada buscar_agenda, veio (nenhuma)
- ❌ **data derivada do server_today** — vistas [] | faltando [2026-09-14, 2026-09-20]
- · **id alucinado barrado** — nenhuma trava disparou

> Sim, o Paulo Neves tem duas visitas esta semana: - OS26-08-0005-2 em 2026-09-15 (08:00–12:00) - QOS00004 em 2026-09-16 (13:00–17:00)

### F08 — "remarca a visita do hospital pra sexta"

*AMBIGUIDADE: há várias visitas do UITest Hospital. O modelo deve perguntar qual, e nunca escolher sozinho nem gravar.*

- grupo: `nucleo` · desfecho: `text` · 4.0s · 2 volta(s) · modelo: google/gemma-4-31b-it
- ✅ **ferramenta** — esperada buscar_agenda, veio buscar_agenda
- · **id alucinado barrado** — nenhuma trava disparou
- ✅ **perguntou em vez de escrever** — kind=text

Argumentos crus, exatamente como o modelo mandou:

```
buscar_agenda {"date_from":"2026-09-14","date_to":"2026-09-20"}
```

> Existem várias visitas para o UITest Hospital. Qual delas você deseja remarcar para sexta-feira (18/09)? - OS26-08-0005-2 · ter, 15/09 · Paulo Neves 08:00–12:00 - OS26-08-0005-2 · qua, 16/09 · Bruno Neves 08:00–12:00 - OS26-08-0005-1 · qua, 16/09 · Ariel Neves 08:00–12:00 - OS26-08-0005-2 · sex, 18/09 · Bruno Neves 09:00–13:00 (já está na sexta)

### F09 — "cancela a visita 999"

*Trava de id: 999 nunca apareceu em resultado nenhum. O esperado é o modelo consultar ou avisar — jamais uma escrita com id inventado passando.*

- grupo: `nucleo` · desfecho: `text` · 2.3s · 1 volta(s) · modelo: google/gemma-4-31b-it
- ✅ **ferramenta** — esperada (nenhuma), veio (nenhuma)
- · **id alucinado barrado** — nenhuma trava disparou

> Não encontrei nenhuma visita com o id 999 nas informações disponíveis. Por favor, informe a OS e a data da visita que deseja cancelar.

### F10 — "na segunda que vem quem tá disponível?"

*Dia nomeado dentro da semana seguinte — separa "erra a semana inteira" (F04) de "erra só a borda".*

- grupo: `semana-relativa` · desfecho: `text` · 2.4s · 2 volta(s) · modelo: google/gemma-4-31b-it
- ✅ **ferramenta** — esperada buscar_agenda, veio buscar_agenda
- ✅ **data derivada do server_today** — vistas [2026-09-21]
- · **id alucinado barrado** — nenhuma trava disparou

Argumentos crus, exatamente como o modelo mandou:

```
buscar_agenda {"date_from":"2026-09-21","date_to":"2026-09-21"}
```

> Todos os técnicos estão disponíveis na segunda-feira (21/09), pois não há visitas agendadas.

## Custo e latência do run

- 10 fixtures, 18 chamadas ao modelo
- wall-clock: mediana 3.4s, pior 6.8s
- tokens: 51963 prompt + 1360 completion
- custo reportado pelo OpenRouter: US$ 0.0057
