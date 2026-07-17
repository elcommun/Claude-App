#!/bin/bash
# 平日15:00の定時実行を停止する（launchd解除 + スリープ解除設定の取り消し）。
#
# 使い方:
#   cd apj-auto
#   bash setup/disable_schedule.sh
#
# venv / .env / 作業フォルダはそのまま残るため、手動実行
# （run_apj_order.py --dry-run 等）は引き続き可能。
# 再開は setup/enable_schedule.sh。

set -euo pipefail

PLIST_LABEL="jp.co.elcommun.apj-order"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

if [ -f "$PLIST_DST" ]; then
  launchctl unload "$PLIST_DST" 2>/dev/null || true
  rm -f "$PLIST_DST"
  echo "✅ launchd の定時実行を停止・登録解除しました"
else
  echo "ℹ️  launchd は登録されていません（停止済み）"
fi

echo ""
echo "平日14:58の自動スリープ解除を取り消します（sudoパスワードが必要）..."
if sudo pmset repeat cancel; then
  echo "✅ pmset のスケジュールを取り消しました（確認: pmset -g sched）"
else
  echo "⚠️  pmset の取り消しに失敗しました。後で手動で実行してください:"
  echo "    sudo pmset repeat cancel"
fi

echo ""
echo "== 定時実行 停止完了（手動実行は引き続き可能） =="
