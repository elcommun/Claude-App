# -*- coding: utf-8 -*-
"""GoQ受注CSV → APJ発注書データへの変換ロジック。

整形ルールは既存アプリ apj-order-app (https://elcommun.github.io/apj-order-app/)
の processProductName / processOptions を正として移植したもの。
挙動を変える場合は必ず apj-order-app 側と揃えること。
"""

import csv
import io
import re

# GoQ受注CSV(CP932)の列順。apj-order-app と同一。
SOURCE_COLUMNS = [
    "商品名(削除)",
    "項目・選択肢(削除)",
    "個数",
    "氏名",
    "郵便番号",
    "都道府県",
    "都市区",
    "町以降",
    "電話番号(削除)",
    "お届け日指定(削除)",
    "お届け時間帯(削除)",
    "備考(削除)",
]

# 発注書に出力する列（備考は含めない）
OUTPUT_HEADERS = [
    "商品名",
    "項目・選択肢",
    "個数",
    "氏名",
    "郵便番号",
    "都道府県",
    "都市区",
    "町以降",
    "電話番号",
    "お届け日指定",
    "お届け時間帯",
]


def process_product_name(s: str) -> str:
    """商品名の整形。

    - 先頭の【APJ】を除去
    - 商品コード表記 (apj-...) を除去
    - クーポン表記 ＼P2倍＋クーポン／ を除去
    - 最初の【...】(サイズ表記)を残し、それ以降の付帯文言を除去
      (例: "FIT FRAME【610mm×915mm】あす楽対応" → "FIT FRAME【610mm×915mm】")
    """
    if not s:
        return ""
    r = re.sub(r"^【APJ】", "", s).strip()
    r = re.sub(r"\(apj-[^)]*\)?", "", r).strip()
    r = r.replace("＼P2倍＋クーポン／", "").strip()
    size = re.search(r"【[^】]+】", r)
    main = re.split(r"【", r)[0].strip()
    return main + size.group(0) if size else main


def process_options(s: str) -> str:
    """項目・選択肢の整形。

    - 複数行テキストの1行目のみ抽出（【長期商品... 等の注記を除去）
    - 「【」「発送までに」以降を除去
    - 先頭の「デザイン:」「フレームカラー=」「カラー:」を除去
    - 「ダークブルー」→「ブルー」に変換
    """
    if not s:
        return ""
    line = re.split(r"\r?\n", s)[0].strip()
    line = re.split(r"【|発送までに", line)[0].strip()
    for prefix in ("デザイン:", "フレームカラー=", "カラー:"):
        if line.startswith(prefix):
            line = line[len(prefix):].strip()
            break
    return "ブルー" if line == "ダークブルー" else line


def convert_row(row: list) -> dict:
    """CSV1行(SOURCE_COLUMNS順) → 発注書1行(dict)。備考は出力しない。"""
    get = lambda i: (row[i] if i < len(row) else "") or ""
    return {
        "商品名": process_product_name(get(0)),
        "項目・選択肢": process_options(get(1)),
        "個数": get(2),
        "氏名": get(3),
        "郵便番号": get(4),
        "都道府県": get(5),
        "都市区": get(6),
        "町以降": get(7),
        "電話番号": get(8),
        "お届け日指定": get(9),
        "お届け時間帯": get(10),
    }


def parse_goq_csv(raw: bytes) -> list:
    """GoQからダウンロードしたCSV(CP932、ヘッダー行あり)をパースし、
    変換済みの行dictのリストを返す。空行はスキップ。
    """
    text = None
    for enc in ("cp932", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("CSVの文字コードを判定できません (CP932/UTF-8 以外)")

    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if len(rows) < 2:
        return []
    return [convert_row(r) for r in rows[1:]]
