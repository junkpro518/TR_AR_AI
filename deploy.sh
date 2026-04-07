#!/bin/bash
# deploy.sh — نشر البوت على VPS
# الاستخدام: ./deploy.sh user@your-vps-ip

set -e

VPS="${1:?Usage: ./deploy.sh user@vps-ip}"
REMOTE_DIR="/opt/turkish-tutor"

echo "==> نسخ ملفات المشروع..."
ssh "$VPS" "mkdir -p $REMOTE_DIR"
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='.DS_Store' \
  bot/ "$VPS:$REMOTE_DIR/"

echo "==> نسخ بيانات مصادقة nlm..."
ssh "$VPS" "mkdir -p ~/.notebooklm-mcp-cli/profiles/default"
rsync -avz ~/.notebooklm-mcp-cli/profiles/default/cookies.json \
  "$VPS:~/.notebooklm-mcp-cli/profiles/default/"

echo "==> التحقق من وجود .env على السيرفر..."
if ! ssh "$VPS" "test -f $REMOTE_DIR/.env"; then
  echo "⚠️  لم يُوجد .env على السيرفر."
  echo "   انسخ .env.example وعدّله:"
  echo "   scp bot/.env.example $VPS:$REMOTE_DIR/.env"
  echo "   ssh $VPS 'nano $REMOTE_DIR/.env'"
  exit 1
fi

echo "==> بناء ونشر Docker..."
ssh "$VPS" "cd $REMOTE_DIR && docker compose up -d --build"

echo "==> الحالة:"
ssh "$VPS" "cd $REMOTE_DIR && docker compose ps"

echo ""
echo "✅ تم النشر! لمتابعة السجلات:"
echo "   ssh $VPS 'cd $REMOTE_DIR && docker compose logs -f'"
