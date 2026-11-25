# INTENT.md: one-page product brief

Keep it to one page. Write it first, then update it when testing changes your mind.

**Product:** PitchCheck (working name) · **Team:** Arsh Jain (solo) · **Product Page:** https://gen-ai-lab-f26.github.io/arsh-project/

## 1. Who is it for?

*A real person or group you can put the prototype in front of before December 8. Not "students" or "busy professionals."*

- **The person:** Members of the investment committee (IC) of the fixed income fund in NYU Stern's student-managed investment fund (MPSIF). Every member writes bond pitches and reviews the others' before the vote.
- **How you'll reach them to test:** I am the fund's portfolio manager. Around November 30 I send the IC (about 10 members) a link so each member runs their own pitch alone, with no coaching. I collect their reactions at the IC meeting on Tuesday, December 1.

## 2. Their workflow today, and with your product

- **Today (before):** A member builds a deck from company filings, data terminals and broker quotes and uploads it to the fund's shared drive. Nobody checks the numbers before the IC votes.
- **With your product (after):** Paste the pitch in. A table comes back with every number, a status (matches the filing, differs, differs by definition, or not in filings), the filing's value and a link to the filing. The reviewer reads only the flagged rows.

## 3. Your core claim

*One sentence a tester could prove wrong.*

On a real bond pitch for a US company, PitchCheck catches every reported financial figure (revenue, operating income, net income, interest, cash from operations, cash, debt) that is more than 1% away from the issuer's filings as of the pitch date, with no more than one false flag per pitch, in under two minutes.

## 4. Why not just use a plain AI chat?

*What your product does that pasting the problem into ChatGPT, Claude or Gemini does not.*

- The filing figures come from SEC's own structured data, pulled by code. The model only reads the pitch and lists the claims in it. It never supplies a financial figure.
- Code does the arithmetic, such as trailing twelve months.
- Prices, spreads and ratings come back as "not in filings", not as a guess.
- Every row links to its filing, and the same pitch gives the same result each time.
- In the baseline on two real decks, a plain chat said it could not see filings newer than its training data and checked no latest-quarter figure (see `TEST_LOG.md`).

## 5. Where a person checks the AI

*The step where a person reviews or approves before anything is sent, spent, saved or published.*

PitchCheck never edits the pitch. The writer first confirms the issuer and the date the pitch was written. Each flag shows the pitch's number beside the filing's number and the link, and the writer accepts it or dismisses it with a reason. The list of claims the model pulled out is shown too, so a person can see what it missed.

## 6. What one run costs

*Run it ten times and divide. In your cube, compare the "On me" credit before and after.*

- **Cost per run:** `$[not measured yet]`
- **How you measured it:** [Ten runs through OpenRouter, divided by ten. SEC data is free.]

## 7. Your first 50 users

*Where they are, and how you'd reach them.*

The fixed income IC first (about 10 members). Then the rest of MPSIF (about 40 students in all): I ask the portfolio managers of the other funds to share it with their analysts. The last 10 or so come from student-managed funds at other schools.

## 8. Not building (yet)

- Prices, yields, spreads and ratings. Filings do not hold them, so they are labeled "not in filings".
- Bond terms such as coupon, maturity and call dates. They sit in prospectus text, not in SEC's structured data.
- Sovereign, structured product, private or non-US issuers, and any view on whether the bond is a good buy.
- Numbers a deck states two different ways. A plain chat already catches these, so this was cut after the baseline.
- Ratios and non-GAAP measures such as leverage, coverage, EBITDA and free cash flow. They are labeled, not checked.

## 9. Riskiest assumption

*The one thing that sinks the product if it's wrong. Test it first.*

That real pitches contain filing figures that are wrong. In the two decks checked against SEC data so far, every in-scope figure matched or was within 1%. If that holds across the IC's decks, the tool only confirms numbers that are already right, and its value is the confirmation and the filing links, not the catches. The first test is to run every US-company deck in the fund's drive and count the catches, and to seed known errors to prove a wrong figure gets flagged. The sizing notes are in `TEST_LOG.md`.
