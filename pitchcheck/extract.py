"""Ask a model to list the financial figures a pitch claims.

The model only reads the pitch and reports what it says. It never supplies a
figure of its own, and code throws out any claim whose quote is not in the deck.
"""

from __future__ import annotations

import json
import re

from pitchcheck.llm import chat

METRICS = {
    "revenue": "total company revenue or net sales. Not a segment, product line or region.",
    "operating_income": "GAAP operating income for the whole company. Not adjusted.",
    "net_income": "GAAP net income for the whole company. Not adjusted, not a segment.",
    "interest_expense": "interest expense of the whole consolidated company. Leave out parent-only or holding-company figures.",
    "d_and_a": "depreciation and amortization for the whole company.",
    "cash_from_operations": "GAAP cash flow from operating activities.",
    "buybacks": "cash paid to repurchase the company's own shares.",
    "cash": "cash and cash equivalents only. Not cash plus investments.",
    "debt": "total long-term debt including the current portion, excluding leases.",
    "non_gaap": "EBITDA, free cash flow, billings, or any adjusted measure.",
}

PROMPT = """You are reading a bond pitch about one company. List the financial \
figures it states for that company, as JSON. Do not judge whether they are right \
and do not add any number that is not written in the pitch.

List a figure only if it is one of these metrics:
{metrics}

Leave out everything else: prices, yields, spreads, ratings, ratios, margins, \
growth rates, segment or product figures, guidance, forecasts, peers, and the \
fund's own position. If you cannot tell for sure which metric a number is, or \
which period it covers, leave it out.

For each figure give:
- "metric": one of the names above
- "period_type": "FY" (a full fiscal year), "Q" (one quarter), "YTD" (year to \
date, such as nine months), "LTM" (trailing twelve months) or "POINT" (a \
balance on one date, for cash and debt)
- "period_end": the last day of the period as YYYY-MM-DD
- "value": the number as written, for example 108.4
- "scale": "bn", "m", "k" or "one"
- "as_written": the figure as it appears, for example "$108.4bn"
- "quote": a short stretch of the pitch, copied exactly, that contains the number
- "slide": the slide or page number it is on

Answer with JSON only, in this shape: {{"claims": [ ... ]}}

<pitch>
{deck}
</pitch>"""

# With thinking off the model is three times faster but mislabels look-alike
# figures (cash plus investments as cash, bank dividends as operating cash
# flow), which become false flags. Tested November 25; see TEST_LOG.md.
EFFORT = "low"
PERIOD_TYPES = {"FY", "Q", "YTD", "LTM", "POINT"}
SCALES = {"bn": 1e9, "m": 1e6, "k": 1e3, "one": 1.0}


def _squash(text: str) -> str:
    """Lower-case and strip everything but letters and digits, to compare quotes."""
    return re.sub(r"[^a-z0-9.]", "", text.lower())


def extract_claims(deck_text: str, model: str | None = None) -> dict:
    """Returns the claims that passed the checks, the ones dropped, and usage."""
    prompt = PROMPT.format(
        metrics="\n".join(f"- {name}: {meaning}" for name, meaning in METRICS.items()),
        deck=deck_text,
    )
    kwargs = {"model": model} if model else {}
    result = chat(prompt, json_mode=True, effort=EFFORT, **kwargs)
    raw = result["text"].strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        items = json.loads(raw).get("claims", [])
    except (json.JSONDecodeError, AttributeError) as error:
        raise RuntimeError("The model's answer was not valid JSON.") from error

    # One block per slide or page, so a quote has to come from one place.
    blocks = [_squash(block) for block in re.split(r"--- (?:Slide|Page) \d+ ---", deck_text)]
    kept, dropped, seen = [], [], set()
    for item in items if isinstance(items, list) else []:
        reason = _problem(item, blocks)
        if reason:
            dropped.append({"claim": item, "reason": reason})
            continue
        key = (item["metric"], item["period_type"], item["period_end"], float(item["value"]), item["scale"])
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return {"claims": kept, "dropped": dropped, "model": result["model"], "usage": result["usage"]}


def _problem(item: object, blocks: list[str]) -> str:
    """Why a claim can't be used, or an empty string if it can."""
    if not isinstance(item, dict):
        return "not a claim"
    if item.get("metric") not in METRICS:
        return "unknown metric"
    if item.get("period_type") not in PERIOD_TYPES:
        return "unknown period type"
    if item.get("scale") not in SCALES:
        return "unknown scale"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(item.get("period_end", ""))):
        return "period end is not a date"
    try:
        float(item.get("value"))
    except (TypeError, ValueError):
        return "value is not a number"
    quote = str(item.get("quote", ""))
    # Look-alike measures the filings do not report under this metric.
    lowered = quote.lower()
    if item["metric"] == "cash" and re.search(r"invest|securit", lowered):
        return "cash plus investments is not cash and equivalents"
    if item["metric"] != "non_gaap" and "parent" in lowered:
        return "a parent-only figure, not the whole company"
    if item["metric"] != "non_gaap" and re.search(r"adjusted|non-gaap", lowered):
        item["metric"] = "non_gaap"
    digits = re.sub(r"[^0-9.]", "", str(item.get("as_written", ""))).strip(".")
    if not digits or digits not in _squash(quote):
        return "the number is not in the quote"
    # A quote from a table row often skips columns ("Revenue | 6.80"), so each
    # piece has to appear on the same slide rather than the quote as a whole.
    pieces = [_squash(piece) for piece in re.split(r"\||…|\.\.\.", quote)]
    pieces = [piece for piece in pieces if piece]
    if not pieces or len("".join(pieces)) < 4:
        return "the quote is too short"
    if not any(all(piece in block for piece in pieces) for block in blocks):
        return "the quote is not in the deck"
    return ""
