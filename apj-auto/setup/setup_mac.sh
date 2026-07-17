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
#
# ※ 平日15:00の定時実行はこのスクリプトでは登録しない。
#   「ログイン〜発注書生成」の動作確認が完了してから
#   bash setup/enable_schedule.sh で有効化すること。
#   （停止は bash setup/disable_schedule.sh）

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

# 定時実行が過去のセットアップで登録済みの場合は停止しておく
if [ -f "$PLIST_DST" ]; then
  launchctl unload "$PLIST_DST" 2>/dev/null || true
  echo "ℹ️  既存の定時実行(launchd)を停止しました。再開は setup/enable_schedule.sh"
fi

echo ""
echo "== セットアップ完了（定時実行は未登録） =="
echo "次の手順:"
echo "  1. $APJ_DIR/.env に GoQ のログイン情報を記入（まずは GOQ_* だけでOK）"
echo "  2. セレクタ確認:  venv/bin/python run_apj_order.py --inspect"
echo "     → ~/apj-order/logs/ のスクショ/HTMLを見て apj_auto/goq.py の SELECTORS を調整"
echo "  3. 発注書生成テスト: venv/bin/python run_apj_order.py --dry-run --force"
echo "     → ~/apj-order/orders/APJ発注書_YYYYMMDD.xlsx を確認"
echo ""
echo "ここまで確立できたら（メール・GoQ更新・定時実行はその後）:"
echo "  4. .env に SMTP / 宛先 を記入して手動本実行: venv/bin/python run_apj_order.py --force"
echo "  5. 定時実行の有効化: bash setup/enable_schedule.sh"
