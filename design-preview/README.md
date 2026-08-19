# デザインプレビュー

Photoshop（.psd / .psb）・Illustrator（.ai）・PDF をブラウザ上でそのまま大きくプレビューする閲覧専用ツール。
ファイルはサーバーに送信されず、すべて端末内（JavaScript）で処理される。

## 機能

- ドラッグ&ドロップ / クリック選択（複数ファイル可）
- ファイルタブで切替、✕で削除
- ページ送り（複数アートボードのAI・複数ページのPDF、←→キー対応）
- ズーム（フィット / 10〜400% / 100%）、全画面表示（Escで解除）
- プレビューの保存：JPG（表示中ページ）、PDF（全ページまとめて1ファイル、jsPDF使用）
- PSDはWeb Workerで展開（UIをブロックしない）。埋め込みサムネイルを先に即表示し、高解像度が完成したら自動で差し替え
- 3分ごとの自動更新チェック（`APP_VERSION`、ファイル未読込時のみ自動リロード）

## 対応形式と制限

| 形式 | 描画方法 | 制限 |
|---|---|---|
| .psd / .psb | ag-psd（統合プレビュー画像） | 「互換性を優先」OFF保存はサムネイル表示のみ。CMYK等の特殊カラーモードは非対応（RGBで保存し直す） |
| .ai | pdf.js（PDF互換データ） | 「PDF互換ファイルを作成」OFF保存は表示不可 |
| .pdf | pdf.js | — |

大きな画像は端末のcanvas上限（iOS Safari 約16Mピクセル）に合わせて縮小描画される。

## ライブラリ（lib/ に同梱）

- `ag-psd.min.js` — ag-psd 14.3.6（PSD解析）
- `psd-worker.js` — PSD解析用Web Worker（ag-psdをバックグラウンドで実行）
- `pdf.min.js` / `pdf.worker.min.js` — pdfjs-dist 3.11.174 legacy build（AI/PDF描画）
- `jspdf.min.js` — jsPDF 2.5.2（PDF保存）
