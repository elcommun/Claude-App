# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This is a small internal tooling repo for EL COMMUN, a Japanese stationery/lifestyle goods company. It contains:

- **`item-data/index.html`** — single-page app for aggregating EC (e-commerce) sales data from uploaded Excel files (uses SheetJS / xlsx.js)
- **`ranking/index.html`** — single-page app for visualising EC sales rankings from uploaded Excel files (uses SheetJS + ExcelJS)
- **`generate_pdf.py`** — Python script that generates a formatted A4 meeting-minutes PDF using ReportLab

All three tools are self-contained (no build step, no server required).

---

## HTML apps (`item-data/`, `ranking/`)

Open directly in a browser — no build or serve step needed:

```bash
open item-data/index.html
open ranking/index.html
```

### Design system (shared CSS variables)

Both pages share the same design token set:

| Variable | Value | Role |
|---|---|---|
| `--ink` | `#1c1917` | Primary text / header bg |
| `--paper` | `#faf8f4` | Page background |
| `--gold` | `#92754a` | Accent / labels |
| `--green` | `#3a6b52` | Positive / success |
| `--red` | `#b85c3c` | Negative / alert |
| `--border` | `#e7e2da` | Dividers |

Font stack: `'Hiragino Kaku Gothic Pro', 'Meiryo', sans-serif` — no external font load.

### Architecture pattern

Each page is fully self-contained HTML + inline CSS + inline JS. Data flow:

1. User drops / selects Excel file(s) via a drag-and-drop modal
2. SheetJS parses the workbook client-side
3. JS processes rows and renders results into the DOM — no network calls after initial CDN load

---

## PDF generator (`generate_pdf.py`)

### Dependencies

```bash
pip install reportlab python-docx fonttools
```

### Font setup (required before first run)

The script expects pre-converted TrueType fonts at `/tmp/`. Run this once per environment:

```python
# Requires fonts-noto-cjk to be installed:
#   apt-get install -y fonts-noto-cjk
#
# Then convert the CFF-based TTC to TrueType (ReportLab cannot read CFF):
from fontTools.ttLib import TTCollection
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables._g_l_y_f import Glyph as TTGlyph, table__g_l_y_f
from fontTools.ttLib.tables import _l_o_c_a

def convert_cjk_ttc(in_path, out_path, index=0):
    ttc = TTCollection(in_path)
    font = ttc.fonts[index]
    cff = font['CFF '].cff
    charstrings = cff.topDictIndex[0].CharStrings
    glyphOrder = font.getGlyphOrder()
    glyphs = {}
    for name in glyphOrder:
        try:
            pen = TTGlyphPen(None)
            charstrings[name].draw(Cu2QuPen(pen, 1.0, all_quadratic=True))
            glyphs[name] = pen.glyph()
        except Exception:
            glyphs[name] = TTGlyph()
    glyf = table__g_l_y_f(); glyf.glyphs = glyphs; glyf.glyphOrder = glyphOrder
    font['glyf'] = glyf
    loca = _l_o_c_a.table__l_o_c_a(); loca.locations = []; font['loca'] = loca
    font['head'].indexToLocFormat = 1; font['head'].magicNumber = 0x5F0F3CF5
    maxp = font['maxp']
    maxp.tableVersion = 0x00010000; maxp.maxZones = 1
    for attr in ('maxTwilightPoints','maxStorage','maxFunctionDefs',
                 'maxInstructionDefs','maxStackElements','maxSizeOfInstructions'):
        setattr(maxp, attr, 0)
    maxp.maxComponentElements = max(
        (len(g.components) if hasattr(g,'components') and g.components else 0)
        for g in glyphs.values())
    for t in ['CFF ','VORG']:
        if t in font: del font[t]
    font.save(out_path)
    with open(out_path,'r+b') as f: f.write(b'\x00\x01\x00\x00')

convert_cjk_ttc('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/tmp/NotoSansJP-Regular.ttf')
convert_cjk_ttc('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',    '/tmp/NotoSansJP-Bold.ttf')
```

### Running

```bash
python3 generate_pdf.py
# → 議事録_2026年5月22日.pdf
```

### Design system (PDF)

The PDF uses an **editorial minimal** style:

| Token | Value | Role |
|---|---|---|
| `INK` | `#1E1E1E` | Body text, H2 background |
| `SAGE` | `#4D7168` | Single accent — H3 left border, table accent line, footer rule |
| `RULE` | `#DEDEDE` | Table grid, thin separators |
| `ROW` | `#F5F5F5` | Alternating table rows |
| `MID` | `#6B6B6B` | Secondary text (subtitles, footnotes) |

Key layout rules:
- Page margins: 14mm left/right, 13mm top/bottom
- H2: full-width `INK` charcoal banner, white text
- H3: no background fill — `3pt SAGE` left border only (`LINEBEFORE`)
- Item labels: bold, no bullet symbol
- One accent color only — do not add more colors
- No decorative symbols (◆, ■, ▶ etc.) — decoration was explicitly removed as it made the design look "uncool"
