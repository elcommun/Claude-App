#!/usr/bin/env python3
"""Generate a well-formatted PDF from the meeting minutes docx."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    KeepTogether
)
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# Noto Sans CJK JP converted to TrueType for ReportLab compatibility
pdfmetrics.registerFont(TTFont("NotoSansJP",      "/tmp/NotoSansJP-Regular.ttf"))
pdfmetrics.registerFont(TTFont("NotoSansJP-Bold", "/tmp/NotoSansJP-Bold.ttf"))
registerFontFamily("NotoSansJP", normal="NotoSansJP", bold="NotoSansJP-Bold",
                   italic="NotoSansJP", boldItalic="NotoSansJP-Bold")
FONT      = "NotoSansJP"
FONT_BOLD = "NotoSansJP-Bold"

# Color palette
C_NAVY = colors.HexColor("#1A3557")
C_TEAL = colors.HexColor("#2E7D8C")
C_STEEL = colors.HexColor("#4A6FA5")
C_LIGHT_BLUE = colors.HexColor("#E8F4F8")
C_LIGHT_GRAY = colors.HexColor("#F5F7FA")
C_MID_GRAY = colors.HexColor("#C8D0DC")
C_DARK_GRAY = colors.HexColor("#4A4A4A")
C_TEXT = colors.HexColor("#2D2D2D")
C_ACCENT = colors.HexColor("#D4E8F0")

W, H = A4
MARGIN_L = 20*mm
MARGIN_R = 20*mm
MARGIN_T = 18*mm
MARGIN_B = 18*mm
BODY_W = W - MARGIN_L - MARGIN_R

def make_styles():
    s = {}
    s["title"] = ParagraphStyle(
        "title", fontName=FONT, fontSize=18, leading=26,
        textColor=C_NAVY, alignment=TA_CENTER,
        spaceAfter=4, spaceBefore=0,
    )
    s["subtitle"] = ParagraphStyle(
        "subtitle", fontName=FONT, fontSize=10, leading=15,
        textColor=C_STEEL, alignment=TA_CENTER,
        spaceAfter=0,
    )
    s["h2"] = ParagraphStyle(
        "h2", fontName=FONT, fontSize=13, leading=20,
        textColor=colors.white, alignment=TA_LEFT,
        spaceBefore=10, spaceAfter=4,
        leftIndent=0, rightIndent=0,
        borderPadding=(4, 8, 4, 8),
    )
    s["h3"] = ParagraphStyle(
        "h3", fontName=FONT, fontSize=11, leading=17,
        textColor=C_NAVY, alignment=TA_LEFT,
        spaceBefore=7, spaceAfter=3,
        leftIndent=2,
        borderPadding=(3, 6, 3, 6),
    )
    s["body"] = ParagraphStyle(
        "body", fontName=FONT, fontSize=9, leading=16,
        textColor=C_TEXT, alignment=TA_JUSTIFY,
        spaceBefore=2, spaceAfter=4,
        leftIndent=8, rightIndent=4,
    )
    s["bullet"] = ParagraphStyle(
        "bullet", fontName=FONT, fontSize=9, leading=16,
        textColor=C_TEXT, alignment=TA_JUSTIFY,
        spaceBefore=1, spaceAfter=2,
        leftIndent=16, firstLineIndent=-8, rightIndent=4,
    )
    s["note"] = ParagraphStyle(
        "note", fontName=FONT, fontSize=8, leading=14,
        textColor=C_STEEL, alignment=TA_LEFT,
        spaceBefore=2, spaceAfter=2,
        leftIndent=10, rightIndent=4,
    )
    s["table_header"] = ParagraphStyle(
        "table_header", fontName=FONT, fontSize=9, leading=14,
        textColor=colors.white, alignment=TA_CENTER,
    )
    s["table_cell"] = ParagraphStyle(
        "table_cell", fontName=FONT, fontSize=8.5, leading=13,
        textColor=C_TEXT, alignment=TA_LEFT,
    )
    s["table_cell_center"] = ParagraphStyle(
        "table_cell_center", fontName=FONT, fontSize=8.5, leading=13,
        textColor=C_TEXT, alignment=TA_CENTER,
    )
    return s

def heading2_block(text, styles):
    """Returns a colored bar paragraph for H2."""
    p = Paragraph(text, styles["h2"])
    tbl = Table([[p]], colWidths=[BODY_W])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_NAVY]),
    ]))
    return tbl

def heading3_block(text, styles):
    """Returns a left-bordered style for H3."""
    p = Paragraph(text, styles["h3"])
    tbl = Table([[p]], colWidths=[BODY_W])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT_BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEAFTER", (0, 0), (0, -1), 0, colors.white),
        ("LINEABOVE", (0, 0), (-1, 0), 2, C_TEAL),
    ]))
    return tbl

def build_schedule_table(styles):
    headers = ["月日", "イベント / 業務内容", "備考"]
    rows_data = [
        ["5/26〜28", "大阪展示会（設営26日、会期27〜28日）", "社長は夜の会合のみ出席"],
        ["6/3〜4", "鈴木海文堂 展示会（設営3日、会期4日）", ""],
        ["6/9〜12", "福岡設営＆展示会（9日設営、10〜11日会期）", ""],
        ["6/10〜14", "文具女子博（10日午後開催〜14日）", "デザイン部見学調整"],
        ["6/9〜12", "インテリアライフスタイル（食器・9日並び、10〜12日）", "11日にメンバー交代あり"],
        ["6/9〜12", "日本橋3丁目（9日搬入、10〜12日会期）", ""],
        ["6/18〜19", "日設展示会（19日のみ）", ""],
        ["6/24〜25", "ニコフェス（ISOT併催・リード）", "春手帳の企画に絡めて視察"],
        ["7/7〜9", "MDS商談会（東京7〜9日、設営7日、会期7・8・9日）", ""],
        ["7/21〜24", "大原展示会（設営21日、会期22〜23日）", "関西メンバー中心、社長は大原出席"],
        ["7/21〜26", "文具女子博 mini京都（21日設営、土日まで開催）", ""],
        ["8/4〜7", "ラップス（北海道・搬入4日、会期5〜7日）", ""],
        ["8/8〜16", "お盆休み（9連休）", "全社（※10日出勤は要調整、辻氏は韓国渡航予定）"],
        ["8/24〜25", "名古屋商談会（朝4:30集合の早朝対応）", "朝に強いメンバーで対応"],
        ["8/29〜9/14", "ニューヨーク出張（オブジェクト展含む）", "帰国後そのまま北海道等の連携あり"],
        ["9/1〜4", "合同展示会（モンタージュ / エビス）", "インテリア・新商品・食器担当"],
        ["9/8〜10", "関西展示会（8日設営、9〜10日会期）", "関西担当"],
        ["9/10〜13", "台湾イベント（10日設営、11〜13日会期）", ""],
        ["9/19〜23", "シルバーウィーク（5連休）", "全社"],
        ["10/2〜4", "森の文学・文博（3〜4日開催、日曜まで）", ""],
        ["10/9〜11", "紙博（東京・平和島/昭和島・9日設営、10〜11日）", ""],
        ["11/4〜9", "長沢商談会（4日設営、5〜9日開催、月曜まで）", ""],
        ["11/11〜13", "メルクロス（大阪・コントラクト系設備商談会、出展料11万）", "住宅設備、施工・施工業者対応"],
        ["11/14〜15", "フィールドスタイル（名古屋・アウトドア物販イベント）", "キャンプグッズ担当中心"],
        ["12/15〜21", "文具女子博 横浜（15日設営、21日まで開催）", "総出対応"],
    ]

    col_w = [BODY_W * 0.18, BODY_W * 0.57, BODY_W * 0.25]
    table_data = [[
        Paragraph(h, styles["table_header"]) for h in headers
    ]]
    for i, row in enumerate(rows_data):
        table_data.append([
            Paragraph(row[0], styles["table_cell_center"]),
            Paragraph(row[1], styles["table_cell"]),
            Paragraph(row[2], styles["table_cell"]),
        ])

    t = Table(table_data, colWidths=col_w, repeatRows=1)
    row_colors = []
    for i in range(1, len(rows_data) + 1):
        bg = C_LIGHT_GRAY if i % 2 == 1 else colors.white
        row_colors.append(("BACKGROUND", (0, i), (-1, i), bg))

    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, C_MID_GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_LIGHT_GRAY, colors.white]),
    ] + row_colors))
    return t

def build_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title="社内会議議事録 2026年5月22日",
        author="社内",
    )

    styles = make_styles()
    story = []

    # ── Title block ─────────────────────────────────────────────────────
    title_tbl = Table(
        [[Paragraph("議事録：社内会議", styles["title"])],
         [Paragraph("2026年5月22日（金）　本社 会議室", styles["subtitle"])]],
        colWidths=[BODY_W]
    )
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT_BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, 0), (-1, 0), 3, C_NAVY),
        ("LINEBELOW", (0, -1), (-1, -1), 3, C_TEAL),
    ]))
    story.append(title_tbl)
    story.append(Spacer(1, 6*mm))

    # ── Section 1 ───────────────────────────────────────────────────────
    story.append(heading2_block("1. 経営・財務および市場動向報告", styles))
    story.append(Spacer(1, 2*mm))

    items_sec1 = [
        ("今期の業績動向",
         "売上・利益ともに前年同期を上回るペースで推移。ただし、利益の多くが在庫に充てられているためキャッシュフローは実質マイナス傾向であり、楽観視できない状況。"),
        ("市場環境と競合分析",
         "雑貨業界全体が低迷する一方、文具業界は好調。シールブーム（「ボンボンドロップ」等）を牽引したクーリア社・BGM社は大幅増収。自社ブランドは「リーフレッツ」を除き前年比超。"
         "他社では財務悪化による入金遅延・廃業・M&A（マークス社、アートワークス社）など業界再編が加速。"),
        ("営業効率の課題",
         "雑貨業界の営業担当1人あたり平均売上（約700万円）と自社（時短勤務者）の乖離が課題。グリーンフラッシュ社等の事例を参考に改善策を検討。"),
        ("将来的な事業継承・統合への備え",
         "キングジム社・パイロット社等への統合の可能性を視野に、組織スリム化・労務環境整備を推進。"
         "買収・ファンド傘下に入った場合、過剰な休日数や不明瞭な手当が「隠れ負債」として査定されるリスクがあるため、就業規則を現段階から大幅アップデートし適正な企業価値を担保する。"),
    ]
    for label, text in items_sec1:
        story.append(Paragraph(f"<b>■ {label}</b>", styles["body"]))
        story.append(Paragraph(text, styles["bullet"]))

    story.append(Spacer(1, 4*mm))

    # ── Section 2 ───────────────────────────────────────────────────────
    story.append(heading2_block("2. 労務・就業規則の大幅改定について", styles))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "コンプライアンスの徹底と企業評価向上を目的に、就業規則を現代基準に合わせて刷新する。",
        styles["body"]
    ))

    items_sec2 = [
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
         "リモートワーク・遠方在籍者も含め出退勤管理を厳格化。特に遠方在籍者の午前中のみ稼働等、契約形態（時短イン、インハウス契約等）の実態に即した是正を行う。"),
    ]
    for label, text in items_sec2:
        story.append(Paragraph(f"<b>■ {label}</b>", styles["body"]))
        story.append(Paragraph(text, styles["bullet"]))

    story.append(Spacer(1, 4*mm))

    # ── Section 3 ───────────────────────────────────────────────────────
    story.append(heading2_block("3. 各事業部・新商品企画および進捗状況", styles))
    story.append(Spacer(1, 2*mm))

    # 3.1
    story.append(heading3_block("3.1 文具・ステーショナリー関連", styles))
    items_31 = [
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
    ]
    for label, text in items_31:
        story.append(Paragraph(f"<b>▶ {label}</b>", styles["body"]))
        story.append(Paragraph(text, styles["bullet"]))

    # 3.2
    story.append(heading3_block("3.2 陶器・食器・生活雑貨関連", styles))
    items_32 = [
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
    ]
    for label, text in items_32:
        story.append(Paragraph(f"<b>▶ {label}</b>", styles["body"]))
        story.append(Paragraph(text, styles["bullet"]))

    # 3.3
    story.append(heading3_block("3.3 ファブリック・キッチン・ランチ雑貨関連", styles))
    items_33 = [
        ("ランチバッグ・巾着・レジかごバッグ",
         "アルミ／シルバーコーティング仕様の保温保冷アイテム。"
         "松尾さんランチボックス用巾着袋は汎用性の高い「ミニ巾着」としてカタログ掲載。"
         "新型レジかごバッグ（ダークグレー、スモークグリーン等）は東海エリア等の車社会需要を想定。アミング等実店舗での反応を確認。"),
        ("ピザ・寿司用テイクアウトバッグ（新規）",
         "大型ピザ・オードブル・お寿司を水平に保って持ち運べる大型バッグ（インド製リサイクル素材、3,800円想定）。"
         "「都市部の徒歩圏向けに1〜2回り小さいサイズも」「オンセブンデイズ・アミングの意見を事前確認してサイズ調整」"
         "等のフィードバックを受け、仕様を微調整。"),
    ]
    for label, text in items_33:
        story.append(Paragraph(f"<b>▶ {label}</b>", styles["body"]))
        story.append(Paragraph(text, styles["bullet"]))

    # 3.4
    story.append(heading3_block("3.4 ガーデン・インテリア・照明関連", styles))
    items_34 = [
        ("プランター・鉢・園芸資材",
         "【中国生産】ホウロウ製バット（コッシュリビング社別注）は来年6〜7月入荷予定。"
         "新規のペーパー素材・キャンバスケット風陶器以外の鉢（高価格帯、9〜10月発売）のサンプル進行中。\n"
         "【インド生産】コッパー素材トレー（レーザー/シルク印刷ロゴ）サンプル到着・耐水性テスト継続。"
         "エナメル大型フラワーベース（5,000〜10,000円、20〜30cm）や手書き線画の陶器ポットカバーを27年SSカタログに向けて仕込み中。"),
        ("デコランプ・バーランプ（大型照明）",
         "160cmサイズ超の配送は「ラージ便（3,000〜6,000円以上）」で送料高騰。"
         "【別途送料の設定】で進めることを決定。"),
        ("トラフィックシリーズ（復刻・新作時計）",
         "WCL-025番同ボディ（ハンマー仕上げ等）で文字盤2タイプ。為替の影響で5,000円台への価格調整を視野に入れ、"
         "早ければ7月入荷・秋向け商材として進行。"),
        ("ソーラー付リチウムイオン電池式ポータブルライト（新規検討）",
         "4月法改正に伴う「使用済みリチウム電池の回収・廃棄義務（JBRC等加入コスト、遡及リスク）」を確認・クリアした上で進行。"),
        ("スヌーピー（ピーナッツ）コラボ第2弾（ネオンライト・バルブ電球）",
         "調光機能付きだとUSB給電不可（電池駆動のみ）のデメリットあり → 今月届くサンプルで価格・仕様を判断。"
         "9月のイベント（ソカロ等）でのお披露目を目指す。\n"
         "※ SNS掲載画像は「公式監修済みの画像・文章」の流用を徹底。店舗独自撮影やキャラクター（オラフ等）の過度な露出は原則NG。"),
    ]
    for label, text in items_34:
        story.append(Paragraph(f"<b>▶ {label}</b>", styles["body"]))
        story.append(Paragraph(text, styles["bullet"]))

    story.append(Spacer(1, 4*mm))

    # ── Section 4 ───────────────────────────────────────────────────────
    story.append(heading2_block("4. 長期検討アイテムおよび仕様変更会議", styles))
    story.append(Spacer(1, 2*mm))

    story.append(heading3_block("4.1 正方形リングノート（9月予定）", styles))
    story.append(Paragraph(
        "<b>仕様：</b>A6とB6の間の正方形サイズ。梨地下敷き＋艶なし厚紙表紙、本文100枚・20mm大型リング綴じ。"
        "ジオジャパン・大和印刷など4社に見積もり依頼中。",
        styles["body"]
    ))
    story.append(Paragraph(
        "<b>本文罫線：</b>「無地は売れにくい」というデータとシールブーム落ち着き後の貼り先需要を考慮。"
        "「10mm方眼」または「薄い5mm方眼」をベースに、大人が日記・ログとしても使えるドット・点線仕様を検証中。",
        styles["body"]
    ))

    story.append(heading3_block("4.2 ライフログ・日記帳（10月カレンダー・ダイアリー期予定）", styles))
    story.append(Paragraph(
        "<b>サイズ・素材：</b>従来のB6・PVCカバーに加え、携帯しやすい「新書・A6ミニサイズ（ボタン/留め紐付き）」を女性陣の意見から採用。高級路線の合皮カバーも検討。",
        styles["body"]
    ))

    formats_data = [
        ["①", "1週間俯瞰型", "曜日が薄く入った週ごとの体調・予定比較仕様"],
        ["②", "1ヶ月俯瞰型（マンスリー）", "1ヶ月の気分の波をポジティブに捉えるフォーマット"],
        ["③ ★採用", "1日1ページ（自己肯定感アップ型）", "今日の出来事に「もう1人の自分」がポジティブなコメントを返す形式"],
        ["④", "1日2分割フリー型", "③の要素を省きページ数を抑えたシンプル版"],
        ["⑤", "水彩・イラスト枠入りデザイン型", "数種類の柄が繰り返されるおしゃれなフォーマット"],
    ]
    col_w_fmt = [BODY_W*0.12, BODY_W*0.30, BODY_W*0.58]
    fmt_tbl_data = [[
        Paragraph("No.", styles["table_header"]),
        Paragraph("案名", styles["table_header"]),
        Paragraph("概要", styles["table_header"]),
    ]]
    for row in formats_data:
        fmt_tbl_data.append([
            Paragraph(row[0], styles["table_cell_center"]),
            Paragraph(row[1], styles["table_cell"]),
            Paragraph(row[2], styles["table_cell"]),
        ])
    fmt_tbl = Table(fmt_tbl_data, colWidths=col_w_fmt)
    fmt_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_TEAL),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#E6F4EA")),
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, C_MID_GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_LIGHT_GRAY, colors.white]),
    ]))
    story.append(fmt_tbl)
    story.append(Paragraph(
        "社内投票の結果、<b>③（1日1ページ・自己肯定感アップ型）</b>をベースに進行。"
        "ページ数・厚み（ウィークリー程度）、3年連用にするかどうかの構成案をさらに検討。",
        styles["body"]
    ))

    story.append(Spacer(1, 4*mm))

    # ── Section 5 ───────────────────────────────────────────────────────
    story.append(heading2_block("5. 広報（PR）・EC戦略および販路の構造改革", styles))
    story.append(Spacer(1, 2*mm))

    items_sec5 = [
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
    ]
    for label, text in items_sec5:
        story.append(Paragraph(f"<b>■ {label}</b>", styles["body"]))
        story.append(Paragraph(text, styles["bullet"]))

    story.append(Spacer(1, 4*mm))

    # ── Section 6 ───────────────────────────────────────────────────────
    story.append(heading2_block("6. 今後の主要スケジュール（展示会・イベント・年末年始）", styles))
    story.append(Spacer(1, 2*mm))

    story.append(build_schedule_table(styles))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph(
        "<b>年末年始の休暇日程（調整中）：</b>「12月29日〜1月4日か5日」案、「前倒しで24〜25日付近に会議を終わらせる」案等が提案。"
        "物流動向を確認の上、次回会議までに確定（現状は仮で28・29日会議案を保留）。",
        styles["body"]
    ))
    story.append(Paragraph(
        "<b>次回会議：</b>各工場の見積もりが出揃うタイミング（来週以降スケジュール通り）に実施。",
        styles["body"]
    ))

    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width=BODY_W, thickness=0.5, color=C_MID_GRAY))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("以上", styles["subtitle"]))

    doc.build(story)
    print(f"PDF generated: {output_path}")


if __name__ == "__main__":
    build_pdf("/home/user/Claude-App/議事録_2026年5月22日.pdf")
