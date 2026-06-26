from fpdf import FPDF
from datetime import datetime
import os

REPORT_COLORS = {
    "hedge_fund": (20, 60, 100),
    "ipo":        (0, 100, 60),
    "ma":         (120, 30, 30),
    "issuance":   (80, 50, 120),
}

REPORT_TITLES = {
    "hedge_fund": "HEDGE FUND ACTIVITY REPORT",
    "ipo":        "IPO PIPELINE REPORT",
    "ma":         "M&A ACTIVITY REPORT",
    "issuance":   "EQUITY & BOND ISSUANCE REPORT",
}

def clean(text):
    text = (text or "").encode("latin-1", errors="replace").decode("latin-1")
    words = text.split(" ")
    broken = []
    for w in words:
        while len(w) > 60:
            broken.append(w[:60])
            w = w[60:]
        broken.append(w)
    return " ".join(broken)


class ReportPDF(FPDF):
    def __init__(self, category):
        super().__init__()
        self.category = category
        self.color = REPORT_COLORS.get(category, (20, 40, 80))
        self.set_margins(15, 25, 15)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        r, g, b = self.color
        self.set_fill_color(r, g, b)
        self.rect(0, 0, 210, 22, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 13)
        self.set_xy(0, 6)
        self.cell(0, 10, REPORT_TITLES.get(self.category, "REPORT"), align="C")
        self.set_text_color(0, 0, 0)
        self.ln(20)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 8, f"Hedge Fund News Agent  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  Page {self.page_no()}", align="C")

    def summary_box(self, points):
        r, g, b = self.color
        self.set_fill_color(r, g, b)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 10)
        w = self.w - self.l_margin - self.r_margin
        self.set_x(self.l_margin)
        self.cell(w, 7, "  KEY TAKEAWAYS", ln=True, fill=True)
        self.set_fill_color(240, 243, 250)
        self.set_text_color(30, 30, 30)
        self.set_font("Helvetica", "", 8)
        for point in points:
            self.set_x(self.l_margin)
            self.multi_cell(w, 5, clean(f"  •  {point}"), fill=True)
        self.ln(4)

    def section_header(self, title):
        r, g, b = self.color
        self.set_fill_color(r + 40 if r < 216 else 255,
                            g + 40 if g < 216 else 255,
                            b + 40 if b < 216 else 255)
        self.set_text_color(30, 30, 30)
        self.set_font("Helvetica", "B", 9)
        w = self.w - self.l_margin - self.r_margin
        self.set_x(self.l_margin)
        self.cell(w, 7, clean(f"  {title}"), ln=True, fill=True)
        self.ln(1)

    def item_block(self, item, index):
        w = self.w - self.l_margin - self.r_margin
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(30, 30, 80)
        self.multi_cell(w, 5, clean(f"[{index}]  {item.get('title', '')}"))
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(90, 90, 90)
        if item.get("published"):
            self.cell(w, 4, clean(f"  {item['published'][:50]}"), ln=True)
        if item.get("summary"):
            self.set_x(self.l_margin)
            self.multi_cell(w, 4, clean("  " + item["summary"].replace("\n", " ").strip()[:300]))
        if item.get("link"):
            self.set_x(self.l_margin)
            self.set_text_color(0, 80, 180)
            self.cell(w, 4, clean("  " + item["link"][:85]), ln=True)
        self.set_text_color(0, 0, 0)
        self.set_draw_color(210, 210, 210)
        self.set_x(self.l_margin)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(4)


def generate_report(category, news_items, sec_items, summary_points, output_dir="."):
    pdf = ReportPDF(category)
    pdf.add_page()

    date_str = datetime.now().strftime("%A, %B %d, %Y  |  %H:%M")
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 5, f"Report Date: {date_str}", ln=True)
    pdf.ln(2)

    if summary_points:
        pdf.summary_box(summary_points)

    if news_items:
        pdf.section_header(f"NEWS  ({len(news_items)} articles)")
        sources = {}
        for a in news_items:
            sources.setdefault(a["source"], []).append(a)
        i = 1
        for source, items in sources.items():
            for item in items:
                pdf.item_block(item, i)
                i += 1

    if sec_items:
        pdf.section_header(f"SEC FILINGS  ({len(sec_items)} filings)")
        sources = {}
        for a in sec_items:
            sources.setdefault(a["source"], []).append(a)
        i = 1
        for source, items in sources.items():
            for item in items:
                pdf.item_block(item, i)
                i += 1

    filename = os.path.join(
        output_dir,
        f"{category.upper()}_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )
    pdf.output(filename)
    return filename
