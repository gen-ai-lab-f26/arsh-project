"""Check that pitchcheck.sec returns the filing figures we expect.

Run it:  python checks/check_sec.py

The expected values are for two real issuers, limited to filings made on or
before November 24, 2026, so they stay true when newer filings arrive. They
were worked out by hand from SEC's data on that date.

This checks the plumbing. It is not one of the five product checks in
TEST_LOG.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pitchcheck.sec import filing_figures, find  # noqa: E402

AS_OF = "2026-11-24"
HEALTH_ISSUER = 64803  # CVS Health
TECH_ISSUER = 1262039  # Fortinet

# (issuer, metric, period, expected value in $ millions)
EXPECTED = [
    (HEALTH_ISSUER, "revenue", "FY", 402_067),
    (HEALTH_ISSUER, "revenue", "LTM", 420_614),
    (HEALTH_ISSUER, "revenue", "Q", 108_399),
    (HEALTH_ISSUER, "operating_income", "LTM", 15_061),
    (HEALTH_ISSUER, "interest_expense", "LTM", 3_065),
    (HEALTH_ISSUER, "d_and_a", "LTM", 4_520),
    (HEALTH_ISSUER, "cash_from_operations", "YTD", 15_318),
    (HEALTH_ISSUER, "cash", "instant", 11_738),
    (HEALTH_ISSUER, "debt", "instant", 60_680),
    (TECH_ISSUER, "revenue", "FY", 6_799.6),
    (TECH_ISSUER, "revenue", "LTM", 7_880.9),
    (TECH_ISSUER, "buybacks", "FY", 2_289.8),
    (TECH_ISSUER, "cash_from_operations", "FY", 2_590.6),
    (TECH_ISSUER, "cash", "instant", 3_750.6),
    (TECH_ISSUER, "debt", "instant", 497.1),
]

failures = 0


def report(ok: bool, text: str) -> None:
    global failures
    failures += 0 if ok else 1
    print(("PASS  " if ok else "FAIL  ") + text)


def main() -> int:
    results = {cik: filing_figures(cik=cik, as_of=AS_OF) for cik in (HEALTH_ISSUER, TECH_ISSUER)}

    for cik, metric, period, expected in EXPECTED:
        fig = find(results[cik], metric, period)
        got = None if fig is None or not fig.found else fig.value / 1e6
        ok = got is not None and abs(got - expected) < 0.06
        report(ok, f"{results[cik]['name']}: {metric} {period} = {got} (expected {expected})")

    # Every figure that has a value names the filing it came from.
    for result in results.values():
        missing = [f for f in result["figures"] if f.found and not f.sources]
        report(not missing, f"{result['name']}: every figure has a filing behind it")

    # The annual figure cites the 10-K, not a proxy statement that repeats it.
    fig = find(results[TECH_ISSUER], "net_income", "FY")
    report(fig.sources[0].form == "10-K", "Net income FY cites the 10-K")

    # When the tags do not line up, the answer is "not found", not a guess.
    fig = find(results[TECH_ISSUER], "interest_expense", "LTM")
    report(not fig.found and fig.note != "", "Interest expense LTM is 'not found' with a reason")

    # A figure older than the newest period says so.
    fig = find(results[HEALTH_ISSUER], "buybacks", "LTM")
    report("Older than" in fig.note, "A stale figure is labeled as older")

    # An earlier cutoff ignores later filings.
    earlier = filing_figures(cik=HEALTH_ISSUER, as_of="2026-10-01")
    fig = find(earlier, "revenue", "YTD")
    report(fig.end == "2026-06-30", "A cutoff of Oct 1 stops at the June quarter")

    # An issuer SEC has no data for is an error, not an empty table.
    try:
        filing_figures(cik=999_999_999)
        report(False, "Unknown issuer raises an error")
    except LookupError:
        report(True, "Unknown issuer raises an error")

    print(f"\n{failures} failed" if failures else "\nAll passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
