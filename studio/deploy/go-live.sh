#!/usr/bin/env bash
# One-shot go-live for Idea Factory Studio on studio.enjoyapier.cloud.
# Run as root (claude-user has no passwordless sudo):
#   sudo bash studio/deploy/go-live.sh
#
# It: installs+starts the backend as a systemd service, backs up the old Hermes
# Studio nginx conf, points studio.enjoyapier.cloud at the new panel (3010),
# validates, and reloads nginx. Idempotent; safe to re-run.
set -euo pipefail

REPO=/home/claude-user/workspace/idea-factory
AV=/etc/nginx/sites-available/oc-studio
EN=/etc/nginx/sites-enabled/oc-studio

echo "==> 1/5 free port 3010 (stop any ad-hoc backend) + install systemd service"
pkill -f "studio/server/app.py" 2>/dev/null || true
cp "$REPO/studio/deploy/idea-factory-studio.service" /etc/systemd/system/idea-factory-studio.service
systemctl daemon-reload
systemctl enable --now idea-factory-studio
sleep 2

echo "==> 2/5 backend health on 127.0.0.1:3010"
curl -fsS -o /dev/null "http://127.0.0.1:3010/api/me" && echo "    backend OK" || { echo "    backend NOT responding — check: journalctl -u idea-factory-studio -n 50"; exit 1; }

echo "==> 3/5 back up current nginx conf + install new one"
[ -f "$AV" ] && cp -n "$AV" "$AV.hermes.bak" && echo "    backed up -> $AV.hermes.bak" || true
cp "$REPO/studio/deploy/studio.enjoyapier.cloud.conf" "$AV"
ln -sf "$AV" "$EN"

echo "==> 4/5 validate nginx"
nginx -t

echo "==> 5/5 reload nginx"
systemctl reload nginx
echo
echo "DONE. studio.enjoyapier.cloud now serves the idea-factory panel (127.0.0.1:3010)."
echo "Login password = STUDIO_PASSWORD in $REPO/.env"
echo "Rollback: sudo cp $AV.hermes.bak $AV && sudo nginx -t && sudo systemctl reload nginx"
echo "Optional: stop old Hermes Studio container:"
echo "  (cd /home/claude-user/workspace/one-creator && sudo docker compose --profile studio stop hermes-studio)"
