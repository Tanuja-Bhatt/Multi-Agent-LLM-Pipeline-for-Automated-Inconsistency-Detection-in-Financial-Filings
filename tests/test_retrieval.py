from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.vector_store import create_vector_store


def main() -> None:

    store = create_vector_store()

    print("=" * 70)
    print("PHASE 1C - RETRIEVAL SMOKE TEST")
    print("=" * 70)

    print(f"Collection : {store.collection_name}")
    print(f"Count      : {store.count():,}")

    query = "What were Apple's total net sales?"

    print()
    print(f"Query: {query}")
    print()

    results = store.retrieve(
        query=query,
        top_k=5,
    )

    if not results:
        print("FAIL: No retrieval results returned.")
        raise SystemExit(1)

    print(f"Retrieved: {len(results)} results")
    print()

    required_metadata = [
        "document_id",
        "ticker",
        "section",
        "source_location",
    ]

    traceability_pass = True

    for rank, result in enumerate(results, start=1):

        metadata = result["metadata"]

        print("-" * 70)
        print(f"Rank       : {rank}")
        print(f"Chunk ID    : {result['chunk_id']}")
        print(f"Similarity : {result['similarity']:.4f}")

        print("Metadata:")
        for field in required_metadata:
            value = metadata.get(field, "")

            print(f"  {field}: {value}")

            if value in ("", None):
                traceability_pass = False

        print()
        print("Text:")
        print(result["text"][:800])

    print()
    print("=" * 70)

    if traceability_pass:
        print("PASS: Retrieval and source traceability verified.")
    else:
        print("FAIL: One or more required metadata fields are missing.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()