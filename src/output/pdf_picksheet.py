"""Render a ``WavePickSheet`` to a Go Cold-themed PDF.

The PDF is what the picker carries on the floor. Three sections:

  Page 1 — Cover with wave ID, stream, run group, receive date, totals,
           estimated pick time, and a stream-specific instruction note.
  Page 2+ — The pick lines table, pre-numbered in walk order, with big
           tick-boxes per row. Location code rendered monospace.
  Final page — Order summary: the SO refs and destinations the operator
               pastes into CC when manually creating the wave.

Footer on every page: wave_id + page X of Y + generation timestamp.

Theme: navy header rows, green underlines, brand split bars on the
cover. Honours the operator-locked Go Cold palette:
  GREEN  #00C452   BLUE  #0096CC   DARK  #003366   MID  #0076A8
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from analysis.wave_picks import (
    DEFAULT_LINES_PER_HOUR,
    WavePickSheet,
    estimated_time_to_pick_minutes,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoColdTheme:
    """Locked Go Cold brand colours + font choices."""
    green: colors.Color = colors.HexColor("#00C452")
    blue: colors.Color = colors.HexColor("#0096CC")
    dark: colors.Color = colors.HexColor("#003366")
    mid: colors.Color = colors.HexColor("#0076A8")
    light_grey: colors.Color = colors.HexColor("#F4F4F6")
    body_font: str = "Helvetica"
    body_font_bold: str = "Helvetica-Bold"
    mono_font: str = "Courier-Bold"


THEME = GoColdTheme()


# ---------- styles ----------

def _build_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "wave_title": ParagraphStyle(
            "wave_title",
            parent=base["Title"],
            fontName=THEME.body_font_bold,
            fontSize=34,
            leading=38,
            textColor=colors.white,
            alignment=1,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName=THEME.body_font_bold,
            fontSize=15,
            leading=18,
            textColor=colors.white,
            alignment=1,
        ),
        "doc_id": ParagraphStyle(
            "doc_id",
            parent=base["Normal"],
            fontName=THEME.body_font_bold,
            fontSize=12,
            leading=14,
            textColor=colors.white,
            alignment=1,
        ),
        "section_h": ParagraphStyle(
            "section_h",
            parent=base["Heading2"],
            fontName=THEME.body_font_bold,
            fontSize=13,
            leading=16,
            textColor=colors.white,
            backColor=THEME.dark,
            borderPadding=(6, 8, 4, 8),
            spaceBefore=10,
            spaceAfter=2,
            underlineColor=THEME.green,
            underlineWidth=3,
            underlineOffset=-3,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName=THEME.body_font,
            fontSize=10,
            leading=13,
        ),
        "body_bold": ParagraphStyle(
            "body_bold",
            parent=base["BodyText"],
            fontName=THEME.body_font_bold,
            fontSize=10,
            leading=13,
        ),
        "callout": ParagraphStyle(
            "callout",
            parent=base["BodyText"],
            fontName=THEME.body_font_bold,
            fontSize=12,
            leading=15,
            textColor=THEME.dark,
            backColor=colors.HexColor("#FFF7D6"),
            borderPadding=(8, 10, 8, 10),
        ),
    }


# ---------- cover page primitives ----------

def _draw_split_bar(c: canvas.Canvas, y: float, width: float, height: float) -> None:
    """Brand-coloured split bar: half green, half blue."""
    half = width / 2.0
    c.setFillColor(THEME.green)
    c.rect(0, y, half, height, stroke=0, fill=1)
    c.setFillColor(THEME.blue)
    c.rect(half, y, half, height, stroke=0, fill=1)


def _draw_cover_canvas(
    c: canvas.Canvas,
    sheet: WavePickSheet,
    logo_path: Path | None,
    lines_per_hour: int,
) -> None:
    """Paint the cover page directly on the canvas for full theme control."""
    page_w, page_h = A4

    # top split bar
    _draw_split_bar(c, page_h - 8 * mm, page_w, 8 * mm)
    # bottom split bar
    _draw_split_bar(c, 0, page_w, 8 * mm)

    # logo (graceful skip if missing)
    if logo_path and logo_path.exists():
        try:
            img_w = 70 * mm
            img_h = 28 * mm
            c.drawImage(
                str(logo_path),
                (page_w - img_w) / 2.0,
                page_h - 50 * mm,
                width=img_w,
                height=img_h,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("could not draw logo from %s: %s", logo_path, exc)

    # navy title block
    title_y = page_h - 110 * mm
    title_h = 38 * mm
    c.setFillColor(THEME.dark)
    c.rect(15 * mm, title_y, page_w - 30 * mm, title_h, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(THEME.body_font_bold, 14)
    c.drawCentredString(
        page_w / 2.0, title_y + title_h - 8 * mm, "WAVE PICK SHEET"
    )
    c.setFont(THEME.body_font_bold, 28)
    c.drawCentredString(
        page_w / 2.0, title_y + title_h / 2.0 - 10, sheet.wave_id
    )

    # blue subtitle strip
    sub_y = title_y - 14 * mm
    c.setFillColor(THEME.blue)
    c.rect(15 * mm, sub_y, page_w - 30 * mm, 11 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(THEME.body_font_bold, 13)
    stream_label = sheet.stream.replace("_", " ").upper()
    c.drawCentredString(page_w / 2.0, sub_y + 3.5 * mm, stream_label)

    # green doc id strip
    docid_y = sub_y - 9 * mm
    c.setFillColor(THEME.green)
    c.rect(15 * mm, docid_y, page_w - 30 * mm, 7 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(THEME.body_font_bold, 10)
    receive = sheet.receive_date.isoformat() if sheet.receive_date else "TBD"
    c.drawCentredString(
        page_w / 2.0, docid_y + 2 * mm,
        f"RUN GROUP {sheet.run_group}  ·  RECEIVE DATE {receive}",
    )

    # metadata table
    meta_y = docid_y - 6 * mm
    time_mins = estimated_time_to_pick_minutes(
        sheet.total_lines, lines_per_hour=lines_per_hour
    )
    rows = [
        ("Total pick lines", f"{sheet.total_lines:,}"),
        ("Total cartons", f"{sheet.total_cartons:,}"),
        ("Orders in wave", f"{len(sheet.orders):,}"),
        ("Estimated time", f"{time_mins} minutes (at {lines_per_hour} lines/hr)"),
        ("Estimated walk", f"{sheet.estimated_walk_distance_m:.0f} m"),
    ]
    box_w = page_w - 50 * mm
    box_h = len(rows) * 9 * mm
    box_x = 25 * mm
    box_y = meta_y - box_h
    c.setStrokeColor(THEME.dark)
    c.setLineWidth(0.8)
    c.rect(box_x, box_y, box_w, box_h, stroke=1, fill=0)
    for i, (label, value) in enumerate(rows):
        row_y = box_y + box_h - (i + 1) * 9 * mm
        if i % 2 == 0:
            c.setFillColor(THEME.light_grey)
            c.rect(box_x, row_y, box_w, 9 * mm, stroke=0, fill=1)
        c.setFillColor(THEME.dark)
        c.setFont(THEME.body_font_bold, 11)
        c.drawString(box_x + 6 * mm, row_y + 3 * mm, label)
        c.setFont(THEME.body_font, 11)
        c.drawString(box_x + box_w / 2.0, row_y + 3 * mm, value)

    # instruction callout
    note_y = box_y - 24 * mm
    c.setStrokeColor(THEME.dark)
    c.setFillColor(colors.HexColor("#FFF7D6"))
    c.rect(20 * mm, note_y, page_w - 40 * mm, 20 * mm, stroke=1, fill=1)
    c.setFillColor(THEME.dark)
    c.setFont(THEME.body_font_bold, 11)
    if sheet.stream.startswith("3"):
        note = (
            "Print this sheet. Pick the lines in walk order. "
            "Return to the pick BENCH for scan + repack before staging."
        )
    else:
        note = (
            "Print this sheet. Pick the lines in walk order. "
            "Take cartons straight to dispatch staging (BENCH BYPASS)."
        )
    text_obj = c.beginText(24 * mm, note_y + 13 * mm)
    text_obj.setFont(THEME.body_font_bold, 11)
    text_obj.setLeading(13)
    # naive wrap because reportlab text obj doesn't auto-wrap
    words = note.split()
    line = ""
    max_chars = 70
    for w in words:
        candidate = (line + " " + w).strip()
        if len(candidate) > max_chars:
            text_obj.textLine(line)
            line = w
        else:
            line = candidate
    if line:
        text_obj.textLine(line)
    c.drawText(text_obj)

    # footer
    c.setFillColor(THEME.dark)
    c.setFont(THEME.body_font, 8)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.drawString(20 * mm, 12 * mm, f"Wave ID: {sheet.wave_id}")
    c.drawRightString(page_w - 20 * mm, 12 * mm, f"Generated {ts}")
    c.drawCentredString(page_w / 2.0, 12 * mm, "Go Cold — operator pick sheet")


# ---------- page templates ----------

class _PicksheetDoc(BaseDocTemplate):
    """Doc template with cover handled by canvas and body via Frame.

    Templates registered in order:
      ``cover`` (id 0) — used for page 1 only; cover graphics painted
                          directly onto the canvas via ``onPage``.
      ``body``  (id 1) — used from page 2 onwards; standard Frame with
                          a footer band.
    """

    def __init__(self, filename: str, **kwargs):
        super().__init__(filename, pagesize=A4, **kwargs)
        page_w, page_h = A4

        cover_frame = Frame(
            0, 0, page_w, page_h, id="cover_frame", showBoundary=0,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        body_frame = Frame(
            18 * mm,
            18 * mm,
            page_w - 36 * mm,
            page_h - 36 * mm,
            id="body_frame",
            showBoundary=0,
        )
        self._wave_id = ""
        self._gen_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._cover_painter = None  # set later by caller

        self.addPageTemplates([
            PageTemplate(id="cover", frames=[cover_frame],
                         onPage=self._draw_cover_onpage),
            PageTemplate(id="body", frames=[body_frame],
                         onPage=self._draw_body_footer),
        ])

    def set_wave_id(self, wid: str) -> None:
        self._wave_id = wid

    def set_cover_painter(self, fn) -> None:
        self._cover_painter = fn

    def _draw_cover_onpage(self, c: canvas.Canvas, _doc) -> None:
        if self._cover_painter is not None:
            self._cover_painter(c)

    def _draw_body_footer(self, c: canvas.Canvas, doc) -> None:
        page_w, _ = A4
        c.saveState()
        c.setStrokeColor(THEME.green)
        c.setLineWidth(2)
        c.line(18 * mm, 16 * mm, page_w - 18 * mm, 16 * mm)
        c.setFillColor(THEME.dark)
        c.setFont(THEME.body_font, 8)
        c.drawString(18 * mm, 10 * mm, f"Wave {self._wave_id}")
        c.drawRightString(
            page_w - 18 * mm, 10 * mm, f"Generated {self._gen_ts}"
        )
        c.drawCentredString(
            page_w / 2.0, 10 * mm, f"Page {doc.page}"
        )
        c.restoreState()


# ---------- table builders ----------

def _esc(text) -> str:
    """Escape ampersands and angle brackets so they survive Paragraph parsing."""
    return (
        str(text if text is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _wrap_cell(
    html: str, font: str | None = None, size: int = 9,
    align: str = "left",
) -> Paragraph:
    """Build a Paragraph cell.

    ``html`` is treated as Paragraph markup (so ``<b>x</b>`` is bold).
    Caller must escape any user-supplied content with ``_esc``.
    """
    font = font or THEME.body_font
    alignment = {"left": 0, "center": 1, "right": 2}.get(align, 0)
    style = ParagraphStyle(
        f"cell_{font}_{size}_{align}",
        fontName=font,
        fontSize=size,
        leading=size + 2,
        textColor=THEME.dark,
        alignment=alignment,
    )
    return Paragraph(html, style)


def _pick_lines_table(pick_lines: pd.DataFrame) -> Table:
    header = [
        _wrap_cell("Walk #", THEME.body_font_bold, 10),
        _wrap_cell("Location", THEME.body_font_bold, 10),
        _wrap_cell("SKU", THEME.body_font_bold, 10),
        _wrap_cell("Description", THEME.body_font_bold, 10),
        _wrap_cell("Qty", THEME.body_font_bold, 10),
        _wrap_cell("Run total", THEME.body_font_bold, 10),
        _wrap_cell("Orders", THEME.body_font_bold, 10),
        _wrap_cell("Done", THEME.body_font_bold, 10),
    ]
    rows = [header]
    for r in pick_lines.itertuples(index=False):
        rows.append([
            _wrap_cell(
                f"<b>{int(r.walk_index)}</b>",
                THEME.body_font_bold, 12, "center",
            ),
            _wrap_cell(
                _esc(r.location), THEME.mono_font, 11, "center",
            ),
            _wrap_cell(_esc(r.product_code), THEME.body_font_bold, 9),
            _wrap_cell(_esc(r.product_name), THEME.body_font, 9),
            _wrap_cell(
                f"<b>{int(r.qty_cartons):,}</b>",
                THEME.body_font_bold, 13, "center",
            ),
            _wrap_cell(
                f"{int(r.cartons_running_total):,}",
                THEME.body_font, 9, "center",
            ),
            _wrap_cell(_esc(r.contributing_so_refs), THEME.body_font, 8),
            _wrap_cell("", THEME.body_font, 9),
        ])

    col_widths = [
        13 * mm,  # walk #
        26 * mm,  # location
        22 * mm,  # sku
        46 * mm,  # description
        14 * mm,  # qty
        16 * mm,  # run total
        40 * mm,  # orders
        12 * mm,  # done
    ]
    table = Table(rows, colWidths=col_widths, repeatRows=1)

    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), THEME.dark),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (4, 1), (5, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.3, THEME.dark),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, THEME.light_grey]),
        ("BOX", (-1, 1), (-1, -1), 1.0, THEME.dark),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ])
    # Override header text colour back to white (Paragraph style baked dark)
    table.setStyle(style)
    # Rewrap headers with white text now that style is locked in
    header_white_style = ParagraphStyle(
        "header_white",
        fontName=THEME.body_font_bold,
        fontSize=10,
        leading=12,
        textColor=colors.white,
        alignment=1,
    )
    for col_idx, label in enumerate(
        ["Walk #", "Location", "SKU", "Description", "Qty",
         "Run total", "Orders", "Done"]
    ):
        rows[0][col_idx] = Paragraph(label, header_white_style)
    return table


def _unallocated_table(pick_lines: pd.DataFrame) -> Table:
    """Table for unallocated pick lines.

    Identical to ``_pick_lines_table`` in style but omits the
    "Walk #" and "Run total" columns — both are meaningless for lines
    that have no confirmed stock location.  Six columns:
      Location | SKU | Description | Qty | Orders | Done
    """
    col_labels = ["Location", "SKU", "Description", "Qty", "Orders", "Done"]
    header_white_style = ParagraphStyle(
        "header_white_unalloc",
        fontName=THEME.body_font_bold,
        fontSize=10,
        leading=12,
        textColor=colors.white,
        alignment=1,
    )
    header = [Paragraph(label, header_white_style) for label in col_labels]
    rows = [header]
    for r in pick_lines.itertuples(index=False):
        rows.append([
            _wrap_cell(
                _esc(r.location), THEME.mono_font, 11, "center",
            ),
            _wrap_cell(_esc(r.product_code), THEME.body_font_bold, 9),
            _wrap_cell(_esc(r.product_name), THEME.body_font, 9),
            _wrap_cell(
                f"<b>{int(r.qty_cartons):,}</b>",
                THEME.body_font_bold, 13, "center",
            ),
            _wrap_cell(_esc(r.contributing_so_refs), THEME.body_font, 8),
            _wrap_cell("", THEME.body_font, 9),
        ])

    # Widths sum to 189mm — same total as _pick_lines_table (189mm).
    # The freed "Walk #" (13mm) + "Run total" (16mm) = 29mm is spread
    # across Description (+17mm) and Orders (+12mm).
    col_widths = [
        26 * mm,   # col 0 — location
        22 * mm,   # col 1 — sku
        63 * mm,   # col 2 — description  (46+17)
        14 * mm,   # col 3 — qty
        52 * mm,   # col 4 — orders       (40+12)
        12 * mm,   # col 5 — done
    ]
    table = Table(rows, colWidths=col_widths, repeatRows=1)

    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), THEME.dark),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # col 0 = Location, col 3 = Qty — centre those in data rows
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (3, 1), (3, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.3, THEME.dark),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, THEME.light_grey]),
        # Bold border on the "Done" tick-box column
        ("BOX", (-1, 1), (-1, -1), 1.0, THEME.dark),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ])
    table.setStyle(style)
    return table


def _orders_table(sheet: WavePickSheet) -> Table:
    header_white_style = ParagraphStyle(
        "header_white",
        fontName=THEME.body_font_bold,
        fontSize=10,
        leading=12,
        textColor=colors.white,
        alignment=1,
    )
    header = [
        Paragraph(label, header_white_style)
        for label in ["SO ref", "Customer", "Destination", "Cartons", "Lines"]
    ]
    rows = [header]
    for r in sheet.orders.itertuples(index=False):
        dest_parts = [
            str(r.delivery_company or "").strip(),
            str(r.delivery_suburb or "").strip(),
            str(r.delivery_state or "").strip(),
            str(r.delivery_postcode or "").strip(),
        ]
        dest = ", ".join(p for p in dest_parts if p)
        rows.append([
            _wrap_cell(
                f"<b>{_esc(r.so_ref)}</b>", THEME.body_font_bold, 10,
            ),
            _wrap_cell(_esc(r.customer_name), THEME.body_font, 9),
            _wrap_cell(_esc(dest), THEME.body_font, 9),
            _wrap_cell(
                f"<b>{int(r.cartons or 0):,}</b>",
                THEME.body_font_bold, 11, "right",
            ),
            _wrap_cell(
                f"{int(r.lines or 0):,}", THEME.body_font, 10, "right",
            ),
        ])

    col_widths = [44 * mm, 38 * mm, 64 * mm, 18 * mm, 16 * mm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), THEME.dark),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (3, 1), (4, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, THEME.dark),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, THEME.light_grey]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


# ---------- entry point ----------

def generate_wave_pdf(
    sheet: WavePickSheet,
    out_path: Path,
    logo_path: Path | None = None,
    lines_per_hour: int = DEFAULT_LINES_PER_HOUR,
) -> None:
    """Render ``sheet`` to a single PDF at ``out_path``.

    Page 1 = cover (canvas-drawn for full theme control).
    Page 2+ = pick lines + order summary, framed for repeating header.

    ``logo_path`` is optional; if not provided or missing the cover skips
    the logo with a warning rather than erroring.
    """
    if not isinstance(out_path, Path):
        out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if logo_path is not None and not isinstance(logo_path, Path):
        logo_path = Path(logo_path)
    if logo_path is not None and not logo_path.exists():
        log.warning(
            "logo not found at %s; skipping logo on cover", logo_path,
        )
        logo_path = None

    doc = _PicksheetDoc(str(out_path))
    doc.set_wave_id(sheet.wave_id)
    styles = _build_styles()

    # Wire the canvas painter onto the cover template.
    def _paint_cover(c: canvas.Canvas) -> None:
        _draw_cover_canvas(c, sheet, logo_path, lines_per_hour)

    doc.set_cover_painter(_paint_cover)

    # Story: cover is canvas-painted via the cover template's onPage hook;
    # all we need in the flowable list for page 1 is a placeholder Spacer
    # and a PageBreak that switches to the body template.
    from reportlab.platypus.doctemplate import NextPageTemplate

    story: list = [
        Spacer(1, 1),
        NextPageTemplate("body"),
        PageBreak(),
    ]

    # ---- pick lines section ----
    story.append(Paragraph(
        "Pick lines &mdash; walk order", styles["section_h"]))
    story.append(Spacer(1, 4 * mm))
    pl = sheet.pick_lines
    if pl.empty:
        story.append(Paragraph(
            "<i>No pick lines for this wave.</i>", styles["body"]))
    else:
        if "unallocated" in pl.columns:
            located = pl[~pl["unallocated"].fillna(False)]
            unalloc = pl[pl["unallocated"].fillna(False)]
        else:
            located, unalloc = pl, pl.iloc[0:0]
        if not located.empty:
            story.append(_pick_lines_table(located))
        if not unalloc.empty:
            story.append(KeepTogether([
                Spacer(1, 6 * mm),
                Paragraph(
                    "&#9888; UNALLOCATED &mdash; no live stock location, "
                    "locate manually", styles["callout"]),
                Spacer(1, 3 * mm),
                _unallocated_table(unalloc),
            ]))

    # ---- orders section ----
    story.append(PageBreak())
    story.append(Paragraph(
        "Orders in this wave &mdash; paste into CartonCloud",
        styles["section_h"],
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        (
            "Open CartonCloud &rarr; Sale orders &rarr; create wave. "
            "Paste the SO refs below. Total cartons should reconcile "
            f"to <b>{sheet.total_cartons:,}</b> across "
            f"<b>{len(sheet.orders):,}</b> orders."
        ),
        styles["body"],
    ))
    story.append(Spacer(1, 4 * mm))
    if sheet.orders.empty:
        story.append(Paragraph(
            "<i>No orders carried into the wave (all skipped).</i>",
            styles["body"],
        ))
    else:
        story.append(_orders_table(sheet))

    doc.build(story)
    log.info("wrote wave PDF %s (%d pick lines, %d orders)",
             out_path, sheet.total_lines, len(sheet.orders))
