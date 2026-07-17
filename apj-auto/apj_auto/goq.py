# -*- coding: utf-8 -*-
"""GoQ System 操作クライアント（Playwright / ヘッドレスブラウザ）。

要件定義書 §4 の方針:
  1. GoQ System API が契約プランで使えるなら API を最優先（利用可否 要確認）
  2. API 不可の場合は本クライアント（Playwright）で UI 操作を再現

★重要★ SELECTORS は GoQ の実画面を確認して調整すること。
GoQ は画面カスタマイズやバージョンにより DOM が異なるため、
初回は `python run_apj_order.py --inspect` でログイン後の一覧画面の
スクリーンショットと HTML を保存し、実際のセレクタに合わせて修正する。
失敗時は自動でスクリーンショットをログフォルダに保存する。
"""

import datetime
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# セレクタ定義（実画面を確認して要調整。--inspect で確認できる）
# ---------------------------------------------------------------------------
SELECTORS = {
    # ログイン画面
    "login_shop_id": "input[name='shop_id']",
    "login_user_id": "input[name='user_id'], input[name='login_id'], input[name='id']",
    "login_password": "input[type='password']",
    "login_submit": "input[type='submit'], button[type='submit']",
    # 受注一覧（stat=23）
    "order_checkbox": "input[type='checkbox'][name*='order']",  # value=受注番号を想定
    "order_row": "tr:has(input[type='checkbox'][name*='order'])",
    "memo_cell": ".hitokoto, td.memo",  # ひとことメモ表示セル
    "next_page": "a:has-text('次へ'), a:has-text('>')",
    # 処理パネル > CSVダウンロード
    "csv_panel_open": "text=CSVダウンロード",
    "csv_template_select": "select[name*='template'], select[name*='csv']",
    "csv_download_btn": "text=ダウンロード",
    # 処理パネル > 一括入力
    "bulk_panel_open": "text=一括入力",
    "bulk_field_select": "select[name*='bulk'], select[name*='item']",
    "bulk_field_option_memo": "ひとことメモ",
    "bulk_value_input": "input[name*='bulk_value'], textarea[name*='bulk']",
    "bulk_overwrite_save": "text=上書き保存",
    # ステータス移動
    "status_move_select": "select[name*='status'], select[name*='stat']",
    "status_move_btn": "text=ステータス移動",
    "confirm_ok": "text=OK",
}

# ひとことメモに既に「YYYY-MM-DD発注」が入っている注文の検出用
MEMO_ORDERED_RE = re.compile(r"\d{4}-\d{2}-\d{2}発注")


class GoqError(RuntimeError):
    pass


class GoqClient:
    def __init__(self, cfg, logger, shot_dir: Path):
        self.cfg = cfg
        self.log = logger
        self.shot_dir = shot_dir
        self._pw = None
        self._browser = None
        self.page = None

    # -- lifecycle ----------------------------------------------------------
    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.cfg.headless)
        context = self._browser.new_context(accept_downloads=True)
        self.page = context.new_page()
        self.page.set_default_timeout(30000)
        # 「上書き保存」「ステータス移動」等のJS確認ダイアログを自動承認
        self.page.on("dialog", lambda d: d.accept())
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            self.screenshot("error")
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        return False

    def screenshot(self, tag: str) -> Path:
        """失敗時などのスクリーンショット保存（画面変更の調査用）。"""
        self.shot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        path = self.shot_dir / f"goq_{tag}_{ts}.png"
        try:
            self.page.screenshot(path=str(path), full_page=True)
            self.log.info("スクリーンショット保存: %s", path)
        except Exception as e:  # noqa: BLE001 - 撮影失敗で処理は止めない
            self.log.warning("スクリーンショット保存失敗: %s", e)
        return path

    def dump_html(self, tag: str) -> Path:
        self.shot_dir.mkdir(parents=True, exist_ok=True)
        path = self.shot_dir / f"goq_{tag}.html"
        path.write_text(self.page.content(), encoding="utf-8")
        return path

    # -- operations ---------------------------------------------------------
    def login(self):
        self.log.info("GoQ にログイン: %s", self.cfg.goq_login_url)
        self.page.goto(self.cfg.goq_login_url)
        if self.cfg.goq_shop_id:
            if self.page.locator(SELECTORS["login_shop_id"]).count():
                self.page.fill(SELECTORS["login_shop_id"], self.cfg.goq_shop_id)
        self.page.fill(SELECTORS["login_user_id"], self.cfg.goq_user_id)
        self.page.fill(SELECTORS["login_password"], self.cfg.goq_password)
        self.page.click(SELECTORS["login_submit"])
        self.page.wait_for_load_state("networkidle")
        if self.page.locator(SELECTORS["login_password"]).count():
            self.screenshot("login_failed")
            raise GoqError("GoQ ログインに失敗しました（認証情報/セレクタを確認）")
        self.log.info("ログイン成功")

    def fetch_orders(self) -> list:
        """「APJ:発注前」(stat=23) の全ページを巡回し、
        [(受注番号, ひとことメモ), ...] を返す。
        """
        orders = []
        page_no = 1
        while True:
            url = self.cfg.goq_list_url.format(page=page_no)
            self.log.info("受注一覧取得: %s", url)
            self.page.goto(url)
            self.page.wait_for_load_state("networkidle")

            boxes = self.page.locator(SELECTORS["order_checkbox"])
            count = boxes.count()
            if count == 0:
                if page_no == 1:
                    self.dump_html("list_empty")
                break

            for i in range(count):
                box = boxes.nth(i)
                order_id = box.get_attribute("value") or ""
                if not order_id:
                    continue
                memo = ""
                try:
                    row = box.locator(
                        "xpath=ancestor::tr[1]").locator(SELECTORS["memo_cell"])
                    if row.count():
                        memo = row.first.inner_text().strip()
                except Exception:  # noqa: BLE001 - メモ列は任意情報
                    pass
                orders.append((order_id, memo))

            # 次ページ
            nxt = self.page.locator(SELECTORS["next_page"])
            if nxt.count() == 0:
                break
            page_no += 1
            if page_no > 100:  # 無限ループ保険
                raise GoqError("ページ数が異常です（100超）")

        self.log.info("対象注文: %d件", len(orders))
        return orders

    def _select_orders(self, order_ids: list):
        """確定済みの受注番号のみをチェックする（新着注文を巻き込まない）。"""
        self.page.goto(self.cfg.goq_list_url.format(page=1))
        self.page.wait_for_load_state("networkidle")
        selected = set()
        page_no = 1
        while True:
            boxes = self.page.locator(SELECTORS["order_checkbox"])
            for i in range(boxes.count()):
                box = boxes.nth(i)
                oid = box.get_attribute("value") or ""
                if oid in order_ids and oid not in selected:
                    if not box.is_checked():
                        box.check()
                    selected.add(oid)
            if len(selected) == len(order_ids):
                break
            nxt = self.page.locator(SELECTORS["next_page"])
            if nxt.count() == 0:
                break
            page_no += 1
            self.page.goto(self.cfg.goq_list_url.format(page=page_no))
            self.page.wait_for_load_state("networkidle")

        missing = set(order_ids) - selected
        if missing:
            self.screenshot("select_missing")
            raise GoqError(f"選択できなかった受注番号があります: {sorted(missing)}")

    def export_csv(self, order_ids: list) -> bytes:
        """確定リストの注文のみ選択して CSV をダウンロードし、バイト列を返す。"""
        self._select_orders(order_ids)
        self.page.click(SELECTORS["csv_panel_open"])
        if self.cfg.goq_csv_template:
            sel = self.page.locator(SELECTORS["csv_template_select"])
            if sel.count():
                sel.first.select_option(label=self.cfg.goq_csv_template)
        with self.page.expect_download() as dl_info:
            self.page.click(SELECTORS["csv_download_btn"])
        download = dl_info.value
        path = download.path()
        data = Path(path).read_bytes()
        self.log.info("CSVダウンロード完了: %d bytes", len(data))
        return data

    def set_memo(self, order_ids: list, memo_text: str):
        """処理パネル > 一括入力 > ひとことメモ に memo_text を上書き保存。"""
        self.log.info("ひとことメモ一括入力: %s (%d件)", memo_text, len(order_ids))
        self._select_orders(order_ids)
        self.page.click(SELECTORS["bulk_panel_open"])
        self.page.locator(SELECTORS["bulk_field_select"]).first.select_option(
            label=SELECTORS["bulk_field_option_memo"]
        )
        self.page.fill(SELECTORS["bulk_value_input"], memo_text)
        self.page.click(SELECTORS["bulk_overwrite_save"])
        self._accept_confirm()
        self.page.wait_for_load_state("networkidle")
        self.log.info("ひとことメモ入力完了")

    def move_status(self, order_ids: list, status_label: str):
        """確定リストの注文のみ選択してステータスを移動する。"""
        self.log.info("ステータス移動: %s (%d件)", status_label, len(order_ids))
        self._select_orders(order_ids)
        self.page.locator(SELECTORS["status_move_select"]).first.select_option(
            label=status_label
        )
        self.page.click(SELECTORS["status_move_btn"])
        self._accept_confirm()
        self.page.wait_for_load_state("networkidle")
        self.log.info("ステータス移動完了")

    def _accept_confirm(self):
        """確認ボタン型のダイアログに対応（JSダイアログは__enter__で自動承認済み）。"""
        ok = self.page.locator(SELECTORS["confirm_ok"])
        if ok.count():
            try:
                ok.first.click(timeout=3000)
            except Exception:  # noqa: BLE001 - ダイアログ型なら既にaccept済み
                pass

    def inspect(self):
        """セレクタ調整用: ログイン画面 → ログイン試行 → 一覧画面の
        スクショとHTMLを各段階で保存して終了（GoQのデータは変更しない）。
        ログインに失敗してもログイン画面の証跡は残る。
        """
        self.log.info("ログイン画面を確認: %s", self.cfg.goq_login_url)
        self.page.goto(self.cfg.goq_login_url)
        self.page.wait_for_load_state("networkidle")
        self.screenshot("inspect_login")
        self.dump_html("inspect_login")

        try:
            self.login()
        except Exception as e:  # noqa: BLE001 - 証跡は保存済みなので継続不能でも報告して終了
            self.screenshot("inspect_login_failed")
            self.dump_html("inspect_login_failed")
            self.log.error(
                "ログインに失敗しました: %s\n"
                "goq_inspect_login*.png / .html を確認し、SELECTORS の "
                "login_* を実画面に合わせて調整してください。", e)
            return

        self.page.goto(self.cfg.goq_list_url.format(page=1))
        self.page.wait_for_load_state("networkidle")
        shot = self.screenshot("inspect_list")
        html = self.dump_html("inspect_list")
        self.log.info("inspect完了: %s / %s を確認して SELECTORS を調整してください",
                      shot, html)


def retry(logger, func, count: int, wait_sec: int, label: str):
    """一時的なネットワークエラー等に対する自動リトライ（最大count回）。"""
    last = None
    for attempt in range(1, count + 1):
        try:
            return func()
        except Exception as e:  # noqa: BLE001
            last = e
            logger.warning("%s 失敗 (%d/%d回目): %s", label, attempt, count, e)
            if attempt < count:
                time.sleep(wait_sec * attempt)
    raise last
