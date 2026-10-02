#!/usr/bin/env python3
"""楽天画像ダウンローダー（販売ランキング用モード）で作った ranking_images_*.zip を ranking/images/ に取り込む

  python3 tools/import-image-zips.py ranking_images_1.zip ranking_images_2.zip ...
  python3 tools/import-image-zips.py --overwrite  x.zip    # すでにある画像も置き換える（既定は飛ばす）

- ファイル名は次のどれかを受け付け、すべて「品番のハイフンをアンダースコアにしたもの.jpg」（大文字）で保存する
    ・CLB_1210.jpg（すでにその形）
    ・CLB-1210.jpg（ハイフン）
    ・CLB1210.jpg（英字＋数字。品番は基本「英字-数字」なので「CLB-1210」として登録する）
    ・DR_MC_416.jpg / DR-MC-416.jpg（区切りがある複数セグメントの品番）
  ※ 区切りの無い「英字＋数字」以外（例: 5ACE001 のように数字が先頭にくるもの）は解釈できないので取り込まない
- すでに ranking/images/ にある品番は飛ばす（--overwrite のときだけ置き換える）
- 画像として読めないもの・JPEGでないものは取り込まない。長辺が800pxを超えるものは800pxに縮小する
- 品番が商品マスタ（ranking/data.js）に無いものは取り込むが、件数と一覧を必ず表示する
- 取り込んだあとは python3 tools/build-images.py を実行し、ranking/index.html のバージョンを上げること
"""
import argparse, io, json, os, re, sys, zipfile
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, 'ranking', 'images')
EXT_RE = re.compile(r'\.jpe?g$', re.I)


def code_key(stem):
    """ファイル名（拡張子なし）→ 保存名（品番のハイフンをアンダースコアにしたもの）。解釈できなければ None"""
    s = stem.strip().upper().replace('-', '_')
    m = re.fullmatch(r'([A-Z]+)(\d+)', s)          # CLB1210 → CLB_1210（品番は基本「英字-数字」）
    if m:
        return m.group(1) + '_' + m.group(2)
    if re.fullmatch(r'[A-Z0-9]+(_[A-Z0-9]+)+', s):   # CLB_1210 / DR_MC_416 / 5A_CE_114
        return s
    return None
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
    added, skipped, bad, resized, unknown, badname, renamed, conflict = [], [], [], [], [], [], [], []
    seen = {}
    for zp in args.zips:
        with zipfile.ZipFile(zp) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                base = os.path.basename(info.filename)
                if not base or base.startswith('.') or info.filename.startswith('__MACOSX'):
                    continue
                if not EXT_RE.search(base):
                    badname.append(info.filename)
                    continue
                key = code_key(os.path.splitext(base)[0])
                if not key:
                    badname.append(info.filename)
                    continue
                if os.path.splitext(base)[0] != key:
                    renamed.append((base, key))
                if key in seen:                       # 同じ品番になる画像が複数ある（先に出たものを使う）
                    conflict.append((base, seen[key]))
                    continue
                orig = base
                base = key + '.jpg'
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
                seen[key] = orig                      # 取り込めたものだけを「使用済み」にする（読めない画像のあとに正常な同名画像があれば、そちらを使う）
                added.append(base)
                if base[:-4] not in master:
                    unknown.append(base[:-4])

    total = sum(os.path.getsize(os.path.join(IMG_DIR, f)) for f in added)
    print(f'取り込み {len(added)}枚（{total/1e6:.1f}MB）／ すでにあるため飛ばした {len(skipped)}枚'
          f'／ 縮小した {len(resized)}枚／ 読めなかった {len(bad)}枚／ 名前が不正 {len(badname)}件／ 同じ品番の重複 {len(conflict)}件')
    if renamed:
        print(f'ℹ️ 名前を品番の形に直した {len(renamed)}件（例: ' + '、'.join(f'{a}→{b}.jpg' for a, b in renamed[:3]) + '）')
    if skipped:
        print(f'ℹ️ すでに画像がある品番（飛ばした）: ' + ', '.join(skipped))
    for a, b in conflict[:10]:
        print('❌ 同じ品番の重複:', a, '（先に取り込んだ', b, 'を使用）')
    if unknown:
        print(f'⚠️ 商品マスタに無い品番 {len(unknown)}件: {unknown[:10]}')
    for f, e in bad[:10]:
        print('❌', f, e)
    for f in badname[:10]:
        print('❌ 名前が不正:', f)
    print('次: python3 tools/build-images.py を実行 → ranking/index.html のバージョンを上げる')
    return 1 if (bad or badname or conflict) else 0


if __name__ == '__main__':
    sys.exit(main())
