# APJフレーム発注 完全自動化

GoQ System に届く APJ（株式会社アートプリントジャパン）対象の受注を、
**取得 → 発注書生成 → メール送信 → GoQ更新** まで人手ゼロで処理する
Mac（macOS）常駐の自動化スクリプト。

要件定義書（2026-07-17 EL COMMUN EC事業部）に基づく実装。
発注書の整形ルール・Excelレイアウトは既存アプリ
[apj-order-app](https://elcommun.github.io/apj-order-app/) から移植（同一出力）。

> **実データ検証済み（2026-07-17）**: GoQからダウンロードした実受注CSVと
> apj-order-app が生成した発注書xlsxのペアで、本実装の変換出力が
> **全セル値一致**（シート名・ファイル名・11列レイアウト含む）することを確認済み。

## 処理フロー

```
平日15:00（launchd起動、土日祝は jpholiday 判定で即終了）
  [1] GoQ にログイン（Playwright / ヘッドレスブラウザ）
  [2] 「APJ:発注前」(stat=23) を全ページ巡回して注文取得
  [3] 受注番号リストを確定（以後この確定リストのみ操作）
  [4] CSVダウンロード → 変換 → APJ発注書_YYYYMMDD.xlsx 生成
  [5] SMTP でメール送信（発注書添付、定型文）
  [6] 送信成功後に GoQ 更新:
      (a) ひとことメモ「YYYY-MM-DD発注」を一括入力・上書き保存
      (b) ステータスを「APJ:発注【済】」へ移動
  [7] ログ保存（~/apj-order/logs/YYYY-MM-DD.log）、失敗時はメール通知
```

対象0件の日は何もせず正常終了（メール送信・GoQ更新なし）。

## 確認モード（運用開始時の既定）

「最初は送信前に確認して発注」の要件に対応。`.env` の
`APJ_CONFIRM_MODE=true`（既定）のとき、15:00の自動実行は
**[4] 発注書生成まで**行い、APJには送信せず社内（`NOTIFY_TO`）へ
発注書添付の確認メールを送って終了する。

内容を確認して問題なければ:

```bash
cd apj-auto && venv/bin/python run_apj_order.py --approve
```

で **[5] APJへのメール送信 → [6] GoQ更新** が実行される。
対象は15:00時点で確定した受注番号リストのみ（承認までの新着は含めない。
承認しなかった場合は「APJ:発注前」に残り翌営業日にまとめて処理される）。

運用に慣れて完全自動化する場合は `APJ_CONFIRM_MODE=false` にする。

## 安全設計

- **確定リスト厳守**: GoQ更新は [3] で確定した受注番号のみ。実行中の新着や
  他ステータスの注文は受注番号照合により巻き込まない。
- **メール送信失敗時は GoQ を更新しない**（発注書が届いていないのに
  「発注済」にならない）。
- **二重発注防止**:
  - 同日2回目の実行は state ファイル（~/apj-order/state/YYYY-MM-DD.json）で
    スキップ。
  - 途中失敗時は「どこまで完了したか」を state に記録。再実行時、
    メール送信済みなら**再送せず** GoQ 更新のみ再開する。
  - ひとことメモに「YYYY-MM-DD発注」が既に入っている注文が「発注前」に
    残っていた場合は発注対象から除外し、確認メールで通知
    （`EXCLUDE_IF_MEMO_ORDERED=true`）。
- **リトライ**: 一時的なネットワークエラーは各ステップ3回まで自動リトライ。
- **失敗時の証跡**: Playwright 失敗時はスクリーンショットを
  ログフォルダに自動保存。

## セットアップ（初回のみ）

```bash
cd apj-auto
bash setup/setup_mac.sh
```

これで以下がすべて行われる:

1. Python venv + 依存ライブラリ + Playwright Chromium
2. `.env` 雛形コピー（→ **認証情報を記入する**）
3. `~/apj-order/{logs,state,orders}` 作成
4. launchd 登録（`~/Library/LaunchAgents/jp.co.elcommun.apj-order.plist`、平日15:00）
5. `sudo pmset repeat wakeorpoweron MTWRF 14:58:00`（平日14:58に自動スリープ解除）

### スリープ対策（要件 §2）

- pmset で 14:58 に自動復帰 → 15:00 の launchd が正常発火
- launchd の `StartCalendarInterval` はスリープ中に発火時刻を過ぎた場合、
  **復帰時に1回実行される**（保険）
- 同日2回目は state ガードでスキップ（二重発注防止）
- Mac がシャットダウンされていた日は実行されない → 翌営業日の実行で
  「APJ:発注前」に残っている前営業日分もまとめて処理される

### .env に記入する項目（要件 §9 の未確定事項）

| 項目 | 変数 | 状態 |
|---|---|---|
| GoQ ログインID/パスワード | `GOQ_USER_ID` / `GOQ_PASSWORD` | 要記入 |
| GoQ CSVテンプレート名 | `GOQ_CSV_TEMPLATE` | 要記入 |
| SMTP接続情報 | `SMTP_HOST` / `SMTP_PORT` / `SMTP_SSL` / `SMTP_USER` / `SMTP_PASSWORD` | 【要確認】 |
| APJ側送信先（神代様・斎藤様） | `MAIL_TO` | 【要確認】 |
| CC の要否 | `MAIL_CC` | 【要確認】 |
| 社内控え | `MAIL_BCC` | 既定: ec@（BCC推奨） |
| エラー通知先 | `NOTIFY_TO` | 既定: ec@ |

`.env` は git 管理外（chmod 600）。コードに認証情報は書かない。

## 初回の動作確認手順（重要）

GoQ の画面構成は契約・カスタマイズで異なるため、
**`apj_auto/goq.py` 冒頭の `SELECTORS` は実画面で必ず検証すること。**

```bash
# 1. ログイン〜一覧画面のスクショ/HTMLを保存（GoQを操作しない）
venv/bin/python run_apj_order.py --inspect
#    → ~/apj-order/logs/<日付>/ の goq_inspect_list.png / .html を確認し
#      SELECTORS のセレクタを実DOMに合わせて修正

# 2. 取得〜xlsx生成まで（メール送信・GoQ更新なし）
venv/bin/python run_apj_order.py --dry-run --force
#    → ~/apj-order/orders/APJ発注書_YYYYMMDD.xlsx を目視確認

# 3. 監視付き本実行（ブラウザ表示: .env で GOQ_HEADLESS=false）
venv/bin/python run_apj_order.py --force

# 4. launchd 経由のテスト起動
launchctl start jp.co.elcommun.apj-order
```

## GoQ System API について（要件 §4）

要件の優先順は「API > Playwright」。GoQ の受注管理APIが契約プランで
利用可能と確認できた場合は、`goq.py` の `GoqClient` と同じインターフェース
（`fetch_orders` / `export_csv` / `set_memo` / `move_status`）で
APIクライアントを実装して差し替えるのが最小変更。
現時点では API 利用可否が未確認のため Playwright 実装を採用している。

## ファイル構成

```
apj-auto/
  run_apj_order.py        エントリポイント（フロー全体・エラー処理・通知）
  apj_auto/
    config.py             .env 読み込み・設定検証
    guard.py              営業日判定(jpholiday)・実行state(再開/二重防止)
    goq.py                GoQ操作(Playwright)・SELECTORS定義・リトライ
    transform.py          CSV→発注書データ変換（apj-order-appから移植）
    excel.py              発注書xlsx生成（apj-order-appのレイアウトを移植）
    mailer.py             SMTP送信（発注メール定型文・エラー通知）
  tests/test_transform.py 変換・xlsx・営業日・stateのテスト
  setup/
    setup_mac.sh          初回セットアップ（venv/launchd/pmset）
    jp.co.elcommun.apj-order.plist
  .env.example            設定雛形（.env にコピーして記入）
```

## 運用メモ

- ログ: `~/apj-order/logs/YYYY-MM-DD.log`（launchd 標準出力は
  `launchd.out.log` / `launchd.err.log`）
- 発注書控え: `~/apj-order/orders/`
- 実行state: `~/apj-order/state/YYYY-MM-DD.json`
  （テストで同日再実行したい場合はこのファイルを削除するか `--force`）
- メール件名: `フレーム発注書 YYYY/M/D：EL COMMUN EC事業部`（ゼロ埋めなし）
- ひとことメモ: `YYYY-MM-DD発注`（実行当日）
