# Checklist de aceitação — tema claro + correções (2026-09-07)

Branch `feat/tema-claro-contraste`, ainda **não pushado**. 33 commits, 245 testes verdes.

**Ambiente:** app em http://localhost:3010 · Odoo `http://localhost:8084` · banco
`qualificacao-dev` · conta `tecnico.a@teste.local` / `Teste@2026`.

**Trocar de tema:** Perfil → Aparência → "Trocar". O app nasce no escuro.

Ordem pensada por risco: o bloco A é onde estava o pior defeito, o D é o que não
podia ter mudado.

> **Executado pelo user em 2026-09-07: blocos A a E todos OK.** O bloco F
> (celular / app instalado) não foi executado — fica pendente da próxima vez que
> houver aparelho à mão. Com isso o branch `feat/tema-claro-contraste` foi
> integrado ao `main`.

---

## A. Login no tema claro — era a tela quebrada

Antes: rótulos, valor digitado e nome do banco eram branco sobre branco. Você via
um formulário sem legenda nenhuma.

> Para chegar no login no claro: entre, vá em Perfil, troque para claro, saia.

- [ ] **A.1** Passo 1 mostra o rótulo do campo de servidor, o placeholder e o texto de apoio abaixo
- [ ] **A.2** Passo 2 mostra os rótulos "Banco de dados", "Usuário" e "Senha"
- [ ] **A.3** O nome do banco aparece dentro do seletor (não um campo vazio)
- [ ] **A.4** O que você digita no campo de usuário **aparece enquanto digita**
- [ ] **A.5** No indicador de passo, dá pra distinguir o passo concluído do passo futuro
- [ ] **A.6** Errar a senha de propósito → a mensagem de erro é legível
- [ ] **A.7** Passar o mouse no olho de mostrar/ocultar senha → ele muda de cor (tinha morrido)

## B. Deep link e segurança

- [ ] **B.1** Deslogado, abrir direto `http://localhost:3010/tecnico/qualificacao/4/coleta/213` → cai no login → depois de autenticar, abre **a coleta 213**, não a lista
- [ ] **B.2** Abrir `http://localhost:3010/login?next=.//interno.invalid` → autenticar → tem que cair em `/tecnico/qualificacao` e a barra de endereço **continuar em localhost:3010** (este é o open redirect que falhou 3 vezes)
- [ ] **B.3** Depois de entrar, o botão voltar do navegador **não** devolve ao formulário de login

## C. Telas no tema claro

- [ ] **C.1** **Histórico** — os três contadores (Coletas / OSs / Rel. fechados) são a coisa mais legível da tela. Antes eram a menos
- [ ] **C.2** **Histórico** — o cabeçalho "HOJE" não tem mais gradiente colorido
- [ ] **C.3** **Perfil** — o rótulo "TÉCNICO" está legível; o cabeçalho perdeu o gradiente roxo/ciano; os ícones dos campos são todos cinza (antes eram 5 cores diferentes)
- [ ] **C.4** **OS 26-06-0002** (`/tecnico/qualificacao/4`) — os links "Ver foto" e "Baixar" estão legíveis
- [ ] **C.5** **OS 4** — o chip "Ciclo: ..." e o aviso "Sem qualificador/padrão cadastrado" estão legíveis
- [ ] **C.6** **OS 4** — no cabeçalho do grupo de equipamento, o **nome do equipamento** tem mais peso visual que o metadado abaixo (marca/série/contador). Eles chegaram a ficar iguais
- [ ] **C.7** Filtro Pendentes/Realizadas troca o recorte; clicar no cabeçalho do grupo recolhe/expande
- [ ] **C.8** "Ver foto" abre o visualizador de imagem e dá pra ler o botão de fechar
- [ ] **C.9** Abrir uma planilha/PDF → o painel é **escuro de propósito** nos dois temas; o nome do arquivo e os controles estão legíveis
- [ ] **C.10** Num campo de data, o seletor do navegador abre **claro** (era fixo escuro)

## D. Tema escuro — o que NÃO podia mudar

Ele está em produção. Percorra as mesmas telas no escuro.

- [ ] **D.1** Nada parece diferente do que você lembra, **exceto** estas três, que foram autorizadas:
  - verdes e cianos um pouco mais saturados (convergiram para a paleta do DESIGN.md)
  - o fundo do cabeçalho de grupo de equipamento um pouco mais claro
  - o cronômetro de gravação de voz um pouco mais claro
- [ ] **D.2** Se achar qualquer outra diferença no escuro, **é achado** — me diga qual tela

## E. Fluxo real de trabalho

- [ ] **E.1** Iniciar relatório do dia numa OS
- [ ] **E.2** Coletar um item com foto e salvar
- [ ] **E.3** Recoletar um item já feito
- [ ] **E.4** Fechar o turno com assinatura → **esperado falhar** com
      `Invalid field 'request_service_scope' on model 'hr.employee.public'`.
      É bug do módulo `engc_os`, anterior a este trabalho, e não é regressão.
      Se falhar com **outra** mensagem, aí é achado

## F. Celular (se der)

- [ ] **F.1** Abrir no celular, no tema claro, e conferir A.1–A.4 e C.1
- [ ] **F.2** O app instalado continua abrindo e navegando

---

## O que eu **não** consegui verificar

Não teste às cegas por mim — só saiba que ficaram sem prova visual:

- Painel de revisão por IA com veredito renderizado em uso real (a `GROQ_API_KEY` está vazada e desligada; renderizei com dado sintético)
- Estado "selecionado" do seletor de Empresa ativa (a conta de teste só tem uma empresa)
- Prévia de coletas com itens pendentes e sem relatório aberto, e a linha "ignorada" do painel de revisão (o banco não tem OS nesse estado)
