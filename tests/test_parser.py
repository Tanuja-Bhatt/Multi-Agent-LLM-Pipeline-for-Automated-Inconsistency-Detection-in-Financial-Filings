from pathlib import Path
import json
import sys

# Project root = phase1/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "test_data"

# Make parse_filings.py importable regardless of where pytest/python is launched.
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from parse_filings import parse_filing
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        f"\nCould not import parse_filings.py.\n"
        f"Expected file:\n  {SCRIPTS_DIR / 'parse_filings.py'}\n"
        f"Current test file:\n  {Path(__file__).resolve()}\n"
        f"Project structure should be:\n"
        f"  phase1/\n"
        f"    scripts/parse_filings.py\n"
        f"    tests/test_parser.py\n"
        f"    test_data/AAPL_10K.html\n"
        f"    test_data/JPM_10K.html\n"
        f"    test_data/WMT_10K.html\n"
    ) from exc


TICKERS = ("AAPL", "JPM", "WMT")
EXPECTED_SECTIONS = (
    "MD&A",
    "FINANCIAL_STATEMENTS",
    "FOOTNOTES",
    "OTHER",
)


def main() -> None:
    print("Phase 1A parser test")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Data directory: {DATA_DIR}\n")

    if not SCRIPTS_DIR.joinpath("parse_filings.py").exists():
        raise FileNotFoundError(
            f"Missing parser: {SCRIPTS_DIR / 'parse_filings.py'}"
        )

    results = {}

    for ticker in TICKERS:
        html_path = DATA_DIR / f"{ticker}_10K.html"

        if not html_path.exists():
            raise FileNotFoundError(
                f"Missing {ticker} filing:\n  {html_path}\n"
                f"Make sure the original filing is inside test_data/ "
                f"and is named {ticker}_10K.html"
            )

        print(f"Parsing {ticker}...")
        blocks = parse_filing(html_path, ticker)

        if not blocks:
            raise RuntimeError(f"{ticker}: parser returned zero blocks.")

        counts = {
            section: sum(block["section"] == section for block in blocks)
            for section in EXPECTED_SECTIONS
        }

        results[ticker] = {
            "total_blocks": len(blocks),
            "section_counts": counts,
        }

        print(f"  total blocks: {len(blocks)}")
        print(f"  section counts: {counts}")

        # Print a small sample so we can manually sanity-check the output.
        for section in ("MD&A", "FINANCIAL_STATEMENTS", "FOOTNOTES"):
            sample = next(
                (b for b in blocks if b["section"] == section),
                None,
            )
            if sample:
                print(f"  {section}: {sample['text'][:180]}")

        output_path = DATA_DIR / f"{ticker}_parsed.json"
        output_path.write_text(
            json.dumps(blocks, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  saved: {output_path}\n")

    print("=== SUMMARY ===")
    print(json.dumps(results, indent=2))
    print("\nParser test completed.")


if __name__ == "__main__":
    main()
