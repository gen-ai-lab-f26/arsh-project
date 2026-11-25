"""PitchCheck's web page.

Run it:  uvicorn app:app --reload   (then open http://127.0.0.1:8000)

So far it reads an uploaded deck and shows the issuer's figures from SEC
filings. It does not compare the two yet. The deck is read in memory and a
temporary file, which is deleted before the page comes back. Nothing is stored.
"""

from __future__ import annotations

import hmac
import os
import tempfile
from datetime import date
from html import escape
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse

from pitchcheck.deck import read_deck
from pitchcheck.sec import filing_figures, load_env

load_env()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
app = FastAPI(title="PitchCheck", docs_url=None, redoc_url=None)

STYLE = """
body{font:16px/1.5 system-ui,sans-serif;max-width:920px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
h1{margin-bottom:.2rem} .sub{color:#555;margin-top:0}
label{display:block;margin:.9rem 0 .2rem;font-weight:600}
input{font:inherit;padding:.4rem;width:100%;max-width:26rem;box-sizing:border-box}
button{font:inherit;margin-top:1.2rem;padding:.5rem 1.2rem;cursor:pointer}
table{border-collapse:collapse;width:100%;margin-top:1rem;font-size:14px}
th,td{border-bottom:1px solid #ddd;padding:.35rem .5rem;text-align:left;vertical-align:top}
td.n{text-align:right;font-variant-numeric:tabular-nums} .note{color:#666;font-size:13px}
.box{background:#f5f5f5;border-left:4px solid #888;padding:.6rem .9rem;margin:1rem 0}
.err{border-color:#b00020;background:#fdecee}
"""


def page(body: str) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>PitchCheck</title><style>{STYLE}</style></head><body>"
        "<h1>PitchCheck</h1>"
        "<p class='sub'>Check the numbers in a bond pitch against the issuer's SEC filings.</p>"
        f"{body}</body></html>"
    )


def form(error: str = "") -> str:
    need_code = bool(os.environ.get("ACCESS_CODE"))
    return (
        (f"<div class='box err'>{escape(error)}</div>" if error else "")
        + "<div class='box'>Early version: it reads your deck and shows the issuer's filing "
        "figures. It does not compare them yet. Your deck is not stored.</div>"
        "<form method='post' action='/check' enctype='multipart/form-data'>"
        "<label for='deck'>Pitch deck (.pptx or .pdf)</label>"
        "<input id='deck' name='deck' type='file' accept='.pptx,.pdf,.txt' required>"
        "<label for='ticker'>Issuer's stock ticker</label>"
        "<input id='ticker' name='ticker' placeholder='For example CVS' required>"
        "<label for='as_of'>Date the pitch was written</label>"
        f"<input id='as_of' name='as_of' type='date' value='{date.today().isoformat()}' required>"
        + (
            "<label for='code'>Access code</label><input id='code' name='code' type='password' required>"
            if need_code
            else ""
        )
        + "<br><button type='submit'>Check</button></form>"
    )


def figures_table(result: dict) -> str:
    rows = []
    for fig in result["figures"]:
        if fig.found:
            value = f"{fig.value / 1e6:,.0f}"
            links = " ".join(
                f"<a href='{escape(s.url)}' target='_blank' rel='noopener'>{escape(s.form)} "
                f"filed {escape(s.filed)}</a>"
                for s in {s.accession: s for s in fig.sources}.values()
            )
        else:
            value, links = "not found", ""
        note = f"<div class='note'>{escape(fig.note)}</div>" if fig.note else ""
        rows.append(
            f"<tr><td>{escape(fig.label)}</td><td>{escape(fig.period)}</td>"
            f"<td>{escape(fig.end or '')}</td><td class='n'>{value}</td><td>{links}{note}</td></tr>"
        )
    return (
        "<table><tr><th>Figure</th><th>Period</th><th>Ends</th><th>$ millions</th>"
        "<th>Filing</th></tr>" + "".join(rows) + "</table>"
    )


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return page(form())


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/check", response_class=HTMLResponse)
async def check(
    deck: UploadFile = File(...),
    ticker: str = Form(...),
    as_of: str = Form(...),
    code: str = Form(""),
) -> HTMLResponse:
    expected = os.environ.get("ACCESS_CODE", "")
    if expected and not hmac.compare_digest(code.strip(), expected):
        return page(form("That access code is not right."))

    try:
        date.fromisoformat(as_of)
    except ValueError:
        return page(form("Enter the pitch date as a date."))

    data = await deck.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return page(form("That file is over 20 MB. Export a smaller copy and try again."))

    suffix = Path(deck.filename or "").suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
    try:
        text = read_deck(tmp.name)
    except ValueError as error:
        return page(form(str(error)))
    except Exception:
        return page(form("That file could not be read. Is it a real .pptx or .pdf?"))
    finally:
        os.unlink(tmp.name)

    try:
        result = filing_figures(ticker=ticker, as_of=as_of)
    except LookupError as error:
        return page(form(str(error)))

    sections = text.count("--- Slide") + text.count("--- Page")
    pictures = text.count("[Picture: not read]")
    read_line = f"Read {sections} slides or pages and {len(text):,} characters from your deck."
    if pictures:
        read_line += f" {pictures} pictures were not read (logos count), so any numbers inside images are not checked."
    return page(
        f"<div class='box'>{escape(read_line)}</div>"
        f"<h2>{escape(result['name'])}</h2>"
        f"<p>Figures from SEC filings made on or before {escape(as_of)}.</p>"
        + figures_table(result)
        + "<p><a href='/'>Check another deck</a></p>"
    )
