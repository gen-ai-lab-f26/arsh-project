# TEST_LOG.md: baseline, checks, testers, fixes

Log as you go. A check you ran beats a check you planned. Never invent a result, a tester or a quote, and label anything simulated or synthetic.

## 1. Baseline

*The easy option your product has to beat: doing it by hand, or pasting it into a plain AI chat.*

- **Baseline we used:** A plain AI chat. The deck's text is pasted in with one fixed prompt asking it to list (1) figures that do not match the company's latest SEC filings and (2) numbers the pitch states two different ways. No tools, no SEC data. The prompt is in `checks/baseline.py`.
- **Model or tool:** run on five models through OpenRouter, temperature 0 (see the comparison below). PitchCheck itself now uses `google/gemini-3.8-flash`; the baseline on that model has been run on deck B only so far. The first runs used `anthropic/claude-sonnet-5.5`; the results table below is from those runs, and the model comparison under it shows the switch.

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

**Choosing the model (November 25).** Sonnet cost about $0.13 a deck, so I took the best-value models from the Arena text leaderboard's cost chart and ran the same baseline prompt on them.

| Model | Deck A | Deck B | Deck C | Cost per deck |
| --- | --- | --- | --- | --- |
| Claude Sonnet 5.5 | No filing check. Two revenue flags from memory, both right. | Caught the position size | Not run | $0.13 |
| DeepSeek V4 Flash (now the default) | Said it cannot verify against filings | Caught the position size | Caught the spread | $0.001 to $0.002 |
| GLM-5.3-Flash | No filing check. Two revenue flags from memory, both right. | Answer broke down into garbage text and missed the position size | Caught the spread and the date | $0.003 to $0.008 |
| MiMo-V2.6-Pro | Not run | Empty answer: it spent the whole limit thinking | Not run | $0.018 |
| Gemini 3.8 Flash | Not run | Caught the position size | Not run | $0.012 |

No model checked a latest-quarter figure against a filing. DeepSeek V4 Flash was the cheapest that gave a clean answer on all three decks. Gemini 3.8 Flash is the fallback. Whether DeepSeek is good enough at pulling claims out of a deck is still to be tested against the answer key.

**The two failed tries:** the first calls came back empty because the model's thinking used the whole 4,000-token limit. Raising the limit to 16,000 fixed it.

## 2. Checks (at least five, one meant to break it)

| # | Check | Input | Baseline result | Our result | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | A clean pitch gets no flags | Deck A, a healthcare issuer (real) | Checked nothing against the latest filings. From memory, flagged two older revenue figures that are within 1%. | 9 figures matched, 0 flagged, 6 non-GAAP figures labeled "not checked". 11 seconds. | Nov 25. All 9 in-scope figures I had listed by hand were found. |
| 2 | A clean pitch with charts and tables gets no flags | Deck B, a technology issuer (real) | Confirmed no figure against filings. | 27 figures matched, 0 flagged, 19 non-GAAP labeled. 24 seconds. | Nov 25. Includes nine quarters of revenue read from a chart, with fourth quarters worked out from the annual figure. |
| 3 | Planted errors are caught | Deck B's text with three figures changed: revenue with two digits swapped, debt left at the level before a repayment, and a wrong buyback amount (**synthetic**) | Not run yet | 3 of 3 flagged, 0 false flags | Nov 25. The errors are mine, not a member's. |
| 4 | [A units slip, such as millions written as billions] | | | | Not run yet |
| 5 | Meant to break it: a bank | Deck C, a bank (real) | Confirmed no figure against filings. | Found only 3 net income figures, all matching. Nothing on deposits, loans or charge-offs. | Nov 25. An earlier build also raised 5 false flags here; see "Failures found while building". The page now says it is not built for banks. |

**Choosing the model that reads the deck (November 25).** Same decks, same prompt, thinking on.

| Model | Deck A | Deck B | Deck C | Cost per deck | Time |
| --- | --- | --- | --- | --- | --- |
| DeepSeek V4 Flash | 8 matched, 0 false flags | 18 matched, **9 false flags** (it read a chart's billings line as revenue) | 3 matched, 0 false flags | $0.0005 to $0.003 | 19 to 44 s |
| Gemini 3.8 Flash (chosen) | 9 matched, 0 false flags | 21 to 27 matched, 0 false flags | 3 matched, 0 false flags | $0.007 to $0.024 | 4 to 24 s |

DeepSeek is about ten times cheaper, but a false flag costs the reviewer's trust, so Gemini 3.8 Flash reads the deck. The baseline prompt was also run on Gemini for deck B, with the same result as the other models.

**Failures found while building (November 25):**

- **Look-alike figures.** With thinking turned off to save time, the model labeled "cash and investments" as cash, and a bank's dividends from its subsidiary as operating cash flow. That produced 1, 4 and 5 false flags on the three decks. Fix: thinking stays on, and code now drops a cash figure whose quote mentions investments and any figure whose quote says "parent".
- **Table quotes.** The first build threw out 9 correct figures on deck B because the model quoted a table row with columns skipped, and the quote check wanted the exact run of text. Fix: each piece of the quote has to appear on the same slide.
- **Quarterly cash flow.** A third-quarter buyback figure came back "not found" because cash flow statements report year to date only. Fix: the quarter is worked out as this year to date minus the one before, and the row says so.

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
