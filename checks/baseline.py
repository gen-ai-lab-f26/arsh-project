"""Run the plain-chat baseline: paste a pitch into a chat model and ask it to check the numbers.

Run it:  python checks/baseline.py pitches/some_deck.pptx [more decks]

The model gets the same deck text PitchCheck reads and one fixed prompt, with
no tools and no SEC data. Each answer is saved next to the decks in
pitches/baseline/, which Git ignores. Score the answers by hand against the
catches written down in TEST_LOG.md before the run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pitchcheck.deck import read_deck  # noqa: E402
from pitchcheck.llm import DEFAULT_MODEL, chat  # noqa: E402

PROMPT = """I'm reviewing this bond pitch before our investment committee votes. \
Please check the numbers for me.

1. List every financial figure that does not match the company's latest SEC \
filings, and give the correct figure.
2. List every number the pitch states two different ways.

Quote the pitch text for each item. If you can't verify a number, say so.

<pitch>
{deck}
</pitch>"""


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__)
        return 1
    out_dir = Path(paths[0]).resolve().parent / "baseline"
    out_dir.mkdir(exist_ok=True)
    for path in paths:
        deck = read_deck(path)
        result = chat(PROMPT.format(deck=deck))
        name = Path(path).stem
        (out_dir / f"{name}.md").write_text(result["text"])
        (out_dir / f"{name}.usage.json").write_text(
            json.dumps({"model": result["model"], "usage": result["usage"]}, indent=2)
        )
        usage = result["usage"]
        print(
            f"{name}: {len(deck):,} characters in, "
            f"{usage.get('prompt_tokens')} + {usage.get('completion_tokens')} tokens, "
            f"cost ${usage.get('cost')}, saved to {out_dir / (name + '.md')}"
        )
    print(f"Model: {DEFAULT_MODEL}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
