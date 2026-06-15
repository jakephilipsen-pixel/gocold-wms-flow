#!/usr/bin/env python3
"""Render the staff/supervisor WMS-tools brief to a branded Go Cold PDF.

One-pager, plain English, Go Cold colours + logo. Content source of truth is
``docs/staff-brief-wms-tools.md`` — keep the two in sync if you edit copy.

    python scripts/build_staff_brief_pdf.py
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "assests" / "gocold_logo.png"
OUT = ROOT / "docs" / "Go-Cold-WMS-Tools-Staff-Brief.pdf"

# Go Cold palette (mirrors src/output/pdf_picksheet.py).
GREEN = HexColor("#00C452")
DARK = HexColor("#003366")
MID = HexColor("#0076A8")
GREY = HexColor("#5A6472")
LIGHT = HexColor("#F4F4F6")


def main() -> int:
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    title = ParagraphStyle(
        "title", fontName="Helvetica-Bold", fontSize=17, leading=20,
        textColor=DARK)
    subtitle = ParagraphStyle(
        "subtitle", fontName="Helvetica-Oblique", fontSize=9.5, leading=12,
        textColor=GREY)
    intro = ParagraphStyle(
        "intro", fontName="Helvetica", fontSize=9, leading=12.5,
        textColor=HexColor("#222222"), alignment=TA_LEFT, spaceAfter=2)
    h = ParagraphStyle(
        "h", fontName="Helvetica-Bold", fontSize=10.5, leading=13,
        textColor=GREEN, spaceBefore=7, spaceAfter=2)
    body = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=8.6, leading=11.3,
        textColor=HexColor("#222222"), spaceAfter=2)
    bullet = ParagraphStyle(
        "bullet", parent=body, leftIndent=9, bulletIndent=1, spaceAfter=1)
    callout = ParagraphStyle(
        "callout", fontName="Helvetica", fontSize=8.6, leading=11.3,
        textColor=DARK)

    def P(text, style=body):
        return Paragraph(text, style)

    story: list = []

    # ---- header band: logo + title ----
    if LOGO.exists():
        logo = Image(str(LOGO), width=36 * mm, height=20.1 * mm)
    else:
        logo = Spacer(0, 0)
    head = Table(
        [[logo, [P("Warehouse Workflow Tools", title),
                 P("A plain-English guide for the floor and supervisors",
                   subtitle)]]],
        colWidths=[40 * mm, 140 * mm])
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (1, 0), (1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(head)
    story.append(Spacer(0, 4))
    story.append(_rule(GREEN))
    story.append(Spacer(0, 4))

    story.append(P(
        "We're rolling out three tools that work together to make picking "
        "faster, tidier, and grouped by where orders are going. They run "
        "quietly behind the scenes and <b>generate the paperwork</b> — a "
        "person always stays in control. Nothing is changed in CartonCloud "
        "automatically.", intro))

    # ---- the three tools ----
    story.append(P("The three tools", ParagraphStyle(
        "section", fontName="Helvetica-Bold", fontSize=11.5, leading=13,
        textColor=DARK, spaceBefore=6, spaceAfter=1)))

    story.append(P('1. Dim Capture App — <i>"measure it once"</i>', h))
    story.append(P(
        "A simple scan-and-type app on the warehouse network. Scan a product, "
        "then enter the carton's size (L × W × H), weight, units per inner "
        "pack, whether it goes through the pick bench for repack, and which "
        "bay height it lives at.", body))
    story.append(P(
        "Everything downstream needs these numbers — without them the system "
        "can't tell a pallet job from a small pick, or work out how many "
        "cartons fit on a pallet. About <b>409 Forage products are already "
        "measured</b>.", body))
    story.append(P(
        "<b>Your part:</b> when a new product arrives or a carton size "
        "changes, measure it once in the app. That keeps everything else "
        "correct.", body))

    story.append(P('2. Runs — <i>"group by where it’s going"</i>', h))
    story.append(P(
        "Looks at our delivery history and works out which delivery run each "
        "order belongs on today — Geelong, Bendigo, Surf Coast, and so on — "
        "with a confidence and a reason. Carriers and warehouse pickups are "
        "split out automatically. Anything the system is unsure about goes to "
        "a <b>review queue</b> for a person to confirm. The result is a clean "
        "per-run list, so we pick everything for a run together.", body))

    story.append(P('3. Wave Pick Generation — <i>"the right method, in walk '
                   'order"</i>', h))
    story.append(P(
        "Takes the live open orders, groups them by run, and sorts each order "
        "into the right pick method:", body))
    story.append(P(
        "<b>Pallet pick</b> — big orders; the picker builds a pallet "
        "directly, no bench.", bullet, ))
    story.append(P(
        "<b>Wave (bypass)</b> — small orders of full-carton items; waved "
        "together, skip the bench, straight to dispatch.", bullet))
    story.append(P(
        "<b>Wave (bench)</b> — small orders with a repack item; waved "
        "together, through the pick bench for scan/repack.", bullet))
    story.append(P(
        "Then it prints an <b>operator-ready pick sheet</b> for each wave — "
        "every line in walk order with its location, so you just walk down "
        "the page.", body))

    # ---- through-the-day flow (callout box) ----
    flow = [
        P("How it works through the day (with SAP)", ParagraphStyle(
            "flowh", fontName="Helvetica-Bold", fontSize=10.5, leading=13,
            textColor=white, spaceAfter=3)),
        P("Orders come in throughout the day. As they land:", ParagraphStyle(
            "flowi", parent=callout, textColor=white)),
        P("•&nbsp; <b>Big pallet jobs are sorted out straight away</b> and can "
          "go to the floor immediately — no waiting around.", ParagraphStyle(
            "flb", parent=callout, textColor=white, leftIndent=4, spaceBefore=2)),
        P("•&nbsp; <b>Small wave-pick lots are held and batched.</b> Rather "
          "than sending a picker out for a handful of lines, the system waits "
          "until enough orders have built up to make an efficient wave, then "
          "generates the pick sheet in one go.", ParagraphStyle(
            "flb2", parent=callout, textColor=white, leftIndent=4, spaceBefore=2)),
        P("Fewer trips, shorter walks, and orders already grouped by run — the "
          "big stuff flowing immediately, the small stuff combined into tidy "
          "waves.", ParagraphStyle(
            "flf", parent=callout, textColor=white, spaceBefore=3)),
    ]
    box = Table([[flow]], colWidths=[180 * mm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), MID),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    story.append(Spacer(0, 5))
    story.append(box)

    # ---- what stays the same ----
    story.append(P("What stays the same", ParagraphStyle(
        "ssh", fontName="Helvetica-Bold", fontSize=10.5, leading=13,
        textColor=DARK, spaceBefore=8, spaceAfter=2)))
    story.append(P(
        "•&nbsp; The tools <b>read</b> order data and <b>produce paperwork</b>. "
        "They never change anything in CartonCloud on their own.", bullet))
    story.append(P(
        "•&nbsp; A supervisor reviews anything the system is unsure about.",
        bullet))
    story.append(P(
        "•&nbsp; We build behind the scenes, check it against real days first, "
        "then roll it out — no surprises on the floor.", bullet))

    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title="Go Cold — Warehouse Workflow Tools",
        author="Go Cold")
    doc.build(story)
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
    return 0


def _rule(color):
    from reportlab.platypus import Table, TableStyle
    t = Table([[""]], colWidths=[180 * mm], rowHeights=[1.6])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), color)]))
    return t


if __name__ == "__main__":
    raise SystemExit(main())
