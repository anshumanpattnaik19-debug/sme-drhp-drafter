"""reportlab building blocks: fonts, page furniture (letterhead, footer, watermark), styles, tables."""
from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from common import SYNTHETIC_FOOTER, SYNTHETIC_MARK

_FONTS = {"Arial": ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
          "Times": ("times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf")}
for fam, files in _FONTS.items():
    names = [fam, fam + "-Bold", fam + "-Italic", fam + "-BoldItalic"]
    for n, f in zip(names, files):
        pdfmetrics.registerFont(TTFont(n, "C:/Windows/Fonts/" + f))
    pdfmetrics.registerFontFamily(fam, normal=names[0], bold=names[1], italic=names[2], boldItalic=names[3])

W, H = A4
MARGIN = 18 * mm


def styles(font: str = "Arial", size: float = 9.5):
    lead = size * 1.32
    s = {
        "body": ParagraphStyle("body", fontName=font, fontSize=size, leading=lead, alignment=TA_JUSTIFY, spaceAfter=4),
        "left": ParagraphStyle("left", fontName=font, fontSize=size, leading=lead, alignment=TA_LEFT, spaceAfter=3),
        "small": ParagraphStyle("small", fontName=font, fontSize=size - 1.5, leading=(size - 1.5) * 1.3, alignment=TA_JUSTIFY),
        "center": ParagraphStyle("center", fontName=font, fontSize=size, leading=lead, alignment=TA_CENTER),
        "right": ParagraphStyle("right", fontName=font, fontSize=size, leading=lead, alignment=TA_RIGHT),
        "title": ParagraphStyle("title", fontName=font + "-Bold", fontSize=size + 5, leading=(size + 5) * 1.25,
                                alignment=TA_CENTER, spaceAfter=6),
        "h1": ParagraphStyle("h1", fontName=font + "-Bold", fontSize=size + 2.5, leading=(size + 2.5) * 1.3,
                             spaceBefore=8, spaceAfter=5),
        "h2": ParagraphStyle("h2", fontName=font + "-Bold", fontSize=size + 1, leading=(size + 1) * 1.3,
                             spaceBefore=6, spaceAfter=3),
        "h3": ParagraphStyle("h3", fontName=font + "-BoldItalic", fontSize=size, leading=lead, spaceBefore=4, spaceAfter=2),
        "cell": ParagraphStyle("cell", fontName=font, fontSize=size - 1.5, leading=(size - 1.5) * 1.22),
        "cellb": ParagraphStyle("cellb", fontName=font + "-Bold", fontSize=size - 1.5, leading=(size - 1.5) * 1.22),
        "cellr": ParagraphStyle("cellr", fontName=font, fontSize=size - 1.5, leading=(size - 1.5) * 1.22, alignment=TA_RIGHT),
        "cellrb": ParagraphStyle("cellrb", fontName=font + "-Bold", fontSize=size - 1.5, leading=(size - 1.5) * 1.22, alignment=TA_RIGHT),
        "cellc": ParagraphStyle("cellc", fontName=font + "-Bold", fontSize=size - 1.5, leading=(size - 1.5) * 1.22, alignment=TA_CENTER),
    }
    return s


class Doc:
    """A document with optional letterhead, page numbers, footer and a light diagonal watermark."""

    def __init__(self, path, title, font="Arial", size=9.5, letterhead=None, footer_left=None,
                 page_numbers=True, watermark=True, top_margin=None):
        self.path, self.title, self.font = path, title, font
        self.s = styles(font, size)
        self.story = []
        self.letterhead = letterhead      # (line1, line2, line3) or None
        self.footer_left = footer_left
        self.page_numbers = page_numbers
        self.watermark = watermark
        tm = top_margin if top_margin is not None else (34 * mm if letterhead else MARGIN)
        self.doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                                     topMargin=tm, bottomMargin=20 * mm, title=title,
                                     author="Synthetic bundle generator", subject=SYNTHETIC_MARK)

    # page furniture
    def _page(self, canv, doc):
        canv.saveState()
        if self.watermark:
            canv.setFont("Arial-Bold", 44)
            canv.setFillColor(colors.Color(0.55, 0.55, 0.55, alpha=0.10))
            canv.translate(W / 2, H / 2)
            canv.rotate(45)
            canv.drawCentredString(0, 0, SYNTHETIC_MARK)
            canv.rotate(-45)
            canv.translate(-W / 2, -H / 2)
        if self.letterhead:
            l1, l2, l3 = self.letterhead
            canv.setFillColor(colors.HexColor("#1F3A5F"))
            canv.setFont(self.font + "-Bold", 13)
            canv.drawString(MARGIN, H - 16 * mm, l1)
            canv.setFont(self.font, 7.5)
            canv.setFillColor(colors.HexColor("#333333"))
            canv.drawString(MARGIN, H - 20.5 * mm, l2)
            canv.drawString(MARGIN, H - 24 * mm, l3)
            canv.setStrokeColor(colors.HexColor("#1F3A5F"))
            canv.setLineWidth(1.2)
            canv.line(MARGIN, H - 26.5 * mm, W - MARGIN, H - 26.5 * mm)
        canv.setFont("Arial", 6.3)
        canv.setFillColor(colors.HexColor("#666666"))
        canv.drawString(MARGIN, 10 * mm, SYNTHETIC_FOOTER)
        if self.footer_left:
            canv.drawString(MARGIN, 13.5 * mm, self.footer_left)
        if self.page_numbers:
            canv.setFont(self.font, 8)
            canv.drawRightString(W - MARGIN, 10 * mm, f"Page {doc.page}")
        canv.restoreState()

    # content helpers
    def p(self, text, style="body"):
        self.story.append(Paragraph(text, self.s[style]))

    def ps(self, texts, style="body"):
        for t in texts:
            self.p(t, style)

    def h1(self, t):
        self.p(t, "h1")

    def h2(self, t):
        self.p(t, "h2")

    def h3(self, t):
        self.p(t, "h3")

    def title(self, t):
        self.p(t, "title")

    def space(self, h=4):
        self.story.append(Spacer(1, h * mm))

    def br(self):
        self.story.append(PageBreak())

    def table(self, rows, widths=None, header=1, num_cols=(), bold_rows=(), total_rows=(), font_size=None,
              zebra=False, grid=True, keep=False, italic_rows=()):
        """rows: list of lists of str. num_cols: indices right-aligned. Widths in mm (sum <= 174)."""
        s = self.s
        data = []
        for i, r in enumerate(rows):
            line = []
            for j, c in enumerate(r):
                if isinstance(c, Paragraph):
                    line.append(c)
                    continue
                txt = "" if c is None else str(c)
                if i < header:
                    st = s["cellc"] if j > 0 or len(r) > 2 else s["cellb"]
                elif i in bold_rows or i in total_rows:
                    st = s["cellrb"] if j in num_cols else s["cellb"]
                else:
                    st = s["cellr"] if j in num_cols else s["cell"]
                if i in italic_rows:
                    txt = f"<i>{txt}</i>"
                line.append(Paragraph(txt, st))
            data.append(line)
        cw = [w * mm for w in widths] if widths else None
        t = Table(data, colWidths=cw, repeatRows=header, hAlign="LEFT")
        cmds = [("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
                ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
        if header:
            cmds.append(("BACKGROUND", (0, 0), (-1, header - 1), colors.HexColor("#DCE3EC")))
        if grid:
            cmds.append(("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#8C8C8C")))
        else:
            cmds.append(("LINEBELOW", (0, header - 1), (-1, header - 1), 0.6, colors.black))
        for i in total_rows:
            cmds.append(("LINEABOVE", (0, i), (-1, i), 0.7, colors.black))
            cmds.append(("LINEBELOW", (0, i), (-1, i), 0.7, colors.black))
        if zebra:
            for i in range(header, len(data)):
                if (i - header) % 2:
                    cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F4F6F9")))
        t.setStyle(TableStyle(cmds))
        self.story.append(KeepTogether(t) if keep else t)
        self.space(2)

    def signature(self, lines, left=None):
        """Right-hand signature block; optional left block (e.g. place and date)."""
        s = self.s
        right = [Paragraph(x, s["left"]) for x in lines]
        lft = [Paragraph(x, s["left"]) for x in (left or [])]
        t = Table([[lft, right]], colWidths=[87 * mm, 87 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
        self.story.append(KeepTogether([Spacer(1, 6 * mm), t]))

    def build(self):
        self.doc.build(self.story, onFirstPage=self._page, onLaterPages=self._page)
        return self.path
