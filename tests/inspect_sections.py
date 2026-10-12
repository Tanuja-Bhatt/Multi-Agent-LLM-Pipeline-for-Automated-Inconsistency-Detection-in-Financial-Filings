from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "test_data"

TICKERS = ("AAPL", "JPM", "WMT")
SECTIONS = ("MD&A", "FINANCIAL_STATEMENTS", "FOOTNOTES", "OTHER")


def inspect_file(ticker):
    json_path = DATA_DIR / f"{ticker}_parsed.json"

    if not json_path.exists():
        print(f"\nERROR: {json_path} not found")
        return

    blocks = json.loads(
        json_path.read_text(encoding="utf-8")
    )

    print("\n" + "=" * 80)
    print(f"{ticker} SECTION INSPECTION")
    print("=" * 80)

    for section in SECTIONS:
        section_blocks = [
            block
            for block in blocks
            if block["section"] == section
        ]

        print(f"\n--- {section} ---")
        print(f"Block count: {len(section_blocks)}")

        if not section_blocks:
            print("NO BLOCKS FOUND")
            continue

        first = section_blocks[0]
        last = section_blocks[-1]

        print("\nFIRST BLOCK:")
        print(f"Location: {first['source_location']}")
        print(f"Text: {first['text'][:500]}")

        print("\nLAST BLOCK:")
        print(f"Location: {last['source_location']}")
        print(f"Text: {last['text'][:500]}")

    # Show section transitions.
    print("\n--- SECTION TRANSITIONS ---")

    previous = None
    transition_count = 0

    for block in blocks:
        current = block["section"]

        if current != previous:
            transition_count += 1
            print(
                f"{transition_count}. "
                f"{previous or '[START]'} -> {current} "
                f"| {block['source_location']}"
            )
            print(f"   {block['text'][:250]}")

            previous = current

    # Look for obvious TOC contamination.
    print("\n--- POSSIBLE TOC CONTAMINATION ---")

    toc_terms = (
        "table of contents",
        "index to consolidated financial statements",
        "page",
    )

    suspicious = []

    for block in blocks:
        text = block["text"].lower()

        if (
            "index to consolidated financial statements" in text
            or "table of contents" in text
        ):
            suspicious.append(block)

    print(f"Possible TOC blocks: {len(suspicious)}")

    for block in suspicious[:10]:
        print(
            f"- {block['section']} | "
            f"{block['source_location']}"
        )
        print(f"  {block['text'][:300]}")


def main():
    print("PHASE 1A SECTION VALIDATION")

    for ticker in TICKERS:
        inspect_file(ticker)

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()