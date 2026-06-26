# Web Sample — test before the full build

Two small, representative versions of the dashboard (dark Bloomberg theme, a live
market table, an interactive Plotly chart, and a password gate). Use these to
confirm the platform **loads and isn't blocked on your work computer** before we
build the full web app.

---

## STEP 1 — 30-second reachability check (no deploy needed)

From the **computer you'll actually use** (e.g. your work machine), open these
known public URLs. If they load, that hosting domain is not blocked:

- **Streamlit Cloud** domain → open any app at `https://*.streamlit.app`
  (e.g. https://streamlit.io  then click into a live demo app)
- **Render** domain → https://render.com  and any `https://*.onrender.com` app
- **Railway** domain → https://railway.app  and any `https://*.up.railway.app` app

If `*.streamlit.app` loads but `*.onrender.com` is blocked (or vice-versa),
that tells us which host to use. Since you already use Streamlit at work, the
`*.streamlit.app` domain is very likely allowed.

---

## STEP 2 — try the samples locally (optional)

```
pip install -r web_sample/requirements.txt

# Streamlit:
streamlit run web_sample/streamlit_app.py        # http://localhost:8501

# Dash:
python web_sample/dash_app.py                    # http://localhost:8050
```
Password (both): **jaws2026**  (Dash user: `jaws`)

---

## STEP 3 — deploy a sample to test the real URL on your work computer

### Option A — Streamlit Community Cloud  (easiest, you use it at work)
1. Put this project in a **GitHub repo** (I can prep this).
2. Go to https://share.streamlit.io → "New app" → pick the repo.
3. Main file path: `web_sample/streamlit_app.py`
4. Advanced → Secrets:  `app_password = "your-password"`
5. Deploy → you get `https://<name>.streamlit.app` → open it on your work PC.

### Option B — Render  (for the Dash version)
1. Project in a GitHub repo.
2. https://render.com → New → Web Service → connect the repo.
3. Build command: `pip install -r web_sample/requirements.txt`
4. Start command: `gunicorn dash_app:server --chdir web_sample --bind 0.0.0.0:$PORT`
5. Environment: `APP_USER`, `APP_PASS` (your login).
6. Deploy → `https://<name>.onrender.com` → open it on your work PC.

---

## What this proves
- The hosting domain is reachable from your work network.
- The dark theme renders correctly in your browser.
- The password gate works.
- Live data (Yahoo Finance) loads from the cloud host.

Once you confirm which host/framework loads cleanly, I'll build the **full** app
(all tabs, panels, charts, scanner, news, factors, exports) in that framework,
reusing your existing `market_data.py`, `fi_spreads.py`, `factors_data.py`.
