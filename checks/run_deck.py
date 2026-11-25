"""Run the checker on one deck from the command line.

Run it:  python checks/run_deck.py pitches/deck.pptx TICKER 2026-11-17
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pitchcheck.compare import check_claims  # noqa: E402
from pitchcheck.deck import read_deck  # noqa: E402
from pitchcheck.extract import extract_claims  # noqa: E402
from pitchcheck.sec import load_issuer  # noqa: E402


def main(path: str, ticker: str, as_of: str) -> int:
    started = time.time()
    cik, facts = load_issuer(ticker=ticker)
    found = extract_claims(read_deck(path))
    rows = check_claims(found["claims"], cik, facts, as_of)
    for row in rows:
        filing = "" if row["filing_value"] is None else f"{row['filing_value']:,.2f}"
        diff = "" if row["difference"] is None else f"{row['difference']:+.1%}"
        print(
            f"{row['status']:<20}{row['metric']:<22}{row['period_type']:<6}{row['period_end']:<12}"
            f"{row['as_written']:<14}{filing:>12} {diff:>7}  slide {row['slide']}"
        )
    for item in found["dropped"]:
        print(f"dropped ({item['reason']}): {str(item['claim'])[:400]}")
    usage = found["usage"]
    print(
        f"\n{len(rows)} claims, {len(found['dropped'])} dropped, {time.time() - started:.0f}s, "
        f"model {found['model']}, cost ${usage.get('cost')}"
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(*sys.argv[1:]))
