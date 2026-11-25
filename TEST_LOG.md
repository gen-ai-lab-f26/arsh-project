# TEST_LOG.md: baseline, checks, testers, fixes

Log as you go. A check you ran beats a check you planned. Never invent a result, a tester or a quote, and label anything simulated or synthetic.

## 1. Baseline

*The easy option your product has to beat: doing it by hand, or pasting it into a plain AI chat.*

- **Baseline we used:** A plain AI chat. The deck's text is pasted in with one fixed prompt asking it to list (1) figures that do not match the company's latest SEC filings and (2) numbers the pitch states two different ways. No tools, no SEC data. The prompt is in `checks/baseline.py`.
- **Model or tool:** `anthropic/claude-sonnet-5.5` through OpenRouter, temperature 0. PitchCheck will use the same model, so the comparison isolates what the code adds.

**What counts, written down before the first run (November 25):**

| Deck | Known issues, found by hand against SEC data | A catch is | A miss or false flag is |
| --- | --- | --- | --- |
| A, a healthcare issuer (my own pitch) | None above the 1% line. Two revenue figures are 0.6% under the filings. Quarterly revenue, cash from operations and debt match. | Saying it cannot see the latest quarter's filing, and not calling a matching figure wrong. | Calling a matching figure wrong, or supplying a "correct" figure that is not what the filing says. |
| B, a technology issuer | Position size stated two ways (1.75% and 1% of the fund, with different dollar amounts). Filing figures match. | Quoting both position sizes. | Calling a matching filing figure wrong. |
| C, a bank | One spread stated as both 153 and 147 basis points, and one pricing date as both November 16 and 18. Figures not yet checked against filings. | Quoting both values for either one. | To be set once the filing figures are checked. |

**Results:**

| Deck | Date | Baseline result | Cost |
| --- | --- | --- | --- |
| A | Nov 25 | **Filings:** it said it has no filing access and that the latest quarter is after its training data, so it checked nothing against the newest 10-Q. From memory it flagged the 2023 and 2024 revenue figures, and its remembered values match the 10-Ks (the pitch is 0.3% and 0.6% under). It could not check 2025, the trailing twelve months or the quarter. Two other "from memory" doubts could not be confirmed either way. **Two ways:** it listed 12 items. About three are real questions for the writer (two debt totals that do not reconcile, a net leverage ratio that does not tie, debt down $3.9bn against $4.1bn repaid). The rest are rounding (5.31% and 5.32%) or differences the pitch already explains. | $0.14, plus $0.10 on two failed tries |
| B | Nov 25 | **Filings:** it said it cannot open SEC filings and that the latest quarter is beyond what it knows, so it confirmed no figure. **Two ways:** it caught the position size, called it the most important item, and quoted both versions. This run did not include the deck's chart data, which the reader could not extract yet. | $0.13 |
| C | | Not run. The account ran out of credit (the call was refused) before this deck. | |

**What this changed (two decks):** a plain chat is good at finding numbers a deck states two different ways, and noisy about it. It cannot check anything against a filing newer than its training data. I had set the rule before the second run: if the chat quoted both position sizes in deck B, the deck-against-itself check gets cut. It did, so that check is cut and the claim in `INTENT.md` now covers the filing check only.

**The two failed tries:** the first calls came back empty because the model's thinking used the whole 4,000-token limit. Raising the limit to 16,000 fixed it.

## 2. Checks (at least five, one meant to break it)

| # | Check | Input | Baseline result | Our result | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | Meant to break it: | | | | |

## 3. Outside testers (2–3, no coaching)

*People outside your team. Hand it over, stay quiet, and write down what happens.*

| Tester (role, not name) | Date | What they tried | Where they got stuck | What we changed |
| --- | --- | --- | --- | --- |
| | | | | |
| | | | | |
| | | | | |

## 4. One real failure, and the fix

- **What broke:**
- **How we found it:**
- **What we changed:**
- **How we checked the fix:**

## 5. Known limits

*What it still can't do, or does badly. Say it before someone else finds it.*

Found while building the SEC lookup (November 25):

- **Tag switches.** One issuer reports interest expense under one tag for the full year and another for the quarters, so its trailing-twelve-month interest comes back "not found".
- **Current portion of debt.** If an issuer reports no current portion at a date, it is counted as zero and the figure's note says so. An issuer that files it under a tag the lookup does not know would be undercounted.
- **Banks.** The lookup finds a bank's net income but has nothing for deposits, loans or charge-offs, and "revenue" and "cash" mean little for a bank.
- **Capital spending** was dropped: issuers tag it too differently to trust one figure.
- **Vendor definitions.** A pitch built on a data vendor's revenue ran 0.3% to 0.6% under the filings in all four periods checked, which is under the 1% line but systematic.
