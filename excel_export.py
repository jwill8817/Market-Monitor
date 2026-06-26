"""
Excel export for JW Market and News Monitor.
Writes one sheet per market-data category + an embedded chart image sheet.
"""
import datetime
import io
import os
import xlsxwriter


# ── colour palette (hex strings for xlsxwriter) ──────────────
_BG      = "#0d1117"
_CARD    = "#1c2128"
_CARD2   = "#21262d"
_BORDER  = "#30363d"
_ACCENT  = "#f78166"
_GREEN   = "#3fb950"
_RED     = "#f85149"
_YELLOW  = "#e3b341"
_TEXT1   = "#e6edf3"
_TEXT2   = "#8b949e"
_WHITE   = "#ffffff"
_HEADER_BG = "#161b22"


def _col_fmt(wb, bg, fg=_TEXT1, bold=False, align="left", num_format=None, border=False):
    props = dict(bg_color=bg, font_color=fg, bold=bold,
                 align=align, valign="vcenter",
                 font_name="Consolas", font_size=11)
    if num_format:
        props["num_format"] = num_format
    if border:
        props.update(border=1, border_color=_BORDER)
    return wb.add_format(props)


_HEADERS = ["Name", "Ticker", "Price", "1D%", "MTD%", "YTD%", "1Y%",
            "3Y ann%", "5Y ann%", "10Y ann%", "Custom%"]
_COL_WIDTHS = [28, 12, 14, 9, 9, 9, 9, 10, 10, 11, 10]

_PCT_COLS = {3, 4, 5, 6, 7, 8, 9, 10}   # 0-based column indices that hold % values


def _write_sheet(wb, ws, rows, fmts):
    """Write header row then data rows with conditional % colouring."""
    hdr_fmt, num_fmt, pct_pos_fmt, pct_neg_fmt, pct_nil_fmt, plain_fmt = fmts

    for c, (hdr, w) in enumerate(zip(_HEADERS, _COL_WIDTHS)):
        ws.write(0, c, hdr, hdr_fmt)
        ws.set_column(c, c, w)
    ws.set_row(0, 22)
    ws.freeze_panes(1, 0)

    for r, row in enumerate(rows, start=1):
        bg = _CARD if r % 2 == 0 else _CARD2
        row_plain = _col_fmt(wb, bg, _TEXT1, border=True)
        row_num   = _col_fmt(wb, bg, _TEXT1, align="right", border=True)

        for c, val in enumerate(row):
            if c in _PCT_COLS:
                # val is a string like "+1.23%" or "—"
                if val == "—" or val is None:
                    ws.write(r, c, val or "—", pct_nil_fmt)
                else:
                    try:
                        num = float(str(val).replace("%","").replace("+",""))
                        fmt = pct_pos_fmt if num >= 0 else pct_neg_fmt
                        ws.write(r, c, num / 100, fmt)
                    except ValueError:
                        ws.write(r, c, val, pct_nil_fmt)
            elif c == 2:   # Price column — right align
                ws.write(r, c, val if val != "—" else "—", row_num)
            else:
                ws.write(r, c, val or "—", row_plain)
        ws.set_row(r, 18)


def export(market_data: dict, chart_figure=None,
           out_dir: str = None) -> str:
    """
    market_data: dict of {sheet_label: list_of_row_tuples}
      Each row tuple: (name, ticker, price, 1d%, mtd%, ytd%, 1y%, 3y%, 5y%, 10y%)
    chart_figure: matplotlib Figure object to embed (optional)
    out_dir: directory to save to (defaults to ~/Desktop)
    Returns: path to the saved .xlsx file
    """
    if out_dir is None:
        out_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    os.makedirs(out_dir, exist_ok=True)

    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"JAWS_MarketData_{ts}.xlsx")

    wb = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True})
    wb.set_properties({"title": "JW Market and News Monitor",
                       "author": "JAWS"})

    # ── shared formats ──────────────────────────────────────────
    hdr_fmt = _col_fmt(wb, _HEADER_BG, _ACCENT, bold=True, align="left", border=True)
    num_fmt      = _col_fmt(wb, _CARD, _TEXT1,  align="right", border=True,
                            num_format='#,##0.00')
    pct_pos_fmt  = _col_fmt(wb, _CARD, _GREEN,  align="right", border=True,
                            num_format='+0.00%;-0.00%;0.00%')
    pct_neg_fmt  = _col_fmt(wb, _CARD, _RED,    align="right", border=True,
                            num_format='+0.00%;-0.00%;0.00%')
    pct_nil_fmt  = _col_fmt(wb, _CARD, _TEXT2,  align="right", border=True)
    plain_fmt    = _col_fmt(wb, _CARD, _TEXT1,  border=True)
    fmts = (hdr_fmt, num_fmt, pct_pos_fmt, pct_neg_fmt, pct_nil_fmt, plain_fmt)

    title_fmt = wb.add_format(dict(bold=True, font_size=16, font_color=_ACCENT,
                                    bg_color=_BG, font_name="Consolas",
                                    valign="vcenter"))
    sub_fmt   = wb.add_format(dict(font_size=10, font_color=_TEXT2,
                                    bg_color=_BG, font_name="Consolas",
                                    valign="vcenter"))

    # ── Summary sheet ───────────────────────────────────────────
    summary = wb.add_worksheet("Summary")
    summary.hide_gridlines(2)
    summary.set_tab_color(_ACCENT)
    summary.set_column(0, 0, 32)
    summary.set_column(1, 1, 22)
    summary.set_row(0, 36)
    summary.set_row(1, 18)
    summary.set_row(2, 18)

    summary.write(0, 0, "JW Market and News Monitor", title_fmt)
    summary.write(1, 0,
                  f"Exported  {datetime.datetime.now().strftime('%B %d, %Y  %H:%M:%S')}",
                  sub_fmt)
    summary.write(2, 0, "Data sourced from Yahoo Finance / US Treasury", sub_fmt)

    row_s = 4
    sheet_hdr = _col_fmt(wb, _HEADER_BG, _ACCENT, bold=True, border=True)
    cnt_fmt   = _col_fmt(wb, _CARD2, _TEXT1, align="right", border=True)
    lnk_fmt   = wb.add_format(dict(font_color=_ACCENT, underline=True,
                                    bg_color=_CARD2, font_name="Consolas",
                                    font_size=11, border=1, border_color=_BORDER))
    summary.write(row_s, 0, "Sheet", sheet_hdr)
    summary.write(row_s, 1, "Instruments", sheet_hdr)
    row_s += 1

    # ── Data sheets ─────────────────────────────────────────────
    tab_colors = {
        "Equity Indices": "#3fb950",
        "Rates":          "#58a6ff",
        "Volatility":     "#bc8cff",
        "FX":             "#e3b341",
        "Fixed Income":   "#79c0ff",
        "Municipals":     "#56d364",
        "Factors":        "#f78166",
        "Funding Markets":"#ffa657",
        "Commodities":    "#d2a8ff",
    }

    for label, rows in market_data.items():
        safe = label.replace("/", "-")[:31]
        ws   = wb.add_worksheet(safe)
        ws.hide_gridlines(2)
        ws.set_tab_color(tab_colors.get(label, _ACCENT))
        ws.set_zoom(90)

        # Sheet title
        ws.set_row(0, 28)
        ws.merge_range(0, 0, 0, len(_HEADERS)-1, label, title_fmt)
        ws.write(1, 0,
                 f"As of {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                 sub_fmt)

        # Offset data by 2 rows to leave room for title
        ws_offset = wb.add_worksheet(f"_{safe}_tmp") if False else None

        # Re-write with offset: header at row 2, data from row 3
        hdr_r = 2
        for c, (hdr, w) in enumerate(zip(_HEADERS, _COL_WIDTHS)):
            ws.write(hdr_r, c, hdr, hdr_fmt)
            ws.set_column(c, c, w)
        ws.set_row(hdr_r, 22)
        ws.freeze_panes(hdr_r + 1, 0)

        for r_idx, row in enumerate(rows):
            r = hdr_r + 1 + r_idx
            bg = _CARD if r_idx % 2 == 0 else _CARD2
            row_plain = _col_fmt(wb, bg, _TEXT1, border=True)
            row_num   = _col_fmt(wb, bg, _TEXT1, align="right", border=True)

            for c, val in enumerate(row):
                if c in _PCT_COLS:
                    if val == "—" or val is None:
                        ws.write(r, c, "—", _col_fmt(wb, bg, _TEXT2,
                                                      align="right", border=True))
                    else:
                        try:
                            num = float(str(val).replace("%","").replace("+",""))
                            bg2 = _CARD if r_idx % 2 == 0 else _CARD2
                            fmt = _col_fmt(wb, bg2,
                                          _GREEN if num >= 0 else _RED,
                                          align="right", border=True,
                                          num_format='+0.00%;-0.00%;0.00%')
                            ws.write(r, c, num / 100, fmt)
                        except ValueError:
                            ws.write(r, c, val, row_plain)
                elif c == 2:
                    ws.write(r, c, val if val != "—" else "—", row_num)
                else:
                    ws.write(r, c, val or "—", row_plain)
            ws.set_row(r, 18)

        # Summary row
        summary.write(row_s, 0, label, cnt_fmt)
        summary.write(row_s, 1, len(rows), cnt_fmt)
        row_s += 1

    # ── Chart image sheet ────────────────────────────────────────
    if chart_figure is not None:
        try:
            cs = wb.add_worksheet("Chart")
            cs.hide_gridlines(2)
            cs.set_tab_color(_ACCENT)
            cs.write(0, 0, "Chart Export", title_fmt)
            cs.write(1, 0,
                     f"As of {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                     sub_fmt)

            buf = io.BytesIO()
            chart_figure.savefig(buf, format="png", dpi=150,
                                  bbox_inches="tight",
                                  facecolor=_BG)
            buf.seek(0)
            cs.insert_image(3, 0, "chart.png",
                            {"image_data": buf,
                             "x_scale": 1.0, "y_scale": 1.0})
        except Exception:
            pass

    wb.close()
    return path
