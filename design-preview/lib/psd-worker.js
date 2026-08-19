// PSD解析ワーカー：メインスレッドをブロックせずにag-psdでPSDを展開する。
// 1回目のクイック解析でサムネイル（JPEG）を先に返し、2回目で統合画像を返す。
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

self.onmessage = function (e) {
  const id = e.data.id, buf = e.data.buf;
  try {
    let hasThumb = false;
    try {
      const quick = agPsd.readPsd(buf, {
        skipCompositeImageData: true, skipLayerImageData: true,
        useImageData: true, useRawThumbnail: true, throwForMissingFeatures: false
      });
      const t = quick.imageResources && quick.imageResources.thumbnailRaw;
      hasThumb = !!(t && t.data && t.data.length);
      self.postMessage({ id, type: 'quick', width: quick.width, height: quick.height, jpeg: hasThumb ? t.data : null });
    } catch (err) {
      self.postMessage({ id, type: 'quick', width: 0, height: 0, jpeg: null });
    }
    const psd = agPsd.readPsd(buf, {
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
      self.postMessage({ id, type: 'full', width: psd.width, height: psd.height, data: null, hasThumb });
    }
  } catch (err) {
    self.postMessage({ id, type: 'error', message: String((err && err.message) || err) });
  }
};
