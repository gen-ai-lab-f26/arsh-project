# AGENTS.md: rules for your coding agent

Your agent reads this file first. Keep it short and current.

## Project

- **What this builds:** PitchCheck reads a bond pitch and checks its reported financial figures against the issuer's SEC filings. A person reviews every flag.
- **Who it's for:** see `INTENT.md`
- **Stack:** Python 3.11. `app.py` is the web page (FastAPI). `pitchcheck/sec.py` pulls filing figures from SEC's public company-facts API, `pitchcheck/deck.py` reads .pptx and .pdf decks, `pitchcheck/extract.py` asks a model (through `pitchcheck/llm.py` and OpenRouter) to list the figures a deck claims, and `pitchcheck/compare.py` sets each figure's status in code.
- **Product Page:** `docs/index.md`, plain Markdown that GitHub Pages turns into the team's public page. Fill it only with facts from `INTENT.md` and `TEST_LOG.md`, and leave a [bracket] where the team has no answer yet.

## Commands

- **Install:** `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- **Run:** `uvicorn app:app --reload` serves the page at http://127.0.0.1:8000. `python -m pitchcheck.sec --cik 64803` prints one issuer's filing figures; a ticker works in place of `--cik` once `SEC_USER_AGENT` is set in `.env`.
- **Check:** `python checks/check_sec.py`. `python checks/run_deck.py <deck> <ticker> <date>` runs the checker on one deck and `python checks/baseline.py <deck>` runs the plain-chat baseline; each costs one to two cents, so ask before running many.

## Rules

1. **Plan first.** Before changing more than one file, propose a short plan and wait for a yes.
2. **Small changes.** One change at a time, small enough to explain in a sentence.
3. **Explain it.** Say what changed, why, what could break, and how you checked it.
4. **Check your work.** Run the checks and record the results in `TEST_LOG.md`. Never invent a result.
5. **No secrets in code.** Read keys from `.env`. Add new variable names to `.env.example`, never their values.
6. **Ask before acting on the world.** Don't send messages, spend money or publish anything without a person's OK.
7. **Stop when stuck.** If a fix fails twice, stop, say what failed, and ask before trying a third way.
8. **The model never supplies a financial figure.** Filing numbers come from SEC data and arithmetic comes from code. The model only reads the pitch and lists what it claims.
9. **This repo is public.** Never commit a real pitch, a fund holding, a person's name or an email. Real pitches used for testing stay in `pitches/`, which Git ignores.
