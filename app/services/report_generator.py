"""
Professional Financial Report Generator
Produces a multi-page PDF using ReportLab Platypus.
Called by the /api/v1/report/generate endpoint.
"""
from __future__ import annotations
import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF

# ── Colour palette ────────────────────────────────────────────────────────────
GOLD   = colors.HexColor("#D4A843")
GOLD2  = colors.HexColor("#F0C060")
DARK   = colors.HexColor("#080C12")
DARK2  = colors.HexColor("#0E1420")
CARD   = colors.HexColor("#111827")
BORDER = colors.HexColor("#1E2D45")
MUTED  = colors.HexColor("#6B7A8F")
GREEN  = colors.HexColor("#2ECC71")
RED    = colors.HexColor("#E74C3C")
BLUE   = colors.HexColor("#4A9EFF")
WHITE  = colors.white
LIGHT  = colors.HexColor("#F0EEE8")

W, H = A4


# ── Helper: INR formatter ─────────────────────────────────────────────────────
def inr(n) -> str:
    if n is None:
        return "—"
    n = float(n)
    if n >= 10_000_000:
        return f"\u20b9{n/10_000_000:.2f} Cr"
    if n >= 100_000:
        return f"\u20b9{n/100_000:.2f} L"
    return f"\u20b9{n:,.0f}"


def pct(n) -> str:
    if n is None:
        return "—"
    return f"{float(n):.1f}%"


# ── Page templates (header/footer) ────────────────────────────────────────────
def _on_page(canvas, doc):
    """Runs on every page — draws the header bar and footer."""
    canvas.saveState()

    # ── Header bar ──
    canvas.setFillColor(DARK)
    canvas.rect(0, H - 22*mm, W, 22*mm, fill=1, stroke=0)

    canvas.setFillColor(GOLD)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(20*mm, H - 13*mm, "AI MONEY MENTOR")

    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(W - 20*mm, H - 13*mm, "Confidential — For Personal Use Only")

    # Gold accent line under header
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(1.5)
    canvas.line(0, H - 22*mm, W, H - 22*mm)

    # ── Footer ──
    canvas.setFillColor(DARK2)
    canvas.rect(0, 0, W, 14*mm, fill=1, stroke=0)

    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(20*mm, 5*mm, f"Generated {datetime.now().strftime('%d %b %Y, %I:%M %p')}  |  ET AI Hackathon 2026  |  Powered by NVIDIA NIM")
    canvas.drawRightString(W - 20*mm, 5*mm, f"Page {doc.page}")

    canvas.restoreState()


# ── Styles ────────────────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", fontSize=26, textColor=LIGHT, fontName="Helvetica-Bold",
                             spaceAfter=4, leading=30),
        "h2": ParagraphStyle("h2", fontSize=15, textColor=GOLD, fontName="Helvetica-Bold",
                             spaceBefore=14, spaceAfter=6, leading=20),
        "h3": ParagraphStyle("h3", fontSize=11, textColor=LIGHT, fontName="Helvetica-Bold",
                             spaceBefore=8, spaceAfter=4, leading=14),
        "body": ParagraphStyle("body", fontSize=9, textColor=LIGHT, fontName="Helvetica",
                               leading=14, spaceAfter=4),
        "muted": ParagraphStyle("muted", fontSize=8.5, textColor=MUTED, fontName="Helvetica",
                                leading=13, spaceAfter=3),
        "caption": ParagraphStyle("caption", fontSize=8, textColor=MUTED, fontName="Helvetica",
                                  alignment=TA_CENTER),
        "gold_label": ParagraphStyle("gl", fontSize=8, textColor=GOLD, fontName="Helvetica-Bold",
                                     spaceAfter=2, leading=10),
        "big_num": ParagraphStyle("bn", fontSize=20, textColor=GOLD, fontName="Helvetica-Bold",
                                  leading=24),
        "center": ParagraphStyle("ctr", fontSize=9, textColor=LIGHT, fontName="Helvetica",
                                 alignment=TA_CENTER, leading=13),
    }


# ── Cover page ─────────────────────────────────────────────────────────────────
def _cover(story, name: str, date_str: str, S: dict):
    # Dark background block
    cover_bg = Table([[""]], colWidths=[W - 40*mm], rowHeights=[80*mm])
    cover_bg.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), DARK2),
        ("ROUNDEDCORNERS", (0,0), (-1,-1), [8,8,8,8]),
    ]))
    story.append(Spacer(1, 10*mm))
    story.append(cover_bg)
    story.append(Spacer(1, -80*mm))  # overlap

    story.append(Spacer(1, 12*mm))
    story.append(Paragraph("PERSONAL FINANCIAL", ParagraphStyle("cl", fontSize=11, textColor=MUTED,
                             fontName="Helvetica", alignment=TA_CENTER)))
    story.append(Paragraph("INTELLIGENCE REPORT", ParagraphStyle("cl2", fontSize=28, textColor=LIGHT,
                             fontName="Helvetica-Bold", alignment=TA_CENTER, leading=32)))
    story.append(Spacer(1, 4*mm))

    # Gold divider
    story.append(HRFlowable(width="60%", thickness=1.5, color=GOLD, spaceAfter=8))

    story.append(Paragraph(name, ParagraphStyle("nm", fontSize=16, textColor=GOLD,
                             fontName="Helvetica-Bold", alignment=TA_CENTER)))
    story.append(Paragraph(date_str, ParagraphStyle("dt", fontSize=9, textColor=MUTED,
                             fontName="Helvetica", alignment=TA_CENTER, spaceBefore=3)))
    story.append(Spacer(1, 40*mm))

    # Feature pills row
    pills = [["◎ Health Score", "◈ FIRE Planner", "◇ Portfolio X-Ray", "◐ Tax Wizard", "◉ Life Events"]]
    t = Table(pills, colWidths=[32*mm]*5)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), BORDER),
        ("TEXTCOLOR", (0,0),(-1,-1), GOLD),
        ("FONTNAME", (0,0),(-1,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0),(-1,-1), 8),
        ("ALIGN", (0,0),(-1,-1), "CENTER"),
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,0),(-1,-1), [BORDER]),
        ("ROUNDEDCORNERS", (0,0),(-1,-1), [4,4,4,4]),
        ("TOPPADDING", (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
    ]))
    story.append(t)
    story.append(PageBreak())


# ── Section divider ────────────────────────────────────────────────────────────
def _section_header(story, number: str, title: str, subtitle: str, S: dict):
    bg = Table([[f"  {number}  ", Paragraph(f"<b>{title}</b><br/><font size='8' color='#6B7A8F'>{subtitle}</font>",
                  ParagraphStyle("sh", fontSize=13, textColor=LIGHT, fontName="Helvetica-Bold",
                                 leading=18))]],
               colWidths=[14*mm, W - 54*mm])
    bg.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(0,0), GOLD),
        ("BACKGROUND", (1,0),(1,0), DARK2),
        ("TEXTCOLOR", (0,0),(0,0), DARK),
        ("FONTNAME", (0,0),(0,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0),(0,0), 14),
        ("ALIGN", (0,0),(0,0), "CENTER"),
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0),(-1,-1), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
        ("LEFTPADDING", (1,0),(1,0), 12),
    ]))
    story.append(Spacer(1, 5*mm))
    story.append(bg)
    story.append(Spacer(1, 4*mm))


# ── KPI row ────────────────────────────────────────────────────────────────────
def _kpi_row(story, items: list[tuple[str, str, str]], S: dict):
    """items = [(label, value, sub), ...]"""
    n = len(items)
    col_w = (W - 40*mm) / n

    header_row = [Paragraph(f"<font color='#6B7A8F'>{i[0]}</font>",
                  ParagraphStyle("kh", fontSize=7.5, fontName="Helvetica-Bold",
                                 textColor=MUTED, leading=10)) for i in items]
    val_row    = [Paragraph(f"<b>{i[1]}</b>",
                  ParagraphStyle("kv", fontSize=16, fontName="Helvetica-Bold",
                                 textColor=GOLD, leading=20)) for i in items]
    sub_row    = [Paragraph(f"<font color='#6B7A8F'>{i[2]}</font>",
                  ParagraphStyle("ks", fontSize=7.5, fontName="Helvetica",
                                 textColor=MUTED, leading=11)) for i in items]

    t = Table([header_row, val_row, sub_row], colWidths=[col_w]*n)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), DARK2),
        ("TOPPADDING",    (0,0),(-1,-1), 8),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ("LINEAFTER", (0,0),(-2,-1), 0.5, BORDER),
        ("VALIGN", (0,0),(-1,-1), "TOP"),
    ]))
    story.append(t)
    story.append(Spacer(1, 3*mm))


# ── Dimension bar table ────────────────────────────────────────────────────────
def _dim_bars(story, dims: dict, S: dict):
    rows = []
    labels = {"emergency":"Emergency Fund","insurance":"Insurance",
              "investment":"Investment","debt":"Debt Health",
              "tax_efficiency":"Tax Efficiency","retirement":"Retirement"}
    for k, v in dims.items():
        v = float(v)
        color = GREEN if v >= 70 else (GOLD if v >= 45 else RED)
        bar_w = 80*mm * v / 100

        d = Drawing(80*mm, 6)
        d.add(Rect(0, 0, 80*mm, 6, fillColor=BORDER, strokeColor=None))
        d.add(Rect(0, 0, bar_w, 6, fillColor=color, strokeColor=None))

        rows.append([
            Paragraph(labels.get(k, k), ParagraphStyle("dl", fontSize=9, textColor=LIGHT,
                       fontName="Helvetica", leading=12)),
            d,
            Paragraph(f"<b>{v:.0f}</b>/100",
                      ParagraphStyle("dv", fontSize=9, textColor=color,
                                     fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=12)),
        ])

    t = Table(rows, colWidths=[45*mm, 82*mm, 22*mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LINEBELOW", (0,0),(-1,-2), 0.3, BORDER),
    ]))
    story.append(t)


# ── Generic data table ────────────────────────────────────────────────────────
def _data_table(story, headers: list, rows: list, col_widths: list = None, S: dict = None):
    col_widths = col_widths or [(W - 40*mm) / len(headers)] * len(headers)
    data = [[Paragraph(f"<b>{h}</b>",
              ParagraphStyle("th", fontSize=8, textColor=GOLD, fontName="Helvetica-Bold",
                             leading=11)) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c),
                     ParagraphStyle("td", fontSize=8.5, textColor=LIGHT, fontName="Helvetica",
                                    leading=12)) for c in row])
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,0), DARK2),
        ("LINEBELOW", (0,0),(-1,0), 1, GOLD),
        ("ROWBACKGROUNDS", (0,1),(-1,-1), [CARD, DARK2]),
        ("TOPPADDING", (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING", (0,0),(-1,-1), 8),
        ("RIGHTPADDING", (0,0),(-1,-1), 8),
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
        ("LINEBELOW", (0,1),(-1,-1), 0.3, BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 3*mm))


# ── Action card list ──────────────────────────────────────────────────────────
def _action_cards(story, actions: list, S: dict):
    for a in actions[:5]:
        text = a.get("action") or a.get("text") or str(a)
        priority = str(a.get("priority","") or a.get("urgency","") or "").upper()
        impact = a.get("monthly_impact") or a.get("impact") or ""
        color = RED if "CRITICAL" in priority or "HIGH" in priority else (GOLD if "MEDIUM" in priority else BLUE)
        row = [[
            Paragraph(f"<b>{priority}</b>",
                      ParagraphStyle("ap", fontSize=7.5, textColor=color, fontName="Helvetica-Bold", leading=10)),
            Paragraph(text, ParagraphStyle("at", fontSize=9, textColor=LIGHT, fontName="Helvetica", leading=13)),
            Paragraph(impact, ParagraphStyle("ai", fontSize=8, textColor=MUTED, fontName="Helvetica", leading=11)),
        ]]
        t = Table(row, colWidths=[22*mm, 100*mm, 45*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,-1), DARK2),
            ("LINEAFTER", (0,0),(0,0), 2, color),
            ("TOPPADDING", (0,0),(-1,-1), 7),
            ("BOTTOMPADDING", (0,0),(-1,-1), 7),
            ("LEFTPADDING", (0,0),(-1,-1), 8),
            ("VALIGN", (0,0),(-1,-1), "TOP"),
        ]))
        story.append(t)
        story.append(Spacer(1, 1.5*mm))


# ── Bullet list ───────────────────────────────────────────────────────────────
def _bullets(story, items: list, S: dict):
    for item in items[:8]:
        story.append(Paragraph(
            f"<font color='#D4A843'>▸</font>  {item}",
            ParagraphStyle("bl", fontSize=9, textColor=LIGHT, fontName="Helvetica",
                           leading=14, leftIndent=8, spaceAfter=3)
        ))


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
def generate_report(
    user_name: str,
    profile: dict,
    health_data: dict | None = None,
    fire_data: dict | None = None,
    tax_data: dict | None = None,
    portfolio_data: dict | None = None,
    life_data: dict | None = None,
) -> bytes:
    """
    Generate a professional PDF report and return raw bytes.
    Pass None for any section that hasn't been run yet — it will be skipped.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=28*mm, bottomMargin=20*mm,
        title="AI Money Mentor — Personal Financial Report",
        author="AI Money Mentor",
    )
    S = _styles()
    story = []

    date_str = datetime.now().strftime("%d %B %Y")
    _cover(story, user_name, date_str, S)

    # ── SECTION 1: EXECUTIVE SUMMARY ─────────────────────────────────────────
    _section_header(story, "01", "Executive Summary", "Your financial snapshot at a glance", S)

    income   = profile.get("monthly_income") or 0
    expenses = profile.get("monthly_expenses") or 0
    savings  = income - expenses
    sav_rate = (savings / income * 100) if income else 0
    total_inv = sum(profile.get(k, 0) or 0 for k in [
        "existing_mutual_funds","existing_stocks","existing_ppf",
        "existing_nps","existing_fd","existing_real_estate"])
    total_debt = sum(profile.get(k, 0) or 0 for k in [
        "home_loan_outstanding","car_loan_outstanding",
        "personal_loan_outstanding","credit_card_debt"])
    net_worth = total_inv - total_debt

    score = health_data.get("total_score") if health_data else None

    _kpi_row(story, [
        ("Health Score", str(round(score)) if score else "—", f"Grade {health_data.get('grade','—')}" if health_data else "Not run"),
        ("Monthly Income", inr(income), "gross monthly"),
        ("Savings Rate", pct(sav_rate), f"{inr(savings)}/month"),
        ("Total Investments", inr(total_inv), "across all instruments"),
        ("Net Worth", inr(net_worth), "investments minus debt"),
    ], S)

    if health_data and health_data.get("overall_assessment"):
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("<b>AI Assessment</b>", S["h3"]))
        story.append(Paragraph(health_data["overall_assessment"], S["body"]))

    story.append(PageBreak())

    # ── SECTION 2: MONEY HEALTH SCORE ────────────────────────────────────────
    if health_data:
        _section_header(story, "02", "Money Health Score",
                        "6-dimension financial wellness analysis", S)

        score_val = health_data.get("total_score", 0)
        grade = health_data.get("grade", "—")

        kpi_color = GREEN if score_val >= 75 else (GOLD if score_val >= 50 else RED)

        # Score + grade row
        score_t = Table([[
            Paragraph(f"<b>{round(score_val)}</b>",
                      ParagraphStyle("scr", fontSize=48, textColor=kpi_color,
                                     fontName="Helvetica-Bold", leading=52, alignment=TA_CENTER)),
            Paragraph(f"out of 100\n<b>Grade {grade}</b>",
                      ParagraphStyle("grd", fontSize=11, textColor=LIGHT,
                                     fontName="Helvetica", leading=18)),
        ]], colWidths=[35*mm, 50*mm])
        score_t.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,-1), DARK2),
            ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
            ("ALIGN", (0,0),(0,0), "CENTER"),
            ("TOPPADDING", (0,0),(-1,-1), 10),
            ("BOTTOMPADDING", (0,0),(-1,-1), 10),
            ("LEFTPADDING", (0,0),(-1,-1), 12),
        ]))
        story.append(score_t)
        story.append(Spacer(1, 4*mm))

        dims = health_data.get("dimensions", {})
        if dims:
            story.append(Paragraph("<b>Dimension Breakdown</b>", S["h3"]))
            _dim_bars(story, dims, S)

        actions = health_data.get("priority_actions", [])
        if actions:
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph("<b>Priority Actions</b>", S["h3"]))
            _action_cards(story, actions, S)

        wins = health_data.get("quick_wins", [])
        if wins:
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph("<b>Quick Wins</b>", S["h3"]))
            _bullets(story, wins, S)

        story.append(PageBreak())

    # ── SECTION 3: FIRE PLANNER ───────────────────────────────────────────────
    if fire_data:
        _section_header(story, "03", "FIRE Planner",
                        "Financial Independence, Retire Early — your personalised roadmap", S)

        fs = fire_data.get("fire_summary", {})
        _kpi_row(story, [
            ("Corpus Needed", inr(fs.get("corpus_needed")), "at retirement"),
            ("Years to FIRE", str(fs.get("years_to_fire","—")), f"FIRE year: {fs.get('fire_date','—')}"),
            ("Monthly SIP", inr(fs.get("monthly_sip_required")), "@ 12% CAGR"),
            ("Monthly Gap", inr(fs.get("current_gap_per_month")), "to bridge"),
        ], S)

        # SIP breakdown table
        sips = fire_data.get("sip_breakdown", [])
        if sips:
            story.append(Paragraph("<b>SIP Breakdown</b>", S["h3"]))
            _data_table(story,
                ["Fund Category", "Monthly SIP", "Tax Benefit", "Rationale"],
                [[s.get("category",""), inr(s.get("monthly_amount")),
                  s.get("tax_benefit","—"), s.get("rationale","")] for s in sips],
                col_widths=[45*mm, 30*mm, 30*mm, 62*mm], S=S)

        # Milestones
        ms = fire_data.get("milestones", [])
        if ms:
            story.append(Paragraph("<b>Milestone Timeline</b>", S["h3"]))
            _data_table(story,
                ["Year", "Age", "Target Corpus", "Key Action"],
                [[m.get("year",""), m.get("age",""), inr(m.get("target_corpus")), m.get("key_action","")] for m in ms],
                col_widths=[22*mm, 18*mm, 35*mm, 92*mm], S=S)

        # Asset allocation
        alloc = fire_data.get("asset_allocation", {})
        phases = [("current_phase","Now"),("5_years_out","In 5 Years"),("at_retirement","At Retirement")]
        alloc_rows = []
        for key, label in phases:
            a = alloc.get(key, {})
            if a:
                alloc_rows.append([label, f"{a.get('equity',0)}%", f"{a.get('debt',0)}%", f"{a.get('gold',0)}%"])
        if alloc_rows:
            story.append(Paragraph("<b>Asset Allocation Glide Path</b>", S["h3"]))
            _data_table(story, ["Phase","Equity","Debt","Gold"], alloc_rows,
                        col_widths=[50*mm, 40*mm, 40*mm, 37*mm], S=S)

        # Risks
        risks = fire_data.get("risks", [])
        if risks:
            story.append(Paragraph("<b>Key Risks & Mitigations</b>", S["h3"]))
            _data_table(story, ["Risk","Mitigation"],
                [[r.get("risk",""), r.get("mitigation","")] for r in risks[:4]],
                col_widths=[80*mm, 87*mm], S=S)

        story.append(PageBreak())

    # ── SECTION 4: TAX WIZARD ─────────────────────────────────────────────────
    if tax_data:
        _section_header(story, "04", "Tax Analysis",
                        "FY 2024-25 — Old vs New Regime + Deduction Gaps", S)

        rc = tax_data.get("regime_comparison", tax_data.get("comparison", {}))
        old_r = rc.get("old_regime", {})
        new_r = rc.get("new_regime", {})
        rec   = rc.get("recommended", rc.get("recommendation","new_regime"))
        saving = rc.get("savings_with_recommended",
                 abs(rc.get("saving_with_old", rc.get("saving_with_recommended", 0)) or 0))

        story.append(Paragraph("<b>Regime Comparison</b>", S["h3"]))
        regime_rows = [
            ["Old Regime", inr(old_r.get("total_tax", rc.get("old_tax"))),
             pct(old_r.get("effective_rate")), inr(old_r.get("monthly_take_home")),
             "✓ RECOMMENDED" if rec == "old_regime" else ""],
            ["New Regime", inr(new_r.get("total_tax", rc.get("new_tax"))),
             pct(new_r.get("effective_rate")), inr(new_r.get("monthly_take_home")),
             "✓ RECOMMENDED" if rec == "new_regime" else ""],
        ]
        _data_table(story, ["Regime","Total Tax","Effective Rate","Monthly Take-Home",""],
                    regime_rows, col_widths=[35*mm, 35*mm, 32*mm, 42*mm, 23*mm], S=S)

        story.append(Paragraph(
            f"<font color='#2ECC71'><b>Recommendation:</b> {rec.replace('_',' ').title()} — saves {inr(saving)}/year.</font>  {rc.get('reason','')}",
            S["body"]))

        # Deduction gaps
        gaps = tax_data.get("deduction_gaps", [])
        if gaps:
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph("<b>Deduction Gaps — Money Left on Table</b>", S["h3"]))
            _data_table(story,
                ["Section","Max Allowed","Used","Gap","Tax Saved if Filled","Instruments"],
                [[g.get("section",""), inr(g.get("max_allowed")), inr(g.get("currently_used")),
                  inr(g.get("gap")), inr(g.get("potential_saving")),
                  ", ".join(g.get("instruments",[]))[:40]] for g in gaps],
                col_widths=[22*mm, 26*mm, 24*mm, 24*mm, 28*mm, 43*mm], S=S)

        # Tax saving plan
        plan = tax_data.get("tax_saving_plan", [])
        if plan:
            story.append(Paragraph("<b>Action Plan</b>", S["h3"]))
            _action_cards(story, [
                {"action": p.get("action",""), "priority": f"Priority {p.get('priority','')}",
                 "monthly_impact": f"Invest {inr(p.get('invest_amount'))} → Save {inr(p.get('tax_saved'))}"}
                for p in plan], S)

        story.append(PageBreak())

    # ── SECTION 5: PORTFOLIO X-RAY ────────────────────────────────────────────
    if portfolio_data:
        _section_header(story, "05", "Portfolio X-Ray",
                        "Mutual fund analysis — XIRR, overlap, expense drag", S)

        ps = portfolio_data.get("portfolio_summary", portfolio_data.get("summary", {}))
        hs = portfolio_data.get("health_signals", {})

        _kpi_row(story, [
            ("Total Invested", inr(ps.get("total_invested")), ""),
            ("Current Value", inr(ps.get("total_current_value")), ""),
            ("Absolute Gain", inr(ps.get("absolute_gain")), pct(ps.get("gain_pct")) + " returns"),
            ("XIRR", pct(ps.get("xirr", portfolio_data.get("xirr"))), "annualised"),
            ("Overlap Score", str(hs.get("overlap_score", portfolio_data.get("overlap_score","—"))), hs.get("overlap_verdict","") or ""),
        ], S)

        # Fund ratings
        ratings = portfolio_data.get("fund_ratings", [])
        if ratings:
            story.append(Paragraph("<b>Fund-by-Fund Verdict</b>", S["h3"]))
            _data_table(story, ["Fund","Verdict","Reason","Action"],
                [[r.get("fund_name","")[:40], r.get("verdict","").upper(),
                  r.get("reason",""), r.get("action","")] for r in ratings[:10]],
                col_widths=[55*mm, 18*mm, 55*mm, 39*mm], S=S)

        rb = portfolio_data.get("rebalancing_plan", {})
        insights = portfolio_data.get("top_insights", [])
        if insights:
            story.append(Paragraph("<b>Top Insights</b>", S["h3"]))
            _bullets(story, insights, S)

        if rb.get("steps"):
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph("<b>Rebalancing Steps</b>", S["h3"]))
            _bullets(story, rb["steps"], S)
            if rb.get("tax_considerations"):
                story.append(Paragraph(f"<font color='#6B7A8F'>Tax note: {rb['tax_considerations']}</font>", S["muted"]))

        story.append(PageBreak())

    # ── SECTION 6: DISCLAIMER ─────────────────────────────────────────────────
    _section_header(story, "06", "Important Disclaimer", "", S)
    story.append(Paragraph(
        "This report has been generated by AI Money Mentor, an AI-powered personal finance tool "
        "built for the ET AI Hackathon 2026. The analysis is powered by NVIDIA NIM (meta/llama-3.1-70b-instruct) "
        "and deterministic Indian tax/investment math.", S["body"]))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "<b>This report does not constitute financial advice.</b> All figures, projections, and "
        "recommendations are for informational and educational purposes only. Past performance is "
        "not indicative of future results. Consult a SEBI-registered investment advisor before "
        "making any investment decisions. Tax calculations are based on FY 2024-25 Indian income "
        "tax rules and may not account for all individual circumstances.", S["muted"]))
    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "AI Money Mentor  ·  ET AI Hackathon 2026  ·  Powered by NVIDIA NIM  ·  Built with FastAPI + SQLite",
        ParagraphStyle("footer_text", fontSize=8, textColor=MUTED, fontName="Helvetica",
                       alignment=TA_CENTER)))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()
