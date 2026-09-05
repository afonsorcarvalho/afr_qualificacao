# PWA Técnico de campo — `afr_qualificacao`

App Next.js que o técnico usa em tablet/celular para executar coletas de
qualificação: inicia o relatório do dia, anexa fotos/arquivos por item,
assina e fecha o relatório.

Vive dentro do addon de propósito: backend e front compartilham commit, e o
contrato RPC (`action_start_daily_relatorio`, `action_done`,
`afr.qualificacao.collect.item`) não pode dessincronizar.

## Rodar em desenvolvimento

```bash
npm ci
cp .env.example .env.local     # preencher GROQ_API_KEY
npm run dev                    # http://localhost:3010
```

A URL do Odoo não é variável de ambiente: é digitada na tela de login e
guardada em cookie + localStorage. Em desenvolvimento, apontar para
`http://localhost:8084` (container `odoo_engenapp-web-qualificacao-1`).

## Testes

```bash
npm test            # vitest run
npx tsc --noEmit    # type check
npm run build       # build standalone de produção
```

Baseline em `docs/BASELINE.md`. Aceitação end-to-end:
`app/tecnico/qualificacao/F7_0_TEST_CHECKLIST.md`.

## Produção

```bash
export ODOO_ALLOWED_ORIGINS=https://labquali.afrsistemas.com.br
docker compose up -d --build   # publica em :3010
```

`ODOO_ALLOWED_ORIGINS` é **obrigatória** e o compose recusa subir sem ela.
É a allowlist de origens que o proxy `/api/odoo` pode alcançar (formato
`esquema://host[:porta]`, separado por vírgula). Sem ela o proxy falha
fechado — 403 em tudo, app sem Odoo. Não existe default em produção de
propósito: encaminhar para endereço arbitrário transformaria o servidor
Next em open proxy, alcançando hosts internos que o navegador do atacante
não alcança. Em `NODE_ENV=development` loopback e rede privada entram sem
configuração; só ali.

O container fala HTTP puro na 3010. Ele **precisa** de um proxy reverso com
TLS na frente: service worker só registra em contexto seguro, então sem
HTTPS não há instalação no aparelho nem uso offline — e uma página HTTPS
não pode chamar uma API HTTP (conteúdo misto). Ver
`deploy/setup-pwa-proxy.sh`.

Sem `GROQ_API_KEY` exportada no ambiente do host, o `docker-compose.yml`
sobe o container com a variável vazia: as features de IA (auto-resumo,
ditado, revisão pré-fechamento) ficam desligadas (`/api/groq/status` →
`enabled:false`) e o resto do app funciona normal.

## Versionamento

Este PWA **não** bumpa `__manifest__.py` do addon. A versão do front está no
`package.json`; o manifesto Odoo bumpa só em mudança de Python/XML/segurança.

## Origem

Migrado de `frontend_odoo@4cd26dd` (branch `tecnico-qualif-pwa`, 42 commits)
em 2026-09-02. O histórico anterior continua em
`origin/tecnico-qualif-pwa` naquele repositório.
