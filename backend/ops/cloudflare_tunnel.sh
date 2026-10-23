#!/bin/zsh
# Publishes the local backend (launchd me.boxmind.backend, :8001) as https://api.boxmind.deskfox.ai
# through a Cloudflare Tunnel. Idempotent; re-run after changes.
#
# One-time prerequisites (done by hand):
#   1. deskfox.ai is a zone on the Cloudflare account (nameservers moved from Porkbun).
#   2. `cloudflared tunnel login` was run on this Mac and deskfox.ai was picked in the browser.
set -euo pipefail

NAME=${TUNNEL_NAME:-boxmind}
HOST=${TUNNEL_HOST:-api.boxmind.deskfox.ai}
PORT=${BACKEND_PORT:-8001}
CF=~/.cloudflared

[[ -f $CF/cert.pem ]] || { echo "not logged in: run  cloudflared tunnel login  first"; exit 1; }

if ! cloudflared tunnel list -o json | jq -e --arg n "$NAME" '.[] | select(.name == $n)' >/dev/null; then
  cloudflared tunnel create "$NAME"
fi
ID=$(cloudflared tunnel list -o json | jq -r --arg n "$NAME" '.[] | select(.name == $n) | .id')
echo "tunnel $NAME = $ID"

cat > "$CF/config.yml" <<YML
tunnel: $ID
credentials-file: $HOME/.cloudflared/$ID.json
ingress:
  - hostname: $HOST
    service: http://localhost:$PORT
    originRequest:
      connectTimeout: 30s
      noHappyEyeballs: true
  - service: http_status:404
YML

# Creates the CNAME $HOST -> $ID.cfargotunnel.com in the zone (no-op if it exists).
cloudflared tunnel route dns "$NAME" "$HOST" || true

# Run as a user LaunchAgent so it comes back after reboot, like the backend itself.
PLIST=~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
if [[ -f $PLIST ]]; then
  launchctl kickstart -k "gui/$(id -u)/com.cloudflare.cloudflared"
else
  cloudflared service install
fi

sleep 4
echo "--- https://$HOST/api/health"
curl -fsS --max-time 20 "https://$HOST/api/health" && echo
