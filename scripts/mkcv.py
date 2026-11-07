"""Compact one-page CV builder (base-14 Helvetica, no embedded fonts -> tiny PDF).
Usage: python3 mkcv.py job.json out.pdf
job.json keys: role, profile, tj_bullets (list), skills_extra (optional dict label->text to prepend)
"""
import json, sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib import colors

job = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
FS = job.get("fs", 9.3)

LINKS = [("linkedin", "https://www.linkedin.com/in/deepak-prajapati-695963204/"),
         ("github", "https://github.com/Deepak420-GrandMaster"),
         ("web", "https://deepak420-grandmaster.github.io/Deepak_Prajapati_portfolio.github.io/")]

# Official brand marks (Simple Icons, CC0), 24x24 viewBox, drawn as vectors: no images, no extra deps.
ICON_PATHS = {
    "linkedin": ("#0A66C2", "M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.948 1.637-2.182 3.37-2.182 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"),
    "github": ("#181717", "M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"),
}

def _svg_tokens(d):
    import re
    for m in re.finditer(r"[MmLlHhVvCcSsZz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?", d):
        yield m.group(0)

def draw_svg_path(canvas, d, x0, y0, size, color):
    """Draw a 24x24 SVG path (M L H V C S Z, abs+rel) at (x0, y0) bottom-left, scaled to size pt."""
    k = size / 24.0
    P = lambda x, y: (x0 + x * k, y0 + (24 - y) * k)
    path = canvas.beginPath()
    toks = list(_svg_tokens(d)); i = 0
    cx = cy = sx = sy = 0.0; lc2 = None; cmd = None
    isnum = lambda t: t not in "MmLlHhVvCcSsZz"
    def num():
        nonlocal i
        v = float(toks[i]); i += 1; return v
    while i < len(toks):
        if not isnum(toks[i]):
            cmd = toks[i]; i += 1
            if cmd in "Zz":
                path.close(); cx, cy = sx, sy; lc2 = None; continue
        rel = cmd.islower(); C = cmd.upper()
        ox, oy = (cx, cy) if rel else (0, 0)
        if C == "M":
            cx, cy = ox + num(), oy + num(); sx, sy = cx, cy
            path.moveTo(*P(cx, cy)); cmd = "l" if rel else "L"; lc2 = None
        elif C == "L":
            cx, cy = ox + num(), oy + num(); path.lineTo(*P(cx, cy)); lc2 = None
        elif C == "H":
            cx = ox + num(); path.lineTo(*P(cx, cy)); lc2 = None
        elif C == "V":
            cy = oy + num(); path.lineTo(*P(cx, cy)); lc2 = None
        elif C in "CS":
            if C == "C":
                x1, y1 = ox + num(), oy + num()
            else:
                x1, y1 = (2 * cx - lc2[0], 2 * cy - lc2[1]) if lc2 else (cx, cy)
            x2, y2 = ox + num(), oy + num(); x, y = ox + num(), oy + num()
            path.curveTo(*P(x1, y1), *P(x2, y2), *P(x, y))
            lc2 = (x2, y2); cx, cy = x, y
    canvas.saveState()
    canvas.setFillColor(colors.HexColor(color))
    canvas.drawPath(path, stroke=0, fill=1, fillMode=0)
    canvas.restoreState()

def draw_globe(canvas, x0, y0, size, color="#1F6FB2"):
    r = size / 2.0; cx, cy = x0 + r, y0 + r
    canvas.saveState()
    canvas.setFillColor(colors.HexColor(color)); canvas.circle(cx, cy, r, stroke=0, fill=1)
    canvas.setStrokeColor(colors.white); canvas.setLineWidth(size * 0.06)
    rr = r * 0.78
    canvas.circle(cx, cy, rr, stroke=1, fill=0)
    canvas.ellipse(cx - rr * 0.42, cy - rr, cx + rr * 0.42, cy + rr, stroke=1, fill=0)
    canvas.line(cx, cy - rr, cx, cy + rr)
    canvas.line(cx - rr, cy, cx + rr, cy)
    for f in (0.5, -0.5):
        hw = rr * (1 - f * f) ** 0.5
        canvas.line(cx - hw, cy + rr * f, cx + hw, cy + rr * f)
    canvas.restoreState()

def draw_icon(canvas, name, x, y, size):
    if name == "web":
        draw_globe(canvas, x, y, size)
    else:
        color, d = ICON_PATHS[name]
        draw_svg_path(canvas, d, x, y, size, color)

base = ParagraphStyle("b", fontName="Helvetica", fontSize=FS, leading=FS * 1.22, alignment=TA_LEFT)
bul = ParagraphStyle("bul", parent=base, leftIndent=9, bulletIndent=1, spaceAfter=0.6)
h1 = ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=19, leading=22)
role = ParagraphStyle("role", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=13.5)
h2 = ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=FS + 0.9, leading=FS + 3, spaceBefore=5, spaceAfter=1.5)
small = ParagraphStyle("s", parent=base, fontSize=FS - 0.2, leading=(FS - 0.2) * 1.22)
ital = ParagraphStyle("i", parent=base, fontName="Helvetica-Oblique")
W = A4[0] - 28 * mm

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def section(title):
    t = Table([[Paragraph(title.upper(), h2)]], colWidths=[W])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.7, colors.black),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t

def jobline(left, right):
    t = Table([[Paragraph("<b>%s</b>" % esc(left), base), Paragraph("<b>%s</b>" % esc(right), ParagraphStyle("r", parent=base, alignment=2))]],
              colWidths=[W * 0.72, W * 0.28])
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t

def bullets(items):
    return [Paragraph(esc(i), bul, bulletText="•") for i in items]

C = job["content"]  # language-specific base content
story = []
story.append(Paragraph("DEEPAK PRAJAPATI", h1))
story.append(Paragraph(esc(job["role"]), role))
story.append(Spacer(1, 21))  # room for link badges drawn on canvas
story.append(Paragraph(esc(C["status"]), small))
story.append(section(C["h_profile"]))
story.append(Paragraph(esc(job["profile"]), base))
story.append(section(C["h_exp"]))
story.append(jobline(C["tj_title"], C["tj_dates"]))
story.append(Paragraph(esc(C["tj_loc"]), ital))
story += bullets(job["tj_bullets"])
for e in C["experience"]:
    story.append(jobline(e["title"], e["dates"]))
    if e.get("sub"):
        story.append(Paragraph(esc(e["sub"]), ital))
    story += bullets(e["bullets"])
story.append(section(C["h_proj"]))
story += [Paragraph(p, bul, bulletText="•") for p in C["projects"]]
story.append(section(C["h_edu"]))
story += [Paragraph(p, bul, bulletText="•") for p in C["education"]]
story.append(section(C["h_skills"]))
skills = list(job.get("skills_order") or C["skills"].keys())
for k in skills:
    story.append(Paragraph("<b>%s</b> %s" % (esc(k), esc(C["skills"][k])), small))

def first(canvas, doc):
    x = 14 * mm + 6
    y = A4[1] - 10 * mm - 6 - 22 - 13.5 - 19
    size = 15
    for name, url in LINKS:
        draw_icon(canvas, name, x, y, size)
        canvas.linkURL(url, (x, y, x + size, y + size), relative=0)
        x += size + 9
    canvas.setTitle("Deepak Prajapati - CV")
    canvas.setAuthor("Deepak Prajapati")

doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=10 * mm, bottomMargin=8 * mm,
                        title="Deepak Prajapati - CV", author="Deepak Prajapati")
pages = []
doc.build(story, onFirstPage=first, onLaterPages=lambda c, d: pages.append(1))
print("PAGES", 1 + len(pages))
