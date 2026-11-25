"""Pull an issuer's reported figures from SEC's public company-facts data.

Every figure comes back with the filing it came from. When no tag matches,
the figure is reported as not found. Nothing here is estimated or guessed.

Run it:  python -m pitchcheck.sec CVS
         python -m pitchcheck.sec --cik 1262039 --as-of 2026-11-24

Looking an issuer up by ticker needs SEC_USER_AGENT set in .env, because SEC's
ticker list only answers clients that name a contact. A CIK works without it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".cache" / "sec"
CACHE_HOURS = 24
DEFAULT_USER_AGENT = "pitchcheck-class-project/0.1"

# Each metric lists the XBRL tags issuers use for it. Issuers differ, and one
# issuer can switch tags over time, so the tag with the newest data wins and
# the list order only breaks ties.
DURATION_METRICS = {
    "revenue": (
        "Revenue",
        [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "SalesRevenueNet",
        ],
    ),
    "operating_income": ("Operating income", ["OperatingIncomeLoss"]),
    "net_income": ("Net income", ["NetIncomeLoss"]),
    "interest_expense": (
        "Interest expense",
        ["InterestExpenseNonoperating", "InterestExpense", "InterestExpenseDebt"],
    ),
    "d_and_a": (
        "Depreciation and amortization",
        [
            "DepreciationDepletionAndAmortization",
            "DepreciationAndAmortization",
            "DepreciationAmortizationAndAccretionNet",
        ],
    ),
    "cash_from_operations": (
        "Cash from operations",
        ["NetCashProvidedByUsedInOperatingActivities"],
    ),
    "buybacks": ("Share repurchases", ["PaymentsForRepurchaseOfCommonStock"]),
}

# A balance-sheet metric can be one tag or a sum of tags. Each option is a
# list of (tag, required). A missing optional tag is counted as zero and the
# figure's note says so.
INSTANT_METRICS = {
    "cash": ("Cash and equivalents", [[("CashAndCashEquivalentsAtCarryingValue", True)]]),
    "debt": (
        "Long-term debt, with the current portion",
        [
            [("LongTermDebt", True)],
            [("LongTermDebtNoncurrent", True), ("LongTermDebtCurrent", False)],
            [
                ("LongTermDebtAndCapitalLeaseObligations", True),
                ("LongTermDebtAndCapitalLeaseObligationsCurrent", False),
            ],
        ],
    ),
}

STATEMENT_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A"}
ANNUAL_DAYS = (350, 380)
QUARTER_DAYS = (80, 100)
MATCH_DAYS = 10  # slack for 52/53-week fiscal years


@dataclass
class Source:
    """One reported fact and the filing it came from."""

    tag: str
    start: str | None
    end: str
    value: float
    form: str
    filed: str
    accession: str
    url: str


@dataclass
class Figure:
    """One figure the checker can compare a pitch against."""

    metric: str
    label: str
    period: str  # "FY", "LTM", "YTD", "Q" or "instant"
    start: str | None = None
    end: str | None = None
    value: float | None = None  # US dollars; None means not found
    sources: list[Source] = field(default_factory=list)
    note: str = ""

    @property
    def found(self) -> bool:
        return self.value is not None


# --- fetching -----------------------------------------------------------------


def load_env(path: Path = ROOT / ".env") -> None:
    """Read KEY=VALUE lines from .env without overriding the real environment."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _fetch_json(url: str, cache_name: str) -> dict:
    """Get a JSON document from SEC, reusing a copy fetched in the last day."""
    cache_file = CACHE_DIR / cache_name
    if cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_hours < CACHE_HOURS:
            return json.loads(cache_file.read_text())

    load_env()
    response = requests.get(
        url,
        headers={"User-Agent": os.environ.get("SEC_USER_AGENT", DEFAULT_USER_AGENT)},
        timeout=30,
    )
    response.raise_for_status()
    time.sleep(0.2)  # SEC asks automated clients to stay under 10 requests a second

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(response.text)
    return response.json()


def ticker_to_cik(ticker: str) -> int:
    """Look up an issuer's SEC number (CIK). Raises LookupError if it can't."""
    try:
        listing = _fetch_json(
            "https://www.sec.gov/files/company_tickers.json", "company_tickers.json"
        )
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code == 403:
            raise LookupError(
                "SEC's ticker list refused the request. It only answers clients that "
                "name a contact: set SEC_USER_AGENT in .env (see .env.example), "
                "or pass the issuer's SEC number with --cik."
            ) from error
        raise
    wanted = ticker.strip().upper()
    for row in listing.values():
        if row["ticker"].upper() == wanted:
            return int(row["cik_str"])
    raise LookupError(f"No SEC filer found for ticker {ticker!r}")


def company_facts(cik: int) -> dict:
    return _fetch_json(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
        f"facts_{cik:010d}.json",
    )


# --- reading the facts --------------------------------------------------------


def _d(text: str) -> date:
    return date.fromisoformat(text)


def _days(row: dict) -> int:
    return (_d(row["end"]) - _d(row["start"])).days + 1


def _rows(facts: dict, tag: str, as_of: str | None, duration: bool) -> list[dict]:
    """USD facts for one tag, one row per period, keeping the newest filing."""
    units = facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {})

    def rank(row: dict) -> tuple:
        # Prefer the financial statements over a proxy or press release that
        # repeats the number, then the newest filing.
        return (row["form"] in STATEMENT_FORMS, row["filed"])

    best: dict[tuple, dict] = {}
    for row in units.get("USD", []):
        if as_of and row["filed"] > as_of:
            continue
        if duration != ("start" in row):
            continue
        key = (row.get("start"), row["end"])
        if key not in best or rank(row) > rank(best[key]):
            best[key] = row
    return list(best.values())


def _source(cik: int, tag: str, row: dict) -> Source:
    accession = row["accn"]
    folder = accession.replace("-", "")
    return Source(
        tag=tag,
        start=row.get("start"),
        end=row["end"],
        value=float(row["val"]),
        form=row["form"],
        filed=row["filed"],
        accession=accession,
        url=f"https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/",
    )


def _near(a: date, b: date) -> bool:
    return abs((a - b).days) <= MATCH_DAYS


def _duration_figures(
    cik: int, facts: dict, metric: str, as_of: str | None
) -> list[Figure]:
    """Figures for one metric, from the single tag that serves it best.

    The tag whose data runs latest wins. Between tags that end on the same
    date, one that yields a trailing-twelve-month figure wins, then list order.
    Tags are never mixed inside one figure.
    """
    label, tags = DURATION_METRICS[metric]
    best: list[Figure] = []
    best_score: tuple = ()
    for tag in tags:
        rows = _rows(facts, tag, as_of, duration=True)
        if not rows:
            continue
        figures = _figures_for_tag(cik, metric, label, tag, rows)
        ltm = next((f for f in figures if f.period == "LTM"), None)
        score = (max(r["end"] for r in rows), bool(ltm and ltm.found))
        if score > best_score:
            best, best_score = figures, score
    return best or [Figure(metric, label, "LTM", note="No matching tag in SEC data.")]


def _figures_for_tag(
    cik: int, metric: str, label: str, tag: str, rows: list[dict]
) -> list[Figure]:

    def figure(period: str, row: dict, note: str = "") -> Figure:
        return Figure(
            metric, label, period, row["start"], row["end"], float(row["val"]),
            [_source(cik, tag, row)], note,
        )

    figures: list[Figure] = []
    annual = [r for r in rows if ANNUAL_DAYS[0] <= _days(r) <= ANNUAL_DAYS[1]]
    if annual:
        figures.append(figure("FY", max(annual, key=lambda r: r["end"])))

    latest_end = max(r["end"] for r in rows)
    at_end = [r for r in rows if r["end"] == latest_end and _days(r) <= ANNUAL_DAYS[1]]
    longest = max(at_end, key=_days)

    if ANNUAL_DAYS[0] <= _days(longest) <= ANNUAL_DAYS[1]:
        # The newest filing is the annual report, so the year is the last twelve months.
        figures.append(figure("LTM", longest, "Same as the fiscal year."))
    else:
        figures.append(figure("YTD", longest))
        start, end = _d(longest["start"]), _d(longest["end"])
        year = timedelta(days=365)
        prior_year = next(
            (r for r in annual if _near(_d(r["end"]), start - timedelta(days=1))), None
        )
        prior_ytd = next(
            (
                r for r in rows
                if _near(_d(r["start"]), start - year) and _near(_d(r["end"]), end - year)
            ),
            None,
        )
        if prior_year and prior_ytd:
            value = float(prior_year["val"]) + float(longest["val"]) - float(prior_ytd["val"])
            figures.append(
                Figure(
                    metric, label, "LTM",
                    (end - year + timedelta(days=1)).isoformat(), longest["end"], value,
                    [_source(cik, tag, r) for r in (prior_year, longest, prior_ytd)],
                    "Last fiscal year plus this year to date, minus the same span a year ago.",
                )
            )
        else:
            figures.append(
                Figure(
                    metric, label, "LTM", end=longest["end"],
                    note="Could not find the prior year or the prior year-to-date figure.",
                )
            )

    quarter = [
        r for r in at_end if QUARTER_DAYS[0] <= _days(r) <= QUARTER_DAYS[1]
    ]
    if quarter:
        figures.append(figure("Q", quarter[0]))
    return figures


def _instant_figure(cik: int, facts: dict, metric: str, as_of: str | None) -> Figure:
    label, options = INSTANT_METRICS[metric]
    best: Figure | None = None
    for option in options:
        required = [tag for tag, must in option if must]
        rows_by_tag = {tag: _rows(facts, tag, as_of, duration=False) for tag, _ in option}
        if any(not rows_by_tag[tag] for tag in required):
            continue
        end = min(max(r["end"] for r in rows_by_tag[tag]) for tag in required)
        sources, missing = [], []
        for tag, must in option:
            row = next((r for r in rows_by_tag[tag] if r["end"] == end), None)
            if row:
                sources.append(_source(cik, tag, row))
            elif must:
                sources = []
                break
            else:
                missing.append(tag)
        if not sources:
            continue
        note = "Sum of " + " and ".join(s.tag for s in sources) + "." if len(sources) > 1 else ""
        if missing:
            note = (note + " " if note else "") + (
                f"{', '.join(missing)} not reported at this date, counted as zero."
            )
        candidate = Figure(
            metric, label, "instant", None, end, sum(s.value for s in sources), sources, note
        )
        if best is None or candidate.end > best.end:
            best = candidate
    return best or Figure(metric, label, "instant", note="No matching tag in SEC data.")


def filing_figures(
    ticker: str | None = None, cik: int | None = None, as_of: str | None = None
) -> dict:
    """All figures for one issuer, found by ticker or by SEC number (CIK).

    `as_of` ignores anything filed after that date, so a pitch can be checked
    against the filings that existed when it was written.
    """
    if cik is None:
        if not ticker:
            raise LookupError("Give a ticker or a CIK.")
        cik = ticker_to_cik(ticker)
    try:
        facts = company_facts(cik)
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code == 404:
            raise LookupError(f"SEC has no financial data for CIK {cik}.") from error
        raise
    figures: list[Figure] = []
    for metric in DURATION_METRICS:
        figures.extend(_duration_figures(cik, facts, metric, as_of))
    for metric in INSTANT_METRICS:
        figures.append(_instant_figure(cik, facts, metric, as_of))

    # Say so when a figure is older than the issuer's newest period, so an old
    # number is never read as the current one.
    for periods in (("FY",), ("LTM", "YTD", "Q", "instant")):
        ends = [f.end for f in figures if f.found and f.period in periods]
        if not ends:
            continue
        newest = max(ends)
        for fig in figures:
            if fig.found and fig.period in periods and fig.end < newest:
                fig.note = (fig.note + " " if fig.note else "") + (
                    f"Older than the issuer's newest period ({newest}): "
                    "nothing reported under this tag since."
                )
    return {
        "ticker": ticker.upper() if ticker else None,
        "cik": cik,
        "name": facts.get("entityName", ""),
        "as_of": as_of,
        "figures": figures,
    }


def find(result: dict, metric: str, period: str) -> Figure | None:
    for fig in result["figures"]:
        if fig.metric == metric and fig.period == period:
            return fig
    return None


# --- command line -------------------------------------------------------------


def _print_table(result: dict) -> None:
    ticker = f"{result['ticker']}, " if result["ticker"] else ""
    print(f"{result['name']} ({ticker}CIK {result['cik']})")
    if result["as_of"]:
        print(f"Filings up to {result['as_of']}")
    print()
    print(f"{'Figure':<42}{'Period':<9}{'Ends':<12}{'$ millions':>14}  Filing")
    for fig in result["figures"]:
        if fig.found:
            value = f"{fig.value / 1e6:,.0f}"
            filing = "; ".join(f"{s.form} filed {s.filed}" for s in fig.sources)
        else:
            value, filing = "not found", fig.note
        print(f"{fig.label:<42}{fig.period:<9}{fig.end or '':<12}{value:>14}  {filing}")
        if fig.found and fig.note:
            print(f"{'':<63}  {fig.note}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print an issuer's figures from SEC filings.")
    parser.add_argument("ticker", nargs="?")
    parser.add_argument("--cik", type=int, help="The issuer's SEC number, in place of a ticker.")
    parser.add_argument("--as-of", help="Ignore anything filed after this date (YYYY-MM-DD).")
    parser.add_argument("--json", action="store_true", help="Print JSON with filing links.")
    args = parser.parse_args(argv)
    try:
        result = filing_figures(args.ticker, args.cik, args.as_of)
    except LookupError as error:
        print(error, file=sys.stderr)
        return 1
    if args.json:
        result["figures"] = [asdict(fig) for fig in result["figures"]]
        print(json.dumps(result, indent=2))
    else:
        _print_table(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
