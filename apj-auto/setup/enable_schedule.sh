#!/bin/bash
# 平日15:00の定時実行を有効化する（launchd登録 + スリープ解除設定）。
#
# 使い方:
#   cd apj-auto
#   bash setup/enable_schedule.sh
#
# ※「ログイン〜発注書生成」の動作確認（--inspect / --dry-run）が
#   完了してから実行すること。停止は setup/disable_schedule.sh。

set -euo pipefail

APJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_LABEL="jp.co.elcommun.apj-order"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

# launchd plist（パス置換してインストール）
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__APJ_DIR__|$APJ_DIR|g" -e "s|__HOME__|$HOME|g" \
  "$APJ_DIR/setup/$PLIST_LABEL.plist" > "$PLIST_DST"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "✅ launchd 登録: 平日15:00 に自動実行 ($PLIST_DST)"

# pmset: 平日14:58に自動スリープ解除（要 sudo）
echo ""
echo "平日14:58の自動スリープ解除を設定します（sudoパスワードが必要）..."
if sudo pmset repeat wakeorpoweron MTWRF 14:58:00; then
  echo "✅ pmset 設定完了（確認: pmset -g sched）"
else
  echo "⚠️  pmset の設定に失敗しました。後で手動で実行してください:"
  echo "    sudo pmset repeat wakeorpoweron MTWRF 14:58:00"
fi

echo ""
echo "== 定時実行 有効化完了 =="
echo "  手動テスト起動: launchctl start $PLIST_LABEL"
echo "  停止:          bash setup/disable_schedule.sh"
