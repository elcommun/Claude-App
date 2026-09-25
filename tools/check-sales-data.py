#!/usr/bin/env python3
"""販売データ保全チェック

git の基準（既定 origin/main）と作業中の data.js を比べ、既存の販売データが
消えたり書き換わったりしていないかを確認する。販売データを変更するコミットの前に必ず実行すること。

  python3 tools/check-sales-data.py                 # 通常の取り込み（追加のみ）の確認
  python3 tools/check-sales-data.py --base HEAD     # 基準を変える
  python3 tools/check-sales-data.py --allow "理由"  # ユーザーの指示による意図した削除・変更を通す

既存データの削除・変更・既存日付への追加が1件でもあれば exit 1 で止まる。
--allow を付けた場合だけ exit 0 になるが、変更内容は必ずすべて表示する。
"""
import argparse, collections, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = ['ranking/data.js', 'supplier-ranking/data.js']


def parse(text):
    i = text.index('PRELOADED')
    return json.JSONDecoder().raw_decode(text[text.index('{', i):])[0]


def load_base(ref, path):
    r = subprocess.run(['git', '-C', ROOT, 'show', f'{ref}:{path}'], capture_output=True)
    if r.returncode != 0:
        return None
    return parse(r.stdout.decode('utf-8'))


def load_work(path):
    with open(os.path.join(ROOT, path), encoding='utf-8') as f:
        return parse(f.read())


def rows_ranking(d):
    """(日付, 店舗, カテゴリ, 品番) -> (個数, 金額)"""
    out = {}
    for dt, stores in d.get('by_store', {}).items():
        for st, cats in stores.items():
            for cat, items in cats.items():
                for code, v in items.items():
                    out[(dt, st, cat, code)] = (v[0], v[1])
    return out


def rows_supplier(d):
    """(日付, 店舗, 商品ID, 個数, 金額) -> 件数（同じ内容の行が複数あり得るため多重集合）"""
    return collections.Counter(tuple(r[:5]) for r in d.get('records', []))


def yen(n):
    return f'¥{n:,}'


def year_totals(pairs):
    y = collections.defaultdict(lambda: [0, 0])
    for dt, q, a in pairs:
        y[dt[:4]][0] += q
        y[dt[:4]][1] += a
    return y


def show_rows(title, items, limit=40):
    if not items:
        return
    print(f'  {title}: {len(items)}件')
    for line in items[:limit]:
        print('    ' + line)
    if len(items) > limit:
        print(f'    …ほか {len(items) - limit}件')


def check_ranking(base, work):
    b, w = rows_ranking(base), rows_ranking(work)
    bd = {k[0] for k in b}
    wd = {k[0] for k in w}
    added_dates = sorted(wd - bd)
    removed_dates = sorted(bd - wd)
    removed = sorted(k for k in b if k not in w)
    changed = sorted(k for k in b if k in w and b[k] != w[k])
    added_old = sorted(k for k in w if k not in b and k[0] in bd)
    fmt = lambda k, v: f'{k[0]} {k[1]} {k[2]} {k[3]} {v[0]}個 {yen(v[1])}'
    print('■ ranking（自社商品）')
    q = sum(w[k][0] for k in w if k[0] in added_dates)
    a = sum(w[k][1] for k in w if k[0] in added_dates)
    print(f'  追加された日付: {len(added_dates)}日'
          + (f'（{added_dates[0]}〜{added_dates[-1]}）{q:,}個 {yen(a)}' if added_dates else ''))
    show_rows('【消えた日付】', removed_dates)
    show_rows('【既存日付から消えた行】', [fmt(k, b[k]) for k in removed])
    show_rows('【既存日付で値が変わった行】',
              [f'{fmt(k, b[k])} → {w[k][0]}個 {yen(w[k][1])}' for k in changed])
    show_rows('【既存日付に追加された行】', [fmt(k, w[k]) for k in added_old])
    removed_codes = sorted(set(base.get('products', {})) - set(work.get('products', {})))
    show_rows('【商品マスタから消えた品番】', removed_codes)
    yb = year_totals((k[0], *v) for k, v in b.items())
    yw = year_totals((k[0], *v) for k, v in w.items())
    print('  年別合計（基準 → 作業中）:')
    for y in sorted(set(yb) | set(yw)):
        x, z = yb.get(y, [0, 0]), yw.get(y, [0, 0])
        mark = '' if x == z else f'   {z[0] - x[0]:+,}個'
        print(f'    {y}: {x[0]:>7,}個 → {z[0]:>7,}個{mark}')
    return len(removed_dates) + len(removed) + len(changed) + len(added_old) + len(removed_codes)


def check_supplier(base, work):
    b, w = rows_supplier(base), rows_supplier(work)
    bd = {k[0] for k in b}
    wd = {k[0] for k in w}
    added_dates = sorted(wd - bd)
    removed_dates = sorted(bd - wd)
    removed = sorted((k, n - w.get(k, 0)) for k, n in b.items() if n > w.get(k, 0))
    added_old = sorted((k, n - b.get(k, 0)) for k, n in w.items() if k[0] in bd and n > b.get(k, 0))
    fmt = lambda k, n: f'{k[0]} {k[1]} {k[2]} {k[3]}個 {yen(k[4])}' + (f' ×{n}' if n > 1 else '')
    print('■ supplier-ranking（メーカー販売データ）')
    q = sum(k[3] * n for k, n in w.items() if k[0] in added_dates)
    print(f'  追加された日付: {len(added_dates)}日'
          + (f'（{added_dates[0]}〜{added_dates[-1]}）{q:,}個' if added_dates else ''))
    show_rows('【消えた日付】', removed_dates)
    show_rows('【既存日付から消えた行】', [fmt(k, n) for k, n in removed])
    show_rows('【既存日付に追加された行】', [fmt(k, n) for k, n in added_old])
    removed_pids = sorted(set(base.get('products', {})) - set(work.get('products', {})))
    show_rows('【商品マスタから消えた商品】', removed_pids)
    return len(removed_dates) + len(removed) + len(added_old) + len(removed_pids)


def main():
    ap = argparse.ArgumentParser(description='販売データ保全チェック')
    ap.add_argument('--base', default='origin/main', help='比較の基準（git の ref）')
    ap.add_argument('--allow', metavar='理由', help='ユーザーの指示による意図した削除・変更を通す')
    args = ap.parse_args()

    problems = 0
    for path, fn in zip(TARGETS, (check_ranking, check_supplier)):
        base = load_base(args.base, path)
        if base is None:
            print(f'■ {path}: 基準 {args.base} に無いため比較しません')
            continue
        problems += fn(base, load_work(path))
        print()

    if problems == 0:
        print('✅ 既存データの削除・変更: 0件')
        return 0
    if args.allow:
        print(f'⚠️  既存データの削除・変更 {problems}件を許可しました（理由: {args.allow}）')
        print('   上の内容をそのままユーザーへの報告に含めること。')
        return 0
    print(f'❌ 既存データの削除・変更が {problems}件あります。コミットを中止してください。')
    print('   ユーザーの明示的な指示がある場合のみ、--allow "理由" を付けて再実行すること。')
    return 1


if __name__ == '__main__':
    sys.exit(main())
