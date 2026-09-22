#!/usr/bin/env bash
#
# Garante que todas as rotas do PWA Técnico estão no vhost do Apache.
#
# POR QUE ESTE SCRIPT EXISTE
#
# O Apache casa `ProxyPass` na ORDEM em que as diretivas aparecem, e o
# `ProxyPass /` do Odoo, no fim do vhost, pega tudo o que sobrou. Uma rota do
# PWA sem regra própria ANTES dele não chega ao container: cai no Odoo, que
# devolve a página 404 do site.
#
# O sintoma é traiçoeiro porque a rota funciona perfeitamente em
# `127.0.0.1:3010` e só falha pelo domínio. Foi exatamente o que aconteceu com
# `/api/chat` no deploy do chat de agendamento em 2026-09-22: container no ar,
# chave configurada, `{"enabled":true}` no loopback, e 404 do Odoo pelo HTTPS.
#
# Toda rota nova do PWA precisa entrar aqui E no vhost. Esta lista é a fonte
# da verdade; o script compara com o vhost e insere o que faltar.
#
# COMO USAR (no servidor, com sudo)
#
#   sudo ./sync-rotas-apache.sh            # DRY-RUN: mostra o que falta e sai
#   sudo ./sync-rotas-apache.sh --apply    # aplica, testa a config e recarrega
#
# É idempotente: rodar de novo quando não falta nada não escreve nada.
#
# SEGURANÇA DA OPERAÇÃO
#   - Faz backup do vhost antes de escrever.
#   - Roda `apache2ctl configtest` ANTES de recarregar; se reprovar, restaura o
#     backup e aborta sem recarregar.
#   - Usa `reload`, não `restart`: este Apache serve vários inquilinos e um
#     restart derruba as conexões de todos eles.
#
set -euo pipefail

CONF="${CONF:-/etc/apache2/sites-enabled/012-labquali-le-ssl.conf}"
UPSTREAM="${UPSTREAM:-http://127.0.0.1:3010}"
HOST="${HOST:-labquali.afrsistemas.com.br}"
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

# Âncora: as regras do PWA precisam entrar ANTES do `ProxyPass /` do Odoo.
# O vhost já traz este comentário como fim do bloco; se alguém o apagar, o
# fallback abaixo procura o próprio `ProxyPass /`.
ANCORA_PRIMARIA='# ─── fim PWA ───'

# Rotas do PWA. `both` = ProxyPass + ProxyPassReverse (a resposta pode trazer
# redirect/Location que precisa ser reescrito). `oneway` = só ProxyPass, para
# arquivo estático que nunca redireciona.
ROTAS=(
  "/tecnico            both"
  "/login              both"
  "/_next              both"
  "/api/odoo           both"
  "/api/groq           both"
  "/api/chat           both"
  "/icons              both"
  "/manifest.json      oneway"
  "/pdf.worker.min.mjs oneway"
  "/sw.js              oneway"
)

die()  { printf '\n[ERRO] %s\n' "$*" >&2; exit 1; }
info() { printf '[..] %s\n' "$*"; }
ok()   { printf '[ok] %s\n' "$*"; }
warn() { printf '[!!] %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || die "rode com sudo: sudo $0 ${1:-}"
[ -f "$CONF" ] || die "vhost não encontrado: $CONF (defina CONF=... se for outro)"
command -v apache2ctl >/dev/null || die "apache2ctl não encontrado — este host usa Apache?"

# ── 1. O que falta ────────────────────────────────────────────────────────
FALTANDO=()
for entrada in "${ROTAS[@]}"; do
  rota="${entrada%% *}"
  # Procura o destino completo, não só a rota: assim uma linha comentada ou
  # apontando para outro upstream não conta como presente.
  if ! grep -qF "${UPSTREAM}${rota}" "$CONF"; then
    FALTANDO+=("$entrada")
  fi
done

if [ ${#FALTANDO[@]} -eq 0 ]; then
  ok "Todas as ${#ROTAS[@]} rotas do PWA já estão no vhost. Nada a fazer."
  exit 0
fi

# ── 2. Monta o bloco a inserir ────────────────────────────────────────────
BLOCO=""
for entrada in "${FALTANDO[@]}"; do
  rota="${entrada%% *}"
  modo="${entrada##* }"
  BLOCO+=$(printf '    ProxyPass        %-19s %s%s\n' "$rota" "$UPSTREAM" "$rota")
  BLOCO+=$'\n'
  if [ "$modo" = "both" ]; then
    BLOCO+=$(printf '    ProxyPassReverse %-19s %s%s\n' "$rota" "$UPSTREAM" "$rota")
    BLOCO+=$'\n'
  fi
done

printf '\nFaltam %d rota(s) em %s:\n\n' "${#FALTANDO[@]}" "$CONF"
printf '%s' "$BLOCO"

# ── 3. Onde inserir ───────────────────────────────────────────────────────
if grep -qF "$ANCORA_PRIMARIA" "$CONF"; then
  LINHA=$(grep -nF "$ANCORA_PRIMARIA" "$CONF" | head -1 | cut -d: -f1)
  info "Inserção antes da linha $LINHA (marcador de fim do bloco PWA)."
elif grep -nE '^[[:space:]]*ProxyPass[[:space:]]+/[[:space:]]' "$CONF" >/dev/null; then
  LINHA=$(grep -nE '^[[:space:]]*ProxyPass[[:space:]]+/[[:space:]]' "$CONF" | head -1 | cut -d: -f1)
  warn "Marcador '$ANCORA_PRIMARIA' não encontrado; usando o 'ProxyPass /' do Odoo (linha $LINHA)."
else
  die "não achei nem o marcador do bloco PWA nem o 'ProxyPass /' do Odoo em $CONF.
     O vhost não tem o formato esperado — insira as linhas acima à mão, ANTES
     da diretiva que encaminha '/' para o Odoo."
fi

if [ "$APPLY" -eq 0 ]; then
  printf '\nDRY-RUN: nada foi escrito. Para aplicar:\n\n    sudo %s --apply\n\n' "$0"
  exit 0
fi

# ── 4. Aplica ─────────────────────────────────────────────────────────────
BAK="${CONF}.bak-$(date +%Y%m%d_%H%M%S)"
cp -a "$CONF" "$BAK"
ok "Backup: $BAK"

TMP=$(mktemp)
# `head -n $((LINHA-1))` + bloco + resto: insere imediatamente ANTES da âncora,
# preservando o arquivo byte a byte fora do ponto de inserção.
head -n "$((LINHA - 1))" "$CONF"  >  "$TMP"
printf '%s' "$BLOCO"              >> "$TMP"
tail -n "+${LINHA}" "$CONF"       >> "$TMP"
cat "$TMP" > "$CONF"      # `cat >` e não `mv`: preserva dono, modo e inode
rm -f "$TMP"
ok "Rotas inseridas."

if ! apache2ctl configtest; then
  warn "configtest REPROVOU — restaurando o backup e abortando SEM recarregar."
  cp -a "$BAK" "$CONF"
  die "vhost restaurado de $BAK. Nada foi recarregado; o site segue como estava."
fi
ok "configtest aprovado."

systemctl reload apache2
ok "Apache recarregado (reload, sem derrubar os outros inquilinos)."

# ── 5. Confere de fora ────────────────────────────────────────────────────
sleep 2
printf '\nVerificando pelo domínio (https://%s):\n\n' "$HOST"
FALHOU=0
for entrada in "${ROTAS[@]}"; do
  rota="${entrada%% *}"
  alvo="$rota"
  [ "$rota" = "/api/chat" ] && alvo="/api/chat/status"   # /api/chat só aceita POST
  corpo=$(curl -s --max-time 20 "https://${HOST}${alvo}" | head -c 400 || true)
  codigo=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://${HOST}${alvo}" || true)
  # O sintoma da rota faltando é a página 404 do site Odoo, não um erro do PWA.
  if printf '%s' "$corpo" | grep -qi 'Page Not Found\|data-website-id'; then
    printf '  %-22s %s  <<< caindo no Odoo, rota NÃO publicada\n' "$alvo" "$codigo"
    FALHOU=1
  else
    printf '  %-22s %s  ok\n' "$alvo" "$codigo"
  fi
done

printf '\n'
if [ "$FALHOU" -eq 1 ]; then
  die "alguma rota ainda cai no Odoo. Backup em $BAK se precisar voltar."
fi
ok "Todas as rotas do PWA respondem pelo domínio."
printf '\nChat de agendamento: https://%s/api/chat/status deve dizer {"enabled":true}\n' "$HOST"
