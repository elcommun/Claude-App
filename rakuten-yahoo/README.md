# 楽天→Yahoo 商品データ作成（rakuten-yahoo）

楽天RMSの商品CSVから、Yahoo!ショッピング用の商品CSV（data_add.csv）と画像ZIPを作る社内ツール。ストアコンバーターは使わない。

- 公開先（予定）：https://elcommun.github.io/Claude-App/rakuten-yahoo/
- 構成：`index.html` 1ファイルのみ（HTML／CSS／JSをすべて内包。ビルド不要）
- 現在のバージョン：`APP_VERSION = 3`（未公開。v2でオプション・在庫CSVを追加）

このファイルは、Claudeのチャットで作成した初版をClaude Codeに引き継ぐためのメモです。

## 使い方

1. 楽天RMSの `dl-normal-item.csv` と `dl-item-cat.csv` をドロップ
2. 「変換する」を押す
3. 文字数超過があれば、依頼文をコピーしてClaudeのチャットで要約し、返答（JSON）を取り込む
4. `data_add.csv` をダウンロード。画像は「画像ダウンロード用コマンド」をコピーしてMacのターミナルで実行

## index.html の構成

`<script>` は2つ。1つ目は encoding-japanese（Shift-JIS変換ライブラリ）のインライン、2つ目がアプリ本体。本体は上から次の順。

| 部分 | 内容 |
|---|---|
| `LINK_MAP` | 楽天カテゴリ番号 → YahooページID（83件） |
| `GENRE_MAP` | 楽天ジャンルID → Yahoo product-category と spec_id（129件） |
| 変換ロジック | `convertAll`、`convName`、`convPcDesc`、`convAdditional`、`convSp`、`convertUrls`、`shippingFor`、`buildRequest`、`parseResponse`、`buildImageScript` など。DOMに依存しない |
| 画面まわり | `APP_VERSION` 以降。ファイル読み込み、確認画面、設定（localStorage）、ダウンロード |

## 開発時の決まりごと（Claude-App 共通）

- 1ファイル完結。`<script type="module">` は使わない
- CSVの読み書きはShift-JIS（インラインの encoding-japanese を使用）
- ダウンロードは Blob、失敗時は data URI にフォールバック
- 公開後に修正したら `APP_VERSION` を1つ上げる（開いている画面に更新案内が出る）
- デザインは EL COMMUN UI（プライマリ `#E85D26`、カード＋番号付きステップ）

## 変換仕様

### 列の対応

| Yahoo | 楽天の元データ | 処理 |
|---|---|---|
| code | 商品管理番号（商品URL） | そのまま |
| path | dl-item-cat.csv の表示先カテゴリ（全商品分のCSVでOK。dl-normal-item.csv にある商品の分だけ使う） | `\` を `:` に置換、複数は改行で連結 |
| name | 商品名 | 下記「商品名」（上限：半角換算150） |
| headline | キャッチコピー | 【ゆうメール便・送料無料】→【メール便・送料無料】（上限60） |
| caption | PC用商品説明文 | スペック表を整形。関連カテゴリ／関連ワード／メール便注意事項の行を削除 |
| explanation | PC用商品説明文 | タグを外してテキスト化（上限1000＝全角500と推定） |
| additional1 | PC用販売説明文 | h2→b、URL変換 |
| sp-additional | スマートフォン用商品説明文 | font→b、center→div、関連ワード／メール便注意事項の行を削除、URL変換 |
| options | 商品オプション＋バリエーション | 項目ごとに「項目名 選択肢…」、空行区切り。項目名・選択肢内の空白は除去 |
| sub-code | バリエーション＋システム連携用SKU番号 | `項目:選択肢=SKU番号` を `&` で連結（多軸は `#`）。並びは選択肢定義順 |
| price | 通常購入販売価格 | 先頭SKU。SKU間で異なる場合は警告 |
| jan | カタログID | バリエーションなしの商品のみ |
| ship-weight／postage-set | 配送方法セット管理番号＋送料区分1 | 下記「配送」 |
| product-category／spec1〜5 | ジャンルID、商品属性 | `GENRE_MAP` と設定のスペック値から |
| brand-code／product-code | 商品コード、カテゴリ | `cal-` で始まる商品は 64324／11495。ほかは設定のブランドルール |
| 固定値 | — | lead-time-instock=1000、lead-time-outstock=空、keep-stock=0、taxable=1、delivery=0、condition=0、display=1（倉庫指定=1なら0） |

出力するのは上記30列のみ（`OUT_HEADER`）。

### バリエーションなしの商品

楽天の商品番号を採用し、options に `デザイン 商品番号`、sub-code に `デザイン:商品番号=商品番号` を出力する（例：`デザイン:CAL-207=CAL-207`）。

### 商品名

1. 先頭の【】は残し、`＼…／` などの装飾を削除
2. （週間ホリゾンタル）（月間ブロック）（週間ブロック・日記帳）を削除、`｜` はスペースに
3. 上限を超える場合は順に：『A｜B』→『A』／』より後ろの検索ワードを後ろから削除／「スケジュール帳」を削除／末尾の語を削除

### リンク・画像URL

| 楽天 | Yahoo |
|---|---|
| `item.rakuten.co.jp/elcommun/商品管理番号/` | `store.shopping.yahoo.co.jp/el-market/商品管理番号.html` |
| `item.rakuten.co.jp/elcommun/c/番号/` | `store.shopping.yahoo.co.jp/el-market/ページID.html`（`LINK_MAP`＋設定の追加分。未登録は楽天URLのまま＋警告） |
| `www.rakuten.ne.jp/gold/elcommun/…` | `shopping.geocities.jp/el-market/…` |
| `image.rakuten.co.jp/elcommun/cabinet/…/ファイル名` | `shopping.c.yimg.jp/lib/el-market/ファイル名` |

### 配送（既存の yahoo-data-add と同じ6パターン）

| 配送方法セット管理番号 | 送料区分1 | ship-weight | postage-set |
|---|---|---|---|
| 2 | 1 | 1000 | 2 |
| 5 | 5、6 | 1000 | 2 |
| 2、5 | 2、4 | 20 | 2 |
| 1、空欄 | 4 | 20 | 1 |
| 1、空欄 | 6 | 5000 | 1 |
| 4 | 4 | 2000 | 4 |

当てはまらない商品は空欄＋警告。

### オプション・在庫CSV（v2）

Yahoo見本（option／quantity_name のダウンロードCSV、3商品分）の列構成に合わせて出力。ファイル名は `option.csv`・`quantity.csv`（Shift-JIS）。

- **option.csv（21列）**：楽天の商品オプション（メール便の注意など）は選択肢1つにつき1行（sub-code空、option-name-1／option-value-1、unselectable-1=0）。バリエーションはSKUごとに1行（sub-code=システム連携用SKU番号、option-name-1／option-value-1=項目名／選択肢、2軸目は option-name-2／option-value-2）。name は data_add の商品名
- **SKU画像の紐づけ**：SKU画像があるSKUだけ `sub-code-img1`=`https://shopping.c.yimg.jp/lib/ストア/商品コード_サブコード（小文字）.拡張子`、`main-flag`=0、`exist-flag`=1（見本の推定どおり）。この画像は追加画像（lib）として画像スクリプトが取得するので、`lib_images_XX.zip` に入る
- **quantity.csv（6列）**：バリエーションごとに quantity=0、allow-overdraft=0、stock-close=0（在庫はGoQ連携で反映）
- 見本の cal-31- には楽天に無い `cal-129` の在庫行が残っていた（Yahoo側の古い登録）。アプリは楽天のSKUだけ出力する

### 画像

- 商品画像：1枚目 `商品コード.拡張子`、2枚目以降 `商品コード_1`、`_2`…
- SKU画像：商品画像の後ろに、バリエーションの並び順で連番追加。同じ画像は重複させない。1商品20枚まで
- 説明文内の画像：楽天と同じファイル名のまま「追加画像」用に収集
- ブラウザからは楽天の画像を取得できないため、curl でダウンロードしてZIP（20MBごとに分割）を作るシェルスクリプトを発行する。保存先は `~/Downloads/yahoo_images_日時/`、ZIPは `item_images_XX.zip`（商品画像）と `lib_images_XX.zip`（追加画像）

### 文字数超過の要約（追加費用なしのチャット往復方式）

文字数は半角=1、全角=2。超過した項目だけを依頼文（Markdown＋JSON）にまとめ、Claudeのチャットで要約し、返ってきた JSON（`[{"id": "商品コード::項目", "text": "…"}]`）を取り込む。確認画面で手直しもできる。APIキー方式は不採用。

### 設定（localStorage、キー：`rakuten-yahoo-settings-v1`）

ストアアカウント、バリエーションなし商品の項目名、ZIP上限、文字数上限、リンク表の追加、スペック値、スペックIDと属性名、ジャンルごとの固定スペック、ブランドルール。

初期登録のスペック値は、既存データから判明した分のみ。

- 10011（代表カラー）：ベージュ=10690、ブラック=10676
- ジャンル固定：567236 → 52|259、111167 → 1145|431
- ブランド：メーカー・ブランド\MATOKA｜マトカ → 64324

## 検証状況

3商品（cal-31-、elco-svt001-、mh-23-）の楽天データを変換し、Yahooの既存データと突き合わせた。

- 一致：path、price、配送、product-category、sub-code、options、additional1（Yahoo側の手直し分を除く）
- 動作確認済み：読み込み、変換、要約の取り込み、手編集、CSVダウンロード（Shift-JIS）、設定の保存、画像スクリプトの構文
- 未実行：画像の実ダウンロード、Yahooへの実アップロード

## 次の作業

1. **v2で実装済み（Yahoo見本CSVで列構成を確認）**：下記「オプション・在庫CSV」。Yahooへの実アップロードは未確認
2. 検討中：文字数超過の「自動短縮」ボタン（説明文を後ろの文から削る）、画像ダウンロードのChrome拡張化

## 未確認の事項

- explanation の上限：既存データから全角500と推定。運用ルールの650文字にする場合は設定で1300に
- caption：「商品説明」の見出しを削除し、説明文セルを `colspan="2"` にした。Yahooで表示を確認する
- option.csv／quantity.csv のアップロード時のファイル名指定、main-flag=0 の意味、複数選択肢のオプションの行の持ち方（1選択肢1行と推定）
- 30列だけの data_add.csv をYahooが受け付けるか。CSVにない項目は削除されるという情報があるため、**登録済み商品への上書きには使わず、新規登録のみで使う**
- 画像ZIPの容量上限と、1商品あたりの画像枚数上限（20枚は記憶による値）
- 画像と商品CSVのアップ順（商品登録を先にする方が確実と思われる）
- 色のスペック値IDの未登録分（グリーン、ネイビー、ピンク、グレーなど）
- リンク表にないカテゴリ：c/0000001124
