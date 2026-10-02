#!/usr/bin/env python3
"""楽天画像ダウンローダー（販売ランキング用モード）で作った ranking_images_*.zip を ranking/images/ に取り込む

  python3 tools/import-image-zips.py ranking_images_1.zip ranking_images_2.zip ...
  python3 tools/import-image-zips.py --keep-existing x.zip  # すでにある画像は置き換えずに飛ばす（既定は新しい画像に置き換える）
  python3 tools/import-image-zips.py --app supplier-ranking x.zip  # メーカー販売データ（supplier-ranking/）の画像

- ファイル名は次のどれかを受け付け、すべて「品番のハイフンをアンダースコアにしたもの.jpg」（大文字）で保存する
    ・CLB_1210.jpg（すでにその形）
    ・CLB-1210.jpg（ハイフン）
    ・CLB1210.jpg（英字＋数字。品番は基本「英字-数字」なので「CLB-1210」として登録する）
    ・DR_MC_416.jpg / DR-MC-416.jpg（区切りがある複数セグメントの品番）
  ※ 区切りの無い「英字＋数字」以外（例: 5ACE001 のように数字が先頭にくるもの）は解釈できないので取り込まない
- すでに ranking/images/ にある品番は **新しい画像に置き換える**（画像を統一するため。2026-10-02 ユーザー指示）。
  置き換えた品番は件数と一覧を表示する（中身が同じ画像は「変更なし」として数える）。--keep-existing を付けると置き換えずに飛ばす。
  置き換えた品番のサムネは削除するので、build-images.py が新しい画像から作り直す
- 画像として読めないもの・JPEGでないものは取り込まない。長辺が800pxを超えるものは800pxに縮小する
- 品番が商品マスタ（ranking/data.js）に無いもの（まだ売れていない商品）も取り込む。件数と一覧は必ず表示する。
  販売データに登録されたら、アプリが自動でその品番の画像を表示する（画像の一覧 image-index.js に入っているため）
- メーカー販売データ（--app supplier-ranking）: ZIP内のファイル名は rakuten-image-dl の「メーカー販売データ用」が付けたもの
  （商品番号を小文字にし、a-z 0-9 _ - 以外の文字を ~16進コードポイント~ に置き換えた名前。例: cocochi-no1-9-no.1-9 → cocochi-no1-9-no~2e~1-9）。
  そのまま supplier-ranking/images/ に保存する（名前が規則に合わないものは取り込まない）。マスタ = supplier-ranking/data.js の商品番号
- 取り込んだあとは python3 tools/build-images.py（メーカーは --app supplier-ranking を付ける）を実行し、ranking/index.html のバージョンを上げること
"""
import argparse, io, json, os, re, sys, zipfile
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = THUMB_DIR = None   # main() で --app に合わせて決める
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


def supplier_key(code):
    """メーカー販売データの商品番号 → 画像のファイル名（拡張子なし）。小文字にし、a-z 0-9 _ - 以外は ~16進コードポイント~ にする
    （アプリ側の imgKey と同じ規則。日本語や . を含む商品番号でもファイル名にできる）"""
    return ''.join(c if re.fullmatch(r'[a-z0-9_-]', c) else '~%x~' % ord(c) for c in code.strip().lower())


def supplier_stem_key(stem):
    """ZIP内のファイル名（拡張子なし）が supplier_key の規則に合っていればそのまま返す。合わなければ None"""
    s = stem.strip()
    return s if re.fullmatch(r'[a-z0-9_~-]+', s) else None


def master_keys(app='ranking'):
    if app == 'supplier-ranking':
        t = open(os.path.join(ROOT, 'supplier-ranking', 'data.js'), encoding='utf-8').read()
        d = json.JSONDecoder().raw_decode(t[t.index('{', t.index('PRELOADED')):])[0]
        return {supplier_key(p[3]) for p in d['products'].values() if p[3]}
    t = open(os.path.join(ROOT, 'ranking', 'data.js'), encoding='utf-8').read()
    d = json.JSONDecoder().raw_decode(t[t.index('{'):])[0]
    return {c.replace('-', '_') for c in d['products']}


def main():
    ap = argparse.ArgumentParser(description='画像ZIPを ranking/images/ に取り込む')
    ap.add_argument('zips', nargs='+')
    ap.add_argument('--keep-existing', action='store_true', help='すでにある画像は置き換えずに飛ばす（既定は置き換える）')
    ap.add_argument('--app', default='ranking', choices=['ranking', 'supplier-ranking'], help='対象のアプリ（既定: ranking）')
    args = ap.parse_args()
    global IMG_DIR, THUMB_DIR
    IMG_DIR = os.path.join(ROOT, args.app, 'images')
    THUMB_DIR = os.path.join(ROOT, args.app, 'thumbs')
    os.makedirs(IMG_DIR, exist_ok=True)
    to_key = supplier_stem_key if args.app == 'supplier-ranking' else code_key

    master = master_keys(args.app)
    added, skipped, bad, resized, unknown, badname, renamed, conflict, replaced, same = [], [], [], [], [], [], [], [], [], []
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
                key = to_key(os.path.splitext(base)[0])
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
                existed = os.path.exists(dst)
                if existed and args.keep_existing:
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
                buf = io.BytesIO()
                im.save(buf, 'JPEG', quality=82, optimize=True)
                data = buf.getvalue()
                seen[key] = orig                      # 取り込めたものだけを「使用済み」にする（読めない画像のあとに正常な同名画像があれば、そちらを使う）
                if existed:
                    with open(dst, 'rb') as fh:
                        if fh.read() == data:         # 中身が同じ（同じZIPをもう一度取り込んだときなど）→ 何もしない
                            same.append(base)
                            continue
                    replaced.append(base)
                    th = os.path.join(THUMB_DIR, base)   # 古いサムネは消す（build-images.py が新しい画像から作り直す）
                    if os.path.exists(th):
                        os.remove(th)
                with open(dst, 'wb') as fh:
                    fh.write(data)
                added.append(base)
                if base[:-4] not in master:
                    unknown.append(base[:-4])

    total = sum(os.path.getsize(os.path.join(IMG_DIR, f)) for f in added)
    print(f'取り込み {len(added)}枚（{total/1e6:.1f}MB。うち新しい画像への置き換え {len(replaced)}枚）／ 同じ画像で変更なし {len(same)}枚／ 飛ばした {len(skipped)}枚'
          f'／ 縮小した {len(resized)}枚／ 読めなかった {len(bad)}枚／ 名前が不正 {len(badname)}件／ 同じ品番の重複 {len(conflict)}件')
    if renamed:
        print(f'ℹ️ 名前を品番の形に直した {len(renamed)}件（例: ' + '、'.join(f'{a}→{b}.jpg' for a, b in renamed[:3]) + '）')
    if replaced:
        print(f'ℹ️ 新しい画像に置き換えた品番 {len(replaced)}件: ' + ', '.join(replaced))
    if skipped:
        print(f'ℹ️ すでに画像がある品番（--keep-existing のため飛ばした）: ' + ', '.join(skipped))
    for a, b in conflict[:10]:
        print('❌ 同じ品番の重複:', a, '（先に取り込んだ', b, 'を使用）')
    if unknown:
        print(f'⚠️ 商品マスタに無い品番 {len(unknown)}件: {unknown[:10]}')
    for f, e in bad[:10]:
        print('❌', f, e)
    for f in badname[:10]:
        print('❌ 名前が不正:', f)
    print('次: python3 tools/build-images.py' + (' --app supplier-ranking' if args.app == 'supplier-ranking' else '') + ' を実行 → ' + args.app + '/index.html のバージョンを上げる')
    return 1 if (bad or badname or conflict) else 0


if __name__ == '__main__':
    sys.exit(main())
