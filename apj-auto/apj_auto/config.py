# -*- coding: utf-8 -*-
"""設定の読み込み。

認証情報はコードに直書きせず、`.env`（git管理外）から読み込む。
.env.example を .env にコピーして値を埋めること。
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _bool(v: str, default: bool = False) -> bool:
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _split_addrs(v: str) -> list:
    return [a.strip() for a in (v or "").split(",") if a.strip()]


@dataclass
class Config:
    # --- GoQ System ---
    goq_login_url: str = "https://order.goqsystem.com/goq21/"
    goq_list_url: str = "https://order.goqsystem.com/goq21/index_beta.php?stat=23&page={page}"
    goq_shop_id: str = ""
    goq_user_id: str = ""
    goq_password: str = ""
    goq_csv_template: str = ""  # APJ発注書用CSVテンプレート名（GoQ側で作成済みのもの）
    goq_status_done: str = "APJ:発注【済】"
    headless: bool = True

    # --- メール ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_ssl: bool = False  # True: 465/SSL, False: 587/STARTTLS
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "ec@elcommun.co.jp"
    mail_to: list = field(default_factory=list)    # 【要確認】APJ 神代様・斎藤様
    mail_cc: list = field(default_factory=list)
    mail_bcc: list = field(default_factory=list)   # 社内控え推奨: ec@elcommun.co.jp

    # --- 通知・動作 ---
    notify_to: list = field(default_factory=list)  # エラー通知先（省略時 mail_from）
    exclude_if_memo_ordered: bool = True  # ひとことメモに「...発注」既入力の注文を除外
    # 確認モード: 発注書を社内確認メールで送り、--approve 実行で初めて
    # APJへ送信＋GoQ更新する（運用開始時は true 推奨。慣れたら false で完全自動）
    confirm_mode: bool = True
    retry_count: int = 3
    retry_wait_sec: int = 10

    # --- パス ---
    home: Path = Path.home() / "apj-order"

    @property
    def log_dir(self) -> Path:
        return self.home / "logs"

    @property
    def state_dir(self) -> Path:
        return self.home / "state"

    @property
    def out_dir(self) -> Path:
        return self.home / "orders"


def load_config(env_path: Path = None) -> Config:
    """`.env` を読み込んで Config を返す。優先: 引数 > APJ_ENV > スクリプト隣の .env"""
    if env_path is None:
        env_path = os.environ.get("APJ_ENV")
    if env_path is None:
        candidate = Path(__file__).resolve().parent.parent / ".env"
        env_path = candidate if candidate.exists() else None
    if env_path:
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)

    g = os.environ.get
    cfg = Config(
        goq_login_url=g("GOQ_LOGIN_URL", Config.goq_login_url),
        goq_list_url=g("GOQ_LIST_URL", Config.goq_list_url),
        goq_shop_id=g("GOQ_SHOP_ID", ""),
        goq_user_id=g("GOQ_USER_ID", ""),
        goq_password=g("GOQ_PASSWORD", ""),
        goq_csv_template=g("GOQ_CSV_TEMPLATE", ""),
        goq_status_done=g("GOQ_STATUS_DONE", Config.goq_status_done),
        headless=_bool(g("GOQ_HEADLESS"), True),
        smtp_host=g("SMTP_HOST", ""),
        smtp_port=int(g("SMTP_PORT", "587")),
        smtp_ssl=_bool(g("SMTP_SSL"), False),
        smtp_user=g("SMTP_USER", ""),
        smtp_password=g("SMTP_PASSWORD", ""),
        mail_from=g("MAIL_FROM", "ec@elcommun.co.jp"),
        mail_to=_split_addrs(g("MAIL_TO", "")),
        mail_cc=_split_addrs(g("MAIL_CC", "")),
        mail_bcc=_split_addrs(g("MAIL_BCC", "")),
        notify_to=_split_addrs(g("NOTIFY_TO", "")),
        exclude_if_memo_ordered=_bool(g("EXCLUDE_IF_MEMO_ORDERED"), True),
        confirm_mode=_bool(g("APJ_CONFIRM_MODE"), True),
        retry_count=int(g("RETRY_COUNT", "3")),
        retry_wait_sec=int(g("RETRY_WAIT_SEC", "10")),
        home=Path(g("APJ_HOME", str(Path.home() / "apj-order"))).expanduser(),
    )
    if not cfg.notify_to:
        cfg.notify_to = [cfg.mail_from]
    return cfg


def validate_for_run(cfg: Config) -> list:
    """本実行に必要な設定の不足を列挙して返す（dry-run時は未使用）。"""
    missing = []
    if not cfg.goq_user_id or not cfg.goq_password:
        missing.append("GOQ_USER_ID / GOQ_PASSWORD")
    if not cfg.smtp_host or not cfg.smtp_user or not cfg.smtp_password:
        missing.append("SMTP_HOST / SMTP_USER / SMTP_PASSWORD")
    if not cfg.mail_to:
        missing.append("MAIL_TO（APJ側送信先）")
    return missing
