#!/usr/bin/env bash
#
# OBSOLETO no modelo basePath /app.
#
# Antes, cada rota do PWA precisava de um ProxyPass próprio no vhost (o
# `ProxyPass /` do Odoo engolia o que sobrasse). Agora o PWA inteiro vive sob
# /app e basta UM bloco, que está em deploy/apache-labquali-app.conf. Este
# script só confere se o bloco já está no vhost (somente leitura).
#
#   ./sync-rotas-apache.sh
#
set -euo pipefail
CONF="${CONF:-/etc/apache2/sites-enabled/012-labquali-le-ssl.conf}"
UPSTREAM="${UPSTREAM:-http://127.0.0.1:3010}"
[ -r "$CONF" ] || { echo "[ERRO] vhost ilegível: $CONF" >&2; exit 1; }
if grep -qE "^[[:space:]]*ProxyPass[[:space:]]+/app[[:space:]]+${UPSTREAM}/app" "$CONF"; then
  echo "[ok] regra /app presente em $CONF."
else
  echo "[!!] regra /app ausente. Cole deploy/apache-labquali-app.conf no vhost" >&2
  echo "     (apagando as regras por rota antigas) e rode: apache2ctl configtest && systemctl reload apache2" >&2
  exit 1
fi
