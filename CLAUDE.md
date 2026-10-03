# EL COMMUN EC 販売ランキングアプリ — 開発メモ

## アプリ概要

`ranking/index.html` 一枚のシングルページアプリ（約2,100行）。  
EC（楽天・Amazon等）の販売データをExcelでインポートし、カテゴリ別・商品別の売上ランキングを表示する。

**URL（GitHub Pages）**: `elcommun/Claude-App` の `main` ブランチで公開。

---

## 共通データ資産（他アプリでも再利用可・要提案）

### ranking の品番マスタ（`ranking/data.js`）
- `ranking/data.js` の `PRELOADED.products` は `{ "品番": ["商品名", 価格, "検索コード"], ... }` 形式（約5,800件）。
  - 商品名は**バリエーション名（色・デザイン）込み**（例: `DR-MG-585` → `ﾀﾞｲｱﾘｰ 2026年度版 4月始まり B6ﾏﾝｽﾘｰ Medjed Sand Yellow`）。半角カタカナ表記。
  - `PRELOADED.by_store` には日次・店舗別・カテゴリ別の販売数/金額データもある。
- これは **EC系の全アプリで使える「品番 → 商品名 / 価格 / 検索コード」マスタ**として再利用可能。
- 既存の利用例: `ec-category/index.html` は、このデータから抽出した `ec-category/product-names.js`（品番→商品名スナップショット）を読み込み、プレビューの商品名表示に使用。
- **再利用ルール**: 他アプリで「品番から商品名・価格・カテゴリを引きたい」「商品名の表記を統一したい」等の要望が出たら、まずこの ranking データの活用を提案すること。
  - 同一オリジン（`elcommun.github.io`）なので実行時参照も可能だが、`data.js` は約7MBと大きいため、必要な項目だけ抽出したスナップショット（例: product-names.js）を持たせる方式が軽量。
  - スナップショット方式は ranking 側更新が自動反映されない点に注意（更新時は再生成）。

---

## バージョン番号（重要）

- ヘッダーの `.hd-sub` 内に `<span>v77</span>` のようなバージョン番号がある（line ~330）
- ページ末尾のJS（line ~2524〜）が定期的にこの番号を比較し、サーバー側の番号が大きければ自動リロードしてキャッシュを更新する仕組み
- **`index.html` を変更してコミット・プッシュするたびに、このバージョン番号を必ず1つ増やすこと**
- これを忘れると、PWA（ホーム画面に追加したアプリ）やブラウザキャッシュが更新されず、ユーザーの端末に変更が反映されない

### laikle-convert のバージョン番号
- `laikle-convert/index.html` にも `const APP_VERSION = N;`（ヘッダー右上の `#verBadge` に表示）がある
- **このファイルを変更してコミットするたびに `APP_VERSION` を必ず1つ増やすこと**
- 5分ごとにサーバー側と比較し、未作業なら自動リロード、作業中（CSV読込済み）ならバッジで更新を通知する仕組み

### ec-category のバージョン番号
- `ec-category/index.html` に `const APP_VERSION = N;`（フッターの `#verBadge` に `vN` 表示）がある
- **このファイルを変更してコミットするたびに `APP_VERSION` を必ず1つ増やすこと**（フッターの `vN` 表示も合わせて更新）
- 3分ごとにサーバー側の `APP_VERSION` と比較し、大きければ自動リロード（作業中＝CSV選択済みのときはリロードしない）
- `product-names.js` を更新した場合は `<script src="product-names.js?v=N">` の `?v=N` も上げてキャッシュを更新する

### design-preview のバージョン番号
- `design-preview/index.html` に `const APP_VERSION = N;`（フッターの `#verBadge` に `vN` 表示）がある
- **このファイルを変更してコミットするたびに `APP_VERSION` を必ず1つ増やすこと**
- 3分ごとにサーバー側と比較し、大きければ自動リロード（ファイル読込済みのときはリロードしない）
- PSD/AI/PDFのブラウザプレビュー専用アプリ。描画ライブラリは `design-preview/lib/` に同梱（ag-psd 14.3.6 / pdfjs-dist 3.11.174 legacy）

### inventory-convert のバージョン番号
- `inventory-convert/index.html` に `const APP_VERSION = N;`（フッターの `#verBadge` に `vN` 表示）がある
- **このファイルを変更してコミットするたびに `APP_VERSION` を必ず1つ増やすこと**
- 3分ごとにサーバー側と比較し、大きければ自動リロード（ファイル読み込み済みのときはリロードしない）
- 入荷データxlsx（商品コード・売上数列。※入荷数を表すが列名は「売上数」のまま）と itemdata CSV（システム連携用SKU番号）を突合して「SKU,総在庫数（+N）」のCSVを出力するアプリ。SKUは一致したシステム連携用SKU番号をそのまま出力。プレビューで数量の個別編集・チェック選択一括変更が可能

### catalog-check のバージョン番号
- `catalog-check/index.html` に `const APP_VERSION = N;`（フッターの `#verBadge` に `vN` 表示）がある
- **このファイルを変更してコミットするたびに `APP_VERSION` を必ず1つ増やすこと**
- 3分ごとにサーバー側と比較し、大きければ自動リロード（ファイル読み込み済み・実行中のときはリロードしない）
- カタログPDF・画像（JPG/PNG/WebP）の品番・JAN・バリエーション名・価格をExcelマスタとOCR照合する校正チェックアプリ。容量制限なし（50MB超のPDFも動作確認済み）
- ライブラリは `catalog-check/lib/` に同梱（SheetJS / Tesseract.js + traineddata / ZXing バーコード読取）。pdf.js は `design-preview/lib/` を共用しているため、design-preview の lib を移動・削除する場合は注意

### laikle-convert の変換完了メール
- 変換完了時に `ec@elcommun.co.jp` へ自動送信する仕組み（Google Apps Script のウェブアプリ経由）
- GAS側のコードと設定手順は `laikle-convert/mail-gas/`（`Code.gs` / `README.md`）
- `index.html` の `MAIL_WEBHOOK_URL` にデプロイ済みのウェブアプリURLを設定すると有効になる（空の間は送信しない）
- 送信はページを開いてから最初の変換完了時の1通のみ（`MAIL_SENT` フラグ）

---

## ファイル構成

```
ranking/
  index.html          ← メインファイル（HTML + CSS + JS すべて含む）
  images/             ← 商品画像（手帳・カレンダーのみ）
    DR_MC_416.jpg     ← 品番のハイフンをアンダースコアに変換したファイル名
    DR_MC_417.jpg
    ...（現在 約3,500枚）
    .gitkeep
  thumbs/             ← 一覧用の軽いサムネ（images/ と同じ名前・180x240に収まる大きさ。tools/build-images.py が自動生成）
  image-index.js      ← 画像がある品番と原寸の寸法の一覧（自動生成。アプリはこれに無い品番の画像を読みに行かない）
  README.md
item-data/            ← PRELOADED データ（販売元データ、JS変数として埋め込み）
package.json
```

---

## データ構造

### PRELOADED（HTMLに埋め込み済みの静的データ）
```javascript
const PRELOADED = {
  products: { "DR-MC-416": ["フォーマット名", "商品名", "SearchCode", price], ... },
  sales: { "YYYY-MM": { by_store: {}, products: { "DR-MC-416": [qty, amount] } } }
};
```
品番フォーマット: `DR-MC-###`（手帳マンスリーコンパクト）、`DR-WK-###`（手帳週間）、`XDR-WK-###`（XDRシリーズ）、`CAL-###`（カレンダー）など。

### UPLOADS（localStorage保存）
- キー: `ec_ranking_uploads_v2`
- 同じ構造で、PRELOADEDとマージして `DATA` として使う

### STOCKOUT（欠品日データ）
```javascript
let STOCKOUT = {"DR-MC-416": "4/下", "CAL-034": "12/下", ...};
```
- HTMLに直接約500件ハードコード（line ~530）
- ユーザーがExcelをアップロードすると `Object.assign(STOCKOUT, ...)` でマージ
- localStorage（キー: `ec_stockout_v1`）にも保存し、起動時にマージ
- `clearStockout()` はこのオブジェクトをHTMLハードコード値にリセット

---

## 主要な機能・実装

### カテゴリ判定
```javascript
function getCatType(cat) {
  // 手帳系 → '手帳', カレンダー系 → 'カレンダー', それ以外 → falsy
}
```

### 欠品日列（.so-col / .show-so）
```css
.so-col{display:none}
.show-so .so-col{display:table-cell;white-space:nowrap;font-size:11px}
```
`rank-tbl` 要素に `show-so` クラスが付くとき表示。手帳・カレンダーのみ。

### 商品画像列（.img-col / .show-img）
```css
.img-col{display:none}
.show-img .img-col{display:table-cell;text-align:center;padding:5px 8px;vertical-align:middle}
```
画像パス: `images/${code.replace(/-/g,'_')}.jpg`（.pngフォールバックあり）

### ライトボックス
```javascript
function openLightbox(src){...}
function closeLightbox(){...}
// <div id="img-lb"> + <img id="img-lb-img">
```

### 初期画面＝全商品 TOP100（2026-10-02 ユーザー指示）
- リロードした初期の画面は、全カテゴリを通した**全商品のTOP100ランキング**（`showCategory(ALL_TOP_NAME)`。`ALL_TOP_NAME='全商品 TOP100'`、`isAllTop()`）。個数順（並び順が金額順のときは金額順）の上位100商品。サイドバー先頭の「🏆 全商品 TOP100」からも開く
- **福袋は全体のランキング（全商品TOP100）に含めない**（2026-10-03 ユーザー指示）。判定は `isLuckyBag()`＝商品名に「福袋」、または品番が `LBG-` で始まる。KPI（全商品の合計）・前年比較・各カテゴリ（「その他」に出る）は福袋を含めたまま
- 手動リロードではカテゴリは復元せずTOP100に戻る。バージョン更新の自動リロード（`doReload()`）のときだけ `sessionStorage` の `ecRankKeepView` で見ていたカテゴリに戻す
- **期間・店舗の絞り込みの扱い（2026-10-03）**: 店舗はリロードのたびに「すべての店舗」に戻し（保存しても復元しない）、期間は自動更新リロード（`ecRankKeepView`＝1）のときだけ復元、手動リロードは1年に戻す。端末に保存された「店舗＝Shopify・全期間」の絞り込みが残って初期画面の数字が極端に少なくなる事故があったため。期間が1年以外・店舗が「すべて」以外のときは KPI の下に帯（`#flt-note`、`updateFilterNote()`／`resetFilters()`）を出して1タップで戻せる。仕入れ商品アプリも同じ（`ecSupKeepView`）
- 全商品TOP100は実カテゴリではないため、`getCatType()` は `null`、`getCatTotal()`/`catsIn()` は全カテゴリの合計。カタログPDF（`openCategoryCatalog`）の対象外（ボタンは隠す）

### 仕入れ商品アプリ（supplier-ranking）の初期画面＝全商品 TOP100（2026-10-03 ユーザー指示）
- 全体の表（サイドバー先頭「🏆 全商品 TOP100」＝`showAllGroups()`。メーカー別・カテゴリ別とも同じ）は、全商品の上位100（`rankMetric` の個数順/金額順。同数は 個数順なら金額→金額順なら個数→商品番号）。KPI・前年比較は全商品の数字のまま。福袋の除外は無い（仕入れ商品に福袋は無い）
- 手動リロードでは前回のメーカー/カテゴリを復元せずこの表に戻る。バージョン更新の自動リロード（`scheduleReload()`）のときだけ `sessionStorage` の `ecSupKeepView` で復元する

### フォーマット名グループヘッダー
手帳・カレンダーカテゴリで `sortMode !== 'price'` のとき（品番ソートを含む全ソートで）フォーマット名ごとのグループ区切り行を表示。  
条件: `} else if (catType && sortMode!=='price') {`

### colspan計算
```javascript
const showImg = !!catType;
const colspan = 7 + (showCmp ? 2 : 0) + (showSo ? 1 : 0) + (showImg ? 1 : 0);
```

---

## 開発ブランチ

- **メインブランチ**: `main`（GitHub Pages公開ブランチ）
- **機能ブランチ**: `claude/blissful-bohr-BEv4j`
- 基本的に `main` に直接コミット・プッシュして運用している
- feature branch へのマージは PRELOADED の大きなデータが原因でコンフリクトしやすい

---

## 画像の追加方法

1. 画像を用意（JPEGまたはPNG）
2. ファイル名は品番のハイフン→アンダースコア変換: `DR-MC-416` → `DR_MC_416.jpg`
3. `ranking/images/` に配置
4. 大きい画像はPillowで圧縮する（長辺800px程度・JPEG品質82）:
   ```python
   from PIL import Image
   img = Image.open("input.jpg")
   img.thumbnail((600, 800))
   img.save("output.jpg", "JPEG", quality=82)
   ```
5. **`python3 tools/build-images.py` を実行する**（`ranking/thumbs/` のサムネと `ranking/image-index.js` を作る。画像の追加・差し替え・削除のたびに必須）
6. `images/`・`thumbs/`・`image-index.js` を一緒にコミットし、`ranking/index.html` のバージョン番号を1つ上げる（`image-index.js` のキャッシュ更新のため）
- 一覧・カタログ以外の表示: 一覧の小さな画像は `thumbs/`、クリックの拡大表示とホバーの拡大プレビューは `images/`（原寸）、印刷するカタログ（手帳・カレンダー）は `images/` を使う
- 画像は `.jpg` のみ（アプリは `image-index.js` の一覧にある品番だけを読む。`.png` は対象外）
- **画像名の決まり（2026-10-02 ユーザー指示）**: 品番は基本「英字-数字」。画像名が `CLB1210` のように「英字＋数字」でも `CLB-1210` の品番として登録する（保存名は `CLB_1210.jpg`）。`tools/import-image-zips.py` がこの変換を自動で行う
- **すでに画像がある品番と重複したら、新しい画像に置き換える**（画像を統一するため。`tools/import-image-zips.py` の既定の動作。置き換えずに飛ばしたいときだけ `--keep-existing`）
- **商品マスタにない品番（まだ売れていない商品）の画像も取り込む。** 販売データに登録されたら、アプリが自動でその品番の画像を表示する（`image-index.js` に入っているため）。取り込み時は件数と一覧を報告する

### 楽天の「SKU画像パス」から商品画像を一括で追加する
1. ユーザーが `rakuten-image-dl/index.html`（楽天画像ダウンローダー）に楽天の商品CSV（dl-normal-item）を読み込み、**「🏷 販売ランキング用」にチェック**する（品番は「システム連携用SKU番号」から「商品管理番号」を除いた部分。マスタに無い品番・すでに画像がある品番は除外される）
2. 保存した `download_ranking_images.txt` をMacのターミナルで実行 → 取得・縮小（長辺800px・JPEG品質82）され、約25MBごと（チャットの添付上限30MB対策。スクリプト先頭の `LIMIT_MB`）の `ranking_images_N.zip` ができる（楽天の画像サーバーにはこの環境から届かないため、取得はユーザーのMacで行う）
3. ユーザーがZIPをチャットに添付 → **`python3 tools/import-image-zips.py <zip...>`** で `ranking/images/` に取り込む（すでにある画像は飛ばす。読めない画像・不正な名前は取り込まない）
4. `python3 tools/build-images.py` → `ranking/index.html` のバージョンを上げてコミット（一度に大量にならないよう、ZIP 1〜2個ずつ順にPRを分ける）

### 仕入れ商品アプリ（supplier-ranking）の商品画像・カタログPDF
- 画像は `supplier-ranking/images/`・`thumbs/`・`image-index.js`（自社 ranking とは別。`tools/build-images.py --app supplier-ranking` で作る）。**`supplier-ranking/index.html` を変更・画像を追加したら、`.hd-sub` のバージョン番号を必ず1つ上げる**
- **画像キー（ファイル名）**: 商品番号を小文字にし、`a-z 0-9 _ -` 以外の文字（日本語・`.` など）を `~16進コードポイント~` に置き換える（例: `cocochi-no1-9-no.1-9` → `cocochi-no1-9-no~2e~1-9.jpg`）。`index.html` の `imgKey()`・`tools/import-image-zips.py` の `supplier_key()`・`rakuten-image-dl/index.html` の `supKey()` は同じ規則（変えるときは3か所そろえる）。大文字小文字が違うだけの商品番号は同じ画像になる
- **楽天CSVから一括で追加する手順**（自社と同じ流れ）:
  1. ユーザーが `rakuten-image-dl/index.html` に楽天の商品CSV（dl-normal-item・EL COMMUN楽天店）を読み込み、**「🏭 メーカー販売データ用」にチェック**（`supplier-ranking/data.js` の商品番号と照合。照合の順は システム連携用SKU番号 → 商品管理番号＋SKU管理番号 → SKU管理番号 → 商品管理番号（SKUなしの商品）→ それでも無い商品は `supBase()`（`supplier-ranking/index.html` の `rakutenCodeBase` と同じ規則。変えるときは両方そろえる）で商品番号から導いた商品管理番号のメイン画像。画像はSKU画像パス1を優先し、無ければ商品画像パス1＝メイン画像。メイン画像は商品管理番号ごとに最初の空でない商品画像パス1を使う。CSVの画像パスに店舗名が無いときは「店舗名（URLの一部）」に `elcommun` が自動で入る（違う店舗のCSVなら書き換える）。2026-10-02時点のEL COMMUN楽天店CSVでは 2,141商品中1,280商品に画像が付く＝販売数の約76%。ユニコン・アイトーはCSVに無く、LAIKLE楽天店のCSVが別に必要）。保存した `download_supplier_images.txt` をMacで実行 → `supplier_images_N.zip`（約25MBごと）
  2. ユーザーがZIPを添付 → `python3 tools/import-image-zips.py --app supplier-ranking <zip...>`（自社と同じく、すでにある画像は新しい画像に置き換え。マスタに無い商品番号も取り込み、件数と一覧を報告）
  3. `python3 tools/build-images.py --app supplier-ranking` → `supplier-ranking/index.html` のバージョンを上げてコミット（ZIP 1〜2個ずつPRを分ける）
- カタログPDF（`cgPaginate` / `showCatalog` ほか）は ranking の仕組みを移植したもの。クラス名は表の `.cat-col` 等と区別するため `cg-` で始める。メーカー別表示ではメーカー→カテゴリ、カテゴリ別表示では親カテゴリ→小分類の順にページを分ける。**ranking の手帳・カレンダーと同じ形式（2026-10-02 ユーザー指示）**: 小見出しごとに商品番号順のカード（バッジ＝個数順/金額順（`rankMetric`）の順位）＋カードの後ろの空きに売上ランキング表（TOP10。5種以下は表なし）。表紙（販売数のまとめの表）は付けない。検索結果のカタログも同じ形式。自社商品（ranking）側も同様（`catalogCatBlocks`／`buildCatTopTable`）

---

## 欠品データの更新方法

1. ユーザーがExcel（.xlsx）をアップロード
2. `A列=品番`, `B列=欠品日` の形式（inlineStr形式にも対応済み）
3. または `STOCKOUT` オブジェクトをHTMLに直接追記

---

## 検索同義語辞書（TRANS / TRANS_GROUPS）

- `TRANS`（静的な完全一致辞書）と `TRANS_GROUPS`（相互に同義な語のグループ配列）が `index.html` 内（line ~1728〜）にある
- `TRANS_GROUPS` は `[['英語表記','カタカナ表記','漢字表記', ...], ...]` の形式。各要素は配列内の他の全要素と相互に紐付けられ、`TRANS_N` にマージされる（重複登録してもOK、上書きされない）
- **商品データを新規追加・更新する際、新しいブランド名・モチーフ名・作家名などで検索同義語辞書に登録すべきものがあれば、ユーザーに確認を取らず都度自動で `TRANS_GROUPS` に追加すること**
- 登録ルール:
  - 英語表記とカタカナ表記は必ずセットで登録する（例: `['Bushou','武将','ぶしょう']`）
  - 日本語のひらがな語に対応する一般的な漢字表記がある場合は、検索性向上のため漢字表記も同じグループに含める（例: `['やま','山','mountain']`、`['ねこ','猫']`）
  - 複数の表記揺れがある場合は1グループにまとめて登録する（例: `['Dog','ドッグ','犬','いぬ']`）
  - 既存のTRANS辞書と重複しても害はないので、迷ったら登録する

---

## カテゴリ分類ルール（固定）

以下のルールは変更せず固定で適用すること。

### マクログループ配置（MACRO_GROUPS）
- **マウスパッド** → ステーショナリー（インテリアではない）
- **デスクトップ** → ステーショナリー
- **ネオンライト** → インテリア

### 品番プレフィックスによるカテゴリ分類（CODE_REMAP_CAT）
- `KRT-`（Kerata）→ デスクトップ（マウスパッドではない）
- `SVT-`（suvanto Book Cover）→ ブックカバー
- `PNT-`（PEANUTS NEON LIGHT）→ ネオンライト
- `MPD-`（マウスパッド）→ マウスパッド（※ステーショナリーではなく必ずマウスパッドに分類）
- 商品名に「Book Cover」を含む → ブックカバー

### 保冷バッグ・ランチバッグ系のカテゴリ（2026-10-02 ユーザー指示）
- 「保冷バッグ」という括りは廃止。CLB・LNC・EBA・GRA の保冷バッグ／ランチバッグ系は、**商品名で形・用途別のカテゴリに分ける**（**保冷かどうかでは分けず、同様のものはまとめる**。2026-10-02 ユーザー指示で、細かすぎた15カテゴリを5つに統合）（`ranking/index.html` の `COOL_NAME_RULES` と `coolCatOf`。`resolveCatOf` から呼ばれる）。色違い・新色は同じカテゴリになる
- ランチ関係: **ランチバッグ**（ランチトート(M)/(L)・バスケット・スクエアランチバッグ・スクエアデリバッグ・ロールトップランチバッグ・インナーバッグ・どの規則にも当たらない商品＝受け皿）／**ランチサック・巾着**（ランチサック・巾着・あづま袋）／**ランチポーチ**（保冷ポーチ・おにぎりポーチ）／**ボトルバッグ**（ボトルホルダー・サコッシュボトルホルダーを含む。2026-10-02 ユーザー指示で「ボトルホルダー・ボトルバッグ」から改名）／**ランチクロス**／ランチボックス・箸セット・食器
- **保冷ショッピングバッグ・保冷ショッピングバックパックはファッション（エコバッグの隣）**
- 新しい保冷・ランチ系の形が出たら `COOL_NAME_RULES` に規則と、`CATEGORY_ORDER`・`CAT_ICONS`・`MACRO_GROUPS` への登録を足す（カテゴリ別の合計が変わるので、変更前後の合計が一致することを照合して報告する）
- 販売データ（`data.js`）の生カテゴリは「ランチ関係」のままで変更しない（分類はアプリ側のルールで決まる）

### 販売データの保全ルール（最優先・2026-09-25 制定）
過去に「YYYY-MM-01 ＝ 旧月まとめ」と決めつけた一括処理（2026-06-17 v118）で、シーズン合計データ66,864個と 2026-06-01 の実売上244個が無断・無報告で消え、削除済みだったデータも復活する事故が起きた（2026-09-25 v267 で復元）。二度と起こさないため以下を厳守する。
- **既存の販売データ（`ranking/data.js`・`supplier-ranking/data.js`）は、ユーザーの明示的な指示なしに削除・変換・付け替え・作り直しをしない。** 必要と思われる場合は、対象の件数と中身を示して先に確認を取る
- **データを変更するコミットの前に必ず `python3 tools/check-sales-data.py` を実行する。** origin/main と比べて、既存日付の消失・既存行の変更・既存日付への追加・マスタからの消失が1件でもあれば止まる（exit 1）。ユーザーの指示による変更のときだけ `--allow "理由"` で通し、出力された内容をそのまま報告に含める
- 取り込みの報告には必ずチェック結果（「追加◯日・◯個／既存データの変更0件」）を書く
- 「YYYY-MM-01 の日付＝月まとめ」と決めつけない（実際の1日の売上がある）。日付の形だけで判断せず、中身と前後の合計を確認する
- **シーズン合計データ（日単位ルールの例外・削除禁止）**: `ranking/data.js` の `2017-10-01`〜`2021-01-01` の11日付（店舗名「合計」だけを持つキー）は、発送日の記載が無い時代（GoQ System 導入前）の手帳・カレンダーのシーズン合計（2017年10月始まり〜2021年1月始まりダイアリー、2019〜2021年カレンダー、計66,864個）。日付は各シーズンの代表日。ユーザー了承済みの形式なので、そのまま残す
- 「2021年　1月始まりダイアリー」「2021年　カレンダー」の日次分（2021年2〜7月）は、上記シーズン合計と重複するため入れない（2026-06-02 にユーザー指示で削除済み）

### 集計・比較の数字を扱う変更のルール（2026-09-28 制定）
販売アプリの数字は業務判断に使われる。2026-05〜09 の間、前期合計を「今期の一覧に並ぶ商品の前期分」だけで足し上げていたため（前期にだけ売れた商品が抜ける）、カテゴリ・KPI・Excel の増減率が実際より大きく出ていた（例: 手帳 前期31,825個を14,736個と表示し ▲7% を ▲132%）。v269 / v125 で修正済み。
- 合計・前期比・シェアなどの数字を**新しく出す／計算を変える**ときは、**その数字を data.js から独立に集計した値と突き合わせて一致を確認**してから出す（行の数字を足した値が「期間の合計」になっているとは限らない）
- 比較の「今期」と「前期」は**同じ条件（同じ期間の長さ・同じ対象範囲）**で数えているかを必ず確認する
- 確認した結果（何と何を照合し、何件一致したか）を報告に含める

### 販売データの取り込みルール
- **販売データは必ずYYYY-MM-DD（日単位）で格納すること**（月単位YYYY-MM-01は不可。例外は上記のシーズン合計データのみ）
- Excelの販売日列をそのまま日付キーとして使用する
- `date_ranges` の終了日も最新の販売日に更新する
- デフォルト販売期間は最終更新日から遡って1年間
- **検索コードの補完（手帳・カレンダー必須）**: 取り込み時、品番が `DR-`/`XDR-`/`CAL-` で始まる商品の検索コードが空欄なら、①同バッチの「EL COMMUN 楽天市場店」行の検索コード → ②既存マスタ（`ranking/data.js`）の同品番 → ③同一年度・同一デザインの色違いバリエーション（同じ楽天ページ）の検索コード、の順で必ず補完する
- **DR-/XDR- 品番の統一**: 「X」以外が同一の品番（例: DR-MH-306 と XDR-MH-306）が同一商品を指す場合は **XDR- 側に統一**する。ただし **DR-x 側がマスタに自分の商品として登録されている場合は別商品なので絶対に統一しない**（統一するのは「Xが落ちた行」= DR-x がマスタ未登録で XDR-x のみ存在するケースだけ。item-data / ec-sales-split の統一処理にも同じガードを実装済み）
  - **番号が同じだけの別商品ペアの実例（`XDR_UNIFY_EXCLUDE` にも登録済み）**:
    - DR-WK-638（2025年度版4月始まり Point Kiwi）≠ XDR-WK-638（EC別注2025年版1月始まり ﾜﾝﾎﾟｲﾝﾄﾃﾞﾒﾆｷﾞｽ）
    - DR-MG-593（2027年版 Pieni Sheep）。商品マスタExcelの XDR-MG-593（ﾄｺﾅｯﾂ別注2026年版B6ﾏﾝｽﾘｰﾘﾌｨﾙ）は**実在しない商品の誤登録行**で、2026-09-01にこれへ売上が誤付け替えされる事故が発生→修正済み。マスタExcel側の行削除をユーザーに依頼中
- **`ranking/data.js` の検索コードを追加・更新したら `item-data/search-codes.js`（過去検索コードのスナップショット、item-data と ec-sales-split の両方が読み込む）を再生成し、両アプリの `<script src=...search-codes.js?v=N>` の `?v=N` を上げること**

### 仕入れ商品アプリ（supplier-ranking）のカテゴリ固定ルール
- **スプレーボトル**（TRIのSLOWER PUMP SPRAY BOTTLE等）→ 生活雑貨・アウトドア＞生活雑貨（「ボトル」を含むがマグカップ・カップではない）
- **リングリーフ**（wh-km-rl1001-）→ ステーショナリー＞紙製品・筆記具（ふせんパーツ。アクセサリーではない）
- **BRASSのマグネットリングフック**（sh-305036）→ インテリア小物＞フック・クリップ
- **しおり・ブックマーク** → ステーショナリー＞紙製品・筆記具
- **ぬいぐるみ・マスコット** は独立した親カテゴリ（生活雑貨・アウトドアには入れない）

---

## 注意事項

- `index.html` は2MB超の大きなファイル。`grep -n` で目的の行を探してから `Read` のoffset/limitで部分読み込みすること
- STOCKOUT の `clearStockout()` 関数もHTMLにハードコードされた値を使う。STOCKOUTを更新したら `clearStockout()` も同じ値に更新する必要がある
- ExcelのinlineStr形式（`<is><t>...</t></is>`）は通常のshared strings形式と別処理が必要
- `loadImages()` は削除済み（画像はlocalStorageではなくGitリポジトリから自動読み込み）

---

## UIデザインスキル（社内ツール共通）

アプリの用途・性格に応じて以下の2パターンを使い分けること。

### パターンA: モダンダーク系（参考: `ec-monthly/index.html`）
シンプルなツール・データ変換系に適する。
- **フォント**: Inter + Noto Sans JP（本文）、JetBrains Mono（コード・データ）
- **カラー**: アクセントにパープル系（`#7c3aed` ライト / `#8b5cf6` ダーク）
- **レイアウト**: 中央寄せ max-width 720px、カードベース、グラスモーフィズム（backdrop-filter blur）
- **背景**: 微妙なグラデーショングロウエフェクト（radial-gradient, 疑似要素）
- **ライト/ダークモード**: デフォルトはライト（白背景）。右上にトグルボタン（月/太陽アイコン）。`data-theme="dark"` 属性で切り替え。選択は `localStorage` に保存
- **アニメーション**: ホバー時のスケール・グロウ、メッセージのフェードイン（cubic-bezier(0.4,0,0.2,1)）
- **ボタン**: アクセントカラー背景 + グロウシャドウ、hover時に translateY(-1px)
- **ドロップゾーン**: ダッシュボーダー、ドラッグオーバー時にソリッド化 + グロウ
- **バッジ**: 999px border-radius のピル型、accent-dim背景
- **レスポンシブ**: 600px以下でパディング・フォントサイズ調整

### パターンB: EL COMMUNブランド系（参考: `raffinart-order/index.html`）
業務フロー・ステップ型の操作画面に適する。
- **フォント**: Hiragino Sans / Noto Sans JP / Meiryo
- **カラー**: EL COMMUNオレンジ（`#E85D26`）をプライマリに使用
- **レイアウト**: ヘッダー（白背景 + オレンジ下線）+ カード型ステップUI、max-width 1200px
- **カード**: 白背景、ステップ番号バッジ（オレンジ丸）付きヘッダー
- **ドロップゾーン**: ダッシュボーダー、グレー系背景
- **情報ボックス**: 黄色系（注意）/ 青系（ルール説明）の色分け
- **ボタン**: オレンジ背景、角丸8px

---

## 運用ルール

- アプリを作成・更新した場合、PRは自動でマージしてmainに反映すること（確認不要）
