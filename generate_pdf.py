#!/usr/bin/env python3
"""Generate a styled meeting-minutes PDF — contemporary Japanese chic."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ── Fonts ────────────────────────────────────────────────────────────────────
pdfmetrics.registerFont(TTFont("NotoSansJP",      "/tmp/NotoSansJP-Regular.ttf"))
pdfmetrics.registerFont(TTFont("NotoSansJP-Bold", "/tmp/NotoSansJP-Bold.ttf"))
registerFontFamily("NotoSansJP",
                   normal="NotoSansJP", bold="NotoSansJP-Bold",
                   italic="NotoSansJP", boldItalic="NotoSansJP-Bold")
F  = "NotoSansJP"
FB = "NotoSansJP-Bold"

# ── Color palette  ──────────────────────────────────────────────────────────
# "Soft Indigo × Dusty Rose" — 2025 trend
C_INK       = colors.HexColor("#1C1830")  # deep indigo-navy  (H2 bg, headings)
C_PLUM      = colors.HexColor("#4A3B6E")  # medium plum       (H3 text, table hdr)
C_LILAC     = colors.HexColor("#8B76BE")  # lilac             (left bars, accents)
C_ROSE      = colors.HexColor("#C47A96")  # dusty rose        (accent lines, ◆)
C_MAUVE     = colors.HexColor("#E8C4D4")  # light mauve       (highlight row)
C_LAVENDER  = colors.HexColor("#EDE8F7")  # very light lavender (H3 bg, alt rows)
C_MIST      = colors.HexColor("#F7F4FD")  # near-white lavender (title bg)
C_BORDER    = colors.HexColor("#D4C8E8")  # soft purple border
C_TEXT      = colors.HexColor("#1C1830")  # body text
C_TEXT2     = colors.HexColor("#6B5F8A")  # secondary / muted text

# ── Layout ───────────────────────────────────────────────────────────────────
W, H       = A4
ML = MR    = 20 * mm
MT = MB    = 18 * mm
BW         = W - ML - MR          # body width

# ── Styles ───────────────────────────────────────────────────────────────────
def styles():
    _s = {}

    _s["title"] = ParagraphStyle(
        "title", fontName=FB, fontSize=19, leading=28,
        textColor=C_INK, alignment=TA_CENTER,
        spaceAfter=2, spaceBefore=0,
    )
    _s["subtitle"] = ParagraphStyle(
        "subtitle", fontName=F, fontSize=9.5, leading=14,
        textColor=C_TEXT2, alignment=TA_CENTER,
        spaceAfter=0,
    )
    _s["deco"] = ParagraphStyle(
        "deco", fontName=F, fontSize=9, leading=14,
        textColor=C_LILAC, alignment=TA_CENTER,
        spaceAfter=0,
    )
    _s["h2"] = ParagraphStyle(
        "h2", fontName=FB, fontSize=12, leading=18,
        textColor=colors.white, alignment=TA_LEFT,
        spaceBefore=0, spaceAfter=0,
        leftIndent=0, rightIndent=0,
    )
    _s["h3"] = ParagraphStyle(
        "h3", fontName=FB, fontSize=10.5, leading=16,
        textColor=C_PLUM, alignment=TA_LEFT,
        spaceBefore=0, spaceAfter=0,
        leftIndent=0,
    )
    _s["label"] = ParagraphStyle(
        "label", fontName=FB, fontSize=9, leading=15,
        textColor=C_INK, alignment=TA_LEFT,
        spaceBefore=4, spaceAfter=1,
        leftIndent=0,
    )
    _s["body"] = ParagraphStyle(
        "body", fontName=F, fontSize=9, leading=16,
        textColor=C_TEXT, alignment=TA_JUSTIFY,
        spaceBefore=0, spaceAfter=5,
        leftIndent=0, rightIndent=0,
    )
    _s["note"] = ParagraphStyle(
        "note", fontName=F, fontSize=8, leading=13,
        textColor=C_TEXT2, alignment=TA_LEFT,
        spaceBefore=1, spaceAfter=3,
        leftIndent=0,
    )
    _s["th"] = ParagraphStyle(
        "th", fontName=FB, fontSize=8.5, leading=13,
        textColor=colors.white, alignment=TA_CENTER,
    )
    _s["td"] = ParagraphStyle(
        "td", fontName=F, fontSize=8.5, leading=13,
        textColor=C_TEXT, alignment=TA_LEFT,
    )
    _s["td_c"] = ParagraphStyle(
        "td_c", fontName=F, fontSize=8.5, leading=13,
        textColor=C_TEXT, alignment=TA_CENTER,
    )
    _s["footer"] = ParagraphStyle(
        "footer", fontName=F, fontSize=8.5, leading=13,
        textColor=C_TEXT2, alignment=TA_CENTER,
    )
    return _s


# ── Component builders ────────────────────────────────────────────────────────

def title_block(S):
    rows = [
        [Paragraph("議事録：社内会議", S["title"])],
        [Paragraph("◆　◆　◆", S["deco"])],
        [Paragraph("2026年5月22日（金）　本社 会議室", S["subtitle"])],
    ]
    tbl = Table(rows, colWidths=[BW])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_MIST),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("LINEABOVE",     (0, 0), (-1,  0),  3, C_PLUM),
        ("LINEBELOW",     (0, -1), (-1, -1), 2, C_ROSE),
    ]))
    return tbl


def h2(text, S):
    """Dark banner with lilac left stripe."""
    p = Paragraph(text, S["h2"])
    inner = Table([[p]], colWidths=[BW - 5*mm])
    inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_INK),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))

    stripe = Table([[""]], colWidths=[5*mm])
    stripe.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_LILAC),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))

    outer = Table([[stripe, inner]], colWidths=[5*mm, BW - 5*mm])
    outer.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return outer


def h3(text, S):
    """Light lavender bg with 3pt lilac left border."""
    p = Paragraph(text, S["h3"])
    tbl = Table([[p]], colWidths=[BW])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_LAVENDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("LINEBEFORE",    (0, 0), (0,  -1),  3, C_LILAC),
    ]))
    return tbl


def item_label(txt, S):
    """Section item label with rose diamond bullet."""
    return Paragraph(
        f'<font color="#C47A96">◆</font>  <b>{txt}</b>',
        S["label"]
    )


def divider_rose():
    """Thin double-line divider: lilac over rose."""
    return [
        HRFlowable(width=BW, thickness=1.2, color=C_LILAC, spaceAfter=1),
        HRFlowable(width=BW, thickness=0.5, color=C_ROSE),
    ]


def schedule_table(S):
    headers = ["月日", "イベント / 業務内容", "備考"]
    rows_data = [
        ["5/26〜28",  "大阪展示会（設営26日、会期27〜28日）",               "社長は夜の会合のみ出席"],
        ["6/3〜4",    "鈴木海文堂 展示会（設営3日、会期4日）",              ""],
        ["6/9〜12",   "福岡設営＆展示会（9日設営、10〜11日会期）",          ""],
        ["6/10〜14",  "文具女子博（10日午後開催〜14日）",                    "デザイン部見学調整"],
        ["6/9〜12",   "インテリアライフスタイル（食器・9日並び、10〜12日）","11日にメンバー交代あり"],
        ["6/9〜12",   "日本橋3丁目（9日搬入、10〜12日会期）",               ""],
        ["6/18〜19",  "日設展示会（19日のみ）",                              ""],
        ["6/24〜25",  "ニコフェス（ISOT併催・リード）",                      "春手帳の企画に絡めて視察"],
        ["7/7〜9",    "MDS商談会（東京7〜9日、設営7日、会期7・8・9日）",    ""],
        ["7/21〜24",  "大原展示会（設営21日、会期22〜23日）",                "関西メンバー中心、社長は大原出席"],
        ["7/21〜26",  "文具女子博 mini京都（21日設営、土日まで開催）",       ""],
        ["8/4〜7",    "ラップス（北海道・搬入4日、会期5〜7日）",            ""],
        ["8/8〜16",   "お盆休み（9連休）",                                   "全社（※10日出勤は要調整、辻氏は韓国渡航予定）"],
        ["8/24〜25",  "名古屋商談会（朝4:30集合の早朝対応）",               "朝に強いメンバーで対応"],
        ["8/29〜9/14","ニューヨーク出張（オブジェクト展含む）",              "帰国後そのまま北海道等の連携あり"],
        ["9/1〜4",    "合同展示会（モンタージュ / エビス）",                 "インテリア・新商品・食器担当"],
        ["9/8〜10",   "関西展示会（8日設営、9〜10日会期）",                  "関西担当"],
        ["9/10〜13",  "台湾イベント（10日設営、11〜13日会期）",              ""],
        ["9/19〜23",  "シルバーウィーク（5連休）",                           "全社"],
        ["10/2〜4",   "森の文学・文博（3〜4日開催、日曜まで）",              ""],
        ["10/9〜11",  "紙博（東京・平和島/昭和島・9日設営、10〜11日）",      ""],
        ["11/4〜9",   "長沢商談会（4日設営、5〜9日開催、月曜まで）",        ""],
        ["11/11〜13", "メルクロス（大阪・コントラクト系設備商談会、出展料11万）","住宅設備、施工・施工業者対応"],
        ["11/14〜15", "フィールドスタイル（名古屋・アウトドア物販イベント）","キャンプグッズ担当中心"],
        ["12/15〜21", "文具女子博 横浜（15日設営、21日まで開催）",           "総出対応"],
    ]

    cw = [BW * 0.18, BW * 0.57, BW * 0.25]
    data = [[Paragraph(h, S["th"]) for h in headers]]
    for row in rows_data:
        data.append([
            Paragraph(row[0], S["td_c"]),
            Paragraph(row[1], S["td"]),
            Paragraph(row[2], S["td"]),
        ])

    t = Table(data, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,  0), (-1,  0), C_PLUM),
        ("TEXTCOLOR",     (0,  0), (-1,  0), colors.white),
        ("FONTNAME",      (0,  0), (-1, -1), F),
        ("VALIGN",        (0,  0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0,  0), (-1, -1), 5),
        ("BOTTOMPADDING", (0,  0), (-1, -1), 5),
        ("LEFTPADDING",   (0,  0), (-1, -1), 6),
        ("RIGHTPADDING",  (0,  0), (-1, -1), 6),
        ("ROWBACKGROUNDS",(0,  1), (-1, -1), [C_LAVENDER, colors.white]),
        ("GRID",          (0,  0), (-1, -1), 0.4, C_BORDER),
        ("LINEBELOW",     (0,  0), (-1,  0), 1.5, C_ROSE),
    ]))
    return t


def diary_table(S):
    rows = [
        ["①",       "1週間俯瞰型",              "曜日が薄く入った週ごとの体調・予定比較仕様"],
        ["②",       "1ヶ月俯瞰型（マンスリー）", "1ヶ月の気分の波をポジティブに捉えるフォーマット"],
        ["③ ★採用", "1日1ページ（自己肯定感アップ型）",
                                                   "今日の出来事に「もう1人の自分」がポジティブなコメントを返す形式"],
        ["④",       "1日2分割フリー型",           "③の要素を省きページ数を抑えたシンプル版"],
        ["⑤",       "水彩・イラスト枠入りデザイン型","数種類の柄が繰り返されるおしゃれなフォーマット"],
    ]
    cw = [BW * 0.13, BW * 0.30, BW * 0.57]
    data = [[Paragraph(h, S["th"]) for h in ["No.", "案名", "概要"]]]
    for r in rows:
        data.append([Paragraph(r[0], S["td_c"]),
                     Paragraph(r[1], S["td"]),
                     Paragraph(r[2], S["td"])])

    t = Table(data, colWidths=cw)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,  0), (-1,  0), C_PLUM),
        ("BACKGROUND",    (0,  3), (-1,  3), C_MAUVE),   # ★採用行
        ("FONTNAME",      (0,  0), (-1, -1), F),
        ("VALIGN",        (0,  0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0,  0), (-1, -1), 4),
        ("BOTTOMPADDING", (0,  0), (-1, -1), 4),
        ("LEFTPADDING",   (0,  0), (-1, -1), 6),
        ("RIGHTPADDING",  (0,  0), (-1, -1), 6),
        ("ROWBACKGROUNDS",(0,  1), (-1, -1), [C_LAVENDER, colors.white]),
        ("GRID",          (0,  0), (-1, -1), 0.4, C_BORDER),
        ("LINEBELOW",     (0,  0), (-1,  0), 1.5, C_ROSE),
    ]))
    return t


# ── Content helpers ────────────────────────────────────────────────────────────

def add_items(story, items, S):
    for label, text in items:
        story.append(KeepTogether([
            item_label(label, S),
            Paragraph(text, S["body"]),
        ]))


# ── Main builder ──────────────────────────────────────────────────────────────

def build_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title="社内会議議事録 2026年5月22日", author="社内",
    )
    S = styles()
    story = []

    # ── Title ────────────────────────────────────────────────────────────
    story.append(title_block(S))
    story.append(Spacer(1, 7*mm))

    # ── Section 1 ────────────────────────────────────────────────────────
    story.append(h2("1.  経営・財務および市場動向報告", S))
    story.append(Spacer(1, 3*mm))
    add_items(story, [
        ("今期の業績動向",
         "売上・利益ともに前年同期を上回るペースで推移。ただし利益の多くが在庫に充てられているためキャッシュフローは実質マイナス傾向であり、楽観視できない状況。"),
        ("市場環境と競合分析",
         "雑貨業界全体が低迷する一方、文具業界は好調。シールブーム（「ボンボンドロップ」等）を牽引したクーリア社・BGM社は大幅増収。自社ブランドは「リーフレッツ」を除き前年比超。"
         "他社では財務悪化による入金遅延・廃業・M&A（マークス社、アートワークス社）など業界再編が加速。"),
        ("営業効率の課題",
         "雑貨業界の営業担当1人あたり平均売上（約700万円）と自社（時短勤務者）の乖離が課題。グリーンフラッシュ社等の事例を参考に改善策を検討。"),
        ("将来的な事業継承・統合への備え",
         "キングジム社・パイロット社等への統合の可能性を視野に、組織スリム化・労務環境整備を推進。"
         "買収・ファンド傘下に入った場合、過剰な休日数や不明瞭な手当が「隠れ負債」として査定されるリスクがあるため、就業規則を現段階から大幅アップデートし適正な企業価値を担保する。"),
    ], S)
    story.append(Spacer(1, 5*mm))

    # ── Section 2 ────────────────────────────────────────────────────────
    story.append(h2("2.  労務・就業規則の大幅改定について", S))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "コンプライアンスの徹底と企業評価向上を目的に、就業規則を現代基準に合わせて刷新する。",
        S["body"]))
    add_items(story, [
        ("休暇運用の厳格化",
         "過去の曖昧な休職運用を是正。今後は社長による個別判断を廃止し、すべて就業規則に則った標準運用へ統一。"),
        ("生理休暇・公的休暇の扱い",
         "生理休暇・裁判員休暇等は取得権利を保障するが、原則「無給」。給与不支給を避けたい場合は有給休暇を申請する運用とする。"),
        ("休日出勤の取り扱い",
         "【A案】代休なしで割増賃金（日当）を全額支給　／　【B案】特定の休日手当を定額支給し有休取得。"
         "社労士と相談の上、1日あたり8,000〜10,000円程度の手当設定を目安に正式案内する。"),
        ("特別休暇による年間休日数の是正",
         "現状の年間休日（有休含め130〜147日前後）は一般的基準より過剰で、残業割増単価が上昇する要因に。"
         "正月・大型連休の合間の平日を「会社指定の特別休暇」として算入し、日当・時給換算の整合性を確保する。"),
        ("勤怠管理の徹底",
         "リモートワーク・遠方在籍者も含め出退勤管理を厳格化。特に遠方在籍者の午前中のみ稼働等、"
         "契約形態（時短イン、インハウス契約等）の実態に即した是正を行う。"),
    ], S)
    story.append(Spacer(1, 5*mm))

    # ── Section 3 ────────────────────────────────────────────────────────
    story.append(h2("3.  各事業部・新商品企画および進捗状況", S))
    story.append(Spacer(1, 3*mm))

    story.append(h3("3.1  文具・ステーショナリー関連", S))
    story.append(Spacer(1, 2*mm))
    add_items(story, [
        ("マスターピース（ブックアイテムコーナー）",
         "モックアップ4柄を基に進行中。透明PVCカバー・しおり・巾着・ポーチ・メガネケースを展開。"
         "刺繍巾着（想定1,600円、原価率25%目標）はポリエステル100%素材への変更を検討。"
         "メガネケースは蓋形状を変更し柄を入れやすい仕様へ。大型店向けに展示会実績のある「テーマ別コーナー作り」提案を実施予定。"),
        ("たかはしねむ氏シリーズ（来期）",
         "レターセット・マスキングテープ・御朱印帳・メモ帳・ポストカード（8柄）で進行。"
         "テーマは植物・湖の動物・猫。メモ帳は過去に好評のサイズに仕様統一、シルバーサイド印刷を工場と調整中。"),
        ("ポチ袋（11月・年始商材）",
         "①数字つなぎポチ袋（活版印刷）　②仕掛けポチ袋（封筒＋巻き紙）　③タイポポチ袋（厚盛りニス）の3案から"
         "社内投票で①②が上位 → 2シリーズ同時進行でリリース決定。季節限定にせず日常のお礼・車代用の別柄展開も検討。"),
    ], S)

    story.append(h3("3.2  陶器・食器・生活雑貨関連", S))
    story.append(Spacer(1, 2*mm))
    add_items(story, [
        ("美濃焼きのお茶碗（ブランド名未定）",
         "高品質メーカー（BC：不良品ほぼゼロ）と共同開発。9SKU発注、生産約半年。8月末に各50〜100個で発売予定。"
         "マット釉薬使用。ジェンダーバイアスを排除したサイズ展開。"),
        ("リスシリーズ（定番マグ・プレート）",
         "プレート（ネイビー）が急売れ・欠品中 → 300個で再生産。マグは工場廃業により現行形状を再現不可のため、"
         "別メーカーの安定した新形状へ移行しサンプル依頼中。ミニプレートも次回見積もりで進行。"),
        ("スープカップ（秋冬商材）",
         "撥水加工・シルクスクリーン手法で比較的安価かつ短納期で製造。8月盆明けまでに形にする必要あり → デザイン出待ち。"),
        ("篠原さんシリーズ・マグ（第2弾）",
         "既存ルート（撥水仕様・同型）で製造検討。マット釉薬サンプル待ち。10月に向けてサンプル監修を進める。"),
        ("かよさんマグ（フルカラー転写）",
         "転写コスト高のため（想定2,300円前後）、他社共同製造や自社プロパー商品ラインに組み込み、"
         "初期ロット1,000〜2,000個規模でのコスト削減・開発を目指す。"),
    ], S)

    story.append(h3("3.3  ファブリック・キッチン・ランチ雑貨関連", S))
    story.append(Spacer(1, 2*mm))
    add_items(story, [
        ("ランチバッグ・巾着・レジかごバッグ",
         "アルミ／シルバーコーティング仕様の保温保冷アイテム。松尾さんランチボックス用巾着袋は汎用性の高い「ミニ巾着」としてカタログ掲載。"
         "新型レジかごバッグ（ダークグレー、スモークグリーン等）は東海エリア等の車社会需要を想定。アミング等実店舗での反応を確認。"),
        ("ピザ・寿司用テイクアウトバッグ（新規）",
         "大型ピザ・オードブル・お寿司を水平に保って持ち運べる大型バッグ（インド製リサイクル素材、3,800円想定）。"
         "「都市部の徒歩圏向けに1〜2回り小さいサイズも」「オンセブンデイズ・アミングの意見を事前確認してサイズ調整」"
         "等のフィードバックを受け、仕様を微調整。"),
    ], S)

    story.append(h3("3.4  ガーデン・インテリア・照明関連", S))
    story.append(Spacer(1, 2*mm))
    add_items(story, [
        ("プランター・鉢・園芸資材",
         "【中国生産】ホウロウ製バット（コッシュリビング社別注）は来年6〜7月入荷予定。"
         "新規のペーパー素材・キャンバスケット風陶器以外の鉢（高価格帯、9〜10月発売）のサンプル進行中。"
         "【インド生産】コッパー素材トレー（レーザー/シルク印刷ロゴ）サンプル到着・耐水性テスト継続。"
         "エナメル大型フラワーベース（5,000〜10,000円、20〜30cm）や手書き線画の陶器ポットカバーを27年SSカタログに向けて仕込み中。"),
        ("デコランプ・バーランプ（大型照明）",
         "160cmサイズ超の配送は「ラージ便（3,000〜6,000円以上）」で送料高騰。"
         "議論の結果、営業案内がしやすい【別途送料の設定】で進めることを決定。"),
        ("トラフィックシリーズ（復刻・新作時計）",
         "WCL-025番同ボディ（ハンマー仕上げ等）で文字盤2タイプ。為替の影響で5,000円台への価格調整を視野に入れ、"
         "早ければ7月入荷・秋向け商材として進行。"),
        ("ソーラー付リチウムイオン電池式ポータブルライト（新規検討）",
         "4月法改正に伴う「使用済みリチウム電池の回収・廃棄義務（JBRC等加入コスト、遡及リスク）」を確認・クリアした上で進行。"),
        ("スヌーピー（ピーナッツ）コラボ第2弾（ネオンライト・バルブ電球）",
         "調光機能付きだとUSB給電不可（電池駆動のみ）のデメリットあり → 今月届くサンプルで価格・仕様を判断。"
         "9月のイベント（ソカロ等）でのお披露目を目指す。"
         "※ SNS掲載画像は「公式監修済みの画像・文章」の流用を徹底。店舗独自撮影やキャラクター（オラフ等）の過度な露出は原則NG。"),
    ], S)
    story.append(Spacer(1, 5*mm))

    # ── Section 4 ────────────────────────────────────────────────────────
    story.append(h2("4.  長期検討アイテムおよび仕様変更会議", S))
    story.append(Spacer(1, 3*mm))

    story.append(h3("4.1  正方形リングノート（9月予定）", S))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "<b>仕様：</b>A6とB6の間の正方形サイズ。梨地下敷き＋艶なし厚紙表紙、本文100枚・20mm大型リング綴じ。"
        "ジオジャパン・大和印刷など4社に見積もり依頼中。", S["body"]))
    story.append(Paragraph(
        "<b>本文罫線：</b>「無地は売れにくい」というデータとシールブーム落ち着き後の貼り先需要を考慮。"
        "「10mm方眼」または「薄い5mm方眼」をベースに、大人が日記・ログとしても使えるドット・点線仕様を検証中。",
        S["body"]))

    story.append(h3("4.2  ライフログ・日記帳（10月カレンダー・ダイアリー期予定）", S))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "<b>サイズ・素材：</b>従来のB6・PVCカバーに加え、携帯しやすい「新書・A6ミニサイズ（ボタン/留め紐付き）」"
        "を女性陣の意見から採用。高級路線の合皮カバーも検討。", S["body"]))
    story.append(Spacer(1, 2*mm))
    story.append(diary_table(S))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "社内投票の結果、<b>③（1日1ページ・自己肯定感アップ型）</b>をベースに進行。"
        "ページ数・厚み（ウィークリー程度）、3年連用にするかどうかの構成案をさらに検討。", S["body"]))
    story.append(Spacer(1, 5*mm))

    # ── Section 5 ────────────────────────────────────────────────────────
    story.append(h2("5.  広報（PR）・EC戦略および販路の構造改革", S))
    story.append(Spacer(1, 3*mm))
    add_items(story, [
        ("取引先のPB化への危機感",
         "ロフト・ハンズがPB比率を従来の3割から60〜70%へ引き上げる方向で動いており、ナショナルブランドが排除されるリスクが高い。"
         "卸（MDS等）を介した従来ルートだけでなく、自社で一般消費者（B2C）を直接捕まえる施策が急務。"),
        ("自社EC・SNSの強化",
         "アートワーク社の成功事例（インスタフォロワー数万人・実店舗をショールーム化してネット誘導）に倣い、"
         "自社サイトのリニューアルを秋（9月頃）に向けて推進。"),
        ("Instagram運用改善",
         "各ブランドの更新頻度を高め、ストーリー・動画（リール）を積極的に活用。"),
        ("PR TIMESの導入検討",
         "現状HPのプレスリリース配信が機能していない。ニュースページ（プロダクト・メディア・イベント）の運用フォーマットを固定・マニュアル化し各自入稿できる体制を整えた上で、"
         "月額7〜8万円（30本まで）で複数ブランドが使える「PR TIMES」への出稿を開始しネットニュース露出を増やす。"),
        ("外部リソースの活用",
         "カタログ制作のIllustrator→InDesign移行検討。商工会議所の「AI・DX人材育成講習会」を社内で受講し、"
         "請求明細作成・自動メール送信等の業務自動化を加速。"),
    ], S)
    story.append(Spacer(1, 5*mm))

    # ── Section 6 ────────────────────────────────────────────────────────
    story.append(h2("6.  今後の主要スケジュール（展示会・イベント・年末年始）", S))
    story.append(Spacer(1, 3*mm))
    story.append(schedule_table(S))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "<b>年末年始の休暇日程（調整中）：</b>「12月29日〜1月4日か5日」案、"
        "「前倒しで24〜25日付近に会議を終わらせる」案等が提案。"
        "物流動向を確認の上、次回会議までに確定（現状は仮で28・29日会議案を保留）。", S["body"]))
    story.append(Paragraph(
        "<b>次回会議：</b>各工場の見積もりが出揃うタイミング（来週以降スケジュール通り）に実施。",
        S["body"]))

    # ── Footer ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 6*mm))
    for elem in divider_rose():
        story.append(elem)
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("◆　以　上　◆", S["footer"]))

    doc.build(story)
    print(f"PDF generated: {output_path}")


if __name__ == "__main__":
    build_pdf("/home/user/Claude-App/議事録_2026年5月22日.pdf")
