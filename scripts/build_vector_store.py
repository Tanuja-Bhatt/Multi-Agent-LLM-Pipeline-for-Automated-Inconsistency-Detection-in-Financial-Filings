from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------

from scripts.parse_filings import parse_filing
from scripts.chunk_text import chunk_blocks
from scripts.vector_store import (
    FinancialFilingsVectorStore,
    DEFAULT_DB_PATH,
    DEFAULT_COLLECTION_NAME,
)


# ---------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------

DEFAULT_BATCH_SIZE = 500


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def ticker_from_path(path: Path) -> str:
    """
    Extract ticker from filenames such as:

        AAPL_10K.html
        JPM_10K.html
        WMT_10K.html
    """
    return path.stem.split("_")[0].upper()


def build_chunks_for_file(
    html_path: Path,
) -> tuple[str, list[dict]]:
    """
    Parse one filing and convert it into retrieval-ready chunks.
    """

    ticker = ticker_from_path(html_path)

    print(f"\nProcessing {ticker}...")
    print(f"File: {html_path.name}")

    # Phase 1A
    blocks = parse_filing(
        str(html_path),
        ticker,
    )

    print(f"  Parsed blocks: {len(blocks):,}")

    # Phase 1B
    chunks = chunk_blocks(
        blocks,
        document_id=html_path.stem,
        ticker=ticker,
    )

    print(f"  Generated chunks: {len(chunks):,}")

    return ticker, chunks


# ---------------------------------------------------------------------
# Main build process
# ---------------------------------------------------------------------

def build_vector_store(
    data_dir: Path,
    db_path: Path,
    collection_name: str,
    batch_size: int,
    limit: int | None = None,
    reset: bool = False,
) -> int:

    html_files = sorted(data_dir.glob("*.html"))

    if not html_files:
        raise FileNotFoundError(
            f"No HTML filings found in: {data_dir}"
        )

    if limit is not None:
        html_files = html_files[:limit]

    print("=" * 70)
    print("PHASE 1C - VECTOR STORE BUILD")
    print("=" * 70)

    print(f"HTML filings found : {len(html_files)}")
    print(f"Database path      : {db_path}")
    print(f"Collection         : {collection_name}")
    print(f"Batch size         : {batch_size}")
    print(f"Reset              : {reset}")
    print()

    # -------------------------------------------------------------
    # Create Chroma store
    # -------------------------------------------------------------

    if reset and db_path.exists():
        print("Reset requested.")
        print(
            "Existing Chroma database will be removed "
            "before rebuilding."
        )

        import shutil

        shutil.rmtree(db_path)

    store = FinancialFilingsVectorStore(
        db_path=db_path,
        collection_name=collection_name,
    )

    # -------------------------------------------------------------
    # Process filings
    # -------------------------------------------------------------

    total_blocks = 0
    total_chunks = 0
    processed_files = 0

    for html_path in html_files:

        ticker, chunks = build_chunks_for_file(
            html_path
        )

        total_blocks += 0  # retained for future parser statistics
        total_chunks += len(chunks)

        # ---------------------------------------------------------
        # Insert into Chroma
        # ---------------------------------------------------------

        inserted = store.upsert_chunks(
            chunks,
            batch_size=batch_size,
        )

        print(
            f"  Upserted into Chroma: {inserted:,}"
        )

        processed_files += 1

        print(
            f"  Collection count: "
            f"{store.count():,}"
        )

    # -------------------------------------------------------------
    # Final summary
    # -------------------------------------------------------------

    final_count = store.count()

    print()
    print("=" * 70)
    print("VECTOR STORE BUILD COMPLETE")
    print("=" * 70)

    print(f"Files processed       : {processed_files:,}")
    print(f"Chunks generated      : {total_chunks:,}")
    print(f"Chroma collection     : {collection_name}")
    print(f"Final collection size : {final_count:,}")
    print(f"Database path         : {db_path}")

    if final_count != total_chunks:
        print()
        print(
            "WARNING: Final collection count does not match "
            "the number of generated chunks."
        )
    else:
        print()
        print("PASS: All generated chunks are indexed.")

    return final_count


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Build the Phase 1C ChromaDB vector store "
            "from parsed SEC filings."
        )
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "test_data",
        help="Directory containing HTML filings.",
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Persistent ChromaDB directory.",
    )

    parser.add_argument(
        "--collection",
        type=str,
        default=DEFAULT_COLLECTION_NAME,
        help="Chroma collection name.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of chunks inserted per Chroma batch.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N filings.",
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the existing Chroma database before rebuilding.",
    )

    return parser.parse_args()


def main() -> None:

    args = parse_args()

    build_vector_store(
        data_dir=args.data_dir,
        db_path=args.db_path,
        collection_name=args.collection,
        batch_size=args.batch_size,
        limit=args.limit,
        reset=args.reset,
    )


if __name__ == "__main__":
    main()