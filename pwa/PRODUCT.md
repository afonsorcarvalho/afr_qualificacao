# Product

## Register

product

## Users

Técnicos de qualificação em campo, dentro de CME/hospital, sob luz artificial.
Trabalham **de celular, em retrato, com uma mão** — a outra está segurando
instrumento, prancheta ou a porta da autoclave. A conexão é ruim por natureza:
Wi-Fi hospitalar saturado, 4G fraco, casa de máquinas sem sinal.

O trabalho deles é um turno: chegar na OS, abrir o relatório do dia, percorrer
uma lista de coletas (foto da câmara, planilha do datalogger, documento),
anexar evidência item a item e fechar o turno assinando na tela. O que sobra
volta pra próxima sessão. Cada coleta é evidência de um documento regulatório
depois — não é um registro descartável.

Quem consome o resultado não é o técnico: é o gestor que aprova a qualificação
e o cliente que recebe o certificado. O técnico é quem alimenta, no pior
ambiente da cadeia.

## Product Purpose

Substituir o caderno + câmera + planilha por um registro que já nasce ligado à
OS certa, ao equipamento certo e ao turno certo, com data e hora carimbadas
pelo servidor.

Sucesso é o técnico terminar o dia sem retrabalho: nada de foto solta na
galeria pra classificar depois, nada de turno aberto esquecido, nada de item
coletado que ninguém sabe de qual relatório é. O app está bom quando ele some
do caminho — abriu, registrou, assinou, foi embora.

## Brand Personality

**Instrumento de trabalho: direto, sem enfeite.** A referência é um
multímetro ou uma balança de precisão, não um painel. Sóbrio, legível,
previsível. A tela não comemora, informa.

Voz em pt-BR, curta e no imperativo quando pede ação ("Anexe o arquivo antes
de salvar"). Nunca fala em jargão de sistema com quem está de luva.

Ornamento só entra quando carrega informação: uma barra de progresso é
legítima porque mostra quanto falta; um gradiente decorativo não é.

## Anti-references

- **Tela de ERP / backoffice Odoo.** Formulário denso, abas, tabelas largas,
  campo pra tudo. É o oposto do que funciona numa mão só, em pé, em campo.
- **Landing page SaaS genérica.** Grade de cards idênticos (ícone + título +
  texto), muito espaço vazio, hierarquia decorativa em vez de funcional.
- Corolário do que já existe no código: o tema atual é "cyber/neon" (neon
  azul/roxo/rosa, mesh gradient, glass). Isso nasceu como enfeite, não como
  identidade — a direção acordada é reduzir o brilho a favor da leitura, não
  preservá-lo.

## Design Principles

1. **A tela responde "onde eu estou no serviço".** A dor número um é o técnico
   não saber quanto já fez e quanto falta. Todo ecrã de turno responde isso sem
   ele ter que somar nada de cabeça, e deixa claro o que é do turno e o que é
   da OS inteira.
2. **Cada toque precisa se pagar.** Registrar uma coleta é o gesto mais
   repetido do dia. Passo que não muda o resultado (confirmação supérflua,
   volta pra lista pra escolher o próximo item) é passo a eliminar.
3. **Erro é instrução, não código.** Nenhuma mensagem devolve status HTTP ou
   nome de campo pro técnico. Diz o que aconteceu, se o trabalho dele foi
   perdido (na maioria das vezes não foi) e o que fazer agora.
4. **Offline é rotina, não exceção.** Sinal cai no meio do turno o tempo todo.
   O app assume isso: nunca descarta o que o técnico já preencheu, e sempre diz
   se o registro chegou no servidor ou não.
5. **Uma mão, retrato, luva.** Coluna única, alvo de toque grande, pouca
   digitação. Se algo só funciona em tablet deitado, não funciona.
6. **O servidor é o relógio e a verdade.** Data, hora e janela do dia vêm do
   Odoo, nunca do aparelho — celular com relógio torto já produziu dado no
   futuro aqui. A tela nunca inventa número que o backend pode calcular.

## Accessibility & Inclusion

- **Alvos de toque ≥ 44px** em qualquer coisa clicável — requisito explícito,
  o técnico usa de luva.
- Contraste mínimo WCAG AA (4.5:1 em texto normal, 3:1 em texto grande) como
  piso da casa, incluindo placeholder. Cinza-claro decorativo não passa.
- Estado nunca comunicado só por cor: coletado/pendente/erro sempre com texto
  ou ícone junto do verde/âmbar.
- `prefers-reduced-motion` respeitado em toda animação.
