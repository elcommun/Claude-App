# メーカー商品のみ抽出 — プロパー(自社)除外アプリ

`ec-inventory` の **逆**にあたる単機能アプリ。`index.html` 一枚のシングルページアプリ。
itemdata CSV を取り込み、**プロパー（自社）商品の行を削除して、メーカー商品の行だけを残した CSV** を出力する。

公開URL: `https://elcommun.github.io/Claude-App/ec-maker-only/`

## 入力データ

| ファイル | 必須 | 役割 |
|---------|------|------|
| **itemdata CSV** | 必須 | 全商品の一覧（システム連携用SKU番号・商品名・在庫数）。プロパー抽出アプリ（ec-inventory）と同じ入力。Shift-JIS（CP932）想定。 |

**itemdata を GoQ System からダウンロードする手順**: [GoQ System 在庫連携](https://stock2.goqsystem.com/?nav_id=stockSituation) を開き、「すべて」にチェック → プルダウンで「EL COMMUN 楽天市場店」を選択 → 「CSV出力」ボタンを押す。

## 出力

- アップロードした CSV と **同じ列・同じ並び順をそのまま維持**し、メーカー商品の行だけを残した CSV（`{元ファイル名}_メーカーのみ.csv`）。
- 文字コードは入力に合わせて **Shift-JIS（CP932）**。セルの値は無加工でそのまま出力する。

## 判定ルール（`ec-inventory` / `ec-monthly` 準拠）

- システム連携用SKU番号の**接頭辞**で判定。
  - **メーカー（残す）**: `4on- 8mw- ak- alsk- bm- cocochi- cre- ky- ldw ma- mgt- nm- pb- psm- rio- sh- tp- tri- wf wh-` など。
  - **プロパー（削除）**: `elco-` `cal-` ほか、上記メーカー接頭辞・取り寄せ接頭辞のいずれにも該当しない商品 ＝ 自社商品。
  - **取り寄せ**: `apj-` `rft-` は非在庫・取り寄せ商品。**既定では削除**。チェックボックスで「メーカー扱いで残す」に切り替え可能。
  - **SKU空**: システム連携用SKU番号が空の行は判定不可として除外する。

## メモ

- 価格・原価の突合は行わない（純粋な行フィルタ）。`dl-normal-item` や原価マスタは不要。
- 判定ロジックは `ec-inventory/index.html` の `MAKER_PREFIXES` / `EXCLUDE_PREFIXES` と同一。メーカー接頭辞を増やす場合は両方をそろえること。
- `index.html` を更新したらヘッダーの `v○` を1つ増やすこと。
