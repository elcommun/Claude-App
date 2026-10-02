#!/usr/bin/env python3
"""商品画像の一覧用サムネ(ranking/thumbs/)と画像インデックス(ranking/image-index.js)を作る

  python3 tools/build-images.py            # 足りないサムネだけ作り、インデックスを作り直す
  python3 tools/build-images.py --force    # サムネを全部作り直す
  python3 tools/build-images.py --app supplier-ranking   # メーカー販売データ（supplier-ranking/）の画像

ranking/images/ に画像を追加・差し替え・削除したら、コミット前に必ず実行すること
（実行後は ranking/index.html のバージョン番号も1つ上げる）。

- 原寸: ranking/images/<品番のハイフンをアンダースコア>.jpg
  （supplier-ranking は <商品番号を小文字にし、a-z 0-9 _ - 以外の文字を ~16進~ に置き換えたもの>.jpg。置き換え方は tools/import-image-zips.py の supplier_key）
- サムネ: ranking/thumbs/<同じ名前>.jpg（180x240 の枠に収まる大きさ・JPEG。一覧やカタログ表示で使う軽い画像）
- image-index.js: window.IMG_INDEX = { "DR_MC_416": [原寸の幅, 高さ], ... }
  アプリはこの一覧に無い品番の画像を読みに行かない（404を出さない）。プレビューの大きさも原寸の寸法から決める
"""
import argparse, json, os, sys
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = THUMB_DIR = INDEX_JS = None   # main() で --app に合わせて決める
THUMB_BOX = (180, 240)
THUMB_QUALITY = 80


def make_thumb(src, dst):
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ('RGBA', 'LA', 'P'):
            im = im.convert('RGBA')
            bg = Image.new('RGB', im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert('RGB')
        size = im.size
        im.thumbnail(THUMB_BOX, Image.LANCZOS)
        im.save(dst, 'JPEG', quality=THUMB_QUALITY, optimize=True)
    return size


def main():
    ap = argparse.ArgumentParser(description='商品画像のサムネとインデックスを作る')
    ap.add_argument('--force', action='store_true', help='サムネを全部作り直す')
    ap.add_argument('--app', default='ranking', choices=['ranking', 'supplier-ranking'], help='対象のアプリ（既定: ranking）')
    args = ap.parse_args()
    global IMG_DIR, THUMB_DIR, INDEX_JS
    IMG_DIR = os.path.join(ROOT, args.app, 'images')
    THUMB_DIR = os.path.join(ROOT, args.app, 'thumbs')
    INDEX_JS = os.path.join(ROOT, args.app, 'image-index.js')

    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(THUMB_DIR, exist_ok=True)
    names = sorted(f for f in os.listdir(IMG_DIR) if f.lower().endswith('.jpg'))
    others = sorted(f for f in os.listdir(IMG_DIR)
                    if os.path.isfile(os.path.join(IMG_DIR, f)) and not f.lower().endswith('.jpg') and not f.startswith('.'))
    index, made, bad = {}, 0, []
    for f in names:
        key = f[:-4]
        src, dst = os.path.join(IMG_DIR, f), os.path.join(THUMB_DIR, f)
        try:
            if args.force or not os.path.exists(dst):
                size = make_thumb(src, dst)
                made += 1
            else:
                with Image.open(src) as im:
                    size = im.size
            index[key] = [size[0], size[1]]
        except Exception as e:
            bad.append((f, str(e)))
    # 原寸が無くなったサムネは消す
    removed = 0
    for f in os.listdir(THUMB_DIR):
        if f.endswith('.jpg') and f not in set(names):
            os.remove(os.path.join(THUMB_DIR, f)); removed += 1
    body = json.dumps(index, separators=(',', ':'), sort_keys=True)
    with open(INDEX_JS, 'w', encoding='utf-8') as fh:
        fh.write('// 自動生成: python3 tools/build-images.py（手で編集しない）\nwindow.IMG_INDEX=' + body + ';\n')

    full = sum(os.path.getsize(os.path.join(IMG_DIR, f)) for f in names)
    thumbs = sum(os.path.getsize(os.path.join(THUMB_DIR, f)) for f in names if os.path.exists(os.path.join(THUMB_DIR, f)))
    print(f'[{args.app}] 原寸 {len(names)}枚 {full/1e6:.1f}MB / サムネ {len(index)}枚 {thumbs/1e6:.1f}MB'
          f'（今回作成 {made}枚・削除 {removed}枚）/ image-index.js {os.path.getsize(INDEX_JS)/1e3:.0f}KB')
    if others:
        print(f'⚠️ .jpg 以外のファイル {len(others)}件は対象外です（アプリは .jpg だけ読みます）: {others[:5]}')
    if bad:
        print(f'❌ 変換できなかった画像 {len(bad)}件:')
        for f, e in bad[:10]:
            print('  ', f, e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
