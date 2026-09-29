#!/usr/bin/env python3
"""楽天画像ダウンローダー（販売ランキング用モード）で作った ranking_images_*.zip を ranking/images/ に取り込む

  python3 tools/import-image-zips.py ranking_images_1.zip ranking_images_2.zip ...
  python3 tools/import-image-zips.py --overwrite  x.zip    # すでにある画像も置き換える（既定は飛ばす）

- ファイル名は「品番のハイフンをアンダースコアにしたもの.jpg」だけを受け付ける（英数字とアンダースコア）
- すでに ranking/images/ にある品番は飛ばす（--overwrite のときだけ置き換える）
- 画像として読めないもの・JPEGでないものは取り込まない。長辺が800pxを超えるものは800pxに縮小する
- 品番が商品マスタ（ranking/data.js）に無いものは取り込むが、件数と一覧を必ず表示する
- 取り込んだあとは python3 tools/build-images.py を実行し、ranking/index.html のバージョンを上げること
"""
import argparse, io, json, os, re, sys, zipfile
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, 'ranking', 'images')
NAME_RE = re.compile(r'^[A-Za-z0-9_]+\.jpg$')
MAX_SIDE = 800


def master_keys():
    t = open(os.path.join(ROOT, 'ranking', 'data.js'), encoding='utf-8').read()
    d = json.JSONDecoder().raw_decode(t[t.index('{'):])[0]
    return {c.replace('-', '_') for c in d['products']}


def main():
    ap = argparse.ArgumentParser(description='画像ZIPを ranking/images/ に取り込む')
    ap.add_argument('zips', nargs='+')
    ap.add_argument('--overwrite', action='store_true', help='すでにある画像も置き換える')
    args = ap.parse_args()

    master = master_keys()
    added, skipped, bad, resized, unknown, badname = [], [], [], [], [], []
    for zp in args.zips:
        with zipfile.ZipFile(zp) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                base = os.path.basename(info.filename)
                if base.startswith('.') or base.startswith('__MACOSX'):
                    continue
                if not NAME_RE.match(base):
                    badname.append(info.filename)
                    continue
                dst = os.path.join(IMG_DIR, base)
                if os.path.exists(dst) and not args.overwrite:
                    skipped.append(base)
                    continue
                try:
                    im = Image.open(io.BytesIO(zf.read(info)))
                    im.load()
                    im = ImageOps.exif_transpose(im).convert('RGB')
                except Exception as e:
                    bad.append((base, str(e)[:60]))
                    continue
                if max(im.size) > MAX_SIDE:
                    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
                    resized.append(base)
                im.save(dst, 'JPEG', quality=82, optimize=True)
                added.append(base)
                if base[:-4] not in master:
                    unknown.append(base[:-4])

    total = sum(os.path.getsize(os.path.join(IMG_DIR, f)) for f in added)
    print(f'取り込み {len(added)}枚（{total/1e6:.1f}MB）／ すでにあるため飛ばした {len(skipped)}枚'
          f'／ 縮小した {len(resized)}枚／ 読めなかった {len(bad)}枚／ 名前が不正 {len(badname)}件')
    if unknown:
        print(f'⚠️ 商品マスタに無い品番 {len(unknown)}件: {unknown[:10]}')
    for f, e in bad[:10]:
        print('❌', f, e)
    for f in badname[:10]:
        print('❌ 名前が不正:', f)
    print('次: python3 tools/build-images.py を実行 → ranking/index.html のバージョンを上げる')
    return 1 if (bad or badname) else 0


if __name__ == '__main__':
    sys.exit(main())
