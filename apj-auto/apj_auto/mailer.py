# -*- coding: utf-8 -*-
"""発注メール・エラー通知メールの SMTP 送信。

送信方式は SMTP で確定（非 Google Workspace）。
587/STARTTLS または 465/SSL を .env の SMTP_PORT / SMTP_SSL で切り替える。
"""

import datetime
import smtplib
from email.message import EmailMessage
from pathlib import Path

from .config import Config

# 本文（定型・変更しない）
MAIL_BODY = """株式会社アートプリントジャパン
神代様 斎藤様

いつもお世話になっております。
有限会社エルコミューンの 真田です。

発注書を添付ファイルにて送付させて頂きました。

ご手配のほどよろしくお願い申し上げます。
------------------------------------------------------------
　有限会社 EL COMMUN（エルコミューン）
　真田 ゆりえ

　〒468-0007
　愛知県名古屋市天白区植田本町2-1006
　電話番号：052-807-0299
　E-mail：ec@elcommun.co.jp

　＊土日・祝日はお休みを頂いております＊
　（営業時間：平日／AM9時～PM18時）
------------------------------------------------------------
"""


def _connect(cfg: Config) -> smtplib.SMTP:
    if cfg.smtp_ssl:
        server = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=60)
    else:
        server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=60)
        server.starttls()
    server.login(cfg.smtp_user, cfg.smtp_password)
    return server


def _send(cfg: Config, msg: EmailMessage, recipients: list):
    server = _connect(cfg)
    try:
        server.send_message(msg, from_addr=cfg.mail_from, to_addrs=recipients)
    finally:
        server.quit()


def send_order_mail(cfg: Config, xlsx_path: Path, today: datetime.date):
    """発注書を添付して APJ へ送信する。失敗時は例外を送出する。"""
    subject = f"フレーム発注書 {today.year}/{today.month}/{today.day}：EL COMMUN EC事業部"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.mail_from
    msg["To"] = ", ".join(cfg.mail_to)
    if cfg.mail_cc:
        msg["Cc"] = ", ".join(cfg.mail_cc)
    msg.set_content(MAIL_BODY)

    data = xlsx_path.read_bytes()
    msg.add_attachment(
        data,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=xlsx_path.name,
    )

    # Sent に残らない場合があるため BCC で社内控えを送る（envelope のみに含める）
    recipients = cfg.mail_to + cfg.mail_cc + cfg.mail_bcc
    _send(cfg, msg, recipients)


REVIEW_BODY = """（社内確認用）本日のAPJ発注書を生成しました。まだAPJには送信していません。

添付の発注書を確認し、問題なければ以下を実行してください。
（APJへのメール送信と GoQ 更新〔ひとことメモ・ステータス移動〕が行われます）

  cd apj-auto && venv/bin/python run_apj_order.py --approve

対象件数: {n}件
発注書: {xlsx}

※本日中に --approve を実行しなかった場合、注文は「APJ:発注前」に残り、
　翌営業日の実行でまとめて発注対象になります。
"""


def send_review_mail(cfg: Config, xlsx_path: Path, today: datetime.date, n: int):
    """確認モード: 発注書を社内（NOTIFY_TO）に送り、承認を待つ。"""
    msg = EmailMessage()
    msg["Subject"] = f"【要確認】APJ発注書 {today.isoformat()}（承認待ち・未送信）"
    msg["From"] = cfg.mail_from
    msg["To"] = ", ".join(cfg.notify_to)
    msg.set_content(REVIEW_BODY.format(n=n, xlsx=xlsx_path.name))
    msg.add_attachment(
        xlsx_path.read_bytes(),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=xlsx_path.name,
    )
    _send(cfg, msg, cfg.notify_to)


def send_error_mail(cfg: Config, subject: str, body: str):
    """エラー通知メール。通知自体の失敗は呼び出し側でログするのみとする。"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.mail_from
    msg["To"] = ", ".join(cfg.notify_to)
    msg.set_content(body)
    _send(cfg, msg, cfg.notify_to)
