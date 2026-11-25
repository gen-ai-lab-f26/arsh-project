# AGENTS.md: rules for your coding agent

Your agent reads this file first. Keep it short and current.

## Project

- **What this builds:** PitchCheck reads a bond pitch, checks its reported financial figures against the issuer's SEC filings, and lists numbers the deck states two different ways. A person reviews every flag.
- **Who it's for:** see `INTENT.md`
- **Stack:** Python 3.11 with `requests`, and SEC's public company-facts API (`pitchcheck/sec.py`). Planned, not built: the OpenRouter API to pull the claims out of a pitch, and one HTML page.
- **Product Page:** `docs/index.md`, plain Markdown that GitHub Pages turns into the team's public page. Fill it only with facts from `INTENT.md` and `TEST_LOG.md`, and leave a [bracket] where the team has no answer yet.

## Commands

- **Install:** `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- **Run:** `python -m pitchcheck.sec --cik 64803` prints one issuer's filing figures. A ticker works in place of `--cik` once `SEC_USER_AGENT` is set in `.env`.
- **Check:** `python checks/check_sec.py`

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
