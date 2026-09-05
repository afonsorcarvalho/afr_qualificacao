#!/usr/bin/env bash
#
# Publica o PWA Técnico atrás de HTTPS no servidor do labquali.
#
# POR QUE: o container fala HTTP puro na 3010. Service worker só registra em
# contexto seguro, então sem TLS não há instalação no aparelho nem uso
# offline — e uma página HTTPS não pode chamar uma API HTTP (conteúdo misto).
#
# COMO USAR (no servidor, com sudo):
#
#   sudo PWA_HOST=pwa.afrsistemas.com.br ./setup-pwa-proxy.sh          # dry-run
#   sudo PWA_HOST=pwa.afrsistemas.com.br ./setup-pwa-proxy.sh --apply  # aplica
#
# O padrão é DRY-RUN: detecta o que já existe, imprime exatamente o que
# escreveria e sai sem tocar em nada. Só `--apply` escreve. Este script foi
# escrito sem acesso ao servidor (a chave SSH desta máquina é recusada lá),
# então a detecção existe justamente pra ele não chutar a pilha errada: se
# não reconhecer, ele para e diz o que viu.
#
# PRÉ-REQUISITOS
#   1. DNS de $PWA_HOST apontando para este servidor (A/AAAA), já propagado —
#      o Let's Encrypt valida por HTTP-01 e falha sem isso.
#   2. O container do PWA rodando e ouvindo em $PWA_UPSTREAM.
#   3. Portas 80 e 443 alcançáveis de fora.
#
set -euo pipefail

PWA_HOST="${PWA_HOST:-}"
PWA_UPSTREAM="${PWA_UPSTREAM:-127.0.0.1:3010}"
CERT_EMAIL="${CERT_EMAIL:-}"
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

# Foto de celular passa fácil de 1MB, e o proxy `/api/odoo` a repassa em
# base64 (+33%). O default de 1MB do nginx devolveria 413 no meio da coleta,
# em campo, depois do técnico já ter tirado a foto.
MAX_BODY="25m"

die()  { printf '\n[ERRO] %s\n' "$*" >&2; exit 1; }
info() { printf '[..] %s\n' "$*"; }
ok()   { printf '[ok] %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || die "rode com sudo."
[ -n "$PWA_HOST" ] || die "defina PWA_HOST, ex.: sudo PWA_HOST=pwa.afrsistemas.com.br $0"

# ---------------------------------------------------------------- detecção --
detectados=()
have() { command -v "$1" >/dev/null 2>&1; }

if have nginx || [ -d /etc/nginx ]; then detectados+=("nginx"); fi
if have caddy || [ -f /etc/caddy/Caddyfile ]; then detectados+=("caddy"); fi
if have docker && docker ps --format '{{.Image}}' 2>/dev/null | grep -qi traefik; then
  detectados+=("traefik")
fi
if have apache2ctl || [ -d /etc/apache2 ]; then detectados+=("apache"); fi

echo
echo "=== o que este servidor tem ==="
printf 'pilhas encontradas : %s\n' "${detectados[*]:-nenhuma}"
printf 'quem ouve na 80/443: %s\n' \
  "$( (ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep -E ':(80|443)\b' | tr -s ' ' | cut -d' ' -f4,6 | paste -sd'; ' - || echo '?')"
printf 'upstream do PWA    : %s -> %s\n' "$PWA_UPSTREAM" \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://$PWA_UPSTREAM/" 2>/dev/null || echo 'sem resposta')"
echo

[ "${#detectados[@]}" -gt 0 ] || die "nenhum proxy reverso reconhecido. Pare aqui e me mande a saída acima."
if [ "${#detectados[@]}" -gt 1 ]; then
  die "mais de uma pilha presente (${detectados[*]}). Não vou adivinhar qual atende o labquali — mande a saída acima."
fi
STACK="${detectados[0]}"
ok "pilha: $STACK"

# ------------------------------------------------------------------ nginx ---
render_nginx() {
  cat <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $PWA_HOST;
    # O certbot troca isto por um redirect 301 pro HTTPS quando emite o cert.
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://\$host\$request_uri; }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name $PWA_HOST;

    # ssl_certificate / ssl_certificate_key entram aqui pelo certbot.

    # Coleta manda foto em base64 pelo proxy /api/odoo.
    client_max_body_size $MAX_BODY;

    # Upload de foto em 3G/4G de hospital é lento; 60s (default) derruba no meio.
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;

    location / {
        proxy_pass http://$PWA_UPSTREAM;
        proxy_http_version 1.1;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        # Sem isto o Next se acha em HTTP e monta URL absoluta errada.
        proxy_set_header X-Forwarded-Proto \$scheme;
        # Sem Upgrade/Connection de propósito: o PWA em produção não abre
        # WebSocket (o HMR do Next é só de desenvolvimento), e mandar
        # `Connection: upgrade` em toda requisição é header errado de graça.
    }

    location = /sw.js {
        proxy_pass http://$PWA_UPSTREAM;
        proxy_set_header Host \$host;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
}
EOF
}

aplica_nginx() {
  local site=/etc/nginx/sites-available/$PWA_HOST
  [ -d /etc/nginx/sites-available ] || site=/etc/nginx/conf.d/$PWA_HOST.conf
  if [ -f "$site" ]; then
    cp -a "$site" "$site.bak.$(date +%Y%m%d%H%M%S)"
    info "config anterior salva em $site.bak.*"
  fi
  render_nginx > "$site"
  [ -d /etc/nginx/sites-enabled ] && ln -sfn "$site" "/etc/nginx/sites-enabled/$PWA_HOST"

  # O bloco 443 ainda não tem certificado; o certbot escreve as duas linhas de
  # ssl_certificate. Por isso ele roda ANTES do primeiro `nginx -t` valer.
  if have certbot; then
    local args=(--nginx -d "$PWA_HOST" --redirect --non-interactive --agree-tos)
    if [ -n "$CERT_EMAIL" ]; then args+=(-m "$CERT_EMAIL"); else args+=(--register-unsafely-without-email); fi
    info "emitindo certificado Let's Encrypt para $PWA_HOST..."
    certbot "${args[@]}"
  else
    die "certbot não encontrado. Instale (apt install certbot python3-certbot-nginx) e rode de novo — o bloco 443 está escrito mas sem certificado, então NÃO recarregue o nginx antes disso."
  fi

  nginx -t || die "nginx -t falhou; nada foi recarregado. Config em $site (backup ao lado)."
  systemctl reload nginx
  ok "nginx recarregado."
}

# ------------------------------------------------------------------ caddy ---
render_caddy() {
  cat <<EOF
# --- PWA Técnico (afr_qualificacao) ---
$PWA_HOST {
    encode gzip
    request_body {
        max_size $MAX_BODY
    }
    header /sw.js Cache-Control "no-cache, no-store, must-revalidate"
    reverse_proxy $PWA_UPSTREAM
}
EOF
}

aplica_caddy() {
  local f=/etc/caddy/Caddyfile
  [ -f "$f" ] || die "$f não existe."
  if grep -q "^$PWA_HOST" "$f"; then
    die "$PWA_HOST já aparece no Caddyfile. Revise à mão — não vou sobrescrever."
  fi
  cp -a "$f" "$f.bak.$(date +%Y%m%d%H%M%S)"
  render_caddy >> "$f"
  caddy validate --config "$f" --adapter caddyfile || die "Caddyfile inválido; backup ao lado, nada recarregado."
  systemctl reload caddy
  ok "caddy recarregado (o TLS ele resolve sozinho)."
}

# ---------------------------------------------------------------- traefik ---
render_traefik() {
  cat <<EOF
# Traefik é configurado por label, não por arquivo de site. Acrescente ao
# serviço \`pwa\` do docker-compose.yml do PWA e suba de novo:
#
#   docker compose up -d
#
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.pwa.rule=Host(\`$PWA_HOST\`)"
      - "traefik.http.routers.pwa.entrypoints=websecure"
      - "traefik.http.routers.pwa.tls.certresolver=le"   # troque 'le' pelo
                                                          # certresolver que
                                                          # o labquali já usa
      - "traefik.http.services.pwa.loadbalancer.server.port=3000"
#
# Confira também: o container do PWA precisa estar na MESMA rede docker do
# traefik, e o \`ports:\` do compose pode sair (o traefik alcança pela rede
# interna, e aí a 3010 nem fica exposta).
EOF
}

# -------------------------------------------------------------------- main --
echo "=== configuração para $PWA_HOST -> $PWA_UPSTREAM ==="
case "$STACK" in
  nginx)   render_nginx ;;
  caddy)   render_caddy ;;
  traefik) render_traefik ;;
  apache)  die "apache detectado. Não escrevi template pra ele — me mande a saída da detecção que eu escrevo." ;;
esac
echo

if [ "$APPLY" -eq 0 ]; then
  echo "DRY-RUN: nada foi escrito. Para aplicar:"
  echo "  sudo PWA_HOST=$PWA_HOST${CERT_EMAIL:+ CERT_EMAIL=$CERT_EMAIL} $0 --apply"
  exit 0
fi

case "$STACK" in
  nginx)   aplica_nginx ;;
  caddy)   aplica_caddy ;;
  traefik) die "traefik é por label: aplique o bloco acima no docker-compose.yml do PWA e rode 'docker compose up -d'. Nada a escrever aqui." ;;
esac

echo
ok "pronto. Confira de fora:"
echo "  curl -sSI https://$PWA_HOST/ | head -3"
echo "  curl -sS  https://$PWA_HOST/manifest.json | head -5   # 200 SEM sessão"
echo
echo "Depois, num CELULAR de verdade (é o Bloco E do checklist, que nunca rodou):"
echo "  1. abrir https://$PWA_HOST, conferir o convite de instalar"
echo "  2. instalar, abrir pelo ícone, logar"
echo "  3. ativar modo avião e navegar — a casca do app tem que carregar"
