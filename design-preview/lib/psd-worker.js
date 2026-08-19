// PSD解析ワーカー：メインスレッドをブロックせずにag-psdで統合画像を展開する。
// 統合画像はファイル末尾の独立セクションにあるため、レイヤーセクションを
// 取り除いた最小構成のPSDを作ってから渡す（レイヤー数に関係なく一定時間で解析できる）。
importScripts('ag-psd.min.js');

// ワーカーにはdocumentがないため、ag-psdのcanvas/ImageData生成関数を登録する
// （useImageData指定時に実際に使われるのはcreateImageDataのみ）
agPsd.initializeCanvas(
  function (w, h) {
    if (typeof OffscreenCanvas !== 'undefined') return new OffscreenCanvas(w, h);
    throw new Error('Canvas not available in worker');
  },
  undefined,
  function (w, h) { return new ImageData(w, h); }
);

// ヘッダー＋カラーモードデータ＋空リソース＋空レイヤー＋統合画像データ、の最小PSDを構築。
// レイヤー情報（テキストエンジンデータ等）の解析を丸ごとスキップできる。
function stripLayers(buf) {
  const v = new DataView(buf);
  if (v.getUint32(0) !== 0x38425053) return buf;   // '8BPS' でなければそのまま
  const version = v.getUint16(4);                   // 1=PSD, 2=PSB
  const colorEnd = 26 + 4 + v.getUint32(26);        // ヘッダー＋カラーモードデータ末尾
  let p = colorEnd;
  p += 4 + v.getUint32(p);                          // image resources を読み飛ばす
  const lenSize = version === 2 ? 8 : 4;
  const layerLen = version === 2 ? Number(v.getBigUint64(p)) : v.getUint32(p);
  const compStart = p + lenSize + layerLen;
  if (!(layerLen >= 0) || compStart + 2 > buf.byteLength) return buf;
  const head = new Uint8Array(buf, 0, colorEnd);
  const comp = new Uint8Array(buf, compStart);
  // 空のimage resources(4B)と空のレイヤーセクション(lenSize)はゼロ初期化のまま使う
  const out = new Uint8Array(colorEnd + 4 + lenSize + comp.length);
  out.set(head, 0);
  out.set(comp, colorEnd + 4 + lenSize);
  return out.buffer;
}

self.onmessage = function (e) {
  const id = e.data.id, buf = e.data.buf;
  try {
    let data = buf;
    try { data = stripLayers(buf); } catch (err) { data = buf; }
    const psd = agPsd.readPsd(data, {
      skipLayerImageData: true, skipThumbnail: true,
      useImageData: true, throwForMissingFeatures: false
    });
    const img = psd.imageData;
    if (img && img.data) {
      self.postMessage(
        { id, type: 'full', width: psd.width, height: psd.height, imgW: img.width, imgH: img.height, data: img.data.buffer },
        [img.data.buffer]
      );
    } else {
      self.postMessage({ id, type: 'full', width: psd.width, height: psd.height, data: null });
    }
  } catch (err) {
    self.postMessage({ id, type: 'error', message: String((err && err.message) || err) });
  }
};
