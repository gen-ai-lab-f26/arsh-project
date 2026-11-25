"""Compare each claim from a pitch with the issuer's filing figure.

Code alone decides the status. A claim matches when it is within 1% of the
filing, or within the rounding of the number as the pitch wrote it.
"""

from __future__ import annotations

import re

from pitchcheck.extract import SCALES
from pitchcheck.sec import Figure, period_figure

TOLERANCE = 0.01
ORDER = {"differs": 0, "not found": 1, "matches": 2, "not a filing figure": 3}


def _rounding_slack(as_written: str, scale: float) -> float:
    """Half of the last digit shown: "$2.1bn" could be anything from 2.05 to 2.15."""
    number = re.search(r"\d[\d,]*(?:\.(\d+))?", as_written or "")
    decimals = len(number.group(1)) if number and number.group(1) else 0
    return 0.5 * 10 ** (-decimals) * scale


def check_claims(claims: list[dict], cik: int, facts: dict, as_of: str | None) -> list[dict]:
    rows = []
    for claim in claims:
        row = {
            "metric": claim["metric"],
            "period_type": claim["period_type"],
            "period_end": claim["period_end"],
            "as_written": claim["as_written"],
            "quote": claim.get("quote", ""),
            "slide": claim.get("slide"),
            "filing_value": None,
            "difference": None,
            "sources": [],
            "note": "",
        }
        if claim["metric"] == "non_gaap":
            row["status"] = "not a filing figure"
            row["note"] = "A non-GAAP measure. Filings do not report it, so it is not checked."
            rows.append(row)
            continue

        scale = SCALES[claim["scale"]]
        pitch_value = float(claim["value"]) * scale
        kind = "instant" if claim["period_type"] == "POINT" else claim["period_type"]
        fig: Figure = period_figure(cik, facts, claim["metric"], kind, claim["period_end"], as_of)
        row["label"] = fig.label
        if not fig.found:
            row["status"] = "not found"
            row["note"] = fig.note
            rows.append(row)
            continue

        slack = max(TOLERANCE * abs(fig.value), _rounding_slack(claim["as_written"], scale))
        row["filing_value"] = fig.value / scale
        row["difference"] = (pitch_value - fig.value) / fig.value if fig.value else None
        row["status"] = "matches" if abs(pitch_value - fig.value) <= slack else "differs"
        row["sources"] = fig.sources
        row["note"] = fig.note
        rows.append(row)
    rows.sort(key=lambda r: (ORDER[r["status"]], r["metric"], r["period_end"]))
    return rows
