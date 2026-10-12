from pathlib import Path
import sys
import json
from collections import Counter


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "test_data"

sys.path.insert(0, str(SCRIPTS_DIR))

from parse_filings import parse_filing


# ============================================================
# CONFIGURATION
# ============================================================

REQUIRED_SECTIONS = {
    "MD&A",
    "FINANCIAL_STATEMENTS",
    "FOOTNOTES",
}


# ============================================================
# HELPERS
# ============================================================

def infer_ticker(file_path: Path) -> str:
    """
    Infer ticker from filename.

    Examples:
        AAPL_10K.html -> AAPL
        JPM_10K.html  -> JPM
        WMT_10K.html  -> WMT
    """

    return file_path.stem.split("_")[0].upper()


def get_section_counts(blocks):
    counts = Counter(
        block.get("section", "UNKNOWN")
        for block in blocks
    )

    return dict(counts)


def get_first_block(blocks, section):
    for block in blocks:
        if block.get("section") == section:
            return block

    return None


def validate_filing(file_path: Path):
    ticker = infer_ticker(file_path)

    try:
        blocks = parse_filing(
            file_path,
            ticker,
        )

        section_counts = get_section_counts(
            blocks
        )

        missing_sections = [
            section
            for section in REQUIRED_SECTIONS
            if section_counts.get(section, 0) == 0
        ]

        # --------------------------------------------------------
        # Basic structural checks
        # --------------------------------------------------------

        checks = {
            "has_blocks": len(blocks) > 0,
            "has_mdna": section_counts.get(
                "MD&A",
                0,
            ) > 0,
            "has_financial_statements": section_counts.get(
                "FINANCIAL_STATEMENTS",
                0,
            ) > 0,
            "has_footnotes": section_counts.get(
                "FOOTNOTES",
                0,
            ) > 0,
        }

        passed = all(checks.values())

        # --------------------------------------------------------
        # First section block information
        # --------------------------------------------------------

        first_blocks = {}

        for section in [
            "MD&A",
            "FINANCIAL_STATEMENTS",
            "FOOTNOTES",
        ]:

            block = get_first_block(
                blocks,
                section,
            )

            if block:

                first_blocks[section] = {
                    "text": block.get(
                        "text",
                        "",
                    )[:250],
                    "source_location": block.get(
                        "source_location"
                    ),
                }

        return {
            "file": file_path.name,
            "ticker": ticker,
            "status": "PASS" if passed else "FAIL",
            "total_blocks": len(blocks),
            "section_counts": section_counts,
            "missing_sections": missing_sections,
            "checks": checks,
            "first_blocks": first_blocks,
            "error": None,
        }

    except Exception as exc:

        return {
            "file": file_path.name,
            "ticker": ticker,
            "status": "ERROR",
            "total_blocks": 0,
            "section_counts": {},
            "missing_sections": list(
                REQUIRED_SECTIONS
            ),
            "checks": {},
            "first_blocks": {},
            "error": str(exc),
        }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("PHASE 1A - FULL CORPUS VALIDATION")
    print("=" * 70)

    print(
        f"Project root: {PROJECT_ROOT}"
    )

    print(
        f"Data directory: {DATA_DIR}"
    )

    # --------------------------------------------------------
    # Find all HTML filings
    # --------------------------------------------------------

    html_files = sorted(
        DATA_DIR.glob("*.html")
    )

    # Exclude accidental generated HTML files if any.
    html_files = [
        path
        for path in html_files
        if not path.name.lower().endswith(
            "_parsed.html"
        )
    ]

    print(
        f"\nHTML filings discovered: {len(html_files)}"
    )

    if not html_files:

        print(
            "\nERROR: No HTML filings found."
        )

        return

    print()

    # --------------------------------------------------------
    # Validate every filing
    # --------------------------------------------------------

    results = []

    for index, file_path in enumerate(
        html_files,
        start=1,
    ):

        print(
            f"[{index:02d}/{len(html_files):02d}] "
            f"{file_path.name}"
        )

        result = validate_filing(
            file_path
        )

        results.append(result)

        status_symbol = (
            "✓"
            if result["status"] == "PASS"
            else "✗"
        )

        print(
            f"    {status_symbol} "
            f"{result['status']}"
        )

        print(
            f"    Blocks: "
            f"{result['total_blocks']}"
        )

        print(
            f"    Sections: "
            f"{result['section_counts']}"
        )

        if result["missing_sections"]:

            print(
                "    Missing: "
                + ", ".join(
                    result["missing_sections"]
                )
            )

        if result["error"]:

            print(
                f"    Error: "
                f"{result['error']}"
            )

        print()

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    passed = [
        result
        for result in results
        if result["status"] == "PASS"
    ]

    failed = [
        result
        for result in results
        if result["status"] == "FAIL"
    ]

    errors = [
        result
        for result in results
        if result["status"] == "ERROR"
    ]

    print("=" * 70)
    print("FULL CORPUS SUMMARY")
    print("=" * 70)

    print(
        f"Total HTML filings: {len(results)}"
    )

    print(
        f"Passed: {len(passed)}"
    )

    print(
        f"Failed: {len(failed)}"
    )

    print(
        f"Errors: {len(errors)}"
    )

    # --------------------------------------------------------
    # Detailed failures
    # --------------------------------------------------------

    if failed:

        print("\nFILINGS REQUIRING INSPECTION")
        print("-" * 70)

        for result in failed:

            print(
                f"\n{result['file']}"
            )

            print(
                f"Missing sections: "
                f"{result['missing_sections']}"
            )

            print(
                f"Section counts: "
                f"{result['section_counts']}"
            )

            print(
                f"First blocks: "
                f"{json.dumps(result['first_blocks'], indent=2)}"
            )

    if errors:

        print("\nFILINGS WITH PARSER ERRORS")
        print("-" * 70)

        for result in errors:

            print(
                f"{result['file']}: "
                f"{result['error']}"
            )

    # --------------------------------------------------------
    # Save validation report
    # --------------------------------------------------------

    report_path = (
        DATA_DIR /
        "phase1a_corpus_validation.json"
    )

    report = {
        "total_files": len(results),
        "passed": len(passed),
        "failed": len(failed),
        "errors": len(errors),
        "results": results,
    }

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"\nValidation report saved:"
    )

    print(
        report_path
    )

    print(
        "\nPhase 1A full-corpus validation complete."
    )


if __name__ == "__main__":
    main()