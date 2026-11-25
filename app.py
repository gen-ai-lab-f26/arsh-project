"""PitchCheck's web page.

Run it:  uvicorn app:app --reload   (then open http://127.0.0.1:8000)

It reads an uploaded deck, asks a model to list the financial figures the deck
claims, and compares each one with the issuer's SEC filings in code. The deck
is read in memory and a temporary file, which is deleted before the page comes
back. Nothing is stored.
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

from pitchcheck.compare import check_claims
from pitchcheck.deck import read_deck
from pitchcheck.extract import extract_claims
from pitchcheck.sec import filing_figures, load_env, load_issuer

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
tr.differs td{background:#fdecee} tr.matches td:first-child{color:#17692d}
.q{color:#555;font-size:13px}
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
        + "<div class='box'>Upload a bond pitch for a US company. PitchCheck lists the "
        "revenue, income, cash flow, cash and debt figures it states and compares each with "
        "the company's SEC filings. It takes up to a minute. Your deck's text is sent to an "
        "outside AI model (through OpenRouter) to list its numbers. PitchCheck does not "
        "store your deck. It does not check prices, spreads, ratings, ratios or segments, "
        "and it is not built for banks.</div>"
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


STATUS_TEXT = {
    "differs": "Differs",
    "not found": "Not in filings",
    "matches": "Matches",
    "not a filing figure": "Not checked",
}
PERIOD_TEXT = {"FY": "Year to", "Q": "Quarter to", "YTD": "Year to date,", "LTM": "12 months to", "POINT": "At"}
METRIC_TEXT = {
    "revenue": "Revenue", "operating_income": "Operating income", "net_income": "Net income",
    "interest_expense": "Interest expense", "d_and_a": "Depreciation and amortization",
    "cash_from_operations": "Cash from operations", "buybacks": "Share repurchases",
    "cash": "Cash and equivalents", "debt": "Long-term debt", "non_gaap": "Non-GAAP measure",
}


def results_table(rows: list[dict]) -> str:
    out = []
    for row in rows:
        filing = "" if row["filing_value"] is None else f"{row['filing_value']:,.2f}"
        diff = "" if row["difference"] is None else f"{row['difference']:+.1%}"
        links = " ".join(
            f"<a href='{escape(s.url)}' target='_blank' rel='noopener'>{escape(s.form)} "
            f"filed {escape(s.filed)}</a>"
            for s in {s.accession: s for s in row["sources"]}.values()
        )
        note = f"<div class='note'>{escape(row['note'])}</div>" if row["note"] else ""
        css = row["status"].split()[0]
        out.append(
            f"<tr class='{css}'><td>{STATUS_TEXT[row['status']]}</td>"
            f"<td>{METRIC_TEXT.get(row['metric'], row['metric'])}<div class='note'>"
            f"{PERIOD_TEXT[row['period_type']]} {escape(row['period_end'])}</div></td>"
            f"<td class='n'>{escape(str(row['as_written']))}</td><td class='n'>{filing}</td>"
            f"<td class='n'>{diff}</td>"
            f"<td><div class='q'>Slide {escape(str(row['slide']))}: “{escape(row['quote'][:160])}”</div>"
            f"{links}{note}</td></tr>"
        )
    return (
        "<table><tr><th>Status</th><th>Figure</th><th>Pitch says</th><th>Filing says</th>"
        "<th>Gap</th><th>Where, and the filing</th></tr>" + "".join(out) + "</table>"
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


@app.get("/healthz/sec")
def healthz_sec() -> dict:
    """Can this server reach SEC? Looks up one fixed issuer. Shows no secrets."""
    try:
        result = filing_figures(ticker="CVS")
    except Exception as error:  # report any failure; this route exists to diagnose
        return {"sec": "failed", "reason": f"{type(error).__name__}: {error}"[:300]}
    found = sum(1 for fig in result["figures"] if fig.found)
    return {
        "sec": "ok",
        "issuer": result["name"],
        "figures_found": found,
        "model_key_set": bool(os.environ.get("OPENROUTER_API_KEY")),
    }


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
        cik, facts = load_issuer(ticker=ticker)
    except LookupError as error:
        return page(form(str(error)))
    try:
        found = extract_claims(text)
    except Exception:
        return page(form("The AI model did not return a usable answer. Try again in a minute."))
    rows = check_claims(found["claims"], cik, facts, as_of)

    counts = {status: sum(1 for r in rows if r["status"] == status) for status in STATUS_TEXT}
    sections = text.count("--- Slide") + text.count("--- Page")
    pictures = text.count("[Picture: not read]")
    read_line = f"Read {sections} slides or pages."
    if pictures:
        read_line += f" {pictures} pictures were not read (logos count), so numbers inside images are not checked."
    summary = (
        f"Found {len(rows)} figures: {counts['differs']} differ from the filings, "
        f"{counts['matches']} match, {counts['not found']} could not be found in the filings, "
        f"and {counts['not a filing figure']} are non-GAAP measures that filings do not report."
    )
    dropped = ""
    if found["dropped"]:
        items = "".join(
            f"<li>{escape(str(d['claim'].get('as_written', '')))}: {escape(d['reason'])}</li>"
            for d in found["dropped"]
            if isinstance(d["claim"], dict)
        )
        dropped = (
            f"<details><summary>{len(found['dropped'])} figures were read but left out</summary>"
            f"<ul>{items}</ul></details>"
        )
    return page(
        f"<h2>{escape(facts.get('entityName', ticker))}</h2>"
        f"<div class='box'>{escape(summary)}</div>"
        f"<p>Compared with SEC filings made on or before {escape(as_of)}. A figure matches when "
        "it is within 1% of the filing or within the rounding of the number as written. "
        "Look at each row marked \"differs\" and decide whether the pitch needs to change.</p>"
        + results_table(rows)
        + dropped
        + f"<p class='note'>{escape(read_line)}</p>"
        + "<p><a href='/'>Check another deck</a></p>"
    )
