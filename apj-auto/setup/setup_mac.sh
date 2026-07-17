#!/bin/bash
# APJフレーム発注 自動化 — Mac 初回セットアップスクリプト
#
# 使い方:
#   cd apj-auto
#   bash setup/setup_mac.sh
#
# 実行内容:
#   1. Python venv 作成 + 依存ライブラリ + Playwright Chromium インストール
#   2. .env の雛形コピー（未作成時）
#   3. 作業フォルダ ~/apj-order/{logs,state,orders} 作成
#   4. launchd plist をインストール（平日15:00起動）
#   5. pmset で平日14:58の自動スリープ解除を設定（要 sudo・パスワード入力あり）

set -euo pipefail

APJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_LABEL="jp.co.elcommun.apj-order"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

echo "== APJ発注自動化 セットアップ =="
echo "インストール先: $APJ_DIR"

# 1. venv + 依存
if [ ! -d "$APJ_DIR/venv" ]; then
  python3 -m venv "$APJ_DIR/venv"
fi
"$APJ_DIR/venv/bin/pip" install --upgrade pip -q
"$APJ_DIR/venv/bin/pip" install -r "$APJ_DIR/requirements.txt" -q
"$APJ_DIR/venv/bin/python" -m playwright install chromium
echo "✅ Python環境 + Playwright Chromium"

# 2. .env
if [ ! -f "$APJ_DIR/.env" ]; then
  cp "$APJ_DIR/.env.example" "$APJ_DIR/.env"
  chmod 600 "$APJ_DIR/.env"
  echo "⚠️  $APJ_DIR/.env を作成しました。認証情報を記入してください。"
else
  echo "✅ .env は既存のものを使用"
fi

# 3. 作業フォルダ
mkdir -p "$HOME/apj-order/logs" "$HOME/apj-order/state" "$HOME/apj-order/orders"
echo "✅ 作業フォルダ: ~/apj-order/"

# 4. launchd plist（パス置換してインストール）
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__APJ_DIR__|$APJ_DIR|g" -e "s|__HOME__|$HOME|g" \
  "$APJ_DIR/setup/$PLIST_LABEL.plist" > "$PLIST_DST"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "✅ launchd 登録: 平日15:00 に自動実行 ($PLIST_DST)"

# 5. pmset: 平日14:58に自動スリープ解除（要 sudo）
echo ""
echo "平日14:58の自動スリープ解除を設定します（sudoパスワードが必要）..."
if sudo pmset repeat wakeorpoweron MTWRF 14:58:00; then
  echo "✅ pmset 設定完了（確認: pmset -g sched）"
else
  echo "⚠️  pmset の設定に失敗しました。後で手動で実行してください:"
  echo "    sudo pmset repeat wakeorpoweron MTWRF 14:58:00"
fi

echo ""
echo "== セットアップ完了 =="
echo "次の手順:"
echo "  1. $APJ_DIR/.env に GoQ / SMTP / 宛先 を記入"
echo "  2. セレクタ確認:  venv/bin/python run_apj_order.py --inspect"
echo "     → ~/apj-order/logs/ のスクショ/HTMLを見て apj_auto/goq.py の SELECTORS を調整"
echo "  3. テスト実行:    venv/bin/python run_apj_order.py --dry-run --force"
echo "  4. 手動本実行:    venv/bin/python run_apj_order.py --force"
echo "  5. 定時実行テスト: launchctl start $PLIST_LABEL"
