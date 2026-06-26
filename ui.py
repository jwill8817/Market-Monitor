import tkinter as tk
from tkinter import ttk, scrolledtext
import threading, os, webbrowser, urllib.parse
from datetime import datetime, timedelta
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from dateutil.relativedelta import relativedelta

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

BG      = "#0d1117"; SIDEBAR = "#161b22"; CARD  = "#1c2128"; CARD2 = "#21262d"
BORDER  = "#30363d"; ACCENT  = "#f78166"; BLUE  = "#58a6ff"; GREEN = "#3fb950"
RED     = "#f85149"; YELLOW  = "#e3b341"; PURPLE= "#bc8cff"; CYAN  = "#79c0ff"
TEXT1   = "#e6edf3"; TEXT2   = "#8b949e"; TEXT3  = "#484f58"; WHITE = "#ffffff"
ROW_A   = "#1c2128"; ROW_B   = "#21262d"; HOVER  = "#2d333b"

F_MONO   = ("Consolas", 12)
F_MONO_S = ("Consolas", 11)
F_MONO_L = ("Consolas", 14, "bold")
F_SANS   = ("Segoe UI", 12)
F_SANS_H = ("Segoe UI", 18, "bold")
F_TREE   = ("Consolas", 14)
F_HEAD   = ("Consolas", 12, "bold")

PCT_COLS = {"1D%","MTD%","YTD%","1Y%","3Y ann%","5Y ann%","10Y ann%","Custom%"}
CURVE_COLORS = [ACCENT, BLUE, GREEN, YELLOW, PURPLE, CYAN, "#ff6b6b", "#51cf66", "#ffa94d"]

NEWS_WEIGHT = {
    "bloomberg":10, "wsj":9, "wall street journal":9,
    "reuters":8, "financial times":8, "ft":8,
    "cnbc":7, "yahoo finance":6, "seeking alpha":5, "zero hedge":4,
}
CAT_COLORS = {"hedge_fund":CYAN, "ipo":GREEN, "ma":YELLOW, "issuance":PURPLE}
CAT_LABELS = {"hedge_fund":"HF", "ipo":"IPO", "ma":"M&A", "issuance":"ISS"}

plt.rcParams.update({
    "figure.facecolor": BG,  "axes.facecolor": CARD,
    "axes.edgecolor":   BORDER, "axes.labelcolor": TEXT2,
    "axes.grid": True,  "grid.color": BORDER, "grid.linewidth": 0.5,
    "xtick.color": TEXT3, "ytick.color": TEXT3, "text.color": TEXT1,
    "legend.facecolor": CARD2, "legend.edgecolor": BORDER, "legend.fontsize": 10,
})


# ── Per-cell color market table ────────────────────────────────
COLS    = ("Name","Ticker","Price","1D%","MTD%","YTD%","1Y%","3Y ann%","5Y ann%","10Y ann%","Custom%")
COL_W   = (190,   80,      115,    88,    88,    88,    88,   96,       96,       96,        96)   # px

def _pct_to_float(s):
    try: return float(s.replace("+","").replace("%","").replace("—",""))
    except: return None

def _cell_fg(col, val_str):
    if col not in PCT_COLS: return TEXT1
    v = _pct_to_float(val_str)
    if v is None: return TEXT2
    return GREEN if v >= 0 else RED


def _fmt_price(v, name=""):
    if v is None: return "—"
    if any(x in name for x in ["EUR/","GBP/","AUD/"]): return f"{v:.4f}"
    if any(x in name for x in ["JPY","CNY","MXN","CAD","CHF"]): return f"{v:.4f}"
    if v < 10: return f"{v:.4f}"
    if v < 1000: return f"{v:,.2f}"
    return f"{v:,.0f}"

def _scroll_table(parent):
    """Scrollable table area with a frozen header that scrolls horizontally in
    sync with the body, plus a vertical scrollbar on the body.
    Returns (container, head_frame, body_frame). Populate both with packed
    labels; scroll regions update automatically. Needed so zoomed-in wide
    tables can be scrolled right to reach hidden columns."""
    cont = tk.Frame(parent, bg=CARD)
    head_cv = tk.Canvas(cont, bg=CARD2, highlightthickness=0, height=26)
    body_cv = tk.Canvas(cont, bg=CARD, highlightthickness=0)
    vsb = ttk.Scrollbar(cont, orient="vertical", style="Vertical.TScrollbar",
                        command=body_cv.yview)
    def _xv(*a):
        head_cv.xview(*a); body_cv.xview(*a)
    hsb = ttk.Scrollbar(cont, orient="horizontal", style="Horizontal.TScrollbar",
                        command=_xv)
    body_cv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    head_frame = tk.Frame(head_cv, bg=CARD2)
    body_frame = tk.Frame(body_cv, bg=CARD)
    head_cv.create_window((0,0), window=head_frame, anchor="nw")
    body_cv.create_window((0,0), window=body_frame, anchor="nw")
    head_cv.grid(row=0, column=0, sticky="ew")
    body_cv.grid(row=1, column=0, sticky="nsew")
    vsb.grid(row=1, column=1, sticky="ns")
    hsb.grid(row=2, column=0, sticky="ew")
    cont.rowconfigure(1, weight=1); cont.columnconfigure(0, weight=1)
    def _upd(_=None):
        body_cv.configure(scrollregion=body_cv.bbox("all"))
        head_cv.configure(scrollregion=head_cv.bbox("all"),
                          height=max(24, head_frame.winfo_reqheight()))
    head_frame.bind("<Configure>", _upd)
    body_frame.bind("<Configure>", _upd)
    body_cv.bind("<MouseWheel>",
                 lambda e: body_cv.yview_scroll(int(-1*(e.delta/120)), "units"))
    body_cv.bind("<Shift-MouseWheel>",
                 lambda e: _xv("scroll", int(-1*(e.delta/120)), "units"))
    return cont, head_frame, body_frame


def _fmt_pct(v):
    if v is None: return "—"
    return f"{'+'if v>=0 else ''}{v:.2f}%"

def _fmt_abs(v):
    """Absolute level difference for rates (e.g. +0.25 means +25 bps)."""
    if v is None: return "—"
    return f"{'+'if v>=0 else ''}{v:.2f}%"


class ColorTable(tk.Frame):
    """Scrollable table with independent per-cell color for every % column."""

    def __init__(self, parent, on_select=None, **kw):
        super().__init__(parent, bg=CARD, **kw)
        self.on_select = on_select
        self._selected_name = ""
        self._rows = []
        self._build()

    def _build(self):
        # Fixed header
        hdr = tk.Frame(self, bg=CARD2)
        hdr.pack(fill="x", side="top")
        for col, w in zip(COLS, COL_W):
            anc = "w" if col in ("Name","Ticker") else "e"
            tk.Label(hdr, text=col, bg=CARD2, fg=TEXT2,
                     font=F_HEAD, width=w//8, anchor=anc, padx=6,
                     pady=6).pack(side="left")

        # Scrollable body via Canvas
        frame = tk.Frame(self, bg=CARD)
        frame.pack(fill="both", expand=True)

        self._cv = tk.Canvas(frame, bg=CARD, highlightthickness=0)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._cv.yview,
                            style="Vertical.TScrollbar")
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self._cv.xview,
                            style="Horizontal.TScrollbar")
        self._cv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._cv.pack(side="left", fill="both", expand=True)

        self._body = tk.Frame(self._cv, bg=CARD)
        self._win  = self._cv.create_window((0,0), window=self._body, anchor="nw")
        self._body.bind("<Configure>", lambda e:
            self._cv.configure(scrollregion=self._cv.bbox("all")))
        self._cv.bind("<Configure>", lambda e:
            self._cv.itemconfig(self._win, width=e.width))
        self._cv.bind("<MouseWheel>", lambda e:
            self._cv.yview_scroll(-1*(e.delta//120), "units"))

    def clear(self):
        for w in self._body.winfo_children():
            w.destroy()
        self._rows = []

    def add_row(self, values):
        """values: tuple/list matching COLS order.  values[0] = name."""
        i   = len(self._rows)
        bg  = ROW_A if i % 2 == 0 else ROW_B
        row = tk.Frame(self._body, bg=bg, cursor="hand2")
        row.pack(fill="x")

        lbls = []
        for col, w, val in zip(COLS, COL_W, values):
            anc = "w" if col in ("Name","Ticker") else "e"
            fg  = _cell_fg(col, str(val))
            lbl = tk.Label(row, text=val, bg=bg, fg=fg,
                           font=F_TREE, anchor=anc, padx=6, pady=5,
                           width=w//8)
            lbl.pack(side="left")
            lbls.append(lbl)

        name = values[0]
        def _click(e, n=name, r=row, ls=lbls):
            self._deselect()
            self._selected_name = n
            r.config(bg=HOVER)
            for l in ls: l.config(bg=HOVER)
            if self.on_select: self.on_select(n, values[1])

        def _enter(e, r=row, ls=lbls, b=bg):
            if self._selected_name != name:
                r.config(bg=HOVER)
                for l in ls: l.config(bg=HOVER)

        def _leave(e, r=row, ls=lbls, b=bg):
            if self._selected_name != name:
                r.config(bg=b)
                for l in ls:
                    col = COLS[lbls.index(l)]
                    l.config(bg=b)

        row.bind("<Button-1>", _click)
        row.bind("<Enter>",    _enter)
        row.bind("<Leave>",    _leave)
        for lbl in lbls:
            lbl.bind("<Button-1>", _click)
            lbl.bind("<Enter>",    _enter)
            lbl.bind("<Leave>",    _leave)

        self._rows.append((row, lbls, bg, name))

    def get_rows(self):
        """Return raw cell text for every row — used by Excel export."""
        result = []
        for row, lbls, bg, name in self._rows:
            result.append(tuple(lbl.cget("text") for lbl in lbls))
        return result

    def _deselect(self):
        for row, lbls, bg, name in self._rows:
            row.config(bg=bg)
            for lbl in lbls: lbl.config(bg=bg)


# ── Chart panel (reusable) ─────────────────────────────────────
class ChartPanel(tk.Frame):
    """Self-contained chart panel with controls, crosshair, and hover tooltip."""

    def __init__(self, parent, ticker_map_fn, log_fn, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._ticker_map  = ticker_map_fn   # callable → dict
        self._log         = log_fn
        self.chart_mode   = tk.StringVar(value="line")
        self.chart_data   = tk.StringVar(value="price")
        self.chart_period = tk.StringVar(value="1Y")
        self.chart_custom = tk.StringVar(value="")
        self.title_var    = tk.StringVar(value="Select a row above to view chart")
        self._series      = None
        self._is_bar      = False
        self._bar_dates   = None
        self._bar_vals    = None
        self._ann         = None
        self._vline       = None
        self._hline       = None
        self._compare     = {}     # sym → name  (extra tickers to overlay)
        self._factor      = None   # (dates, decimal_returns) when plotting a L/S factor
        self._cmp_colors  = [BLUE, GREEN, PURPLE, YELLOW, CYAN, "#ff6b6b", "#ffa94d"]
        self._build()

    def _build(self):
        ctrl = tk.Frame(self, bg=CARD2, height=46)
        ctrl.pack(fill="x"); ctrl.pack_propagate(False)
        tk.Label(ctrl, textvariable=self.title_var, bg=CARD2, fg=TEXT1,
                 font=("Consolas", 13, "bold"), padx=10).pack(side="left")

        def rb(text, var, val):
            tk.Radiobutton(ctrl, text=text, variable=var, value=val,
                           bg=CARD2, fg=TEXT2, selectcolor=CARD,
                           activebackground=CARD2, activeforeground=TEXT1,
                           font=("Segoe UI", 11), indicatoron=False,
                           relief="flat", bd=1, padx=9, pady=5,
                           cursor="hand2", command=self.refresh).pack(side="left", padx=1)

        sep = lambda: tk.Frame(ctrl, bg=BORDER, width=1).pack(side="left", padx=4, fill="y")
        for t, v in [("Line","line"),("Bar","bar")]: rb(t, self.chart_mode, v)
        sep()
        for t, v in [("Price","price"),("Returns","returns")]: rb(t, self.chart_data, v)
        sep()
        for p in ["MTD","3M","6M","YTD","1Y","3Y","5Y","10Y"]: rb(p, self.chart_period, p)
        sep()
        tk.Label(ctrl, text="From:", bg=CARD2, fg=TEXT3,
                 font=("Segoe UI", 11)).pack(side="left", padx=(4,2))
        self._entry = tk.Entry(ctrl, textvariable=self.chart_custom,
                               bg=CARD, fg=TEXT1, insertbackground=TEXT1,
                               font=("Consolas", 11), width=12, relief="flat", bd=2)
        self._entry.pack(side="left", padx=2)
        tk.Label(ctrl, text="YYYY-MM-DD", bg=CARD2, fg=TEXT3,
                 font=("Consolas", 9)).pack(side="left")
        tk.Button(ctrl, text="Go", bg=CARD, fg=ACCENT, font=("Segoe UI", 11),
                  relief="flat", bd=0, padx=8, cursor="hand2",
                  command=self._use_custom).pack(side="left", padx=4)
        tk.Button(ctrl, text="↺", bg=CARD2, fg=TEXT2, font=("Segoe UI", 14),
                  relief="flat", bd=0, cursor="hand2",
                  command=self.refresh).pack(side="right", padx=4)
        tk.Button(ctrl, text="⬇ XLS", bg="#1f6b2e", fg=WHITE,
                  font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
                  padx=8, cursor="hand2",
                  command=self._export).pack(side="right", padx=4)

        # ── Compare row: add extra tickers to overlay ─────────
        crow = tk.Frame(self, bg=SIDEBAR, height=32)
        crow.pack(fill="x"); crow.pack_propagate(False)
        tk.Label(crow, text="  Compare +", bg=SIDEBAR, fg=TEXT2,
                 font=("Segoe UI",10,"bold")).pack(side="left")
        self._cmp_var = tk.StringVar()
        cmp_entry = tk.Entry(crow, textvariable=self._cmp_var, bg=CARD, fg=TEXT1,
                             insertbackground=TEXT1, font=("Consolas",10),
                             width=18, relief="flat")
        cmp_entry.pack(side="left", padx=6, pady=4, ipady=2)
        cmp_entry.bind("<Return>", lambda e: self._add_compare())
        tk.Button(crow, text="Add", bg=ACCENT, fg=BG, font=("Segoe UI",10),
                  relief="flat", padx=8, cursor="hand2",
                  command=self._add_compare).pack(side="left", padx=2)
        tk.Label(crow, text="(adds normalized % return overlay)", bg=SIDEBAR,
                 fg=TEXT3, font=("Consolas",9)).pack(side="left", padx=4)
        self._cmp_chip_frame = tk.Frame(crow, bg=SIDEBAR)
        self._cmp_chip_frame.pack(side="left", padx=6)

        self.fig, self.ax = plt.subplots(figsize=(7, 3.2))
        self.fig.subplots_adjust(left=0.1, right=0.97, top=0.87, bottom=0.18)
        self._placeholder()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.draw()
        self.canvas.mpl_connect("motion_notify_event", self._hover)
        self.canvas.mpl_connect("axes_leave_event",    self._leave)

    # ── Compare overlays ──────────────────────────────────────
    def _add_compare(self):
        raw = self._cmp_var.get().strip()
        if not raw:
            return
        self._cmp_var.set("")
        threading.Thread(target=self._add_compare_worker, args=(raw,),
                         daemon=True).start()

    def _add_compare_worker(self, query):
        try:
            import yfinance as yf
            sym, name = query.upper(), query.upper()
            # If not an obvious ticker, search for best match
            if not (len(query) <= 6 and query.replace("^","").replace("=","").isalnum()):
                hits = yf.Search(query, max_results=1).quotes
                if hits:
                    sym  = hits[0].get("symbol", query.upper())
                    name = hits[0].get("shortname") or hits[0].get("longname") or sym
            # Validate it has data
            h = yf.Ticker(sym).history(period="1mo")
            if h.empty:
                self.after(0, lambda: self.title_var.set(f"  No data for {query}"))
                return
            self.after(0, lambda s=sym, n=name: self._register_compare(s, n))
        except Exception as e:
            self.after(0, lambda m=str(e): self.title_var.set(f"  Compare error: {m}"))

    def _register_compare(self, sym, name):
        if sym in self._compare:
            return
        self._compare[sym] = name
        self._update_cmp_chips()
        self.refresh()

    def _update_cmp_chips(self):
        for w in self._cmp_chip_frame.winfo_children():
            w.destroy()
        for i, (sym, name) in enumerate(self._compare.items()):
            col = self._cmp_colors[i % len(self._cmp_colors)]
            chip = tk.Frame(self._cmp_chip_frame, bg=CARD)
            chip.pack(side="left", padx=2)
            tk.Label(chip, text="■", bg=CARD, fg=col,
                     font=("Consolas",10)).pack(side="left")
            tk.Label(chip, text=sym, bg=CARD, fg=TEXT1,
                     font=("Consolas",9)).pack(side="left")
            tk.Button(chip, text="✕", bg=CARD, fg=TEXT3, font=("Consolas",9),
                      relief="flat", cursor="hand2", padx=1,
                      command=lambda s=sym: self._remove_compare(s)).pack(side="left")

    def _remove_compare(self, sym):
        self._compare.pop(sym, None)
        self._update_cmp_chips()
        self.refresh()

    def select(self, name, ticker):
        self._name   = name
        self._ticker = ticker
        self._factor = None          # normal (yfinance) mode
        self.title_var.set(f"  {name}  ({ticker})")
        self.refresh()

    def select_factor(self, name, dates, rets):
        """Plot an L/S factor: dates + decimal periodic returns (no ticker)."""
        self._name   = name
        self._ticker = None
        self._factor = (list(dates), list(rets))
        self.title_var.set(f"  {name}  (L/S factor)")
        self.refresh()

    def refresh(self):
        name = getattr(self, "_name", None)
        if not name: return
        threading.Thread(target=self._fetch, args=(name,), daemon=True).start()

    def _use_custom(self):
        raw = self.chart_custom.get().strip()
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            self.chart_period.set("custom")
            self.refresh()
        except ValueError:
            self._entry.config(bg="#3a1a1a")
            self.after(800, lambda: self._entry.config(bg=CARD))

    def _period_start(self, period):
        today = datetime.today()
        if period == "custom":
            try: return datetime.strptime(self.chart_custom.get().strip(), "%Y-%m-%d")
            except: return None
        pm = {"MTD":today.replace(day=1), "3M":today-relativedelta(months=3),
              "6M":today-relativedelta(months=6), "YTD":today.replace(month=1,day=1),
              "1Y":today-relativedelta(years=1),  "3Y":today-relativedelta(years=3),
              "5Y":today-relativedelta(years=5),  "10Y":today-relativedelta(years=10)}
        return pm.get(period, today-relativedelta(years=1))

    def _fetch(self, name):
        # ── L/S factor mode: build a synthetic growth series from returns ──
        if self._factor is not None:
            self._fetch_factor()
            return
        import yfinance as yf
        tm = self._ticker_map()
        sym = tm.get(name)
        if not sym: return
        period = self.chart_period.get()
        mode   = self.chart_mode.get()
        data_t = self.chart_data.get()
        today  = datetime.today()
        if period == "custom":
            try: start = datetime.strptime(self.chart_custom.get().strip(), "%Y-%m-%d")
            except: return
        else:
            pm = {"MTD":today.replace(day=1), "3M":today-relativedelta(months=3),
                  "6M":today-relativedelta(months=6), "YTD":today.replace(month=1,day=1),
                  "1Y":today-relativedelta(years=1),  "3Y":today-relativedelta(years=3),
                  "5Y":today-relativedelta(years=5),  "10Y":today-relativedelta(years=10)}
            start = pm.get(period, today-relativedelta(years=1))

        # ── Comparison mode: overlay normalized % returns ─────
        if self._compare:
            try:
                import market_data as _md
                combo = {sym: name}
                combo.update(self._compare)   # sym → display name
                norm = {}
                for s, nm in combo.items():
                    c = _md.price_history(s, start=start.strftime("%Y-%m-%d"))
                    if c.empty:
                        continue
                    base = float(c.iloc[0])
                    if base:
                        norm[nm] = (c - base) / base * 100
                lbl = period if period != "custom" else self.chart_custom.get().strip()
                self.after(0, lambda d=dict(norm), l=lbl: self._draw_compare(d, l))
            except Exception as e:
                self.after(0, lambda err=str(e): self._log(f"Compare: {err}", "red"))
            return

        try:
            import market_data as _md
            price_s = _md.price_history(sym, start=start.strftime("%Y-%m-%d"))
            if price_s.empty: return
            if data_t == "returns":
                base   = float(price_s.iloc[0])
                series = ((price_s - base)/base*100) if base else price_s*0
                ylabel = "Cumulative Return (%)"; fmt = lambda v: f"{v:+.1f}%"
            else:
                series = price_s
                ylabel = "Price"; fmt = lambda v: f"{v:,.2f}" if v<1000 else f"{v:,.0f}"
            lbl = period if period != "custom" else self.chart_custom.get().strip()
            self.after(0, lambda s=series, ps=price_s, y=ylabel, f=fmt, m=mode, l=lbl:
                       self._draw(s, ps, y, f, m, l))
        except Exception as e:
            self.after(0, lambda err=str(e): self._log(f"Chart: {err}", "red"))

    def _fetch_factor(self):
        """Plot an L/S factor from its decimal return stream (no yfinance)."""
        import pandas as pd
        dates, rets = self._factor
        period = self.chart_period.get()
        mode   = self.chart_mode.get()
        data_t = self.chart_data.get()
        start  = self._period_start(period)
        s = pd.Series(rets, index=pd.to_datetime(dates)).sort_index().dropna()
        if start is not None:
            s = s[s.index >= pd.Timestamp(start)]
        if s.empty:
            return
        # Synthetic growth-of-100 index so Price/Returns/Bar modes all work
        price_s = (1.0 + s).cumprod() * 100.0
        if data_t == "returns":
            base   = float(price_s.iloc[0])
            series = ((price_s - base)/base*100) if base else price_s*0
            ylabel = "Cumulative Return (%)"; fmt = lambda v: f"{v:+.1f}%"
        else:
            series = price_s
            ylabel = "Growth of 100"; fmt = lambda v: f"{v:,.1f}"
        lbl = period if period != "custom" else self.chart_custom.get().strip()
        self.after(0, lambda s=series, ps=price_s, y=ylabel, f=fmt, m=mode, l=lbl:
                   self._draw(s, ps, y, f, m, l))

    def _draw(self, series, price_s, ylabel, fmt_fn, mode, period):
        self._clear_crosshair()
        self.ax.clear(); self.ax.set_facecolor(CARD)
        self._ann = None; self._vline = None; self._hline = None

        if mode == "bar":
            monthly = price_s.resample("ME").last()
            m_ret   = monthly.pct_change().dropna()*100
            cols    = [GREEN if v>=0 else RED for v in m_ret.values]
            self.ax.bar(m_ret.index, m_ret.values, color=cols, width=20, alpha=0.85)
            self.ax.axhline(0, color=BORDER, linewidth=0.8)
            self.ax.set_ylabel("Monthly Return (%)", color=TEXT2, fontsize=11)
            self.ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
            self._series    = None; self._is_bar = True
            self._bar_dates = list(m_ret.index.to_pydatetime())
            self._bar_vals  = list(m_ret.values)
        else:
            self.ax.plot(series.index, series.values, color=ACCENT, linewidth=2.0)
            self.ax.fill_between(series.index, series.values, series.values.min(),
                                 alpha=0.12, color=ACCENT)
            self.ax.set_ylabel(ylabel, color=TEXT2, fontsize=11)
            if len(series) > 1:
                chg = series.iloc[-1]-series.iloc[0]
                pct = chg/series.iloc[0]*100 if series.iloc[0] else 0
                c   = GREEN if pct>=0 else RED
                self.ax.annotate(f"{'+'if pct>=0 else ''}{pct:.2f}%",
                                 xy=(series.index[-1], series.iloc[-1]),
                                 xytext=(-55,12), textcoords="offset points",
                                 color=c, fontsize=12, fontweight="bold")
            self.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: fmt_fn(v)))
            self._series = series; self._is_bar = False

        name = getattr(self, "_name", "")
        self.ax.set_title(f"{name}  ·  {period}  ·  hover for values",
                          color=TEXT1, fontsize=12, fontweight="bold", pad=8)
        self.ax.tick_params(colors=TEXT3, labelsize=10)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self.fig.autofmt_xdate(rotation=28, ha="right")
        self.fig.subplots_adjust(left=0.11, right=0.97, top=0.87, bottom=0.19)
        self.canvas.draw()

    def _draw_compare(self, norm_dict, period):
        """Overlay multiple instruments as normalized % returns for comparison."""
        self._clear_crosshair()
        self.ax.clear(); self.ax.set_facecolor(CARD)
        self._ann = None; self._vline = None; self._hline = None
        self._series = None; self._is_bar = False   # disable single-series hover

        colors = [ACCENT] + self._cmp_colors
        for i, (nm, series) in enumerate(norm_dict.items()):
            col = colors[i % len(colors)]
            self.ax.plot(series.index, series.values, color=col, linewidth=1.7,
                         label=f"{nm[:18]} ({series.iloc[-1]:+.1f}%)")
        self.ax.axhline(0, color=BORDER, linewidth=0.8, linestyle="--")
        self.ax.set_ylabel("Cumulative Return (%)", color=TEXT2, fontsize=11)
        self.ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
        self.ax.legend(fontsize=8, facecolor=CARD2, labelcolor=TEXT1,
                       edgecolor=BORDER, loc="upper left")
        self.ax.set_title(f"Comparison · normalized % return · {period}",
                          color=TEXT1, fontsize=12, fontweight="bold", pad=8)
        self.ax.tick_params(colors=TEXT3, labelsize=10)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self.fig.autofmt_xdate(rotation=28, ha="right")
        self.fig.subplots_adjust(left=0.11, right=0.97, top=0.87, bottom=0.19)
        self.canvas.draw()

    def _export(self):
        name   = getattr(self, "_name", None)
        ticker = getattr(self, "_ticker", None)
        if not name or not ticker:
            self._log("No instrument selected — click a row first.", "red")
            return
        self.title_var.set(f"  {name}  ({ticker})  — exporting…")

        def worker():
            try:
                import yfinance as yf
                import xlsxwriter, os
                from dateutil.relativedelta import relativedelta as rd
                import datetime as dt_mod

                today = dt_mod.datetime.today()
                periods = [
                    ("MTD",  today.replace(day=1),          None),
                    ("3M",   today - rd(months=3),           None),
                    ("6M",   today - rd(months=6),           None),
                    ("YTD",  today.replace(month=1, day=1),  None),
                    ("1Y",   today - rd(years=1),            None),
                    ("3Y",   today - rd(years=3),            3),
                    ("5Y",   today - rd(years=5),            5),
                    ("10Y",  today - rd(years=10),           10),
                ]

                hist = yf.Ticker(ticker).history(period="10y")
                if hist.empty:
                    self.after(0, lambda: self.title_var.set(
                        f"  {name}  ({ticker})  — no data"))
                    return
                hist.index = hist.index.tz_localize(None) if hist.index.tzinfo else hist.index

                # Monthly OHLC for chart sheet
                monthly = hist["Close"].resample("ME").last()
                monthly_ret = monthly.pct_change() * 100

                close   = hist["Close"]
                current = float(close.iloc[-1])

                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                safe    = "".join(c for c in name if c.isalnum() or c in " _-")[:30].strip()
                ts      = dt_mod.datetime.now().strftime("%Y%m%d_%H%M%S")
                path    = os.path.join(desktop, f"JAWS_Chart_{safe}_{ts}.xlsx")

                wb = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True,
                                                 "default_date_format": "yyyy-mm-dd"})

                def F(bg="#0d1117", fg="#e6edf3", bold=False,
                      align="left", nf=None, border=True):
                    p = dict(bg_color=bg, font_color=fg, bold=bold,
                             align=align, valign="vcenter",
                             font_name="Consolas", font_size=11)
                    if nf:     p["num_format"] = nf
                    if border: p.update(border=1, border_color="#30363d")
                    return wb.add_format(p)

                title_f = wb.add_format(dict(bold=True, font_size=15,
                                             font_color="#f78166", bg_color="#0d1117",
                                             font_name="Consolas", valign="vcenter"))
                sub_f   = wb.add_format(dict(font_size=10, font_color="#8b949e",
                                             bg_color="#0d1117", font_name="Consolas"))
                hdr_f   = F("#161b22", "#f78166", bold=True)
                pr_f    = F("#1c2128", "#e6edf3", align="right", nf="#,##0.00")
                pr_alt  = F("#21262d", "#e6edf3", align="right", nf="#,##0.00")
                pos_f   = F("#1c2128", "#3fb950", align="right", nf='0.00%')
                neg_f   = F("#1c2128", "#f85149", align="right", nf='0.00%')
                pos_alt = F("#21262d", "#3fb950", align="right", nf='0.00%')
                neg_alt = F("#21262d", "#f85149", align="right", nf='0.00%')
                nil_f   = F("#1c2128", "#8b949e", align="right")
                nil_alt = F("#21262d", "#8b949e", align="right")
                txt_f   = F("#1c2128", "#e6edf3")
                txt_alt = F("#21262d", "#e6edf3")
                date_f  = F("#1c2128", "#8b949e", nf="yyyy-mm-dd")
                date_alt= F("#21262d", "#8b949e", nf="yyyy-mm-dd")

                # ── Sheet 1: Returns Summary ──────────────────────
                ws1 = wb.add_worksheet("Returns Summary")
                ws1.hide_gridlines(2); ws1.set_tab_color("#f78166")
                ws1.set_column(0, 0, 14); ws1.set_column(1, 3, 18)
                ws1.set_row(0, 32)
                ws1.merge_range(0, 0, 0, 3, f"{name}  ({ticker})", title_f)
                ws1.write(1, 0, f"Exported {dt_mod.datetime.now().strftime('%Y-%m-%d %H:%M')}", sub_f)
                ws1.write(1, 2, f"Current Price: {current:,.2f}", sub_f)

                for c, h in enumerate(["Period", "Start Date", "Start Price", "Return (ann. if >1Y)"]):
                    ws1.write(3, c, h, hdr_f)
                ws1.set_row(3, 22)

                for r_idx, (period, start, ann_yrs) in enumerate(periods, start=4):
                    bg  = "#1c2128" if r_idx % 2 == 0 else "#21262d"
                    tf  = txt_f if r_idx % 2 == 0 else txt_alt
                    prf = pr_f  if r_idx % 2 == 0 else pr_alt
                    subset = close[close.index >= start]
                    ws1.write(r_idx, 0, period, tf)
                    ws1.write(r_idx, 1, start.strftime("%Y-%m-%d"), tf)
                    if subset.empty:
                        ws1.write(r_idx, 2, "—", nil_f)
                        ws1.write(r_idx, 3, "—", nil_f)
                    else:
                        sp = float(subset.iloc[0])
                        ws1.write(r_idx, 2, sp, prf)
                        if sp != 0:
                            if ann_yrs:
                                ret = (current / sp) ** (1 / ann_yrs) - 1
                            else:
                                ret = (current - sp) / sp
                            pf = (pos_f if r_idx%2==0 else pos_alt) if ret>=0 else (neg_f if r_idx%2==0 else neg_alt)
                            ws1.write(r_idx, 3, ret, pf)
                        else:
                            ws1.write(r_idx, 3, "—", nil_f)
                    ws1.set_row(r_idx, 18)

                # ── Sheet 2: Monthly Data (source for chart) ──────
                ws2 = wb.add_worksheet("Monthly Data")
                ws2.hide_gridlines(2); ws2.set_tab_color("#58a6ff")
                ws2.set_column(0, 0, 14); ws2.set_column(1, 2, 16)
                ws2.set_row(0, 32)
                ws2.merge_range(0, 0, 0, 2, f"{name} — Monthly Prices & Returns", title_f)
                ws2.write(1, 0, "10-year monthly history", sub_f)

                for c, h in enumerate(["Date", "Close Price", "Monthly Return"]):
                    ws2.write(3, c, h, hdr_f)
                ws2.set_row(3, 22)
                ws2.freeze_panes(4, 0)

                data_start_row = 4
                for r_idx, (dt_val, price) in enumerate(zip(monthly.index, monthly.values), start=data_start_row):
                    prf  = pr_f  if r_idx%2==0 else pr_alt
                    dtf  = date_f if r_idx%2==0 else date_alt
                    ws2.write_datetime(r_idx, 0, dt_val.to_pydatetime(), dtf)
                    ws2.write(r_idx, 1, float(price), prf)
                    ret_val = monthly_ret.iloc[r_idx - data_start_row] if r_idx - data_start_row < len(monthly_ret) else None
                    if ret_val is not None and not (ret_val != ret_val):  # not NaN
                        pf = (pos_f if r_idx%2==0 else pos_alt) if ret_val>=0 else (neg_f if r_idx%2==0 else neg_alt)
                        ws2.write(r_idx, 2, ret_val / 100, pf)
                    else:
                        ws2.write(r_idx, 2, "—", nil_f)
                    ws2.set_row(r_idx, 16)

                last_data_row = data_start_row + len(monthly) - 1

                # ── Sheet 3: Chart (linked to Monthly Data) ───────
                ws3 = wb.add_worksheet("Chart")
                ws3.hide_gridlines(2); ws3.set_tab_color("#3fb950")
                ws3.set_row(0, 32)
                ws3.merge_range(0, 0, 0, 8, f"{name} — Price Chart (linked to Monthly Data)", title_f)
                ws3.write(1, 0,
                          f"Period: {self.chart_period.get()}  ·  {dt_mod.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                          sub_f)

                # Native Excel line chart linked to Monthly Data sheet
                chart = wb.add_chart({"type": "line"})
                chart.add_series({
                    "name":       f"{name} Close Price",
                    "categories": ["Monthly Data", data_start_row, 0, last_data_row, 0],
                    "values":     ["Monthly Data", data_start_row, 1, last_data_row, 1],
                    "line":       {"color": "#f78166", "width": 2},
                    "marker":     {"type": "none"},
                })
                chart.set_title({"name": f"{name}  ({ticker})  — Monthly Close Price",
                                 "name_font": {"color": "#e6edf3", "size": 13, "bold": True}})
                chart.set_x_axis({"name": "Date", "name_font": {"color": "#8b949e"},
                                  "num_font": {"color": "#8b949e"},
                                  "line": {"color": "#30363d"},
                                  "date_axis": True})
                chart.set_y_axis({"name": "Price", "name_font": {"color": "#8b949e"},
                                  "num_font": {"color": "#8b949e"},
                                  "line": {"color": "#30363d"},
                                  "num_format": "#,##0.00"})
                chart.set_legend({"font": {"color": "#8b949e"}})
                chart.set_plotarea({"border": {"color": "#30363d"},
                                    "fill":   {"color": "#1c2128"}})
                chart.set_chartarea({"border": {"color": "#30363d"},
                                     "fill":   {"color": "#0d1117"}})
                chart.set_size({"width": 900, "height": 420})
                ws3.insert_chart(3, 0, chart)

                # Also add a monthly-return bar chart below
                bar_chart = wb.add_chart({"type": "bar"})
                bar_chart.add_series({
                    "name":       "Monthly Return %",
                    "categories": ["Monthly Data", data_start_row, 0, last_data_row, 0],
                    "values":     ["Monthly Data", data_start_row, 2, last_data_row, 2],
                    "fill":       {"color": "#3fb950"},
                    "line":       {"none": True},
                })
                bar_chart.set_title({"name": f"{name} — Monthly Returns",
                                     "name_font": {"color": "#e6edf3", "size": 12, "bold": True}})
                bar_chart.set_x_axis({"num_font":  {"color": "#8b949e"},
                                      "line":       {"color": "#30363d"},
                                      "num_format": "0.0%"})
                bar_chart.set_y_axis({"name": "Month", "name_font": {"color": "#8b949e"},
                                      "num_font": {"color": "#8b949e"},
                                      "line": {"color": "#30363d"}})
                bar_chart.set_plotarea({"border": {"color": "#30363d"},
                                        "fill":   {"color": "#1c2128"}})
                bar_chart.set_chartarea({"border": {"color": "#30363d"},
                                         "fill":   {"color": "#0d1117"}})
                bar_chart.set_size({"width": 900, "height": 300})
                ws3.insert_chart(24, 0, bar_chart)

                # ── Sheet 4: Daily Prices ─────────────────────────
                ws4 = wb.add_worksheet("Daily Prices")
                ws4.hide_gridlines(2); ws4.set_tab_color("#bc8cff")
                ws4.set_column(0, 0, 14); ws4.set_column(1, 2, 16)
                ws4.set_row(0, 32)
                ws4.merge_range(0, 0, 0, 2, f"{name} — Daily Price History", title_f)
                ws4.write(1, 0, "10-year daily history", sub_f)
                for c, h in enumerate(["Date", "Close Price", "Daily Return"]):
                    ws4.write(3, c, h, hdr_f)
                ws4.set_row(3, 22)
                ws4.freeze_panes(4, 0)

                prev = None
                for r_idx, (dt_val, price) in enumerate(zip(close.index, close.values), start=4):
                    dtf = date_f if r_idx%2==0 else date_alt
                    prf = pr_f   if r_idx%2==0 else pr_alt
                    ws4.write_datetime(r_idx, 0, dt_val.to_pydatetime(), dtf)
                    ws4.write(r_idx, 1, float(price), prf)
                    if prev is not None and prev != 0:
                        ret = (float(price) - prev) / prev
                        pf = (pos_f if r_idx%2==0 else pos_alt) if ret>=0 else (neg_f if r_idx%2==0 else neg_alt)
                        ws4.write(r_idx, 2, ret, pf)
                    else:
                        ws4.write(r_idx, 2, "—", nil_f)
                    prev = float(price)
                    ws4.set_row(r_idx, 15)

                wb.close()
                import subprocess
                subprocess.Popen(["explorer", path])
                self.after(0, lambda p=path:
                           self.title_var.set(f"  {name}  ({ticker})  — exported ✓"))
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                self.after(0, lambda m=err: self._log(f"Export error:\n{m}", "red"))

        threading.Thread(target=worker, daemon=True).start()

    def _placeholder(self):
        self._series = None; self._is_bar = False
        self.ax.clear(); self.ax.set_facecolor(CARD)
        self.ax.text(0.5, 0.5, "Select a row above to view chart",
                     transform=self.ax.transAxes, ha="center", va="center",
                     color=TEXT3, fontsize=13)
        self.ax.set_xticks([]); self.ax.set_yticks([])

    def _hover(self, event):
        if event.inaxes != self.ax: self._clear_crosshair(); return
        x, y = event.xdata, event.ydata
        if x is None: return
        import numpy as np
        if self._is_bar and self._bar_dates:
            dates, vals = self._bar_dates, self._bar_vals
            diffs = [abs(mdates.date2num(d)-x) for d in dates]
            idx   = int(np.argmin(diffs))
            v     = vals[idx]
            label = f"{dates[idx].strftime('%b %Y')}\n{v:+.2f}%"
            col   = GREEN if v>=0 else RED
        elif self._series is not None:
            s     = self._series
            xnums = mdates.date2num(s.index.to_pydatetime())
            idx   = int(np.argmin(np.abs(xnums-x)))
            v     = float(s.iloc[idx])
            is_r  = self.chart_data.get()=="returns"
            label = (f"{s.index[idx].strftime('%d %b %Y')}\n"
                     f"{'Return: ' if is_r else 'Price: '}"
                     f"{'+'if(is_r and v>=0)else''}{v:,.2f}{'%'if is_r else ''}")
            col   = ACCENT
        else:
            return

        if self._vline: self._vline.set_xdata([x,x])
        else: self._vline = self.ax.axvline(x, color=TEXT3, linewidth=0.8, linestyle="--")
        if self._hline: self._hline.set_ydata([y,y])
        else: self._hline = self.ax.axhline(y, color=TEXT3, linewidth=0.8, linestyle="--")
        if self._ann: self._ann.remove()
        self._ann = self.ax.annotate(label, xy=(x,y), xycoords="data",
            xytext=(12,12), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", facecolor=CARD2, edgecolor=col, linewidth=1.5),
            color=col, fontsize=10, fontweight="bold", zorder=10)
        self.canvas.draw_idle()

    def _leave(self, event): self._clear_crosshair()

    def _clear_crosshair(self):
        changed = False
        for attr in ("_ann","_vline","_hline"):
            obj = getattr(self, attr)
            if obj:
                try: obj.remove()
                except: pass
                setattr(self, attr, None); changed = True
        if changed: self.canvas.draw_idle()


# ── Yield curve panel (reusable) ──────────────────────────────
class YieldCurvePanel(tk.Frame):
    """
    Supports three curve types on the same chart:
      • Nominal Treasury par yields  (13 maturities, MATURITIES list)
      • TIPS real yields             (5 maturities, dashed lines)
      • Muni ETF proxy curve         (6 duration buckets, dotted lines)
    Each overlay dict has: date, yields, source, curve_type ("nom"/"tips"/"muni")
    """
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._overlays = {}   # label → row dict
        self._ann = None; self._vline = None
        self._build()

    def _build(self):
        # ── Row 1: Treasury nominal buttons ───────────────────
        row1 = tk.Frame(self, bg=CARD2, height=42)
        row1.pack(fill="x"); row1.pack_propagate(False)
        tk.Label(row1, text="  Treasury:", bg=CARD2, fg=TEXT2,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(6,3))
        for label, days in [("Today",0),("-1W",7),("-1M",30),("-3M",91),
                             ("-6M",182),("-1Y",365),("-2Y",730),("-3Y",1095)]:
            tk.Button(row1, text=label, bg=CARD, fg=TEXT2,
                      activebackground=CARD2, activeforeground=TEXT1,
                      font=("Segoe UI", 10), relief="flat", bd=1,
                      padx=7, pady=3, cursor="hand2",
                      command=lambda d=days, l=label: self._add_nom(l, d)
                      ).pack(side="left", padx=2, pady=6)
        tk.Frame(row1, bg=BORDER, width=1).pack(side="left", padx=5, fill="y")
        # TIPS button
        tk.Button(row1, text="TIPS Real", bg="#1e2d1e", fg=GREEN,
                  activebackground=CARD2, activeforeground=GREEN,
                  font=("Segoe UI", 10, "bold"), relief="flat", bd=1,
                  padx=7, pady=3, cursor="hand2",
                  command=self._add_tips).pack(side="left", padx=2, pady=6)
        # Muni button
        tk.Button(row1, text="Muni Proxy", bg="#1e1e2d", fg=PURPLE,
                  activebackground=CARD2, activeforeground=PURPLE,
                  font=("Segoe UI", 10, "bold"), relief="flat", bd=1,
                  padx=7, pady=3, cursor="hand2",
                  command=self._add_muni).pack(side="left", padx=2, pady=6)
        tk.Frame(row1, bg=BORDER, width=1).pack(side="left", padx=5, fill="y")
        self._custom_var = tk.StringVar()
        tk.Entry(row1, textvariable=self._custom_var, bg=CARD, fg=TEXT1,
                 insertbackground=TEXT1, font=("Consolas",10), width=12,
                 relief="flat", bd=2).pack(side="left", padx=2)
        tk.Label(row1, text="YYYY-MM-DD", bg=CARD2, fg=TEXT3,
                 font=("Consolas",9)).pack(side="left")
        tk.Button(row1, text="Add", bg=CARD, fg=ACCENT, font=("Segoe UI",10),
                  relief="flat", bd=0, padx=7, cursor="hand2",
                  command=self._add_custom).pack(side="left", padx=3)
        tk.Button(row1, text="Clear All", bg=CARD2, fg=RED, font=("Segoe UI",10),
                  relief="flat", bd=0, padx=7, cursor="hand2",
                  command=self._clear).pack(side="right", padx=10)
        tk.Button(row1, text="⬇ XLS", bg="#1f6b2e", fg=WHITE, font=("Segoe UI",10),
                  relief="flat", bd=0, padx=7, cursor="hand2",
                  command=self._export).pack(side="right", padx=2)

        self._status = tk.StringVar(value="Click a period to load Treasury curve  ·  TIPS = real yields  ·  Muni = ETF proxy")
        tk.Label(self, textvariable=self._status, bg=BG, fg=TEXT3,
                 font=("Consolas",10), anchor="w").pack(fill="x", padx=10, pady=2)

        self.fig, self.ax = plt.subplots(figsize=(7,3.0))
        self.fig.subplots_adjust(left=0.09, right=0.97, top=0.87, bottom=0.13)
        self._placeholder()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.draw()
        self.canvas.mpl_connect("motion_notify_event", self._hover)
        self.canvas.mpl_connect("axes_leave_event",    self._leave)

    def _placeholder(self):
        self.ax.clear(); self.ax.set_facecolor(CARD)
        self.ax.text(0.5, 0.5,
                     "Click Treasury / TIPS / Muni buttons to load curves",
                     transform=self.ax.transAxes, ha="center", va="center",
                     color=TEXT3, fontsize=12)
        self.ax.set_xticks([]); self.ax.set_yticks([])

    # ── Fetch helpers ─────────────────────────────────────────
    def _add_nom(self, label, days_back):
        target = datetime.today() - timedelta(days=days_back)
        self._status.set(f"Fetching Treasury {label}…")
        threading.Thread(target=self._fetch_nom, args=(label, target), daemon=True).start()

    def _add_tips(self):
        self._status.set("Fetching TIPS real yield curve…")
        threading.Thread(target=self._fetch_tips, daemon=True).start()

    def _add_muni(self):
        self._status.set("Fetching muni proxy curve from ETF yields…")
        threading.Thread(target=self._fetch_muni, daemon=True).start()

    def _add_custom(self):
        raw = self._custom_var.get().strip()
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d")
            self._status.set(f"Fetching Treasury {raw}…")
            threading.Thread(target=self._fetch_nom, args=(raw, dt), daemon=True).start()
        except ValueError:
            self._status.set("Invalid date — use YYYY-MM-DD")

    def _fetch_nom(self, label, dt):
        try:
            from yield_curve import fetch_curve_for_date
            row = fetch_curve_for_date(dt)
            if row:
                row["curve_type"] = "nom"
                self._overlays[label] = row
                self.after(0, self._redraw)
                self.after(0, lambda: self._status.set(
                    f"{len(self._overlays)} curve(s)  ·  {label}: {row['date']}  [{row['source']}]"))
            else:
                self.after(0, lambda: self._status.set(f"No data near {dt.strftime('%Y-%m-%d')}"))
        except Exception as e:
            self.after(0, lambda err=str(e): self._status.set(f"Error: {err}"))

    def _fetch_tips(self):
        try:
            from yield_curve import fetch_tips_curve_for_date
            row = fetch_tips_curve_for_date(datetime.today())
            if row:
                row["curve_type"] = "tips"
                self._overlays["TIPS Real"] = row
                self.after(0, self._redraw)
                self.after(0, lambda: self._status.set(
                    f"{len(self._overlays)} curve(s)  ·  TIPS: {row['date']}  [{row['source']}]"))
            else:
                self.after(0, lambda: self._status.set("TIPS data unavailable"))
        except Exception as e:
            self.after(0, lambda err=str(e): self._status.set(f"TIPS Error: {err}"))

    def _fetch_muni(self):
        try:
            from yield_curve import fetch_muni_curve
            row = fetch_muni_curve(datetime.today())
            if row:
                row["curve_type"] = "muni"
                self._overlays["Muni Proxy"] = row
                self.after(0, self._redraw)
                self.after(0, lambda: self._status.set(
                    f"{len(self._overlays)} curve(s)  ·  Muni: {row['date']}  [{row['source']}]"))
            else:
                self.after(0, lambda: self._status.set("Muni yield data unavailable from ETF info"))
        except Exception as e:
            self.after(0, lambda err=str(e): self._status.set(f"Muni Error: {err}"))

    def _redraw(self):
        from yield_curve import MATURITIES, TIPS_MATURITIES, MUNI_MATURITIES
        self.ax.clear(); self.ax.set_facecolor(CARD)
        self._ann = None; self._vline = None
        if not self._overlays:
            self._placeholder(); self.canvas.draw(); return

        # Separate curves by type
        nom_items  = [(l,r) for l,r in self._overlays.items() if r.get("curve_type","nom")=="nom"]
        tips_items = [(l,r) for l,r in self._overlays.items() if r.get("curve_type")=="tips"]
        muni_items = [(l,r) for l,r in self._overlays.items() if r.get("curve_type")=="muni"]

        all_items  = nom_items + tips_items + muni_items
        color_idx  = 0
        ax2        = None  # second y-axis for TIPS/muni if needed

        for lbl, row in nom_items:
            col = CURVE_COLORS[color_idx % len(CURVE_COLORS)]; color_idx += 1
            mats = MATURITIES
            x    = list(range(len(mats)))
            y    = [row["yields"].get(m) for m in mats]
            vx   = [xi for xi,yi in zip(x,y) if yi is not None]
            vy   = [yi for yi in y if yi is not None]
            if vy:
                self.ax.plot(vx, vy, color=col, linewidth=2.2, marker="o", markersize=5,
                             label=f"{lbl}  ({row['date']})")
                self.ax.fill_between(vx, vy, min(vy), alpha=0.05, color=col)

        for lbl, row in tips_items:
            col  = GREEN; color_idx += 1
            mats = TIPS_MATURITIES
            # Map TIPS maturities to x positions on the nominal axis
            x_nom = {m: i for i, m in enumerate(MATURITIES)}
            vx    = [x_nom[m] for m in mats if m in x_nom and row["yields"].get(m) is not None]
            vy    = [row["yields"][m] for m in mats if m in x_nom and row["yields"].get(m) is not None]
            if vy:
                self.ax.plot(vx, vy, color=col, linewidth=1.8, marker="s", markersize=5,
                             linestyle="--", label=f"TIPS Real  ({row['date']})")

        for lbl, row in muni_items:
            col  = PURPLE; color_idx += 1
            mats = MUNI_MATURITIES
            # Spread muni buckets across x axis (6 buckets → map to nominal x range)
            nom_len   = len(MATURITIES)
            bucket_xs = [i * (nom_len-1) / max(1, len(mats)-1) for i in range(len(mats))]
            vx = [bx for bx,m in zip(bucket_xs, mats) if row["yields"].get(m) is not None]
            vy = [row["yields"][m] for m in mats if row["yields"].get(m) is not None]
            if vy:
                self.ax.plot(vx, vy, color=col, linewidth=1.8, marker="^", markersize=5,
                             linestyle=":", label=f"Muni Proxy  ({row['date']})")

        # X-axis labels — always show nominal maturities
        x_all = list(range(len(MATURITIES)))
        self.ax.set_xticks(x_all)
        self.ax.set_xticklabels(MATURITIES, fontsize=9, color=TEXT2, rotation=30, ha="right")
        self.ax.set_ylabel("Yield (%)", color=TEXT2, fontsize=10)
        self.ax.set_title(
            "Yield Curves  ·  ─ Treasury  ·  - - TIPS Real  ·  ··· Muni  ·  hover for values",
            color=TEXT1, fontsize=10, fontweight="bold", pad=8)
        self.ax.tick_params(colors=TEXT3, labelsize=9)
        self.ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f%%"))
        if len(all_items) > 0:
            self.ax.legend(loc="best", framealpha=0.85, fontsize=8, ncol=2)
        self.fig.subplots_adjust(left=0.09, right=0.97, top=0.85, bottom=0.18)
        self.canvas.draw()

    def _hover(self, event):
        if event.inaxes != self.ax or not self._overlays:
            self._hide_tip(); return
        from yield_curve import MATURITIES, TIPS_MATURITIES, MUNI_MATURITIES
        x = event.xdata
        if x is None: return

        idx  = max(0, min(int(round(x)), len(MATURITIES)-1))
        mat  = MATURITIES[idx]
        lines = []

        for lbl, row in self._overlays.items():
            ct = row.get("curve_type","nom")
            if ct == "nom":
                v = row["yields"].get(mat)
                if v is not None: lines.append(f"{lbl}: {v:.2f}%")
            elif ct == "tips":
                v = row["yields"].get(mat)
                if v is not None: lines.append(f"TIPS Real {mat}: {v:.2f}%")
            elif ct == "muni":
                # Find nearest muni bucket
                muni_xs = [i*(len(MATURITIES)-1)/max(1,len(MUNI_MATURITIES)-1)
                           for i in range(len(MUNI_MATURITIES))]
                diffs   = [abs(mx - x) for mx in muni_xs]
                mi      = diffs.index(min(diffs))
                bkt     = MUNI_MATURITIES[mi]
                v       = row["yields"].get(bkt)
                if v is not None: lines.append(f"Muni {bkt}: {v:.2f}%")

        if not lines: return
        if self._vline: self._vline.set_xdata([idx,idx])
        else: self._vline = self.ax.axvline(idx, color=TEXT3, linewidth=0.8, linestyle="--")
        if self._ann: self._ann.remove()
        self._ann = self.ax.annotate(
            mat + "\n" + "\n".join(lines),
            xy=(idx, event.ydata), xycoords="data",
            xytext=(12,12), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", facecolor=CARD2, edgecolor=ACCENT, linewidth=1.5),
            color=TEXT1, fontsize=10, zorder=10)
        self.canvas.draw_idle()

    def _leave(self, event): self._hide_tip()

    def _hide_tip(self):
        changed = False
        for attr in ("_ann","_vline"):
            obj = getattr(self, attr)
            if obj:
                try: obj.remove()
                except: pass
                setattr(self, attr, None); changed = True
        if changed: self.canvas.draw_idle()

    def _clear(self):
        self._overlays.clear()
        self._status.set("Cleared — use buttons above to reload")
        self._placeholder(); self.canvas.draw()

    def _export(self):
        if not self._overlays:
            self._status.set("Load a curve first, then export")
            return
        try:
            import xlsxwriter, os
            import datetime as _dt
            from yield_curve import MATURITIES, TIPS_MATURITIES, MUNI_MATURITIES
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            ts   = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(desktop, f"JAWS_YieldCurve_{ts}.xlsx")
            wb   = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True})
            ws   = wb.add_worksheet("Yield Curves"); ws.hide_gridlines(2)
            ws.set_tab_color("#f78166")
            title_f = wb.add_format(dict(bold=True, font_size=14, font_color="#f78166",
                        bg_color="#0d1117", font_name="Consolas"))
            hf = wb.add_format(dict(bold=True, font_color="#f78166", bg_color="#161b22",
                        font_name="Consolas", font_size=10, border=1, border_color="#30363d"))
            tf = wb.add_format(dict(font_name="Consolas", font_size=10, border=1, border_color="#30363d"))
            nf = wb.add_format(dict(num_format="0.000", font_name="Consolas", font_size=10,
                        border=1, border_color="#30363d"))

            # Union of all maturities used, preserving canonical order
            all_mats = list(dict.fromkeys(
                list(MATURITIES) + list(TIPS_MATURITIES) + list(MUNI_MATURITIES)))
            ws.merge_range(0,0,0,len(self._overlays),
                           f"Yield Curves  ·  {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}", title_f)
            ws.write(1,0,"Maturity",hf)
            labels = list(self._overlays.keys())
            for c,lbl in enumerate(labels):
                ws.write(1,c+1, lbl, hf)
            ws.set_column(0,0,12); ws.set_column(1,len(labels),14)
            ws.freeze_panes(2,1)
            for r,mat in enumerate(all_mats):
                ws.write(r+2,0,mat,tf)
                for c,lbl in enumerate(labels):
                    v = self._overlays[lbl]["yields"].get(mat)
                    if v is None: ws.write(r+2,c+1,"—",tf)
                    else:         ws.write_number(r+2,c+1,float(v),nf)

            # Native chart
            chart = wb.add_chart({"type":"line"})
            n=len(all_mats)
            for c,lbl in enumerate(labels):
                chart.add_series({"name":["Yield Curves",1,c+1],
                    "categories":["Yield Curves",2,0,n+1,0],
                    "values":["Yield Curves",2,c+1,n+1,c+1]})
            chart.set_title({"name":"Yield Curves (%)"})
            chart.set_x_axis({"name":"Maturity"}); chart.set_y_axis({"name":"Yield %"})
            chart.set_size({"width":820,"height":420})
            ws.insert_chart(1,len(labels)+2,chart)
            wb.close()
            import subprocess
            subprocess.Popen(["explorer", path])
            self._status.set(f"Exported → {os.path.basename(path)}")
        except Exception as e:
            self._status.set(f"Export error: {e}")


# ── News panel (reusable) ─────────────────────────────────────
class NewsPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._all_items = []
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=CARD2, height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="  Top Stories", bg=CARD2, fg=TEXT1,
                 font=("Segoe UI", 13, "bold")).pack(side="left", fill="y", padx=8)
        self._status = tk.StringVar(value="Click Fetch News to load")
        tk.Label(hdr, textvariable=self._status, bg=CARD2, fg=TEXT3,
                 font=("Consolas",10)).pack(side="left", padx=6)
        tk.Button(hdr, text="⟳ Fetch", bg=BLUE, fg=BG,
                  font=("Segoe UI",11,"bold"), relief="flat", bd=0,
                  padx=10, pady=5, cursor="hand2",
                  command=self.load).pack(side="right", padx=8, pady=6)

        filt = tk.Frame(self, bg=BG, height=32)
        filt.pack(fill="x", padx=8, pady=(3,0)); filt.pack_propagate(False)
        tk.Label(filt, text="Filter:", bg=BG, fg=TEXT3,
                 font=("Segoe UI",10)).pack(side="left", padx=(2,6))
        self._filter = tk.StringVar(value="All")
        for lbl in ["All","HF","IPO","M&A","ISS"]:
            tk.Radiobutton(filt, text=lbl, variable=self._filter, value=lbl,
                           bg=BG, fg=TEXT2, selectcolor=CARD2,
                           activebackground=BG, activeforeground=TEXT1,
                           font=("Segoe UI",10), indicatoron=False,
                           relief="flat", bd=1, padx=8, pady=3,
                           cursor="hand2",
                           command=self._apply_filter).pack(side="left", padx=2)

        cont = tk.Frame(self, bg=BG)
        cont.pack(fill="both", expand=True, padx=4, pady=3)
        self._cv  = tk.Canvas(cont, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(cont, orient="vertical", command=self._cv.yview,
                            style="Vertical.TScrollbar")
        self._cv.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._cv.pack(side="left", fill="both", expand=True)
        self._inner = tk.Frame(self._cv, bg=BG)
        self._win   = self._cv.create_window((0,0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", lambda e:
            self._cv.configure(scrollregion=self._cv.bbox("all")))
        self._cv.bind("<Configure>", lambda e:
            self._cv.itemconfig(self._win, width=e.width))
        self._cv.bind("<MouseWheel>", lambda e:
            self._cv.yview_scroll(-1*(e.delta//120),"units"))

    def load(self):
        self._status.set("Fetching…")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            from categorized_news import fetch_all_news_categorized
            all_news = fetch_all_news_categorized()
            scored = []
            for cat, items in all_news.items():
                for item in items:
                    src = (item.get("source") or item.get("publisher") or "").lower()
                    w   = max((v for k,v in NEWS_WEIGHT.items() if k in src), default=3)
                    scored.append((w, cat, item))
            scored.sort(key=lambda x: (x[0], x[2].get("published","") or ""), reverse=True)
            self._all_items = scored
            self.after(0, lambda: self._render(scored))
            self.after(0, lambda: self._status.set(f"{len(scored)} stories · ranked by source"))
        except Exception as e:
            self.after(0, lambda err=str(e): self._status.set(f"Error: {err}"))

    def _render(self, items):
        for w in self._inner.winfo_children(): w.destroy()
        filt  = self._filter.get()
        filtered = []
        for rank, (score, cat, item) in enumerate(items):
            lbl = CAT_LABELS.get(cat, cat.upper())
            if filt != "All" and lbl != filt: continue
            if len(filtered) >= 100: break
            filtered.append((rank + 1, score, cat, lbl, item))

        # Two-column grid: pair items into rows
        for i in range(0, len(filtered), 2):
            pair_bg = CARD if (i // 2) % 2 == 0 else BG
            grid_row = tk.Frame(self._inner, bg=pair_bg)
            grid_row.pack(fill="x", pady=1)
            grid_row.columnconfigure(0, weight=1)
            grid_row.columnconfigure(1, weight=1)
            for col_idx, entry in enumerate(filtered[i:i+2]):
                rank, score, cat, lbl, item = entry
                self._add_card(grid_row, col_idx, rank, cat, lbl, item, pair_bg)
            tk.Frame(self._inner, bg=BORDER, height=1).pack(fill="x")

        self._inner.update_idletasks()
        self._cv.configure(scrollregion=self._cv.bbox("all"))

    def _add_card(self, parent, col_idx, rank, cat, cat_lbl, item, bg):
        title = item.get("title","") or item.get("headline","") or "(no title)"
        url   = item.get("url","") or item.get("link","") or ""
        src   = item.get("source","") or item.get("publisher","") or "Unknown"
        pub   = item.get("published","") or item.get("date","") or ""
        col   = CAT_COLORS.get(cat, TEXT2)

        cell = tk.Frame(parent, bg=bg, pady=5, padx=8,
                        highlightbackground=BORDER, highlightthickness=1)
        cell.grid(row=0, column=col_idx, sticky="nsew", padx=(0 if col_idx else 0, 1))

        top = tk.Frame(cell, bg=bg); top.pack(fill="x")
        tk.Label(top, text=f"#{rank:>2}", bg=bg, fg=TEXT3,
                 font=("Consolas",9)).pack(side="left")
        tk.Label(top, text=f" {cat_lbl}", bg=col, fg=BG,
                 font=("Consolas",9,"bold"), padx=4, pady=1).pack(side="left", padx=4)
        tk.Label(top, text=src, bg=bg, fg=col,
                 font=("Segoe UI",10,"bold")).pack(side="left")
        if pub:
            tk.Label(top, text=f"  {pub[:16]}", bg=bg, fg=TEXT3,
                     font=("Segoe UI",9)).pack(side="left")

        hl = tk.Label(cell, text=title, bg=bg, fg=TEXT1,
                      font=("Segoe UI",11), anchor="w", justify="left",
                      wraplength=480, cursor="hand2" if url else "arrow")
        hl.pack(fill="x", pady=(3, 0))
        if url:
            hl.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            hl.bind("<Enter>", lambda e, w=hl: w.config(fg=BLUE, font=("Segoe UI",11,"underline")))
            hl.bind("<Leave>", lambda e, w=hl: w.config(fg=TEXT1, font=("Segoe UI",11)))

    def _apply_filter(self):
        if self._all_items: self._render(self._all_items)


# ── FI Spreads Panel ──────────────────────────────────────────
class SpreadPanel(tk.Frame):
    """Credit spreads from FRED — auto-loads, ColorTable-style layout."""

    # Column headers and pixel widths — same font (Consolas 11) for header + data
    _SCOLS = ("Name",    "Unit", "Current","1M Ago","3M Ago","1Y Ago",
              "3Y Ago","5Y Ago","10Y Ago","Min",   "Max",   "Z-Score")
    _SW    = (210,       42,     84,       80,      80,      80,
              80,       80,      80,       80,      80,      84)
    _PERIODS = [("1Y", 1), ("3Y", 3), ("5Y", 5), ("All", 30)]

    def __init__(self, parent, fetch_fn=None, title=None,
                 needs_fred_key=True, **kw):
        super().__init__(parent, bg=BG, **kw)
        from fi_spreads import fetch_spread_analytics
        self._fetch_fn     = fetch_fn or fetch_spread_analytics
        self._title        = title or "Credit Spreads  (ICE BofA / FRED)"
        self._needs_key    = needs_fred_key
        self._rows         = []
        self._selected_idx = None
        self._hist_years   = 3
        self._thread       = None
        self._period_btns  = {}
        self._build()
        # Auto-load on creation
        self.after(100, self._fetch)

    # ── layout ───────────────────────────────────────────────
    def _build(self):
        # Header bar
        hdr = tk.Frame(self, bg=SIDEBAR, height=42, pady=0)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"  {self._title}",
                 bg=SIDEBAR, fg=TEXT1, font=("Consolas", 13, "bold")).pack(side="left", pady=8)
        self._status = tk.Label(hdr, text="Loading…", bg=SIDEBAR, fg=TEXT3,
                                font=("Consolas", 10))
        self._status.pack(side="left", padx=10)
        btn_f = tk.Frame(hdr, bg=SIDEBAR); btn_f.pack(side="right", padx=8)
        tk.Button(btn_f, text="↻ Refresh", bg=CARD2, fg=TEXT2,
                  font=F_SANS, relief="flat", padx=8, pady=2, cursor="hand2",
                  command=self._fetch).pack(side="left", padx=4)
        tk.Button(btn_f, text="⬇ Export XLS", bg="#1f6b2e", fg=WHITE,
                  font=F_SANS, relief="flat", padx=8, pady=2, cursor="hand2",
                  command=self._export).pack(side="left", padx=4)

        # FRED API key banner — shown only when no key is set
        self._key_bar = tk.Frame(self, bg="#161b22", height=38)
        if not os.environ.get("FRED_API_KEY", ""):
            self._key_bar.pack(fill="x"); self._key_bar.pack_propagate(False)
        tk.Label(self._key_bar,
                 text="  5Y / 10Y columns need a free FRED API key:",
                 bg="#161b22", fg=YELLOW, font=("Consolas", 10)).pack(side="left", padx=4)
        tk.Button(self._key_bar, text="1. Get Free Key →",
                  bg=CARD2, fg=BLUE, font=("Consolas", 10),
                  relief="flat", padx=6, cursor="hand2",
                  command=lambda: webbrowser.open(
                      "https://fred.stlouisfed.org/docs/api/api_key.html")
                  ).pack(side="left", padx=4)
        tk.Label(self._key_bar, text="  2. Paste key:",
                 bg="#161b22", fg=TEXT2, font=("Consolas", 10)).pack(side="left")
        self._key_var = tk.StringVar()
        tk.Entry(self._key_bar, textvariable=self._key_var, bg=CARD, fg=TEXT1,
                 insertbackground=TEXT1, font=("Consolas", 10),
                 relief="flat", width=34).pack(side="left", padx=4, ipady=2)
        tk.Button(self._key_bar, text="Save & Reload",
                  bg=ACCENT, fg=BG, font=("Consolas", 10, "bold"),
                  relief="flat", padx=8, cursor="hand2",
                  command=self._save_fred_key).pack(side="left", padx=4)

        # Paned: top = table, bottom = chart
        paned = tk.PanedWindow(self, orient="vertical", bg=BG,
                               sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        # ── spread table ─────────────────────────────────────
        tbl_host = tk.Frame(paned, bg=CARD)
        paned.add(tbl_host, minsize=160)

        _F = ("Consolas", 11)   # single font for BOTH header and data — guarantees alignment
        self._F = _F

        # Synced-scroll table (header + body share horizontal scrollbar)
        cont, head_frame, self._inner = _scroll_table(tbl_host)
        cont.pack(fill="both", expand=True)
        for col, w in zip(self._SCOLS, self._SW):
            anc = "w" if col in ("Name",) else "e"
            tk.Label(head_frame, text=col, bg=CARD2, fg=TEXT2, font=_F,
                     width=w//7, anchor=anc, padx=4, pady=4).pack(side="left")

        # ── history chart ────────────────────────────────────
        chart_host = tk.Frame(paned, bg=BG)
        paned.add(chart_host, minsize=200)

        # Period toggle bar — sits directly above the chart
        period_bar = tk.Frame(chart_host, bg=SIDEBAR, height=32)
        period_bar.pack(fill="x", side="top"); period_bar.pack_propagate(False)
        tk.Label(period_bar, text="  Chart Period:", bg=SIDEBAR, fg=TEXT3,
                 font=("Segoe UI", 10)).pack(side="left", padx=(6,2))
        for lbl, yrs in self._PERIODS:
            b = tk.Button(period_bar, text=lbl,
                          bg=ACCENT if yrs == self._hist_years else CARD2,
                          fg=BG if yrs == self._hist_years else TEXT2,
                          font=("Segoe UI", 10), relief="flat", padx=10, pady=3,
                          cursor="hand2",
                          command=lambda y=yrs, l=lbl: self._set_period(y, l))
            b.pack(side="left", padx=2, pady=4)
            self._period_btns[lbl] = b

        self._chart_title = tk.Label(chart_host,
                                     text="  Click a row above to view spread history",
                                     bg=BG, fg=TEXT2, font=("Consolas", 10))
        self._chart_title.pack(fill="x", side="top", pady=(4,0))

        fig = matplotlib.figure.Figure(facecolor=BG, tight_layout=True)
        self._ax = fig.add_subplot(111)
        self._ax.set_facecolor(CARD)
        self._fig = fig
        self._canvas_chart = FigureCanvasTkAgg(fig, master=chart_host)
        self._canvas_chart.get_tk_widget().pack(fill="both", expand=True)

        self._annot = self._ax.annotate("", xy=(0,0), xytext=(8,8),
                                        textcoords="offset points",
                                        bbox=dict(boxstyle="round,pad=0.3",
                                                  fc=CARD2, ec=BORDER),
                                        color=TEXT1, fontsize=9, visible=False)
        self._vline = self._ax.axvline(x=0, color=TEXT3, lw=0.8, visible=False)
        self._canvas_chart.mpl_connect("motion_notify_event", self._hover)
        self._canvas_chart.mpl_connect("axes_leave_event",
                                        lambda e: (self._annot.__setattr__("visible", False),
                                                   self._vline.__setattr__("visible", False),
                                                   self._canvas_chart.draw_idle()))

    # ── data loading ──────────────────────────────────────────
    def _fetch(self):
        if self._thread and self._thread.is_alive():
            return
        self._status.config(text="Fetching from FRED…", fg=YELLOW)
        self._thread = threading.Thread(target=self._fetch_worker, daemon=True)
        self._thread.start()

    def _fetch_worker(self):
        try:
            rows = self._fetch_fn()
            self.after(0, lambda r=rows: self._populate(r))
        except Exception as ex:
            self.after(0, lambda m=str(ex): self._status.config(
                text=f"Error: {m}", fg=RED))

    def _populate(self, rows):
        self._rows = rows
        for w in self._inner.winfo_children():
            w.destroy()

        _F  = self._F
        cats = {}
        for r in rows:
            cats.setdefault(r["category"], []).append(r)

        data_idx = 0   # index into the flat non-error rows list
        for cat, cat_rows in cats.items():
            # Category divider — span full width
            div = tk.Frame(self._inner, bg=CARD2)
            div.pack(fill="x")
            tk.Label(div, text=f"  {cat}", bg=CARD2, fg=ACCENT,
                     font=("Consolas", 10, "bold"), anchor="w", pady=2).pack(side="left")

            for r in cat_rows:
                if r.get("error"):
                    continue
                i   = data_idx; data_idx += 1
                bg  = ROW_A if i % 2 == 0 else ROW_B
                row = tk.Frame(self._inner, bg=bg, cursor="hand2")
                row.pack(fill="x")

                is_oas = r.get("is_oas", False)
                unit   = r.get("unit", "bps" if is_oas else "%")
                dec    = r.get("decimals", 0 if is_oas else 2)
                z      = r.get("z_score")
                hist   = r.get("hist", {})

                def _fmt(v, d=dec):
                    if v is None: return "—"
                    return f"{v:.{d}f}"

                def _z_fg(zv):
                    if zv is None: return TEXT2
                    if zv >  2.0:  return RED
                    if zv >  1.0:  return YELLOW
                    if zv < -1.0:  return GREEN
                    return TEXT2

                # Build each cell with consistent font + pixel-width
                def _cell(text, w_px, fg=TEXT1, anchor="e", fr=row, b=bg):
                    tk.Label(fr, text=text, bg=b, fg=fg, font=_F,
                             width=w_px//7, anchor=anchor,
                             padx=4, pady=5).pack(side="left")

                _cell(r["name"][:30],            self._SW[0], anchor="w")
                _cell(unit,                       self._SW[1], fg=TEXT3, anchor="w")
                _cell(_fmt(r.get("current")),    self._SW[2], fg=_z_fg(z))
                _cell(_fmt(hist.get("1M")),      self._SW[3], fg=TEXT2)
                _cell(_fmt(hist.get("3M")),      self._SW[4], fg=TEXT2)
                _cell(_fmt(hist.get("1Y")),      self._SW[5], fg=TEXT2)
                _cell(_fmt(hist.get("3Y")),      self._SW[6], fg=TEXT2)
                _cell(_fmt(hist.get("5Y")),      self._SW[7], fg=TEXT2)
                _cell(_fmt(hist.get("10Y")),     self._SW[8], fg=TEXT2)
                _cell(_fmt(r.get("all_min")),    self._SW[9],  fg=GREEN)
                _cell(_fmt(r.get("all_max")),    self._SW[10], fg=RED)
                zs_txt = f"{z:+.2f}σ" if z is not None else "—"
                _cell(zs_txt,                    self._SW[11], fg=_z_fg(z))

                def _bind(fr=row, ri=i, b=bg):
                    fr.bind("<Button-1>", lambda e, x=ri: self._select_row(x))
                    for c in fr.winfo_children():
                        c.bind("<Button-1>", lambda e, x=ri: self._select_row(x))
                    fr.bind("<Enter>",  lambda e, f=fr:    [f.config(bg=HOVER)] +
                            [c.config(bg=HOVER) for c in f.winfo_children()])
                    fr.bind("<Leave>",  lambda e, f=fr, bb=b: [f.config(bg=bb)] +
                            [c.config(bg=bb) for c in f.winfo_children()])
                _bind()

        has_key = bool(os.environ.get("FRED_API_KEY",""))
        ok = sum(1 for r in rows if not r.get("error"))
        self._status.config(
            text=f"FRED/ICE BofA · {ok}/{len(rows)} series · {datetime.now().strftime('%H:%M')}",
            fg=GREEN)

    def _select_row(self, idx):
        self._selected_idx = idx
        data_rows = [r for r in self._rows if not r.get("error")]
        if idx < len(data_rows):
            self._load_chart(data_rows[idx])

    def _load_chart(self, row):
        name = row["name"]
        self._chart_title.config(text=f"  {name} — loading history…", fg=YELLOW)
        years = self._hist_years
        # Use pre-fetched raw data when available (avoids second FRED call)
        raw_dates  = row.get("raw_dates",  [])
        raw_values = row.get("raw_values", [])
        is_oas     = row.get("is_oas", False)

        if raw_dates:
            import datetime as _dt
            cutoff = _dt.date.today() - relativedelta(years=years)
            paired = [(d, v) for d, v in zip(raw_dates, raw_values) if d >= cutoff]
            if paired:
                ds, vs = zip(*paired)
                data = {"dates":  [_dt.datetime.combine(d, _dt.time()) for d in ds],
                        "values": list(vs)}
                self._draw_chart(data, name, row)
                return

        # Fallback: re-fetch from FRED
        def worker():
            from fi_spreads import fetch_spread_history_fred
            data = fetch_spread_history_fred(row.get("series_id",""), years=years)
            self.after(0, lambda: self._draw_chart(data, name, row))
        threading.Thread(target=worker, daemon=True).start()

    def _draw_chart(self, data, name, row):
        self._ax.clear()
        self._ax.set_facecolor(CARD)
        self._fig.patch.set_facecolor(BG)

        if not data:
            self._ax.text(0.5, 0.5, "No history available", transform=self._ax.transAxes,
                          color=TEXT2, ha="center", va="center", fontsize=12)
            self._canvas_chart.draw()
            self._chart_title.config(text=f"{name} — no history", fg=RED)
            return

        dates  = data["dates"]
        values = data["values"]
        # All spreads are stored/charted in bps
        y_vals  = values
        y_label = "Spread (bps)"

        import matplotlib.dates as mdates
        color = ACCENT
        self._ax.plot(dates, y_vals, color=color, lw=1.5)
        mean_v = sum(y_vals) / len(y_vals)
        self._ax.axhline(mean_v, color=TEXT3, lw=0.8, ls="--", label=f"Avg {mean_v:.0f}")
        self._ax.fill_between(dates, y_vals, mean_v,
                              where=[v >= mean_v for v in y_vals],
                              alpha=0.18, color=RED)
        self._ax.fill_between(dates, y_vals, mean_v,
                              where=[v < mean_v for v in y_vals],
                              alpha=0.18, color=GREEN)
        self._ax.tick_params(colors=TEXT2, labelsize=9)
        for spine in self._ax.spines.values():
            spine.set_edgecolor(BORDER)
        self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%b'%y"))
        self._ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self._fig.autofmt_xdate(rotation=30, ha="right")
        self._ax.set_ylabel(y_label, color=TEXT2, fontsize=9)
        self._ax.legend(fontsize=8, facecolor=CARD2, labelcolor=TEXT1,
                        edgecolor=BORDER, loc="upper right")

        self._hist_dates  = dates
        self._hist_excess = y_vals
        self._annot = self._ax.annotate("", xy=(0, 0),
                                         xytext=(8, 8), textcoords="offset points",
                                         bbox=dict(boxstyle="round,pad=0.3", fc=CARD2, ec=BORDER),
                                         color=TEXT1, fontsize=9, visible=False)
        self._vline = self._ax.axvline(x=dates[0], color=TEXT3, lw=0.8, visible=False)

        period_str = "Full history" if self._hist_years >= 20 else f"{self._hist_years}Y"
        self._canvas_chart.draw()
        self._chart_title.config(
            text=f"  {name}  ·  {period_str}  ·  {y_label}",
            fg=TEXT1)

    def _hover(self, event):
        if not event.inaxes or not hasattr(self, "_hist_dates") or not self._hist_dates:
            return
        import matplotlib.dates as mdates
        xdata = mdates.date2num(self._hist_dates)
        x = event.xdata
        if x is None:
            return
        idx = min(range(len(xdata)), key=lambda i: abs(xdata[i] - x))
        d = self._hist_dates[idx]
        v = self._hist_excess[idx]
        self._annot.set_text(f"{d.strftime('%Y-%m-%d')}\n{v:+.2f}%")
        self._annot.xy = (d, v)
        self._annot.set_visible(True)
        self._vline.set_xdata([d, d])
        self._vline.set_visible(True)
        self._canvas_chart.draw_idle()

    def _set_period(self, years, label=""):
        self._hist_years = years
        # Update button highlight
        for lbl, btn in self._period_btns.items():
            active = (lbl == label)
            btn.config(bg=ACCENT if active else CARD2,
                       fg=BG    if active else TEXT2)
        # Re-draw chart if a row is already selected
        if self._selected_idx is not None:
            data_rows = [r for r in self._rows if not r.get("error")]
            if self._selected_idx < len(data_rows):
                self._load_chart(data_rows[self._selected_idx])

    def _save_fred_key(self):
        """Save FRED API key to .env, reload data with full history."""
        key = self._key_var.get().strip()
        if not key or len(key) < 10:
            self._status.config(text="Paste a valid FRED API key first", fg=RED)
            return
        # Write to .env
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "FRED_API_KEY=" in content:
                import re
                content = re.sub(r"FRED_API_KEY=.*", f"FRED_API_KEY={key}", content)
            else:
                content += f"\nFRED_API_KEY={key}"
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            self._status.config(text=f"Could not write .env: {e}", fg=RED)
            return
        # Activate in current process
        os.environ["FRED_API_KEY"] = key
        import fi_spreads
        fi_spreads._FRED_KEY = key
        # Hide the banner and reload
        self._key_bar.pack_forget()
        self._status.config(text="FRED key saved — reloading with full history…", fg=GREEN)
        self._fetch()

    # ── Export ────────────────────────────────────────────────
    def _export(self):
        if not self._rows:
            self._status.config(text="Nothing to export yet", fg=RED)
            return
        self._status.config(text="Exporting…", fg=YELLOW)
        rows  = [r for r in self._rows if not r.get("error")]
        title = self._title
        import threading
        threading.Thread(target=self._export_worker, args=(rows, title),
                         daemon=True).start()

    def _export_worker(self, rows, title):
        try:
            import xlsxwriter, os
            import datetime as _dt
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            ts   = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = "".join(c for c in title.split("(")[0].strip()
                           if c.isalnum() or c in " _-")[:24].replace(" ","_")
            path = os.path.join(desktop, f"JAWS_{safe}_{ts}.xlsx")
            wb   = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True})
            ws   = wb.add_worksheet("Data"); ws.hide_gridlines(2)
            ws.set_tab_color("#f78166")

            title_f = wb.add_format(dict(bold=True, font_size=14, font_color="#f78166",
                        bg_color="#0d1117", font_name="Consolas"))
            hf = wb.add_format(dict(bold=True, font_color="#f78166", bg_color="#161b22",
                        font_name="Consolas", font_size=10, border=1, border_color="#30363d"))
            tf = wb.add_format(dict(font_name="Consolas", font_size=10, border=1,
                        border_color="#30363d"))
            nf = wb.add_format(dict(num_format="0.00", font_name="Consolas", font_size=10,
                        border=1, border_color="#30363d"))

            headers = ["Name","Category","Unit","Current","1M Ago","3M Ago","1Y Ago",
                       "3Y Ago","5Y Ago","10Y Ago","All Min","All Max","Z-Score","As Of"]
            ws.merge_range(0,0,0,len(headers)-1, title, title_f)
            for c,h in enumerate(headers): ws.write(1,c,h,hf)
            ws.set_column(0,0,26); ws.set_column(1,1,16); ws.set_column(2,13,11)
            ws.freeze_panes(2,0)

            for r_i, r in enumerate(rows):
                rr = r_i + 2
                h  = r.get("hist", {})
                ws.write(rr,0, r["name"], tf)
                ws.write(rr,1, r.get("category",""), tf)
                ws.write(rr,2, r.get("unit",""), tf)
                vals = [r.get("current"), h.get("1M"), h.get("3M"), h.get("1Y"),
                        h.get("3Y"), h.get("5Y"), h.get("10Y"),
                        r.get("all_min"), r.get("all_max"), r.get("z_score")]
                for c, v in enumerate(vals):
                    if v is None: ws.write(rr, 3+c, "—", tf)
                    else:         ws.write_number(rr, 3+c, float(v), nf)
                ws.write(rr, 13, r.get("as_of",""), tf)

            # Per-series full history sheet (raw)
            hist_ws = wb.add_worksheet("History"); hist_ws.hide_gridlines(2)
            col = 0
            for r in rows:
                d = r.get("raw_dates", []); v = r.get("raw_values", [])
                if not d: continue
                hist_ws.write(0, col, r["name"], hf)
                hist_ws.write(1, col, "Date", hf); hist_ws.write(1, col+1, r.get("unit","val"), hf)
                for i,(dd,vv) in enumerate(zip(d, v)):
                    hist_ws.write(i+2, col, str(dd), tf)
                    hist_ws.write_number(i+2, col+1, float(vv), nf)
                hist_ws.set_column(col, col, 12); hist_ws.set_column(col+1, col+1, 10)
                col += 3

            wb.close()
            import subprocess
            subprocess.Popen(["explorer", path])
            self.after(0, lambda p=path: self._status.config(
                text=f"Exported → {os.path.basename(p)}", fg=GREEN))
        except Exception as e:
            self.after(0, lambda m=str(e): self._status.config(
                text=f"Export error: {m}", fg=RED))


# ── Realized Volatility panel ─────────────────────────────────
_RVOL_WINDOWS = [
    ("1M",  21),
    ("3M",  63),
    ("6M",  126),
    ("1Y",  252),
    ("3Y",  756),
]
# Fixed linestyle per rolling window so it reads consistently across instruments
_RVOL_STYLES = {"1M": "-", "3M": "--", "6M": "-.", "1Y": ":", "3Y": (0,(5,1,1,1))}
# Lookback (display) horizons in years; "Max" = full available history
_RVOL_LOOKBACKS = [("1Y",1), ("2Y",2), ("3Y",3), ("5Y",5), ("10Y",10), ("Max",99)]
_RVOL_COLORS = ["#3fb950","#58a6ff","#f78166","#e3b341","#bc8cff","#79c0ff",
                "#ff6b6b","#ffa94d","#51cf66","#f06595"]

class RealizedVolPanel(tk.Frame):
    """
    Plots annualized realized (historical) volatility over time for one or
    more instruments. Each instrument shows selectable rolling windows.
    Supports search-and-add for any ticker on Yahoo Finance.
    """

    def __init__(self, parent, ticker_map_fn=None, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._ticker_map_fn = ticker_map_fn   # callable → {name: sym}
        self._series   = {}    # sym → (display_name, pd.Series close)  (full 10y)
        self._color_idx = 0
        self._sym_colors = {}  # sym → color
        # Which rolling windows are active (default 1M + 3M for clarity)
        self._win_vars = {label: tk.BooleanVar(value=(label in ("1M","3M")))
                          for label, _ in _RVOL_WINDOWS}
        self._lookback_var = tk.StringVar(value="3Y")   # display horizon
        self._build()

    # ── UI ────────────────────────────────────────────────────
    def _build(self):
        import matplotlib.figure

        # ── Row 1: search + lookback ──────────────────────────
        ctrl = tk.Frame(self, bg=SIDEBAR, height=40)
        ctrl.pack(fill="x", side="top"); ctrl.pack_propagate(False)

        tk.Label(ctrl, text="  Add ticker:", bg=SIDEBAR, fg=TEXT2,
                 font=F_SANS).pack(side="left")
        self._sv = tk.StringVar()
        self._entry = tk.Entry(ctrl, textvariable=self._sv, bg=CARD, fg=TEXT1,
                               insertbackground=TEXT1, font=F_TREE,
                               relief="flat", width=22)
        self._entry.pack(side="left", padx=6, pady=7, ipady=3)
        self._entry.bind("<KeyRelease>", self._on_key)
        self._entry.bind("<Return>",     lambda e: self._do_search())
        self._entry.bind("<Escape>",     lambda e: self._hide_drop())
        tk.Button(ctrl, text="Search", bg=ACCENT, fg=BG, font=F_SANS,
                  relief="flat", padx=10, cursor="hand2",
                  command=self._do_search).pack(side="left", padx=(0,10))

        # Lookback (display horizon) selector
        tk.Label(ctrl, text="Lookback:", bg=SIDEBAR, fg=TEXT3,
                 font=F_SANS).pack(side="left", padx=(4,2))
        for label, _yrs in _RVOL_LOOKBACKS:
            tk.Radiobutton(ctrl, text=label, variable=self._lookback_var,
                           value=label, bg=SIDEBAR, fg=TEXT2, selectcolor=CARD2,
                           activebackground=SIDEBAR, font=("Segoe UI",10),
                           command=self._replot).pack(side="left", padx=1)

        tk.Button(ctrl, text="Clear All", bg=CARD2, fg=TEXT2, font=F_SANS,
                  relief="flat", padx=8, cursor="hand2",
                  command=self._clear_all).pack(side="right", padx=8)
        tk.Button(ctrl, text="⬇ Export XLS", bg="#1f6b2e", fg=WHITE, font=F_SANS,
                  relief="flat", padx=8, cursor="hand2",
                  command=self._export).pack(side="right", padx=2)

        # ── Row 2: rolling-window toggles + status ────────────
        wrow = tk.Frame(self, bg=SIDEBAR, height=30)
        wrow.pack(fill="x", side="top"); wrow.pack_propagate(False)
        tk.Label(wrow, text="  Rolling window:", bg=SIDEBAR, fg=TEXT3,
                 font=F_SANS).pack(side="left")
        for label, _ in _RVOL_WINDOWS:
            tk.Checkbutton(wrow, text=label, variable=self._win_vars[label],
                           bg=SIDEBAR, fg=TEXT2, selectcolor=CARD2,
                           activebackground=SIDEBAR, font=("Segoe UI",10),
                           command=self._replot).pack(side="left", padx=3)
        self._rvol_status = tk.Label(wrow,
                                     text="Click a row in the table above, or search to add",
                                     bg=SIDEBAR, fg=TEXT3, font=F_SANS)
        self._rvol_status.pack(side="left", padx=14)

        # Search dropdown (overlay)
        self._drop = tk.Frame(self, bg="#1c2128", bd=1, relief="solid")

        # Instrument legend strip (color = instrument)
        self._leg_frame = tk.Frame(self, bg=CARD2, height=24)
        self._leg_frame.pack(fill="x", side="top"); self._leg_frame.pack_propagate(False)

        # Matplotlib chart
        self.fig = matplotlib.figure.Figure(facecolor=BG, tight_layout=True)
        self.ax  = self.fig.add_subplot(111)
        self._style_ax()
        self._canvas = FigureCanvasTkAgg(self.fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        self._debounce = None
        self._last_q   = ""

    def _style_ax(self):
        self.ax.set_facecolor(BG)
        self.ax.tick_params(colors=TEXT2, labelsize=9)
        for spine in self.ax.spines.values():
            spine.set_color(BORDER if hasattr(self.ax, 'spines') else "#30363d")
        self.ax.set_ylabel("Annualized Vol (%)", color=TEXT2, fontsize=9)
        self.ax.grid(True, color="#30363d", linewidth=0.5, linestyle="--")

    # ── Search ────────────────────────────────────────────────
    def _on_key(self, event=None):
        if self._debounce:
            self.after_cancel(self._debounce)
        q = self._sv.get().strip()
        if not q:
            self._hide_drop(); return
        self._debounce = self.after(400, self._do_search)

    def _do_search(self):
        if self._debounce:
            self.after_cancel(self._debounce); self._debounce = None
        q = self._sv.get().strip()
        if not q or q == self._last_q: return
        self._last_q = q
        self._rvol_status.config(text="Searching…")
        import threading
        threading.Thread(target=self._search_worker, args=(q,), daemon=True).start()

    def _search_worker(self, query):
        try:
            import yfinance as yf
            hits = yf.Search(query, max_results=8).quotes
            results = [(h.get("symbol",""),
                        h.get("shortname") or h.get("longname") or h.get("symbol",""),
                        h.get("typeDisp",""),
                        h.get("exchDisp",""))
                       for h in hits if h.get("symbol")]
            self.after(0, lambda r=results: self._show_drop(r, query))
        except Exception as e:
            self.after(0, lambda: self._rvol_status.config(text=f"Error: {e}"))

    def _show_drop(self, results, query):
        for w in self._drop.winfo_children(): w.destroy()
        if not results:
            self._rvol_status.config(text=f'No results for "{query}"')
            return
        self._rvol_status.config(text=f"{len(results)} results — click to add")
        row_h = 30
        self._drop.place(in_=self, x=0, y=44, relwidth=1,
                         height=min(len(results)*row_h+4, 240))
        self._drop.lift()
        for sym, name, typ, exch in results:
            r = tk.Frame(self._drop, bg="#1c2128", cursor="hand2")
            r.pack(fill="x", padx=2, pady=1)
            tk.Label(r, text=f" {sym}", bg="#1c2128", fg=ACCENT,
                     font=("Consolas",11,"bold"), width=11, anchor="w").pack(side="left")
            tk.Label(r, text=name[:44], bg="#1c2128", fg=TEXT1,
                     font=("Consolas",10), anchor="w").pack(side="left", fill="x", expand=True)
            tk.Label(r, text=f"{typ}  {exch} ", bg="#1c2128", fg=TEXT3,
                     font=("Consolas",9)).pack(side="right")
            def _in(e, fr=r):  fr.config(bg=HOVER); [c.config(bg=HOVER) for c in fr.winfo_children()]
            def _out(e, fr=r): fr.config(bg="#1c2128"); [c.config(bg="#1c2128") for c in fr.winfo_children()]
            def _clk(e, s=sym, n=name): self._pick(s, n)
            for w in [r] + list(r.winfo_children()):
                w.bind("<Enter>",    _in)
                w.bind("<Leave>",    _out)
                w.bind("<Button-1>", _clk)

    def _hide_drop(self):
        self._drop.place_forget(); self._last_q = ""

    def _pick(self, sym, name):
        self._hide_drop()
        self._sv.set("")
        self._last_q = ""
        if sym in self._series:
            self._rvol_status.config(text=f"{sym} already loaded")
            return
        self._rvol_status.config(text=f"Loading {sym}…")
        import threading
        threading.Thread(target=self._load_worker, args=(sym, name), daemon=True).start()

    # ── Public: add from a table-row click ────────────────────
    def add_from_table(self, name, ticker):
        """Called when a row in the market tables above is clicked."""
        if not ticker or ticker == "—":
            return
        if ticker in self._series:
            self._rvol_status.config(text=f"{ticker} already plotted")
            return
        self._rvol_status.config(text=f"Loading {name}…")
        import threading
        threading.Thread(target=self._load_worker,
                         args=(ticker, name), daemon=True).start()

    # ── Data ─────────────────────────────────────────────────
    def _load_worker(self, sym, name):
        try:
            import market_data as _md
            close = _md.price_history(sym, period="10y").dropna()
            if close.empty:
                self.after(0, lambda: self._rvol_status.config(
                    text=f"No data for {sym}"))
                return
            self.after(0, lambda c=close, s=sym, n=name: self._add_series(s, n, c))
        except Exception as e:
            self.after(0, lambda err=str(e): self._rvol_status.config(text=f"Error: {err}"))

    def _add_series(self, sym, name, close):
        col = _RVOL_COLORS[self._color_idx % len(_RVOL_COLORS)]
        self._color_idx += 1
        self._sym_colors[sym] = col
        self._series[sym] = (name, close)
        self._update_legend()
        self._replot()
        self._rvol_status.config(text=f"{len(self._series)} instrument(s) loaded")

    def _clear_all(self):
        self._series.clear()
        self._sym_colors.clear()
        self._color_idx = 0
        self._update_legend()
        self._replot()
        self._rvol_status.config(text="Cleared")

    # ── Plot ──────────────────────────────────────────────────
    def _replot(self):
        import pandas as pd
        self.ax.clear()
        self._style_ax()

        if not self._series:
            self._canvas.draw()
            return

        # Display cutoff from lookback selector
        lb_label = self._lookback_var.get()
        lb_years = dict(_RVOL_LOOKBACKS).get(lb_label, 3)
        cutoff   = None
        if lb_years < 99:
            cutoff = pd.Timestamp(datetime.now()) - pd.DateOffset(years=lb_years)

        active_windows = [(lbl, d) for lbl, d in _RVOL_WINDOWS
                          if self._win_vars[lbl].get()]
        n_inst = len(self._series)

        for sym, (name, close) in self._series.items():
            col  = self._sym_colors.get(sym, GREEN)
            rets = close.pct_change().dropna()
            for label, days in active_windows:
                if len(rets) < days:
                    continue
                # Compute rolling vol on the FULL series (so the left edge of
                # the display window is still accurate), then slice for display.
                roll_vol = (rets.rolling(days).std() * (252 ** 0.5) * 100).dropna()
                if cutoff is not None:
                    roll_vol = roll_vol[roll_vol.index >= cutoff]
                if roll_vol.empty:
                    continue
                style = _RVOL_STYLES.get(label, "-")
                # Label: instrument + window so every line is identifiable
                disp = f"{name[:16]} · {label}"
                self.ax.plot(roll_vol.index, roll_vol.values,
                             color=col, linestyle=style, linewidth=1.4,
                             label=disp, alpha=0.9)

        # Legend: keep compact; only show if not too many lines
        n_lines = n_inst * len(active_windows)
        if 0 < n_lines <= 12:
            self.ax.legend(fontsize=8, facecolor=CARD2, labelcolor=TEXT1,
                           edgecolor="#30363d", loc="upper left", ncol=max(1, n_inst))
        self.ax.set_title(f"Realized Volatility (annualized %)  ·  {lb_label} view",
                          color=TEXT2, fontsize=10, pad=6)
        import matplotlib.dates as mdates_
        self.ax.xaxis.set_major_formatter(mdates_.DateFormatter("%b '%y"))
        self.ax.xaxis.set_major_locator(mdates_.AutoDateLocator())
        self.fig.autofmt_xdate(rotation=30, ha="right")
        self._canvas.draw()

    def _update_legend(self):
        for w in self._leg_frame.winfo_children(): w.destroy()
        if not self._series:
            tk.Label(self._leg_frame, text="  No instruments plotted",
                     bg=CARD2, fg=TEXT3, font=("Consolas",9)).pack(side="left", padx=6)
            return
        tk.Label(self._leg_frame, text="  Color =", bg=CARD2, fg=TEXT3,
                 font=("Consolas",9)).pack(side="left")
        for sym, (name, _) in self._series.items():
            col = self._sym_colors.get(sym, GREEN)
            f = tk.Frame(self._leg_frame, bg=CARD2)
            f.pack(side="left", padx=5)
            tk.Label(f, text="■", bg=CARD2, fg=col,
                     font=("Consolas",11)).pack(side="left")
            tk.Label(f, text=f"{name[:18]} ({sym})", bg=CARD2, fg=TEXT2,
                     font=("Consolas",9)).pack(side="left")
            tk.Button(f, text="✕", bg=CARD2, fg=TEXT3, font=("Consolas",9),
                      relief="flat", cursor="hand2", padx=2,
                      command=lambda s=sym: self._remove(s)).pack(side="left")
        # Linestyle = window hint
        tk.Label(self._leg_frame,
                 text="  |  Line style = window (1M solid, 3M dashed, 6M dash-dot, 1Y dotted)",
                 bg=CARD2, fg=TEXT3, font=("Consolas",9)).pack(side="left", padx=6)

    def _remove(self, sym):
        self._series.pop(sym, None)
        self._sym_colors.pop(sym, None)
        self._update_legend()
        self._replot()
        self._rvol_status.config(text=f"{len(self._series)} instrument(s)")

    # ── Export ────────────────────────────────────────────────
    def _export(self):
        if not self._series:
            self._rvol_status.config(text="Nothing to export — add an instrument first")
            return
        self._rvol_status.config(text="Exporting…")
        # Capture state on main thread
        lb_label = self._lookback_var.get()
        lb_years = dict(_RVOL_LOOKBACKS).get(lb_label, 3)
        active   = [(lbl, d) for lbl, d in _RVOL_WINDOWS if self._win_vars[lbl].get()]
        series   = {s: (n, c.copy()) for s, (n, c) in self._series.items()}
        import threading
        threading.Thread(target=self._export_worker,
                         args=(series, active, lb_years, lb_label), daemon=True).start()

    def _export_worker(self, series, active, lb_years, lb_label):
        try:
            import xlsxwriter, os, pandas as pd
            import datetime as _dt
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            ts   = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(desktop, f"JAWS_RealizedVol_{ts}.xlsx")
            wb   = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True})

            cutoff = None
            if lb_years < 99:
                cutoff = pd.Timestamp(_dt.datetime.now()) - pd.DateOffset(years=lb_years)

            # Build a combined DataFrame: index = date, columns = "name (sym) - window"
            cols = {}
            for sym, (name, close) in series.items():
                rets = close.pct_change().dropna()
                for label, days in active:
                    if len(rets) < days:
                        continue
                    rv = (rets.rolling(days).std() * (252 ** 0.5) * 100).dropna()
                    if cutoff is not None:
                        rv = rv[rv.index >= cutoff]
                    cols[f"{name} ({sym}) {label}"] = rv
            if not cols:
                self.after(0, lambda: self._rvol_status.config(text="No data to export"))
                wb.close(); return
            df = pd.DataFrame(cols).sort_index()

            # ── Realized Vol sheet ──
            ws = wb.add_worksheet("Realized Vol")
            ws.hide_gridlines(2); ws.set_tab_color("#f78166")
            title_f = wb.add_format(dict(bold=True, font_size=14, font_color="#f78166",
                        bg_color="#0d1117", font_name="Consolas"))
            hdr_f = wb.add_format(dict(bold=True, font_color="#f78166", bg_color="#161b22",
                        font_name="Consolas", font_size=10, border=1, border_color="#30363d"))
            date_f = wb.add_format(dict(num_format="yyyy-mm-dd", font_name="Consolas",
                        font_size=10, border=1, border_color="#30363d"))
            num_f = wb.add_format(dict(num_format="0.00", font_name="Consolas",
                        font_size=10, border=1, border_color="#30363d"))

            ws.merge_range(0, 0, 0, len(df.columns),
                           f"Realized Volatility (annualized %)  ·  {lb_label} lookback", title_f)
            ws.write(1, 0, "Date", hdr_f)
            for c, col in enumerate(df.columns):
                ws.write(1, c+1, col, hdr_f)
            ws.set_column(0, 0, 12)
            ws.set_column(1, len(df.columns), 22)
            ws.freeze_panes(2, 1)

            for r, (idx, row) in enumerate(df.iterrows()):
                ws.write_datetime(r+2, 0, idx.to_pydatetime(), date_f)
                for c, val in enumerate(row):
                    if pd.notna(val):
                        ws.write_number(r+2, c+1, float(val), num_f)
                    else:
                        ws.write_blank(r+2, c+1, None, num_f)

            # Native line chart linked to the data
            chart = wb.add_chart({"type": "line"})
            n = len(df)
            for c, col in enumerate(df.columns):
                chart.add_series({
                    "name":       ["Realized Vol", 1, c+1],
                    "categories": ["Realized Vol", 2, 0, n+1, 0],
                    "values":     ["Realized Vol", 2, c+1, n+1, c+1],
                    "line":       {"width": 1.25},
                })
            chart.set_title({"name": f"Realized Volatility — {lb_label}"})
            chart.set_x_axis({"name": "Date", "date_axis": True})
            chart.set_y_axis({"name": "Annualized Vol (%)"})
            chart.set_size({"width": 900, "height": 460})
            ws.insert_chart(1, len(df.columns)+2, chart)

            # ── Summary sheet: latest / min / max / avg per column ──
            ss = wb.add_worksheet("Summary")
            ss.hide_gridlines(2)
            ss.write_row(0, 0, ["Series", "Latest", "Min", "Max", "Average"], hdr_f)
            for r, col in enumerate(df.columns):
                s = df[col].dropna()
                ss.write(r+1, 0, col, date_f)
                if len(s):
                    ss.write_number(r+1, 1, float(s.iloc[-1]), num_f)
                    ss.write_number(r+1, 2, float(s.min()),  num_f)
                    ss.write_number(r+1, 3, float(s.max()),  num_f)
                    ss.write_number(r+1, 4, float(s.mean()), num_f)
            ss.set_column(0, 0, 30); ss.set_column(1, 4, 12)

            wb.close()
            import subprocess
            subprocess.Popen(["explorer", path])
            self.after(0, lambda p=path: self._rvol_status.config(
                text=f"Exported → {os.path.basename(p)}"))
        except Exception as e:
            self.after(0, lambda m=str(e): self._rvol_status.config(text=f"Export error: {m}"))


# ── Market Scanner panel ──────────────────────────────────────
_SCAN_UNIVERSE = {
    # Equities
    "S&P 500":        "^GSPC",
    "Nasdaq 100":     "^NDX",
    "Dow Jones":      "^DJI",
    "Russell 2000":   "^RUT",
    "EAFE (EFA)":     "EFA",
    "EM (EEM)":       "EEM",
    "Japan (EWJ)":    "EWJ",
    "Germany (EWG)":  "EWG",
    "UK (EWU)":       "EWU",
    "China (MCHI)":   "MCHI",
    "Brazil (EWZ)":   "EWZ",
    # Sectors
    "Tech (XLK)":     "XLK",
    "Finance (XLF)":  "XLF",
    "Energy (XLE)":   "XLE",
    "Health (XLV)":   "XLV",
    "Utilities (XLU)":"XLU",
    "Real Estate (XLRE)":"XLRE",
    # Rates & FI
    "US 10Y Yield":   "^TNX",
    "US 2Y Yield":    "^IRX",
    "HY Bond (HYG)":  "HYG",
    "IG Bond (LQD)":  "LQD",
    "TLT (20yr)":     "TLT",
    # Commodities
    "Gold":           "GC=F",
    "Crude Oil":      "CL=F",
    "Natural Gas":    "NG=F",
    "Copper":         "HG=F",
    # FX
    "EUR/USD":        "EURUSD=X",
    "USD/JPY":        "JPY=X",
    "DXY (UUP)":      "UUP",
    # Vol
    "VIX":            "^VIX",
    "MOVE Index":     "^MOVE",
}

# Rolling windows in trading days
_SCAN_WINDOWS = {"5d": 5, "21d": 21, "63d": 63, "252d": 252}

class ScannerPanel(tk.Frame):
    """
    Market Scanner — shows rolling z-scores and standard-deviation move flags
    for a curated universe, with a paired news snippet for flagged moves.
    """

    def __init__(self, parent, news_api_key="", **kw):
        super().__init__(parent, bg=BG, **kw)
        self._api_key  = news_api_key
        self._rows_data = []   # list of dicts, one per instrument
        self._sort_col  = "z_21d"
        self._sort_rev  = True
        self._build()

    # ── UI ────────────────────────────────────────────────────
    def _build(self):
        # Control bar
        bar = tk.Frame(self, bg=SIDEBAR, height=44)
        bar.pack(fill="x"); bar.pack_propagate(False)

        tk.Label(bar, text="  Market Scanner", bg=SIDEBAR, fg=TEXT1,
                 font=("Segoe UI",13,"bold")).pack(side="left")

        self._window_var = tk.StringVar(value="21d")
        for w in ("5d","21d","63d","252d"):
            tk.Radiobutton(bar, text=w, variable=self._window_var, value=w,
                           bg=SIDEBAR, fg=TEXT2, selectcolor=CARD2,
                           activebackground=SIDEBAR, font=F_SANS,
                           command=self._re_sort).pack(side="left", padx=4)

        tk.Label(bar, text="  |  Sort:", bg=SIDEBAR, fg=TEXT3, font=F_SANS).pack(side="left")
        self._sort_var = tk.StringVar(value="z-score")
        for s in ("z-score","move%","name"):
            tk.Radiobutton(bar, text=s, variable=self._sort_var, value=s,
                           bg=SIDEBAR, fg=TEXT2, selectcolor=CARD2,
                           activebackground=SIDEBAR, font=F_SANS,
                           command=self._re_sort).pack(side="left", padx=3)

        self._scan_status = tk.Label(bar, text="Click Scan to load",
                                     bg=SIDEBAR, fg=TEXT3, font=F_SANS)
        self._scan_status.pack(side="left", padx=14)

        tk.Button(bar, text="⟳ Scan", bg=ACCENT, fg=BG, font=F_SANS,
                  relief="flat", padx=12, cursor="hand2",
                  command=self.run_scan).pack(side="right", padx=10, pady=6)
        tk.Button(bar, text="⬇ XLS", bg="#1f6b2e", fg=WHITE, font=F_SANS,
                  relief="flat", padx=8, cursor="hand2",
                  command=self._export).pack(side="right", padx=2, pady=6)

        # Legend
        leg = tk.Frame(self, bg=CARD2, height=22)
        leg.pack(fill="x"); leg.pack_propagate(False)
        for txt, fg in [("■ >2σ move", RED), ("■ 1–2σ move", YELLOW),
                        ("■ <1σ",TEXT3), ("  z-score = (ret − avg) / stdev over window",TEXT3)]:
            tk.Label(leg, text=f"  {txt}", bg=CARD2, fg=fg,
                     font=("Consolas",9)).pack(side="left")

        # Column header
        self._hdr_frame = tk.Frame(self, bg=CARD2, height=26)
        self._hdr_frame.pack(fill="x"); self._hdr_frame.pack_propagate(False)
        self._build_header_row()

        # Scrollable body
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)
        self._cv = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=self._cv.yview,
                            style="Vertical.TScrollbar")
        self._cv.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._cv.pack(side="left", fill="both", expand=True)
        self._body = tk.Frame(self._cv, bg=BG)
        self._win  = self._cv.create_window((0,0), window=self._body, anchor="nw")
        self._body.bind("<Configure>", lambda e:
            self._cv.configure(scrollregion=self._cv.bbox("all")))
        self._cv.bind("<Configure>", lambda e:
            self._cv.itemconfig(self._win, width=e.width))
        self._cv.bind("<MouseWheel>", lambda e:
            self._cv.yview_scroll(-1*(e.delta//120), "units"))

    def _build_header_row(self):
        for w in self._hdr_frame.winfo_children():
            w.destroy()
        cols = [("Instrument",200), ("Ticker",70), ("Last",80),
                ("Move%",70), ("z-5d",62), ("z-21d",62),
                ("z-63d",62), ("z-252d",62), ("σ Flag",62), ("News Headline",0)]
        for name, w in cols:
            kw = dict(bg=CARD2, fg=TEXT2, font=("Consolas",10,"bold"),
                      anchor="w", padx=6)
            if w:
                tk.Label(self._hdr_frame, text=name, width=w//7, **kw).pack(side="left")
            else:
                tk.Label(self._hdr_frame, text=name, **kw).pack(side="left",
                         fill="x", expand=True)

    # ── Scan ─────────────────────────────────────────────────
    def run_scan(self):
        self._scan_status.config(text="Scanning…")
        import threading
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        import yfinance as yf
        import numpy as np
        results = []
        total   = len(_SCAN_UNIVERSE)
        for i, (name, sym) in enumerate(_SCAN_UNIVERSE.items()):
            try:
                hist = yf.Ticker(sym).history(period="2y", interval="1d")
                if hist.empty or len(hist) < 10:
                    continue
                hist.index = hist.index.tz_localize(None) if hist.index.tzinfo else hist.index
                close = hist["Close"].dropna()
                last  = float(close.iloc[-1])
                # daily returns
                rets  = close.pct_change().dropna()
                zs = {}
                for label, days in _SCAN_WINDOWS.items():
                    if len(rets) < days + 1:
                        zs[label] = None
                        continue
                    window  = rets.iloc[-days:]
                    history = rets.iloc[:-days]
                    if len(history) < 5:
                        zs[label] = None
                        continue
                    roll_ret   = float(window.sum())   # cumulative
                    hist_rolls = [float(rets.iloc[j:j+days].sum())
                                  for j in range(0, len(history)-days, max(1,days//5))]
                    if len(hist_rolls) < 3:
                        zs[label] = None
                        continue
                    mu  = float(np.mean(hist_rolls))
                    std = float(np.std(hist_rolls, ddof=1))
                    zs[label] = (roll_ret - mu) / std if std > 1e-9 else None

                move_pct = float(rets.iloc[-1]) * 100 if len(rets) else 0.0
                results.append({
                    "name":    name,
                    "sym":     sym,
                    "last":    last,
                    "move":    move_pct,
                    "z_5d":    zs.get("5d"),
                    "z_21d":   zs.get("21d"),
                    "z_63d":   zs.get("63d"),
                    "z_252d":  zs.get("252d"),
                })
                if (i+1) % 5 == 0:
                    self.after(0, lambda d=i+1, t=total:
                               self._scan_status.config(text=f"Scanning {d}/{t}…"))
            except Exception:
                continue

        self.after(0, lambda r=results: self._finish_scan(r))

    def _finish_scan(self, results):
        self._rows_data = results
        self._re_sort()
        self._scan_status.config(text=f"Done — {len(results)} instruments")
        # Fetch news headlines for flagged items (|z| > 1.5) in background
        flagged = [r for r in results
                   if r.get("z_21d") is not None and abs(r["z_21d"]) >= 1.5]
        if flagged and self._api_key:
            import threading
            threading.Thread(target=self._fetch_headlines,
                             args=(flagged,), daemon=True).start()

    # ── Sorting & rendering ───────────────────────────────────
    def _re_sort(self):
        w  = self._window_var.get()
        sk = self._sort_var.get()
        zk = f"z_{w}"

        def sort_key(r):
            if sk == "z-score":
                v = r.get(zk)
                return (-abs(v) if v is not None else 0)
            elif sk == "move%":
                return -abs(r.get("move", 0))
            else:
                return r.get("name","")

        self._rows_data.sort(key=sort_key)
        self._render(zk)

    def _render(self, zk):
        for w in self._body.winfo_children():
            w.destroy()

        for i, r in enumerate(self._rows_data):
            bg  = ROW_A if i % 2 == 0 else ROW_B
            z   = r.get(zk)
            az  = abs(z) if z is not None else 0

            # Row highlight by sigma band
            if   az >= 2.0: row_accent = RED
            elif az >= 1.0: row_accent = YELLOW
            else:           row_accent = None

            row = tk.Frame(self._body, bg=bg)
            row.pack(fill="x")

            # Sigma flag stripe (4px left border)
            stripe_col = row_accent or bg
            tk.Frame(row, bg=stripe_col, width=4).pack(side="left", fill="y")

            def _lbl(text, width=0, fg=TEXT1, bold=False, anchor="w"):
                f = ("Consolas",10,"bold") if bold else ("Consolas",10)
                kw = dict(bg=bg, fg=fg, font=f, anchor=anchor, padx=5)
                if width:
                    tk.Label(row, text=text, width=width, **kw).pack(side="left")
                else:
                    tk.Label(row, text=text, **kw).pack(side="left",
                             fill="x", expand=True)

            _lbl(r["name"][:28], width=27)
            _lbl(r["sym"], width=9, fg=TEXT3)
            _lbl(_fmt_price(r["last"], r["name"]), width=10, anchor="e")

            mv   = r.get("move", 0)
            mv_c = GREEN if mv >= 0 else RED
            _lbl(f"{'+'if mv>=0 else ''}{mv:.2f}%", width=9, fg=mv_c, anchor="e")

            for wk in ("z_5d","z_21d","z_63d","z_252d"):
                zv = r.get(wk)
                if zv is None:
                    _lbl("—", width=8, fg=TEXT3, anchor="e")
                else:
                    zfg = RED if abs(zv)>=2 else (YELLOW if abs(zv)>=1 else TEXT2)
                    _lbl(f"{'+'if zv>=0 else ''}{zv:.2f}", width=8, fg=zfg, anchor="e", bold=abs(zv)>=1.5)

            # Sigma flag label
            if   az >= 2.0: flag_txt, flag_c = f"{'+'if z>=0 else ''}{az:.1f}σ !!!", RED
            elif az >= 1.5: flag_txt, flag_c = f"{'+'if z>=0 else ''}{az:.1f}σ !",  YELLOW
            elif az >= 1.0: flag_txt, flag_c = f"{'+'if z>=0 else ''}{az:.1f}σ",    TEXT2
            else:           flag_txt, flag_c = "",                                    TEXT3
            _lbl(flag_txt, width=8, fg=flag_c, bold=az>=1.5)

            # News headline (added async — placeholder for now)
            hl = r.get("headline","")
            _lbl(hl[:60] if hl else "", fg=TEXT3)

    # ── News fetch ────────────────────────────────────────────
    def _fetch_headlines(self, flagged):
        try:
            import urllib.request, json, time
            for r in flagged[:12]:   # limit API calls
                query = r["name"].split("(")[0].strip()
                url   = (f"https://newsapi.org/v2/everything"
                         f"?q={urllib.parse.quote(query)}"
                         f"&sortBy=publishedAt&pageSize=1"
                         f"&apiKey={self._api_key}")
                try:
                    req = urllib.request.Request(url, headers={"User-Agent":"JAWS/1.0"})
                    with urllib.request.urlopen(req, timeout=4) as resp:
                        data = json.loads(resp.read())
                    arts = data.get("articles",[])
                    if arts:
                        r["headline"] = arts[0].get("title","")[:80]
                except Exception:
                    pass
                time.sleep(0.15)
            self.after(0, lambda: self._render(f"z_{self._window_var.get()}"))
        except Exception:
            pass

    # ── Export ────────────────────────────────────────────────
    def _export(self):
        if not self._rows_data:
            self._scan_status.config(text="Run a scan first")
            return
        self._scan_status.config(text="Exporting…")
        rows = list(self._rows_data)
        import threading
        threading.Thread(target=self._export_worker, args=(rows,), daemon=True).start()

    def _export_worker(self, rows):
        try:
            import xlsxwriter, os
            import datetime as _dt
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            ts   = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(desktop, f"JAWS_MarketScanner_{ts}.xlsx")
            wb   = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True})
            ws   = wb.add_worksheet("Scanner"); ws.hide_gridlines(2)
            ws.set_tab_color("#f78166")
            title_f = wb.add_format(dict(bold=True, font_size=14, font_color="#f78166",
                        bg_color="#0d1117", font_name="Consolas"))
            hf = wb.add_format(dict(bold=True, font_color="#f78166", bg_color="#161b22",
                        font_name="Consolas", font_size=10, border=1, border_color="#30363d"))
            tf = wb.add_format(dict(font_name="Consolas", font_size=10, border=1, border_color="#30363d"))
            nf = wb.add_format(dict(num_format="0.00", font_name="Consolas", font_size=10,
                        border=1, border_color="#30363d"))
            headers = ["Instrument","Ticker","Last","1D Move %","z-5d","z-21d","z-63d","z-252d","News"]
            ws.merge_range(0,0,0,len(headers)-1,
                           f"Market Scanner  ·  {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}", title_f)
            for c,h in enumerate(headers): ws.write(1,c,h,hf)
            ws.set_column(0,0,24); ws.set_column(1,1,10); ws.set_column(2,7,11); ws.set_column(8,8,50)
            ws.freeze_panes(2,0)
            for i, r in enumerate(rows):
                rr=i+2
                ws.write(rr,0,r.get("name",""),tf); ws.write(rr,1,r.get("sym",""),tf)
                for c,key in enumerate(["last","move","z_5d","z_21d","z_63d","z_252d"]):
                    v=r.get(key)
                    if v is None: ws.write(rr,2+c,"—",tf)
                    else: ws.write_number(rr,2+c,float(v),nf)
                ws.write(rr,8,r.get("headline",""),tf)
            wb.close()
            import subprocess
            subprocess.Popen(["explorer", path])
            self.after(0, lambda p=path: self._scan_status.config(
                text=f"Exported → {os.path.basename(p)}"))
        except Exception as e:
            self.after(0, lambda m=str(e): self._scan_status.config(text=f"Export error: {m}"))


# ── Watchlist panel ───────────────────────────────────────────
class WatchlistPanel(tk.Frame):
    """Custom ticker watchlist with search-add, remove, and live refresh."""

    # Persisted ticker list shared across both pane instances
    _shared_tickers: list = []   # list of (name, ticker) tuples

    def __init__(self, parent, on_select=None, **kw):
        super().__init__(parent, bg=CARD, **kw)
        self._on_select = on_select
        self._fetch_job = None
        self._build()
        self._refresh_table()

    # ── proxy _rows so custom-range code works unchanged ──────
    @property
    def _rows(self):
        return self.ct._rows

    def get_rows(self):
        return self.ct.get_rows()

    # ── UI ────────────────────────────────────────────────────
    def _build(self):
        # Search / add bar
        bar = tk.Frame(self, bg=SIDEBAR, height=48)
        bar.pack(fill="x", side="top"); bar.pack_propagate(False)

        tk.Label(bar, text="  Search:", bg=SIDEBAR, fg=TEXT2,
                 font=F_SANS).pack(side="left")

        self._search_var = tk.StringVar()
        self._search_entry = tk.Entry(bar, textvariable=self._search_var,
                                      bg=CARD, fg=TEXT1,
                                      insertbackground=TEXT1, font=F_TREE,
                                      relief="flat", width=32)
        self._search_entry.pack(side="left", padx=6, pady=10, ipady=4)
        self._search_entry.bind("<KeyRelease>", self._on_key)
        self._search_entry.bind("<Return>",     lambda e: self._do_search())
        self._search_entry.bind("<Escape>",     lambda e: self._hide_drop())

        tk.Button(bar, text="Search", bg=ACCENT, fg=BG, font=F_SANS,
                  relief="flat", padx=12, cursor="hand2",
                  command=self._do_search).pack(side="left", padx=(0,8))

        tk.Button(bar, text="Remove Selected", bg=CARD2, fg=TEXT2,
                  font=F_SANS, relief="flat", padx=8, cursor="hand2",
                  command=self._remove_selected).pack(side="left", padx=4)

        tk.Button(bar, text="↻ Refresh", bg=CARD2, fg=TEXT2,
                  font=F_SANS, relief="flat", padx=8, cursor="hand2",
                  command=self._fetch_all).pack(side="left", padx=4)

        self._status = tk.Label(bar, text="Type a ticker or name, then press Search",
                                bg=SIDEBAR, fg=TEXT3, font=F_SANS)
        self._status.pack(side="left", padx=12)

        # Drop-down overlay — sits above the table via place()
        self._drop_frame = tk.Frame(self, bg="#1c2128", bd=1, relief="solid")
        self._drop_visible = False

        # Main table
        self.ct = ColorTable(self, on_select=self._on_select)
        self.ct.pack(fill="both", expand=True)

        self._debounce_job = None
        self._last_query   = ""

    # ── Search ────────────────────────────────────────────────
    def _on_key(self, event=None):
        """Debounce: fire search 400 ms after user stops typing."""
        if self._debounce_job:
            self.after_cancel(self._debounce_job)
        query = self._search_var.get().strip()
        if not query:
            self._hide_drop()
            return
        self._debounce_job = self.after(400, self._do_search)

    def _do_search(self):
        if self._debounce_job:
            self.after_cancel(self._debounce_job)
            self._debounce_job = None
        raw = self._search_var.get().strip()
        if not raw or raw == self._last_query:
            return
        self._last_query = raw
        self._status.config(text="Searching…")
        import threading
        threading.Thread(target=self._search_worker, args=(raw,), daemon=True).start()

    def _search_worker(self, query):
        try:
            import yfinance as yf
            results = []
            hits = yf.Search(query, max_results=10).quotes
            for h in hits:
                sym  = h.get("symbol", "")
                name = h.get("shortname") or h.get("longname") or sym
                typ  = h.get("typeDisp") or h.get("quoteType", "")
                exch = h.get("exchDisp", "")
                if sym:
                    results.append((sym, name, typ, exch))
            self.after(0, lambda r=results: self._show_results(r, query))
        except Exception as e:
            self.after(0, lambda: self._status.config(text=f"Search error: {e}"))

    def _show_results(self, results, query):
        for w in self._drop_frame.winfo_children():
            w.destroy()

        if not results:
            self._status.config(text=f'No results for "{query}"')
            self._hide_drop()
            return

        self._status.config(text=f"{len(results)} results — click to add")

        row_h = 32
        drop_h = min(len(results) * row_h + 6, 300)

        # Place drop-down below the search bar, full width
        self._drop_frame.place(in_=self, x=0, y=48, relwidth=1, height=drop_h)
        self._drop_frame.lift()
        self._drop_visible = True

        for sym, name, typ, exch in results:
            row = tk.Frame(self._drop_frame, bg="#1c2128", cursor="hand2")
            row.pack(fill="x", padx=2, pady=1)

            tk.Label(row, text=f" {sym}", bg="#1c2128", fg=ACCENT,
                     font=("Consolas",11,"bold"), width=12, anchor="w"
                     ).pack(side="left")
            tk.Label(row, text=name[:45], bg="#1c2128", fg=TEXT1,
                     font=("Consolas",10), anchor="w"
                     ).pack(side="left", expand=True, fill="x")
            tk.Label(row, text=f"{typ}  {exch} ", bg="#1c2128", fg=TEXT3,
                     font=("Consolas",9), anchor="e"
                     ).pack(side="right")

            def _hover_in(e, r=row):  r.config(bg=HOVER); [c.config(bg=HOVER) for c in r.winfo_children()]
            def _hover_out(e, r=row): r.config(bg="#1c2128"); [c.config(bg="#1c2128") for c in r.winfo_children()]
            def _click(e, s=sym, n=name): self._pick_result(s, n)

            row.bind("<Enter>",    _hover_in)
            row.bind("<Leave>",    _hover_out)
            row.bind("<Button-1>", _click)
            for child in row.winfo_children():
                child.bind("<Enter>",    _hover_in)
                child.bind("<Leave>",    _hover_out)
                child.bind("<Button-1>", _click)

    def _hide_drop(self):
        self._drop_frame.place_forget()
        self._drop_visible = False
        self._last_query   = ""

    def _pick_result(self, sym, name):
        self._hide_drop()
        self._add_ticker(sym, name)
        self._search_var.set("")
        self._status.config(text=f"Adding {sym}…")

    def _add_ticker(self, sym, label):
        # Deduplicate across all panel instances
        if any(t == sym for _, t in WatchlistPanel._shared_tickers):
            self._status.config(text=f"{sym} already in list")
            return
        WatchlistPanel._shared_tickers.append((label, sym))
        self._fetch_one(label, sym)

    # ── Remove ────────────────────────────────────────────────
    def _remove_selected(self):
        sel = self.ct._selected_name
        if not sel:
            self._status.config(text="Select a row first")
            return
        WatchlistPanel._shared_tickers = [
            (n, t) for n, t in WatchlistPanel._shared_tickers if n != sel
        ]
        self._refresh_table()
        self._status.config(text=f"Removed {sel}")

    # ── Data fetch ────────────────────────────────────────────
    def _refresh_table(self):
        self.ct.clear()
        if not WatchlistPanel._shared_tickers:
            return
        self._fetch_all()

    def _fetch_all(self):
        self._status.config(text="Loading…")
        import threading
        tickers = list(WatchlistPanel._shared_tickers)
        threading.Thread(target=self._fetch_worker, args=(tickers,), daemon=True).start()

    def _fetch_worker(self, tickers):
        import market_data as md
        ticker_dict = {name: sym for name, sym in tickers}
        try:
            data = md.fetch_returns(ticker_dict)
            self.after(0, lambda d=data, td=ticker_dict: self._populate(d, td))
        except Exception as e:
            self.after(0, lambda: self._status.config(text=f"Fetch error: {e}"))

    def _fetch_one(self, label, sym):
        import threading, market_data as md
        def worker():
            try:
                data = md.fetch_returns({label: sym})
                self.after(0, lambda d=data, td={label: sym}:
                           self._populate(d, td, append=True))
            except Exception as e:
                self.after(0, lambda: self._status.config(text=f"Error: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _populate(self, data, ticker_dict, append=False):
        """Convert fetch_returns dict → ColorTable rows."""
        if not append:
            self.ct.clear()
        for name, info in data.items():
            sym  = ticker_dict.get(name, "")
            rets = info.get("returns", {})
            row  = (name, sym,
                    _fmt_price(info.get("price"), name),
                    _fmt_pct(info.get("change_1d")),
                    _fmt_pct(rets.get("MTD")),
                    _fmt_pct(rets.get("YTD")),
                    _fmt_pct(rets.get("1Y")),
                    _fmt_pct(rets.get("3Y")),
                    _fmt_pct(rets.get("5Y")),
                    _fmt_pct(rets.get("10Y")),
                    _fmt_pct(rets.get("Custom")))
            self.ct.add_row(row)
        self._status.config(text=f"{len(self.ct._rows)} ticker(s)")


# ── Academic Factors panel ────────────────────────────────────
class AcademicFactorsPanel(tk.Frame):
    """
    Long/short academic factor returns (Kenneth French library).
    Daily and Monthly sections, multi-window return monitor, custom range,
    click-to-chart cumulative growth, and Excel export.
    """
    _FCOLS = ("Factor","1D","1W","1M","MTD","QTD","3M","YTD","1Y","3Y","5Y","7Y","10Y","Custom")
    _FW    = (165,  54,54,54,54,54,54,54,58,58,58,58,60,62)
    _PERIODS = [("1Y",1),("3Y",3),("5Y",5),("7Y",7),("10Y",10),("All",99),("Custom",-1)]

    def __init__(self, parent, on_select=None, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._on_select    = on_select   # callback(name, dates, decimal_returns)
        self._data         = {"daily": [], "monthly": []}
        self._selected     = None      # (section, idx)
        self._hist_years   = 5
        self._custom_start = None
        self._custom_end   = None
        self._period_btns  = {}
        self._thread       = None
        self._build()
        self.after(150, self._fetch)

    # ── UI ────────────────────────────────────────────────────
    def _build(self):
        hdr = tk.Frame(self, bg=SIDEBAR, height=40); hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="  Academic Factors  (Kenneth French, L/S)",
                 bg=SIDEBAR, fg=TEXT1, font=("Consolas",12,"bold")).pack(side="left", pady=8)
        self._status = tk.Label(hdr, text="Loading…", bg=SIDEBAR, fg=TEXT3,
                                font=("Consolas",9)); self._status.pack(side="left", padx=8)
        bf = tk.Frame(hdr, bg=SIDEBAR); bf.pack(side="right", padx=6)
        tk.Button(bf, text="↻", bg=CARD2, fg=TEXT2, font=F_SANS, relief="flat",
                  padx=6, cursor="hand2", command=self._fetch).pack(side="left", padx=2)
        tk.Button(bf, text="⬇ XLS", bg="#1f6b2e", fg=WHITE, font=F_SANS, relief="flat",
                  padx=6, cursor="hand2", command=self._export).pack(side="left", padx=2)

        # Custom range row
        cr = tk.Frame(self, bg=SIDEBAR, height=30); cr.pack(fill="x"); cr.pack_propagate(False)
        tk.Label(cr, text="  Custom  From:", bg=SIDEBAR, fg=TEXT3,
                 font=("Segoe UI",10)).pack(side="left")
        self._from_var = tk.StringVar()
        tk.Entry(cr, textvariable=self._from_var, bg=CARD, fg=TEXT1, insertbackground=TEXT1,
                 font=("Consolas",10), width=11, relief="flat").pack(side="left", padx=3, ipady=1)
        tk.Label(cr, text="To:", bg=SIDEBAR, fg=TEXT3, font=("Segoe UI",10)).pack(side="left")
        self._to_var = tk.StringVar()
        tk.Entry(cr, textvariable=self._to_var, bg=CARD, fg=TEXT1, insertbackground=TEXT1,
                 font=("Consolas",10), width=11, relief="flat").pack(side="left", padx=3, ipady=1)
        tk.Label(cr, text="YYYY-MM-DD", bg=SIDEBAR, fg=TEXT3,
                 font=("Consolas",8)).pack(side="left", padx=2)
        tk.Button(cr, text="Apply", bg=ACCENT, fg=BG, font=("Segoe UI",10), relief="flat",
                  padx=8, cursor="hand2", command=self._apply_custom).pack(side="left", padx=4)
        tk.Label(cr, text="(returns are cumulative total %, L/S dollar-neutral)",
                 bg=SIDEBAR, fg=TEXT3, font=("Consolas",8)).pack(side="left", padx=6)

        self._F = ("Consolas", 10)

        # Scrollable table with synced horizontal scroll (header + body)
        paned = tk.PanedWindow(self, orient="vertical", bg=BG, sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True)
        tbl = tk.Frame(paned, bg=CARD); paned.add(tbl, minsize=150)
        cont, head_frame, self._inner = _scroll_table(tbl)
        cont.pack(fill="both", expand=True)
        for col, w in zip(self._FCOLS, self._FW):
            anc = "w" if col == "Factor" else "e"
            tk.Label(head_frame, text=col, bg=CARD2, fg=TEXT2, font=self._F,
                     width=w//7, anchor=anc, padx=3).pack(side="left")

        # Chart
        chost = tk.Frame(paned, bg=BG); paned.add(chost, minsize=170)
        pbar = tk.Frame(chost, bg=SIDEBAR, height=30); pbar.pack(fill="x"); pbar.pack_propagate(False)
        tk.Label(pbar, text="  Chart Period:", bg=SIDEBAR, fg=TEXT3,
                 font=("Segoe UI",10)).pack(side="left", padx=(4,2))
        for lbl, yrs in self._PERIODS:
            b = tk.Button(pbar, text=lbl, bg=ACCENT if yrs==self._hist_years else CARD2,
                          fg=BG if yrs==self._hist_years else TEXT2, font=("Segoe UI",10),
                          relief="flat", padx=9, pady=2, cursor="hand2",
                          command=lambda y=yrs,l=lbl: self._set_period(y,l))
            b.pack(side="left", padx=2, pady=3); self._period_btns[lbl] = b
        self._ctitle = tk.Label(chost, text="  Click a factor to chart cumulative growth",
                                bg=BG, fg=TEXT2, font=("Consolas",10)); self._ctitle.pack(fill="x")
        self._fig = matplotlib.figure.Figure(facecolor=BG, tight_layout=True)
        self._ax = self._fig.add_subplot(111); self._ax.set_facecolor(CARD)
        self._canvas = FigureCanvasTkAgg(self._fig, master=chost)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

    # ── Data ──────────────────────────────────────────────────
    def _fetch(self):
        if self._thread and self._thread.is_alive(): return
        self._status.config(text="Downloading Ken French data…", fg=YELLOW)
        self._thread = threading.Thread(target=self._fetch_worker, daemon=True)
        self._thread.start()

    def _fetch_worker(self):
        try:
            import factors_data as fd
            data = fd.fetch_factors(self._custom_start, self._custom_end)
            self.after(0, lambda d=data: self._populate(d))
        except Exception as e:
            self.after(0, lambda m=str(e): self._status.config(text=f"Error: {m}", fg=RED))

    def _apply_custom(self):
        import datetime as _dt
        def parse(s):
            s = s.strip()
            if not s: return None
            try: return _dt.datetime.strptime(s, "%Y-%m-%d").date()
            except ValueError: return None
        self._custom_start = parse(self._from_var.get())
        self._custom_end   = parse(self._to_var.get())
        if self._custom_start is None:
            self._status.config(text="Enter a valid From date (YYYY-MM-DD)", fg=RED); return
        self._fetch()

    def _populate(self, data):
        self._data = data
        for w in self._inner.winfo_children(): w.destroy()
        for section, label in [("daily","DAILY  (Kenneth French US, daily L/S returns)"),
                               ("monthly","MONTHLY  (US + Developed + Emerging)")]:
            div = tk.Frame(self._inner, bg=CARD2); div.pack(fill="x")
            tk.Label(div, text=f"  {label}", bg=CARD2, fg=ACCENT,
                     font=("Consolas",10,"bold"), anchor="w", pady=2).pack(side="left")
            for idx, r in enumerate(data.get(section, [])):
                if r.get("error"):
                    continue
                self._add_row(section, idx, r)
        self._status.config(
            text=f"Ken French · {len(data.get('daily',[]))} daily, "
                 f"{len(data.get('monthly',[]))} monthly · {datetime.now().strftime('%H:%M')}",
            fg=GREEN)

    def _add_row(self, section, idx, r):
        n = len([c for c in self._inner.winfo_children()])
        bg = ROW_A if n % 2 == 0 else ROW_B
        row = tk.Frame(self._inner, bg=bg, cursor="hand2"); row.pack(fill="x")
        w = r["windows"]
        def cell(text, wpx, fg=TEXT1, anchor="e"):
            tk.Label(row, text=text, bg=bg, fg=fg, font=self._F, width=wpx//7,
                     anchor=anchor, padx=3, pady=4).pack(side="left")
        def fnum(v):
            if v is None: return ("—", TEXT3)
            return (f"{v:+.2f}", GREEN if v >= 0 else RED)
        cell(r["name"][:22], self._FW[0], fg=TEXT1, anchor="w")
        for ci, key in enumerate(["1D","1W","1M","MTD","QTD","3M","YTD","1Y","3Y","5Y","7Y","10Y","Custom"]):
            txt, fg = fnum(w.get(key))
            cell(txt, self._FW[ci+1], fg=fg)
        def bind(fr=row, s=section, i=idx, b=bg):
            fr.bind("<Button-1>", lambda e: self._select(s, i))
            for c in fr.winfo_children(): c.bind("<Button-1>", lambda e: self._select(s, i))
            fr.bind("<Enter>", lambda e: [fr.config(bg=HOVER)]+[c.config(bg=HOVER) for c in fr.winfo_children()])
            fr.bind("<Leave>", lambda e: [fr.config(bg=b)]+[c.config(bg=b) for c in fr.winfo_children()])
        bind()

    # ── Chart ─────────────────────────────────────────────────
    def _select(self, section, idx):
        self._selected = (section, idx)
        self._draw_chart()
        # Also drive the bottom ChartPanel (bars/price/line/returns)
        if self._on_select:
            rows = self._data.get(section, [])
            if idx < len(rows):
                r = rows[idx]
                if not r.get("error"):
                    self._on_select(r["name"], r["raw_dates"], r["raw_rets"])

    def _set_period(self, years, label=""):
        self._hist_years = years
        for lbl, btn in self._period_btns.items():
            on = (lbl == label)
            btn.config(bg=ACCENT if on else CARD2, fg=BG if on else TEXT2)
        self._draw_chart()

    def _draw_chart(self):
        if not self._selected: return
        import factors_data as fd
        import datetime as _dt
        section, idx = self._selected
        rows = self._data.get(section, [])
        if idx >= len(rows): return
        r = rows[idx]
        start = None
        if self._hist_years == -1:          # Custom
            start = self._custom_start
        elif self._hist_years < 99:
            start = _dt.date.today() - relativedelta(years=self._hist_years)
        ds, vs = fd.cumulative_series(r["raw_dates"], r["raw_rets"], start)
        self._ax.clear(); self._ax.set_facecolor(CARD)
        if ds:
            col = GREEN if (vs and vs[-1] >= 0) else RED
            self._ax.plot(ds, vs, color=col, lw=1.6)
            self._ax.axhline(0, color=TEXT3, lw=0.7, ls="--")
            self._ax.fill_between(ds, vs, 0, where=[v>=0 for v in vs], alpha=0.15, color=GREEN)
            self._ax.fill_between(ds, vs, 0, where=[v<0 for v in vs], alpha=0.15, color=RED)
        self._ax.tick_params(colors=TEXT2, labelsize=9)
        for sp in self._ax.spines.values(): sp.set_color(BORDER)
        self._ax.set_ylabel("Cumulative L/S Return (%)", color=TEXT2, fontsize=9)
        import matplotlib.dates as md
        self._ax.xaxis.set_major_formatter(md.DateFormatter("%b '%y"))
        self._ax.xaxis.set_major_locator(md.AutoDateLocator())
        self._fig.autofmt_xdate(rotation=30, ha="right")
        pstr = "Full history" if self._hist_years==99 else (
               "Custom" if self._hist_years==-1 else f"{self._hist_years}Y")
        self._canvas.draw()
        self._ctitle.config(text=f"  {r['name']}  ·  {pstr}  ·  cumulative growth", fg=TEXT1)

    # ── Export ────────────────────────────────────────────────
    def _export(self):
        if not (self._data.get("daily") or self._data.get("monthly")):
            self._status.config(text="Nothing to export yet"); return
        self._status.config(text="Exporting…", fg=YELLOW)
        data = self._data
        threading.Thread(target=self._export_worker, args=(data,), daemon=True).start()

    def _export_worker(self, data):
        try:
            import xlsxwriter, os
            import datetime as _dt
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(desktop, f"JAWS_AcademicFactors_{ts}.xlsx")
            wb = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True})
            title_f = wb.add_format(dict(bold=True, font_size=14, font_color="#f78166",
                        bg_color="#0d1117", font_name="Consolas"))
            hf = wb.add_format(dict(bold=True, font_color="#f78166", bg_color="#161b22",
                        font_name="Consolas", font_size=10, border=1, border_color="#30363d"))
            tf = wb.add_format(dict(font_name="Consolas", font_size=10, border=1, border_color="#30363d"))
            nf = wb.add_format(dict(num_format="+0.00;-0.00", font_name="Consolas",
                        font_size=10, border=1, border_color="#30363d"))
            cols = list(self._FCOLS)

            ws = wb.add_worksheet("Monitor"); ws.hide_gridlines(2); ws.set_tab_color("#f78166")
            ws.merge_range(0,0,0,len(cols)-1,
                           f"Academic Factors (L/S, cumulative %)  ·  Ken French  ·  "
                           f"{_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}", title_f)
            keys = ["1D","1W","1M","MTD","QTD","3M","YTD","1Y","3Y","5Y","7Y","10Y","Custom"]
            r = 1
            for section in ("daily","monthly"):
                ws.merge_range(r,0,r,len(cols)-1, section.upper(), hf); r += 1
                for c,h in enumerate(cols): ws.write(r,c,h,hf)
                r += 1
                for row in data.get(section, []):
                    if row.get("error"): continue
                    ws.write(r,0,row["name"],tf)
                    for c,k in enumerate(keys):
                        v = row["windows"].get(k)
                        if v is None: ws.write(r,c+1,"—",tf)
                        else: ws.write_number(r,c+1,float(v),nf)
                    r += 1
                r += 1
            ws.set_column(0,0,22); ws.set_column(1,len(cols)-1,9)

            # History sheet: cumulative growth-of-0 series per factor (full history)
            import factors_data as fd
            hs = wb.add_worksheet("History"); hs.hide_gridlines(2)
            col = 0
            for section in ("daily","monthly"):
                for row in data.get(section, []):
                    if row.get("error"): continue
                    ds, vs = fd.cumulative_series(row["raw_dates"], row["raw_rets"])
                    hs.write(0,col,f"{row['name']} ({section})",hf)
                    hs.write(1,col,"Date",hf); hs.write(1,col+1,"Cum %",hf)
                    for i,(d,v) in enumerate(zip(ds,vs)):
                        hs.write(i+2,col,str(d),tf); hs.write_number(i+2,col+1,float(v),nf)
                    hs.set_column(col,col,12); hs.set_column(col+1,col+1,10)
                    col += 3
            wb.close()
            import subprocess
            subprocess.Popen(["explorer", path])
            self.after(0, lambda p=path: self._status.config(
                text=f"Exported → {os.path.basename(p)}", fg=GREEN))
        except Exception as e:
            self.after(0, lambda m=str(e): self._status.config(text=f"Export error: {m}", fg=RED))


# ── Main dashboard ────────────────────────────────────────────
class Dashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("JW Market and News Monitor")
        self.root.configure(bg=BG)
        self.root.geometry("1800x1080")
        self.root.minsize(1300, 800)

        self.running       = False
        self.market_loaded = False
        self.market_cache  = {}
        self.ticker_map    = {}
        self.active_nav    = tk.StringVar(value="dashboard")
        self.status_var    = tk.StringVar(value="Ready")
        self.clock_var     = tk.StringVar()
        self.mkt_status    = tk.StringVar(value="Loading market data…")

        self._style()
        self._layout()
        self._tick()
        self.root.after(800, self._load_market_data)
        self.root.after(400, self._equalize_layout)

    # ── Style ─────────────────────────────────────────────────
    def _style(self):
        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background=CARD, fieldbackground=CARD,
                    rowheight=34, font=F_TREE, borderwidth=0)
        s.configure("Treeview.Heading", background=CARD2, foreground=TEXT2,
                    font=F_HEAD, relief="flat", borderwidth=0)
        s.map("Treeview", background=[("selected", HOVER)])
        for nm in ("Tab","Bottom"):
            s.configure(f"{nm}.TNotebook", background=BG, borderwidth=0, tabmargins=0)
            s.configure(f"{nm}.TNotebook.Tab", background=CARD2, foreground=TEXT2,
                        font=F_SANS, padding=[16,8], borderwidth=0)
            s.map(f"{nm}.TNotebook.Tab",
                  background=[("selected",CARD)], foreground=[("selected",TEXT1)])
        s.configure("Vertical.TScrollbar",
                    background=CARD2, troughcolor=BG, arrowcolor=TEXT3, borderwidth=0)
        s.configure("Horizontal.TScrollbar",
                    background=CARD2, troughcolor=BG, arrowcolor=TEXT3, borderwidth=0)

    # ── Layout ────────────────────────────────────────────────
    def _layout(self):
        self.sidebar = tk.Frame(self.root, bg=SIDEBAR, width=240)
        self.sidebar.pack(side="left", fill="y"); self.sidebar.pack_propagate(False)
        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_header()
        self._build_ticker_strip()

        self.vpane = tk.PanedWindow(self.main, orient="vertical", bg=BG,
                                    sashwidth=7, sashrelief="groove", sashpad=2)
        self.vpane.pack(fill="both", expand=True)

        top = tk.Frame(self.vpane, bg=BG)
        self.vpane.add(top, minsize=300)
        self._build_market_table(top)

        bot = tk.Frame(self.vpane, bg=BG)
        self.vpane.add(bot, minsize=280)
        self._build_bottom(bot)

        self._build_statusbar()

        # Equal vertical split (50/50) after window renders
        self.root.after(400, self._equalize_layout)

        # Re-equalize when window is resized (debounced 120 ms)
        self._resize_job = None
        self.root.bind("<Configure>", self._on_root_resize)

    # ── Sidebar ───────────────────────────────────────────────
    def _build_sidebar(self):
        logo = tk.Frame(self.sidebar, bg=ACCENT, height=70)
        logo.pack(fill="x"); logo.pack_propagate(False)
        tk.Label(logo, text="JAWS", bg=ACCENT, fg=BG,
                 font=("Consolas", 24, "bold")).pack(side="left", padx=16)
        tk.Label(logo, text="v1.0", bg=ACCENT, fg=BG,
                 font=("Consolas", 11)).pack(side="right", padx=12, anchor="s", pady=20)
        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill="x")

        tk.Label(self.sidebar, text="  NAVIGATION", bg=SIDEBAR, fg=TEXT3,
                 font=("Consolas",11), anchor="w").pack(fill="x", pady=(16,4))
        self.nav_buttons = {}
        for key,label,cmd in [
            ("dashboard","  Dashboard",   self._show_dashboard),
            ("hedge",    "  Hedge Funds", lambda: self._run_category("hedge_fund")),
            ("ipo",      "  IPO",         lambda: self._run_category("ipo")),
            ("ma",       "  M&A",         lambda: self._run_category("ma")),
            ("issuance", "  Issuance",    lambda: self._run_category("issuance")),
        ]:
            btn = tk.Button(self.sidebar, text=label, anchor="w",
                            bg=SIDEBAR, fg=TEXT2, activebackground=CARD,
                            activeforeground=TEXT1, font=("Segoe UI",12),
                            relief="flat", bd=0, padx=12, pady=11,
                            cursor="hand2", command=cmd)
            btn.pack(fill="x", padx=8, pady=1)
            self.nav_buttons[key] = btn
            btn.bind("<Enter>", lambda e,b=btn: b.config(bg=CARD) if b.cget("bg")!=CARD2 else None)
            btn.bind("<Leave>", lambda e,b=btn,k=key:
                     b.config(bg=CARD2 if self.active_nav.get()==k else SIDEBAR))
        self._set_nav("dashboard")

        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill="x", pady=12)
        tk.Label(self.sidebar, text="  EXPORT", bg=SIDEBAR, fg=TEXT3,
                 font=("Consolas",11), anchor="w").pack(fill="x", pady=(0,4))
        tk.Button(self.sidebar, text="  ⬇  Export to Excel", anchor="w",
                  bg="#1f6b2e", fg=WHITE, activebackground="#2ea043",
                  activeforeground=WHITE, font=("Segoe UI",12), relief="flat",
                  bd=0, padx=12, pady=11, cursor="hand2",
                  command=self._export_excel).pack(fill="x", padx=8, pady=2)

        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill="x", pady=12)
        tk.Label(self.sidebar, text="  REPORTS", bg=SIDEBAR, fg=TEXT3,
                 font=("Consolas",11), anchor="w").pack(fill="x", pady=(0,4))
        tk.Button(self.sidebar, text="  ▶  Run All Reports", anchor="w",
                  bg=ACCENT, fg=BG, activebackground="#e06050", activeforeground=BG,
                  font=("Segoe UI",13,"bold"), relief="flat", bd=0, padx=12, pady=13,
                  cursor="hand2", command=self._run_all).pack(fill="x", padx=8, pady=2)
        tk.Button(self.sidebar, text="  ⏏  Open Reports Folder", anchor="w",
                  bg=CARD2, fg=TEXT2, activebackground=CARD, activeforeground=TEXT1,
                  font=("Segoe UI",12), relief="flat", bd=0, padx=12, pady=11,
                  cursor="hand2", command=self._open_reports).pack(fill="x", padx=8, pady=2)

        tk.Label(self.sidebar, text="  LAST RUN", bg=SIDEBAR, fg=TEXT3,
                 font=("Consolas",11), anchor="w").pack(fill="x", pady=(16,4))
        self.report_cards = {}
        for key,label,color in [("hedge_fund","Hedge Funds",CYAN),("ipo","IPO",GREEN),
                                 ("ma","M&A",YELLOW),("issuance","Issuance",PURPLE)]:
            f = tk.Frame(self.sidebar, bg=CARD, pady=6)
            f.pack(fill="x", padx=8, pady=3)
            tk.Label(f, text=f"  {label}", bg=CARD, fg=color,
                     font=("Consolas",11,"bold"), anchor="w").pack(fill="x")
            sv = tk.StringVar(value="—")
            tk.Label(f, textvariable=sv, bg=CARD, fg=TEXT2,
                     font=("Consolas",10), anchor="w").pack(fill="x", padx=8)
            self.report_cards[key] = sv

    def _set_nav(self, key):
        self.active_nav.set(key)
        for k,b in self.nav_buttons.items():
            b.config(bg=CARD2 if k==key else SIDEBAR,
                     fg=TEXT1 if k==key else TEXT2)

    # ── Header ────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self.main, bg=SIDEBAR, height=70)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Frame(hdr, bg=BORDER, width=1).pack(side="left", fill="y")
        tk.Label(hdr, text="Market Intelligence Dashboard",
                 bg=SIDEBAR, fg=TEXT1, font=F_SANS_H, padx=18).pack(side="left", pady=16)
        tk.Label(hdr, textvariable=self.mkt_status,
                 bg=SIDEBAR, fg=TEXT3, font=F_SANS).pack(side="left")

        # Zoom controls (right side, before clock)
        tk.Button(hdr, text="  ⟳  Refresh Data", bg=CARD2, fg=BLUE,
                  activebackground=CARD, activeforeground=TEXT1,
                  font=("Segoe UI",12,"bold"), relief="flat", bd=0,
                  padx=14, pady=8, cursor="hand2",
                  command=self._refresh_market).pack(side="right", padx=16, pady=14)
        tk.Label(hdr, textvariable=self.clock_var,
                 bg=SIDEBAR, fg=TEXT2, font=F_MONO_L, padx=16).pack(side="right")

        # Zoom widget
        zoom_f = tk.Frame(hdr, bg=SIDEBAR)
        zoom_f.pack(side="right", padx=8)
        tk.Label(zoom_f, text="Zoom:", bg=SIDEBAR, fg=TEXT3,
                 font=("Segoe UI",10)).pack(side="left")
        self._zoom_var = tk.StringVar(value="100%")
        tk.Button(zoom_f, text="−", bg=CARD2, fg=TEXT1, font=("Segoe UI",11,"bold"),
                  relief="flat", width=2, cursor="hand2",
                  command=lambda: self._zoom_step(-1)).pack(side="left", padx=(4,0))
        for label, scale in [("80%",0.80),("100%",1.00),("125%",1.25),("150%",1.50),
                             ("175%",1.75),("200%",2.00)]:
            tk.Radiobutton(zoom_f, text=label, variable=self._zoom_var, value=label,
                           bg=SIDEBAR, fg=TEXT2, selectcolor=CARD2,
                           activebackground=SIDEBAR, font=("Segoe UI",10),
                           command=lambda s=scale: self._apply_zoom(s)
                           ).pack(side="left", padx=1)
        tk.Button(zoom_f, text="+", bg=CARD2, fg=TEXT1, font=("Segoe UI",11,"bold"),
                  relief="flat", width=2, cursor="hand2",
                  command=lambda: self._zoom_step(+1)).pack(side="left", padx=(0,4))

        tk.Frame(hdr, bg=BORDER, height=1).pack(fill="x", side="bottom")

    def _zoom_step(self, direction):
        """Step zoom up/down with the +/− buttons (continuous, beyond presets)."""
        cur = getattr(self, "_zoom_scale", 1.0)
        new = max(0.7, min(3.0, round(cur + 0.15 * direction, 2)))
        self._zoom_var.set(f"{int(new*100)}%")
        self._apply_zoom(new)

    def _apply_zoom(self, scale):
        """Zoom by walking every widget and rescaling its font."""
        import tkinter.font as tkfont
        self._zoom_scale = scale
        # Base sizes for each font family/style used in the app
        _BASE = {
            ("Consolas", "normal"):        11,
            ("Consolas", "bold"):          11,
            ("Segoe UI", "normal"):        12,
            ("Segoe UI", "bold"):          12,
        }
        def _rescale(widget):
            try:
                spec = widget.cget("font")
                if not spec:
                    return
                f = tkfont.Font(font=spec)
                fam  = f.actual("family")
                wt   = f.actual("weight")
                key  = (fam, wt)
                base = _BASE.get(key, abs(f.actual("size")))
                new_sz = max(7, round(base * scale))
                # Rebuild font tuple preserving slant/weight
                slant  = f.actual("slant")
                styles = []
                if wt == "bold":   styles.append("bold")
                if slant == "italic": styles.append("italic")
                new_font = (fam, new_sz) + (tuple(styles) if styles else ())
                widget.config(font=new_font)
            except Exception:
                pass
            for child in widget.winfo_children():
                _rescale(child)
        _rescale(self.root)
        self.root.update_idletasks()

    # ── Ticker strip ──────────────────────────────────────────
    def _build_ticker_strip(self):
        strip = tk.Frame(self.main, bg=CARD2, height=44)
        strip.pack(fill="x"); strip.pack_propagate(False)
        self.ticker_frame = tk.Frame(strip, bg=CARD2)
        self.ticker_frame.pack(side="left", fill="both", expand=True, padx=12)
        self.ticker_labels = {}
        for name in ["S&P 500","NASDAQ","DOW","FTSE 100","DAX",
                     "Nikkei 225","EUR/USD","GBP/USD","USD/JPY","US 10Y","VIX"]:
            f = tk.Frame(self.ticker_frame, bg=CARD2)
            f.pack(side="left", padx=12, pady=8)
            tk.Label(f, text=name, bg=CARD2, fg=TEXT3,
                     font=("Consolas",11)).pack(side="left")
            val = tk.StringVar(value="  ···"); chg = tk.StringVar(value="")
            tk.Label(f, textvariable=val, bg=CARD2, fg=TEXT2,
                     font=("Consolas",11,"bold")).pack(side="left", padx=(4,0))
            cl = tk.Label(f, textvariable=chg, bg=CARD2, font=("Consolas",11), fg=TEXT2)
            cl.pack(side="left", padx=(3,0))
            self.ticker_labels[name] = (val, chg, cl)
        tk.Frame(self.main, bg=BORDER, height=1).pack(fill="x")

    # ── Market tables ─────────────────────────────────────────
    _TAB_DEFS = [
        ("indices",      "Equity Indices"),
        ("rates",        "Rates"),
        ("volatility",   "Volatility"),
        ("fx",           "FX"),
        ("fixed_income", "Fixed Income"),
        ("munis",        "Municipals"),
        ("factors",      "Factor ETFs"),
        ("ls_factors",   "L/S Factors"),
        ("funding",      "Funding Markets"),
        ("commodities",  "Commodities"),
        ("sectors",      "US Sectors"),
        ("fi_spreads",   "FI Spreads"),
        ("watchlist",    "My Watchlist"),
    ]

    def _build_market_table(self, parent):
        hpane = tk.PanedWindow(parent, orient="horizontal", bg=BG,
                               sashwidth=7, sashrelief="groove", sashpad=2)
        hpane.pack(fill="both", expand=True, padx=6, pady=6)
        self.hpane_top = hpane

        callbacks = [
            lambda name, ticker: (self.chart_left.select(name, ticker),
                                  self.rvol_left.add_from_table(name, ticker)),
            lambda name, ticker: (self.chart_right.select(name, ticker),
                                  self.rvol_right.add_from_table(name, ticker)),
        ]
        labels = ["Left Panel", "Right Panel"]

        self.table_sets = []
        self._table_notebooks = []
        for pane_idx, (cb, pane_lbl) in enumerate(zip(callbacks, labels)):
            # Wrapper frame holds header bar + notebook
            wrapper = tk.Frame(hpane, bg=BG)
            hpane.add(wrapper, minsize=420)

            # Header bar with export button
            hbar = tk.Frame(wrapper, bg=CARD2, height=30)
            hbar.pack(fill="x"); hbar.pack_propagate(False)
            tk.Label(hbar, text=f"  {pane_lbl}", bg=CARD2, fg=TEXT3,
                     font=("Consolas", 10)).pack(side="left")
            xls_btn = tk.Button(hbar, text="⬇ Export Tab to Excel",
                                bg="#1f6b2e", fg=WHITE,
                                font=("Segoe UI", 9, "bold"), relief="flat",
                                bd=0, padx=8, cursor="hand2")
            xls_btn.pack(side="right", padx=6, pady=3)

            # Custom date range bar
            cbar = tk.Frame(wrapper, bg=SIDEBAR, height=32)
            cbar.pack(fill="x"); cbar.pack_propagate(False)
            tk.Label(cbar, text="  Custom From:", bg=SIDEBAR, fg=TEXT2,
                     font=("Segoe UI", 10)).pack(side="left", padx=(4, 2))
            from_var = tk.StringVar()
            from_entry = tk.Entry(cbar, textvariable=from_var, bg=CARD, fg=TEXT1,
                                  insertbackground=TEXT1, font=("Consolas", 10),
                                  width=12, relief="flat", bd=2)
            from_entry.pack(side="left", padx=2, pady=4)
            tk.Label(cbar, text="To:", bg=SIDEBAR, fg=TEXT2,
                     font=("Segoe UI", 10)).pack(side="left", padx=(6, 2))
            to_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
            to_entry = tk.Entry(cbar, textvariable=to_var, bg=CARD, fg=TEXT1,
                                insertbackground=TEXT1, font=("Consolas", 10),
                                width=12, relief="flat", bd=2)
            to_entry.pack(side="left", padx=2, pady=4)
            tk.Label(cbar, text="YYYY-MM-DD", bg=SIDEBAR, fg=TEXT3,
                     font=("Consolas", 8)).pack(side="left", padx=4)

            # "Go" button — captured per pane
            go_btn = tk.Button(cbar, text="Go", bg=CARD, fg=ACCENT,
                               font=("Segoe UI", 10, "bold"), relief="flat",
                               bd=0, padx=10, cursor="hand2")
            go_btn.pack(side="left", padx=4)
            tk.Button(cbar, text="Clear", bg=CARD2, fg=TEXT3,
                      font=("Segoe UI", 9), relief="flat", bd=0,
                      padx=6, cursor="hand2",
                      command=lambda fv=from_var, tv=to_var,
                                     pt=None, lbl=pane_lbl:
                      self._clear_custom_range(fv, tv)).pack(side="left", padx=2)

            nb = ttk.Notebook(wrapper, style="Tab.TNotebook")
            nb.pack(fill="both", expand=True)

            from fi_spreads import (fetch_spread_analytics,
                                    fetch_rates_analytics, fetch_funding_analytics)
            pane_tables = {}
            for key, title in self._TAB_DEFS:
                frame = tk.Frame(nb, bg=CARD)
                nb.add(frame, text=f"  {title}  ")
                if key == "fi_spreads":
                    SpreadPanel(frame).pack(fill="both", expand=True)
                    pane_tables[key] = None
                elif key == "rates":
                    SpreadPanel(frame, fetch_fn=fetch_rates_analytics,
                                title="US Treasury Rates  (FRED, levels in %)"
                                ).pack(fill="both", expand=True)
                    pane_tables[key] = None
                elif key == "funding":
                    SpreadPanel(frame, fetch_fn=fetch_funding_analytics,
                                title="Funding Markets  (FRED, levels in %)"
                                ).pack(fill="both", expand=True)
                    pane_tables[key] = None
                elif key == "ls_factors":
                    AcademicFactorsPanel(
                        frame,
                        on_select=lambda nm, ds, rs, pi=pane_idx:
                            (self.chart_left if pi == 0
                             else self.chart_right).select_factor(nm, ds, rs)
                    ).pack(fill="both", expand=True)
                    pane_tables[key] = None
                elif key == "watchlist":
                    wp = WatchlistPanel(frame, on_select=cb)
                    wp.pack(fill="both", expand=True)
                    pane_tables[key] = wp   # WatchlistPanel exposes get_rows() and .ct
                else:
                    ct = ColorTable(frame, on_select=cb)
                    ct.pack(fill="both", expand=True)
                    pane_tables[key] = ct
            self.table_sets.append(pane_tables)
            self._table_notebooks.append((nb, pane_tables))

            xls_btn.config(command=lambda pt=pane_tables, n=nb, pl=pane_lbl:
                           self._export_table_tab(pt, n, pl))
            go_btn.config(command=lambda fv=from_var, tv=to_var,
                                         pt=pane_tables, pl=pane_lbl:
                          self._apply_custom_range(fv, tv, pt, pl))

        # Default left table → Equity Indices (tab 0), right table → Factors (tab 6)
        if len(self._table_notebooks) >= 2:
            left_nb_ref  = self._table_notebooks[0][0]
            right_nb_ref = self._table_notebooks[1][0]
            factors_idx  = next((i for i, (k, _) in enumerate(self._TAB_DEFS)
                                 if k == "factors"), 6)
            parent.after(50, lambda: left_nb_ref.select(0))
            parent.after(50, lambda: right_nb_ref.select(factors_idx))

    # ── Bottom section — horizontal split ─────────────────────
    def _build_bottom(self, parent):
        hpane = tk.PanedWindow(parent, orient="horizontal", bg=BG,
                               sashwidth=7, sashrelief="groove", sashpad=2)
        hpane.pack(fill="both", expand=True)
        self.hpane_bot = hpane

        # ── Left pane: Yield Curve (default) + Chart ──────────
        left_nb = ttk.Notebook(hpane, style="Bottom.TNotebook")
        hpane.add(left_nb, minsize=400)

        yc_a = tk.Frame(left_nb, bg=BG)
        left_nb.add(yc_a, text="  Yield Curve  ")
        self.yc_left = YieldCurvePanel(yc_a)
        self.yc_left.pack(fill="both", expand=True)

        chart_a = tk.Frame(left_nb, bg=BG)
        left_nb.add(chart_a, text="  Chart  ")
        self.chart_left = ChartPanel(chart_a,
                                     ticker_map_fn=lambda: self.ticker_map,
                                     log_fn=self._log)
        self.chart_left.pack(fill="both", expand=True)

        scan_f = tk.Frame(left_nb, bg=BG)
        left_nb.add(scan_f, text="  Market Scanner  ")
        api_key = os.environ.get("NEWS_API_KEY", "")
        self.scanner = ScannerPanel(scan_f, news_api_key=api_key)
        self.scanner.pack(fill="both", expand=True)

        rvol_a = tk.Frame(left_nb, bg=BG)
        left_nb.add(rvol_a, text="  Realized Vol  ")
        self.rvol_left = RealizedVolPanel(rvol_a,
                                          ticker_map_fn=lambda: self.ticker_map)
        self.rvol_left.pack(fill="both", expand=True)

        # Default bottom-left to Yield Curve tab
        left_nb.select(0)

        # ── Right pane: Top Stories (default) + Chart + Log ───
        right_nb = ttk.Notebook(hpane, style="Bottom.TNotebook")
        hpane.add(right_nb, minsize=400)

        news_f = tk.Frame(right_nb, bg=BG)
        right_nb.add(news_f, text="  Top Stories  ")
        self.news_panel = NewsPanel(news_f)
        self.news_panel.pack(fill="both", expand=True)

        chart_b = tk.Frame(right_nb, bg=BG)
        right_nb.add(chart_b, text="  Chart 2  ")
        self.chart_right = ChartPanel(chart_b,
                                      ticker_map_fn=lambda: self.ticker_map,
                                      log_fn=self._log)
        self.chart_right.pack(fill="both", expand=True)

        yc_b = tk.Frame(right_nb, bg=BG)
        right_nb.add(yc_b, text="  Yield Curve  ")
        YieldCurvePanel(yc_b).pack(fill="both", expand=True)

        rvol_b = tk.Frame(right_nb, bg=BG)
        right_nb.add(rvol_b, text="  Realized Vol  ")
        self.rvol_right = RealizedVolPanel(rvol_b,
                                           ticker_map_fn=lambda: self.ticker_map)
        self.rvol_right.pack(fill="both", expand=True)

        log_f = tk.Frame(right_nb, bg=BG)
        right_nb.add(log_f, text="  Activity Log  ")
        self._build_log_tab(log_f)

        # Default bottom-right to Top Stories tab
        right_nb.select(0)

    # ── Activity log ──────────────────────────────────────────
    def _build_log_tab(self, parent):
        hdr = tk.Frame(parent, bg=CARD2, height=36)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="  Activity Log", bg=CARD2, fg=TEXT2,
                 font=("Segoe UI",13,"bold"), anchor="w").pack(side="left", fill="y", padx=8)
        tk.Button(hdr, text="Clear", bg=CARD2, fg=TEXT3, font=("Segoe UI",11),
                  relief="flat", bd=0, cursor="hand2",
                  command=self._clear_log).pack(side="right", padx=12)
        self.log = scrolledtext.ScrolledText(parent, bg=BG, fg=TEXT1, font=F_MONO,
                                             relief="flat", bd=0, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)
        for tag,color in [("accent",ACCENT),("green",GREEN),("red",RED),
                          ("blue",BLUE),("yellow",YELLOW),("gray",TEXT3),("dim",TEXT2)]:
            self.log.tag_config(tag, foreground=color)

    def _build_statusbar(self):
        bar = tk.Frame(self.main, bg=CARD2, height=28)
        bar.pack(fill="x", side="bottom"); bar.pack_propagate(False)
        tk.Label(bar, textvariable=self.status_var, bg=CARD2, fg=TEXT3,
                 font=F_MONO_S, anchor="w", padx=12).pack(side="left")
        tk.Label(bar, text="Yahoo Finance / US Treasury  ·  Reuters · FT · WSJ · Bloomberg · NewsAPI · SEC EDGAR",
                 bg=CARD2, fg=TEXT3, font=F_MONO_S, padx=12).pack(side="right")

    # ── Clock ─────────────────────────────────────────────────
    def _tick(self):
        self.clock_var.set(datetime.now().strftime("%Y-%m-%d   %H:%M:%S"))
        self.root.after(1000, self._tick)

    # ── Market data ───────────────────────────────────────────
    def _load_market_data(self):
        self.mkt_status.set("Fetching live market data…")
        self.status_var.set("Loading…")
        def worker():
            try:
                from market_data import (fetch_all, INDICES, RATES, VOLATILITY,
                                         FX, FIXED_INCOME, MUNIS, FACTORS,
                                         FUNDING, COMMODITIES, SECTORS)
                result = fetch_all()
                (indices, rates, volatility, fx, fi, munis, factors, funding,
                 commodities, sectors) = result
                all_t = {**INDICES,**RATES,**VOLATILITY,**FX,**FIXED_INCOME,
                         **MUNIS,**FACTORS,**FUNDING,**COMMODITIES,**SECTORS}
                for name,info in {**indices,**rates,**volatility,**fx,**fi,
                                   **munis,**factors,**funding,**commodities,
                                   **sectors}.items():
                    self.market_cache[name] = info
                self.ticker_map = all_t
                self.root.after(0, lambda: self._populate_tables(
                    indices, rates, volatility, fx, fi, munis, factors, funding,
                    commodities, sectors))
                self.root.after(0, lambda: self._populate_ticker(indices, rates, fx))
                self.root.after(0, lambda: self.mkt_status.set(
                    f"Updated  ·  {datetime.now().strftime('%H:%M:%S')}"))
                self.root.after(0, lambda: self.status_var.set("Ready"))
                self.market_loaded = True
                # Auto-activate default panels on first load
                if not getattr(self, "_defaults_activated", False):
                    self._defaults_activated = True
                    self.root.after(200, self._activate_defaults)
            except Exception as e:
                msg = str(e)
                self.root.after(0, lambda m=msg: self.mkt_status.set(f"Error: {m}"))
        threading.Thread(target=worker, daemon=True).start()

    def _on_root_resize(self, event):
        """Debounce window resize — re-equalize 120 ms after user stops dragging."""
        if event.widget is not self.root:
            return
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(120, self._equalize_layout)

    def _equalize_layout(self, attempt=0):
        """Set all four quadrants to equal size. Retries until dimensions are real."""
        self.root.update_idletasks()
        total_h = self.vpane.winfo_height()
        total_w_top = getattr(self, "hpane_top", None) and self.hpane_top.winfo_width()
        total_w_bot = getattr(self, "hpane_bot", None) and self.hpane_bot.winfo_width()

        if total_h < 50 or not total_w_top or total_w_top < 50:
            if attempt < 10:
                self.root.after(150, lambda: self._equalize_layout(attempt + 1))
            return

        # Vertical: top / bottom at 50 %
        self.vpane.sash_place(0, 0, total_h // 2)

        # Horizontal top: left / right at 50 %
        self.hpane_top.sash_place(0, total_w_top // 2, 0)

        # Horizontal bottom: left / right at 50 %
        if total_w_bot and total_w_bot > 50:
            self.hpane_bot.sash_place(0, total_w_bot // 2, 0)

    def _activate_defaults(self):
        """Auto-load yield curve (Today) and news on first launch."""
        try:
            self.yc_left._add_nom("Today", 0)
        except Exception:
            pass
        try:
            self.news_panel.load()
        except Exception:
            pass

    def _refresh_market(self):
        self.market_loaded = False
        self._load_market_data()

    def _clear_custom_range(self, from_var, to_var):
        from_var.set("")
        to_var.set(datetime.now().strftime("%Y-%m-%d"))
        # Re-populate tables without custom column (shows "—")
        if getattr(self, "market_loaded", False):
            for pane_tables in self.table_sets:
                for key, ct in pane_tables.items():
                    if ct is None: continue
                    for row_frame, lbls, bg, name in ct._rows:
                        # Reset Custom% column (last column) to "—"
                        if lbls:
                            lbls[-1].config(text="—", fg=TEXT2)

    def _apply_custom_range(self, from_var, to_var, pane_tables, pane_label):
        from_str = from_var.get().strip()
        to_str   = to_var.get().strip() or datetime.now().strftime("%Y-%m-%d")
        try:
            from_dt = datetime.strptime(from_str, "%Y-%m-%d").date()
        except ValueError:
            self.status_var.set("Invalid From date — use YYYY-MM-DD")
            return
        try:
            to_dt = datetime.strptime(to_str, "%Y-%m-%d").date()
        except ValueError:
            to_dt = datetime.now().date()

        # Capture name→ticker and name→label-list on the main thread
        ticker_map = dict(getattr(self, "ticker_map", {}))
        pane_snapshot = {}   # name → list of tk.Label widgets (last = Custom%)
        for key, ct in pane_tables.items():
            if ct is None: continue
            for _, lbls, _, name in ct._rows:
                if name not in pane_snapshot:
                    pane_snapshot[name] = lbls

        if not ticker_map:
            self.status_var.set("Ticker map not loaded yet.")
            return

        days  = (to_dt - from_dt).days
        years = days / 365.25
        self.status_var.set(
            f"Computing custom returns {from_str} → {to_str} "
            f"({'ann.' if years > 1 else 'total'}) for {pane_label}…")

        def worker():
            import yfinance as yf
            import datetime as dt_mod

            from_s = from_dt.strftime("%Y-%m-%d")
            to_s   = (to_dt + dt_mod.timedelta(days=2)).strftime("%Y-%m-%d")
            from_dtt = dt_mod.datetime.combine(from_dt, dt_mod.time())
            to_dtt   = dt_mod.datetime.combine(to_dt,   dt_mod.time())

            updates = {}   # name → (display_str, fg_color)
            names   = list(pane_snapshot.keys())
            total   = len(names)

            for i, name in enumerate(names):
                ticker = ticker_map.get(name)
                if not ticker:
                    updates[name] = ("—", TEXT2)
                    continue
                try:
                    h = yf.Ticker(ticker).history(start=from_s, end=to_s)
                    if h.empty:
                        updates[name] = ("—", TEXT2); continue
                    h.index = h.index.tz_localize(None) if h.index.tzinfo else h.index
                    c = h["Close"]
                    c_from = c[c.index >= from_dtt]
                    c_to   = c[c.index <= to_dtt]
                    if c_from.empty or c_to.empty:
                        updates[name] = ("—", TEXT2); continue
                    sp = float(c_from.iloc[0])
                    ep = float(c_to.iloc[-1])
                    if sp == 0:
                        updates[name] = ("—", TEXT2); continue
                    if years > 1:
                        val = ((ep / sp) ** (1 / years) - 1) * 100
                    else:
                        val = (ep - sp) / sp * 100
                    txt = f"{'+'if val>=0 else ''}{val:.2f}%"
                    fg  = GREEN if val >= 0 else RED
                    updates[name] = (txt, fg)
                except Exception:
                    updates[name] = ("—", TEXT2)

                if (i + 1) % 10 == 0:
                    self.root.after(0, lambda done=i+1, tot=total:
                        self.status_var.set(
                            f"Custom range: {done}/{tot} fetched…"))

            def apply():
                for name, lbls in pane_snapshot.items():
                    if not lbls: continue
                    txt, fg = updates.get(name, ("—", TEXT2))
                    lbls[-1].config(text=txt, fg=fg)
                lbl = "p.a." if years > 1 else "total"
                self.status_var.set(
                    f"Custom {from_str} → {to_str} ({lbl}) applied to {pane_label}")

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _export_excel(self):
        if not getattr(self, "market_loaded", False):
            self.status_var.set("No data loaded yet — please wait for market data to finish.")
            return
        self.status_var.set("Exporting to Excel…")

        def worker():
            try:
                from market_data import (INDICES, RATES, VOLATILITY, FX,
                                         FIXED_INCOME, MUNIS, FACTORS,
                                         FUNDING, COMMODITIES)
                from excel_export import export

                cache = self.market_cache
                td = {
                    "Equity Indices":  INDICES,
                    "Rates":           RATES,
                    "Volatility":      VOLATILITY,
                    "FX":              FX,
                    "Fixed Income":    FIXED_INCOME,
                    "Municipals":      MUNIS,
                    "Factors":         FACTORS,
                    "Funding Markets": FUNDING,
                    "Commodities":     COMMODITIES,
                }

                market_data = {}
                for label, ticker_dict in td.items():
                    rows = []
                    for name, ticker in ticker_dict.items():
                        info = cache.get(name, {})
                        rets = info.get("returns", {})
                        rows.append((
                            name, ticker,
                            self._fmt_price(info.get("price"), name),
                            self._fmt_pct(info.get("change_1d")),
                            self._fmt_pct(rets.get("MTD")),
                            self._fmt_pct(rets.get("YTD")),
                            self._fmt_pct(rets.get("1Y")),
                            self._fmt_pct(rets.get("3Y")),
                            self._fmt_pct(rets.get("5Y")),
                            self._fmt_pct(rets.get("10Y")),
                        ))
                    market_data[label] = rows

                # Grab the current left chart figure for embedding
                fig = getattr(self.chart_left, "fig", None)
                path = export(market_data, chart_figure=fig)

                import subprocess
                subprocess.Popen(["explorer", path])
                self.root.after(0, lambda p=path:
                    self.status_var.set(f"Exported → {os.path.basename(p)}"))
            except Exception as e:
                msg = str(e)
                self.root.after(0, lambda m=msg:
                    self.status_var.set(f"Export error: {m}"))

        threading.Thread(target=worker, daemon=True).start()

    def _export_table_tab(self, pane_tables, notebook, pane_label):
        if not getattr(self, "market_loaded", False):
            self.status_var.set("No data loaded yet — wait for market data to finish.")
            return
        try:
            active_tab = notebook.tab(notebook.select(), "text").strip()
        except Exception:
            self.status_var.set("No tab selected.")
            return
        key = next((k for k, t in self._TAB_DEFS if t == active_tab), None)
        if key is None or pane_tables.get(key) is None:
            self.status_var.set(f"'{active_tab}' has no exportable table data.")
            return
        ct   = pane_tables[key]
        rows = ct.get_rows()
        if not rows:
            self.status_var.set("Table is empty — load data first.")
            return
        self.status_var.set(f"Exporting {active_tab}…")
        headers = list(COLS)
        pct_idx = {i for i, c in enumerate(COLS) if c in PCT_COLS}

        def worker():
            try:
                import xlsxwriter, os
                import datetime as dt_mod
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                ts   = dt_mod.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe = active_tab.replace("/","-").replace(" ","_")[:28]
                path = os.path.join(desktop, f"JAWS_{safe}_{ts}.xlsx")
                wb   = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True})
                ws   = wb.add_worksheet(active_tab[:31])
                ws.hide_gridlines(2); ws.set_tab_color("#f78166")

                def F(bg, fg, bold=False, align="left", nf=None):
                    p = dict(bg_color=bg, font_color=fg, bold=bold,
                             align=align, valign="vcenter", font_name="Consolas",
                             font_size=11, border=1, border_color="#30363d")
                    if nf: p["num_format"] = nf
                    return wb.add_format(p)

                title_f = wb.add_format(dict(bold=True, font_size=15,
                    font_color="#f78166", bg_color="#0d1117",
                    font_name="Consolas", valign="vcenter"))
                sub_f = wb.add_format(dict(font_size=10, font_color="#8b949e",
                    bg_color="#0d1117", font_name="Consolas"))

                col_widths = [28, 10, 14] + [11] * (len(headers) - 3)
                ws.set_row(0, 32)
                ws.merge_range(0, 0, 0, len(headers)-1,
                               f"{active_tab}  ·  {pane_label}", title_f)
                ws.write(1, 0,
                         f"Exported {dt_mod.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                         sub_f)
                for c, (h, w) in enumerate(zip(headers, col_widths)):
                    ws.write(2, c, h, F("#161b22","#f78166",bold=True))
                    ws.set_column(c, c, w)
                ws.set_row(2, 22)
                ws.freeze_panes(3, 0)

                for r_idx, row in enumerate(rows):
                    r  = r_idx + 3
                    bg = "#1c2128" if r_idx%2==0 else "#21262d"
                    for c, val in enumerate(row):
                        val = val if val else "—"
                        if c in pct_idx and val != "—":
                            try:
                                num = float(str(val).replace("%","").replace("+",""))
                                fg  = "#3fb950" if num >= 0 else "#f85149"
                                ws.write(r, c, num/100,
                                         F(bg, fg, align="right", nf="+0.00%;-0.00%;0.00%"))
                            except ValueError:
                                ws.write(r, c, val, F(bg,"#e6edf3"))
                        elif c in pct_idx:
                            ws.write(r, c, "—", F(bg,"#8b949e",align="right"))
                        elif c == 2:
                            ws.write(r, c, val, F(bg,"#e6edf3",align="right"))
                        else:
                            ws.write(r, c, val, F(bg,"#e6edf3"))
                    ws.set_row(r, 18)
                wb.close()
                import subprocess
                subprocess.Popen(["explorer", path])
                self.root.after(0, lambda p=path:
                    self.status_var.set(
                        f"Exported {active_tab} ({len(rows)} rows) → {os.path.basename(p)}"))
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                self.root.after(0, lambda m=str(e):
                    self.status_var.set(f"Export error: {m}"))

        threading.Thread(target=worker, daemon=True).start()

    def _fmt_price(self, v, name=""): return _fmt_price(v, name)
    def _fmt_pct(self, v):           return _fmt_pct(v)

    def _populate_tables(self, indices, rates, volatility, fx, fi, munis,
                         factors, funding, commodities, sectors):
        from market_data import (INDICES, RATES, VOLATILITY, FX, FIXED_INCOME,
                                 MUNIS, FACTORS, FUNDING, COMMODITIES, SECTORS)
        td = {"indices":INDICES,"rates":RATES,"volatility":VOLATILITY,"fx":FX,
              "fixed_income":FIXED_INCOME,"munis":MUNIS,
              "factors":FACTORS,"funding":FUNDING,"commodities":COMMODITIES,
              "sectors":SECTORS}
        dd = {"indices":indices,"rates":rates,"volatility":volatility,"fx":fx,
              "fixed_income":fi,"munis":munis,
              "factors":factors,"funding":funding,"commodities":commodities,
              "sectors":sectors}

        for key, data in dd.items():
            # Rates + Funding tabs show absolute level differences, not % returns
            fmt = _fmt_abs if key in ("rates", "funding") else _fmt_pct
            for pane_tables in self.table_sets:
                ct = pane_tables.get(key)
                if ct is None: continue
                ct.clear()
                for name, info in data.items():
                    rets = info.get("returns", {})
                    sym  = td[key].get(name, "—")
                    row  = (name, sym,
                            self._fmt_price(info.get("price"), name),
                            fmt(info.get("change_1d")),
                            fmt(rets.get("MTD")),
                            fmt(rets.get("YTD")),
                            fmt(rets.get("1Y")),
                            fmt(rets.get("3Y")),
                            fmt(rets.get("5Y")),
                            fmt(rets.get("10Y")),
                            fmt(rets.get("Custom")))
                    ct.add_row(row)

    def _populate_ticker(self, indices, rates, fx):
        all_d = {**indices,**rates,**fx}
        for name,(val_var,chg_var,chg_lbl) in self.ticker_labels.items():
            info  = all_d.get(name,{})
            price = info.get("price"); chg = info.get("change_1d")
            if price is not None: val_var.set(f"  {self._fmt_price(price,name)}")
            if chg is not None:
                sign = "+" if chg>=0 else ""
                chg_var.set(f"({sign}{chg:.2f}%)")
                chg_lbl.config(fg=GREEN if chg>=0 else RED)

    # ── Log helpers ───────────────────────────────────────────
    def _log(self, text, tag="dim"):
        try:
            self.log.config(state="normal")
            self.log.insert("end", text+"\n", tag)
            self.log.see("end"); self.log.config(state="disabled")
        except: pass

    def _clear_log(self):
        self.log.config(state="normal"); self.log.delete("1.0","end")
        self.log.config(state="disabled")

    # ── Nav / reports ─────────────────────────────────────────
    def _show_dashboard(self):
        self._set_nav("dashboard")
        if not self.market_loaded: self._load_market_data()

    def _open_reports(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True); os.startfile(OUTPUT_DIR)

    def _run_all(self): self._run_category(None)

    def _run_category(self, category):
        if self.running:
            self._log("Already running — please wait.", "yellow"); return
        self.running = True; self.status_var.set("Running reports…")
        def worker():
            try:
                from categorized_news import fetch_all_news_categorized
                from sec_fetcher import fetch_sec_filings
                from summarizer import extractive_summary, CATEGORY_SUMMARIES
                from pdf_generator import generate_report
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                cats = [category] if category else ["hedge_fund","ipo","ma","issuance"]
                self._log(f"\n{'─'*50}","gray")
                self._log(f"  RUN STARTED  {datetime.now().strftime('%H:%M:%S')}","accent")
                self._log(f"{'─'*50}","gray")
                self._log("\n[1/3]  Fetching news…","blue")
                all_news = fetch_all_news_categorized()
                for cat in cats:
                    cfg = CATEGORY_SUMMARIES[cat]
                    self._log(f"       {cfg['title']:<24} {len(all_news.get(cat,[]))} articles","dim")
                self._log("\n[2/3]  Fetching SEC filings…","blue")
                sec_data = {}
                for cat in cats:
                    sec_data[cat] = fetch_sec_filings(cat)
                    self._log(f"       {CATEGORY_SUMMARIES[cat]['title']:<24} {len(sec_data[cat])} filings","dim")
                self._log("\n[3/3]  Generating PDFs…","blue")
                for cat in cats:
                    ni = all_news.get(cat,[]); si = sec_data.get(cat,[])
                    cfg = CATEGORY_SUMMARIES[cat]
                    pts = extractive_summary(ni+si, cfg["keywords"], max_points=4)
                    if ni+si:
                        path = generate_report(cat,ni,si,pts,OUTPUT_DIR)
                        self._log(f"       Saved: {os.path.basename(path)}","green")
                        self.report_cards[cat].set(f"{len(ni)} news · {len(si)} filings")
                    else:
                        self._log(f"       {cfg['title']}: no items","gray")
                self._log(f"\n  COMPLETE  {datetime.now().strftime('%H:%M:%S')}","green")
                self._log(f"{'─'*50}\n","gray")
                self.root.after(0, lambda: self.status_var.set(
                    f"Last run: {datetime.now().strftime('%H:%M:%S')}  ·  Ready"))
            except Exception as e:
                self._log(f"\n  ERROR: {e}","red")
                import traceback; self._log(traceback.format_exc(),"red")
                self.root.after(0, lambda: self.status_var.set("Error — see log"))
            finally:
                self.running = False
        threading.Thread(target=worker, daemon=True).start()


def main():
    root = tk.Tk()
    try: root.iconbitmap(default="")
    except: pass
    Dashboard(root)
    root.mainloop()

if __name__ == "__main__":
    main()
