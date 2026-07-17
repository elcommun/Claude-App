#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APJフレーム発注 完全自動化 エントリポイント。

処理フロー（要件定義書 §3）:
  [1] GoQ System にログイン
  [2] 「APJ:発注前」(stat=23) の注文一覧を全ページ取得
  [3] 受注番号リストを確定（以後この確定リストのみを操作対象とする）
  [4] 発注書 xlsx を生成
  [5] メール送信（発注書を添付）
  [6] 送信成功後に GoQ 更新:
      (a) 確定リストのみ選択 → ひとことメモ「YYYY-MM-DD発注」上書き保存
      (b) 同じ注文のみ再選択 → ステータス「APJ:発注【済】」へ移動
  [7] 実行ログ保存、失敗時は通知

安全要件:
  - [6] の対象は必ず [3] の確定リストのみ（受注番号で厳密照合）
  - メール送信失敗時は GoQ 更新を実行しない
  - ステータス移動完了で初めて成功。途中失敗時は state に進捗を記録し、
    再実行時にメール送信済みなら再送しない（GoQ 更新のみ再開）

使い方:
  python run_apj_order.py            # 本実行（launchd から毎平日15:00に起動）
  python run_apj_order.py --dry-run  # 取得〜xlsx生成のみ（メール送信・GoQ更新なし）
  python run_apj_order.py --inspect  # ログイン後の一覧画面のスクショ/HTMLを保存
  python run_apj_order.py --force    # 営業日・同日実行ガードを無視（テスト用）
"""

import argparse
import datetime
import logging
import sys
import traceback
from pathlib import Path

from apj_auto.config import load_config, validate_for_run
from apj_auto.excel import build_order_xlsx
from apj_auto.goq import MEMO_ORDERED_RE, GoqClient, retry
from apj_auto.guard import RunState, is_business_day
from apj_auto.mailer import send_error_mail, send_order_mail
from apj_auto.transform import parse_goq_csv


def setup_logger(cfg, today: datetime.date) -> logging.Logger:
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("apj")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(cfg.log_dir / f"{today.isoformat()}.log",
                             encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def notify_failure(cfg, log, today, step: str, err: Exception, state: RunState):
    """失敗時の担当者通知（§8）。通知先は NOTIFY_TO（既定: ec@）。"""
    progress = ", ".join(
        f"{k}={'済' if v else '未'}" for k, v in state.data["steps"].items()
    )
    body = (
        f"APJ発注自動処理が失敗しました。\n\n"
        f"日付: {today.isoformat()}\n"
        f"失敗ステップ: {step}\n"
        f"進捗: {progress}\n"
        f"対象受注番号: {state.data.get('order_ids')}\n\n"
        f"エラー:\n{err}\n\n{traceback.format_exc()}\n"
        f"※メール送信済み(mail_sent=済)の場合、再実行しても再送はされず\n"
        f"　GoQ更新のみ再開されます。ログ: {cfg.log_dir / (today.isoformat() + '.log')}"
    )
    try:
        send_error_mail(cfg, f"【要対応】APJ発注自動処理 失敗 ({today.isoformat()}: {step})", body)
        log.info("エラー通知メールを送信しました: %s", cfg.notify_to)
    except Exception as e:  # noqa: BLE001
        log.error("エラー通知メールの送信にも失敗: %s", e)


def main() -> int:
    ap = argparse.ArgumentParser(description="APJフレーム発注 自動処理")
    ap.add_argument("--dry-run", action="store_true",
                    help="メール送信・GoQ更新を行わない（xlsx生成まで）")
    ap.add_argument("--inspect", action="store_true",
                    help="セレクタ調整用: 一覧画面のスクショ/HTML保存のみ")
    ap.add_argument("--force", action="store_true",
                    help="営業日・同日実行ガードを無視")
    args = ap.parse_args()

    cfg = load_config()
    today = datetime.date.today()
    log = setup_logger(cfg, today)

    # --- ガード（§2）---
    if not args.force and not is_business_day(today):
        log.info("本日(%s)は土日祝のため実行しません。", today)
        return 0

    state = RunState(cfg.state_dir, today)
    if not args.force and state.completed:
        log.info("本日分は実行済みのためスキップします（二重発注防止）。")
        return 0

    missing = validate_for_run(cfg)
    if missing and not (args.dry_run or args.inspect):
        log.error("設定不足のため実行できません: %s（.env を確認）", " / ".join(missing))
        return 1
    if not cfg.goq_user_id or not cfg.goq_password:
        log.error("GOQ_USER_ID / GOQ_PASSWORD が未設定です（.env を確認）")
        return 1

    step = "起動"
    try:
        with GoqClient(cfg, log, cfg.log_dir / today.isoformat()) as goq:
            if args.inspect:
                goq.inspect()
                return 0

            # [1] ログイン
            step = "[1] ログイン"
            retry(log, goq.login, cfg.retry_count, cfg.retry_wait_sec, step)

            # [2][3] 注文一覧取得 → 受注番号リスト確定
            step = "[2] 注文一覧取得"
            if state.step_done("mail_sent") and state.data.get("order_ids"):
                # 前回メール送信まで完了 → 同じ確定リストで GoQ 更新のみ再開
                order_ids = state.data["order_ids"]
                log.info("前回メール送信済み。GoQ更新のみ再開します (%d件)", len(order_ids))
            else:
                fetched = retry(log, goq.fetch_orders,
                                cfg.retry_count, cfg.retry_wait_sec, step)

                # §9-5: ひとことメモに「YYYY-MM-DD発注」既入力の注文が
                # 「発注前」に残っていた場合は発注済みとみなして除外し、通知する
                order_ids, already = [], []
                for oid, memo in fetched:
                    if cfg.exclude_if_memo_ordered and MEMO_ORDERED_RE.search(memo or ""):
                        already.append((oid, memo))
                    else:
                        order_ids.append(oid)
                if already:
                    log.warning("発注メモ既入力のため除外: %s", already)
                    try:
                        send_error_mail(
                            cfg,
                            f"【確認】APJ発注前に発注済みメモ付き注文 ({today.isoformat()})",
                            "「APJ:発注前」に、ひとことメモに発注日が既に入っている注文が"
                            f"残っていたため今回の発注から除外しました。\n\n{already}\n\n"
                            "GoQ上でステータスを確認してください。",
                        )
                    except Exception as e:  # noqa: BLE001
                        log.warning("確認通知メールの送信失敗: %s", e)

                if not order_ids:
                    log.info("対象0件のため何もせず正常終了します。")
                    state.finish("対象0件")
                    return 0

                log.info("確定受注番号 (%d件): %s", len(order_ids), order_ids)
                state.mark("fetched", order_ids=order_ids)

                # [4] CSV取得 → 変換 → 発注書xlsx生成
                step = "[4] 発注書生成"
                csv_bytes = retry(log, lambda: goq.export_csv(order_ids),
                                  cfg.retry_count, cfg.retry_wait_sec, "CSVダウンロード")
                rows = parse_goq_csv(csv_bytes)
                if not rows:
                    raise RuntimeError("CSVに明細がありません（テンプレート設定を確認）")
                xlsx_path = build_order_xlsx(rows, cfg.out_dir, today)
                log.info("発注書生成: %s (%d行)", xlsx_path, len(rows))
                state.mark("xlsx", xlsx_path=str(xlsx_path))

                if args.dry_run:
                    log.info("--dry-run のためここで終了（メール送信・GoQ更新なし）")
                    return 0

                # [5] メール送信（成功しない限り GoQ 更新には進まない）
                step = "[5] メール送信"
                retry(log, lambda: send_order_mail(cfg, Path(state.data["xlsx_path"]), today),
                      cfg.retry_count, cfg.retry_wait_sec, step)
                log.info("メール送信成功: To=%s Cc=%s Bcc=%s",
                         cfg.mail_to, cfg.mail_cc, cfg.mail_bcc)
                state.mark("mail_sent")

            # [6] GoQ 更新（確定リストのみ・受注番号で厳密照合）
            memo_text = f"{today.isoformat()}発注"
            if not state.step_done("memo_done"):
                step = "[6a] ひとことメモ入力"
                retry(log, lambda: goq.set_memo(order_ids, memo_text),
                      cfg.retry_count, cfg.retry_wait_sec, step)
                state.mark("memo_done")

            if not state.step_done("status_done"):
                step = "[6b] ステータス移動"
                retry(log, lambda: goq.move_status(order_ids, cfg.goq_status_done),
                      cfg.retry_count, cfg.retry_wait_sec, step)
                state.mark("status_done")

        # [7] 完了
        state.finish(f"{len(order_ids)}件 発注完了")
        log.info("✅ 全ステップ完了: %d件（%s）", len(order_ids), memo_text)
        return 0

    except Exception as e:  # noqa: BLE001
        log.error("❌ 失敗: %s / %s", step, e)
        log.error(traceback.format_exc())
        notify_failure(cfg, log, today, step, e, state)
        return 1


if __name__ == "__main__":
    sys.exit(main())
