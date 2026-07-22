# 楽天→auPAY 商品データ作成ツール

楽天RMSの商品データ（`dl-normal-item.csv`）から、auPAYマーケットにアップロードできる `item.csv` / `stock.csv` を丸ごと生成するシングルページアプリ。

既存の `aupay-convert/`（auPAYの登録済みデータを楽天データで部分修正するツール）と異なり、こちらは**auPAY側の商品行・在庫行そのものを生成**するため、auPAY未登録の新商品の一括登録にも使える。

## 入力ファイル（種類はヘッダーから自動判別・まとめてドロップ可）

| ファイル | 必須 | 用途 |
|---|---|---|
| 楽天 `dl-normal-item.csv` | ✅ | 商品情報・SKU・価格・在庫・画像・オプション |
| 楽天 `dl-item-cat.csv` | 任意 | 店舗内カテゴリ（shopCategory1〜10） |
| auPAY `item.csv` | 任意 | 新規（n）/更新（u）判定・lotNumber・既存設定の引き継ぎ |
| auPAY `stock.csv` | 任意 | バリエーション軸（縦/横）と選択肢コードの引き継ぎ |

## 主な変換ルール

- **商品名**: 先頭装飾（＼P2倍＋クーポン／等）を削除。【限定】【Raffinart】【APJ】は保持
- **価格**: 「表示価格（定価）優先」または「販売価格（楽天セール価格）」を選択
- **説明文**: キャッチコピー→description、スマホ用説明文→descriptionForSP、PC用販売説明文→descriptionForPC。改行除去、`image.rakuten.co.jp/elcommun/cabinet` → `image.wowma.jp/69585078/elcommun/cabinet` 書き換え、商品ページリンクは `/u/69585078/c/品番` に変換、変換できない楽天リンクはアンカー解除して警告
- **カテゴリ**: ジャンルID→auPAYカテゴリIDは実績データから抽出した122件のマッピングを内蔵（未対応は警告）
- **店舗内カテゴリ**: `\` 区切り→`:` 区切り、「セール商品」と親階層の重複を除外、最大10件
- **配送方法**: 楽天の配送方法セット管理番号＋送料区分1の組み合わせから deliveryMethodId/Name を自動設定
- **バリエーション在庫**: SKUごとに stock.csv 行を生成。既存データが縦軸（Vertical）の商品は縦軸のまま、コードもSKU番号照合で引き継ぎ。選択肢名の `&` は `/` に変換
- **固定値**: taxSegment=3 / reducedTax=1 / postageSegment=1 / searchTarget=1 ほか（既存auPAYデータ921商品の実績値と一致確認済み）

## 出力

- `item.csv`（253列）・`stock.csv`（16列）、auPAYダウンロード形式と同一ヘッダー
- 文字コードは Shift-JIS（既定・アップロード用）/ UTF-8 を選択
- ctrlCol: 新規=`n`、更新=`u`

## バージョン番号

`index.html` 内の `const APP_VERSION = N;` を**ファイル変更のたびに必ず1つ増やすこと**（5分ごとにサーバーと比較して自動リロード／更新通知）。
