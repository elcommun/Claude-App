# EL COMMUN EC 販売ランキングアプリ — 開発メモ

## アプリ概要

`ranking/index.html` 一枚のシングルページアプリ（約2,100行）。  
EC（楽天・Amazon等）の販売データをExcelでインポートし、カテゴリ別・商品別の売上ランキングを表示する。

**URL（GitHub Pages）**: `elcommun/Claude-App` の `main` ブランチで公開。

---

## バージョン番号（重要）

- ヘッダーの `.hd-sub` 内に `<span>v77</span>` のようなバージョン番号がある（line ~330）
- ページ末尾のJS（line ~2524〜）が定期的にこの番号を比較し、サーバー側の番号が大きければ自動リロードしてキャッシュを更新する仕組み
- **`index.html` を変更してコミット・プッシュするたびに、このバージョン番号を必ず1つ増やすこと**
- これを忘れると、PWA（ホーム画面に追加したアプリ）やブラウザキャッシュが更新されず、ユーザーの端末に変更が反映されない

---

## ファイル構成

```
ranking/
  index.html          ← メインファイル（HTML + CSS + JS すべて含む）
  images/             ← 商品画像（手帳・カレンダーのみ）
    DR_MC_416.jpg     ← 品番のハイフンをアンダースコアに変換したファイル名
    DR_MC_417.jpg
    ...（DR_MC_416〜434.jpg、計19枚）
    .gitkeep
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
4. 大きい画像はPillowで圧縮してからコミット:
   ```python
   from PIL import Image
   img = Image.open("input.jpg")
   img.thumbnail((600, 800))
   img.save("output.jpg", "JPEG", quality=82)
   ```

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

## 注意事項

- `index.html` は2MB超の大きなファイル。`grep -n` で目的の行を探してから `Read` のoffset/limitで部分読み込みすること
- STOCKOUT の `clearStockout()` 関数もHTMLにハードコードされた値を使う。STOCKOUTを更新したら `clearStockout()` も同じ値に更新する必要がある
- ExcelのinlineStr形式（`<is><t>...</t></is>`）は通常のshared strings形式と別処理が必要
- `loadImages()` は削除済み（画像はlocalStorageではなくGitリポジトリから自動読み込み）

---

## UIデザインスキル（社内ツール共通）

新しい社内ツールを作成する際は、以下のデザインパターンを適用すること（`ec-monthly/index.html` が参考実装）。

### デザイン仕様
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
