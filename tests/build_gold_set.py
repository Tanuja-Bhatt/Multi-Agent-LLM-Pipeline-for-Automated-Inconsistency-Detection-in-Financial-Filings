from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.vector_store import create_vector_store


CLAIMS = [
    {
        "id": "C01",
        "ticker": "AAPL",
        "query": "What were Apple's total net sales in 2022?",
        "terms": ["394,328"],
    },
    {
        "id": "C02",
        "ticker": "AAPL",
        "query": "What was Apple's net income in 2022?",
        "terms": ["99,803"],
    },
    {
        "id": "C03",
        "ticker": "AAPL",
        "query": "What were Apple's iPhone net sales in 2022?",
        "terms": ["205,489"],
    },
    {
        "id": "C04",
        "ticker": "AAPL",
        "query": "What was Apple's gross margin in 2022?",
        "terms": ["170,782"],
    },

    {
        "id": "C05",
        "ticker": "JPM",
        "query": "What was JPMorgan's total net revenue in 2022?",
        "terms": ["128,695"],
    },
    {
        "id": "C06",
        "ticker": "JPM",
        "query": "What was JPMorgan's net income in 2022?",
        "terms": ["37,676"],
    },
    {
        "id": "C07",
        "ticker": "JPM",
        "query": "What were JPMorgan's total assets at the end of 2022?",
        "terms": ["3,384,757"],
    },
    {
        "id": "C08",
        "ticker": "JPM",
        "query": "What was JPMorgan's provision for credit losses in 2022?",
        "terms": ["6,389"],
    },

    {
        "id": "C09",
        "ticker": "WMT",
        "query": "What were Walmart's total revenues in fiscal 2022?",
        "terms": ["572,754"],
    },
    {
        "id": "C10",
        "ticker": "WMT",
        "query": "What was Walmart's net income attributable to Walmart in fiscal 2022?",
        "terms": ["13,673"],
    },
    {
        "id": "C11",
        "ticker": "WMT",
        "query": "What was Walmart's operating income in fiscal 2022?",
        "terms": ["25,942"],
    },
    {
        "id": "C12",
        "ticker": "WMT",
        "query": "What were Walmart's total assets in fiscal 2022?",
        "terms": ["244,860"],
    },

    {
        "id": "C13",
        "ticker": "MSFT",
        "query": "What was Microsoft's revenue in fiscal 2022?",
        "terms": ["198,270"],
    },
    {
        "id": "C14",
        "ticker": "MSFT",
        "query": "What was Microsoft's net income in fiscal year 2022?",
        "terms": ["72,738"],
    },

    {
        "id": "C15",
        "ticker": "AMZN",
        "query": "What were Amazon's net sales in 2022?",
        "terms": ["513,983"],
    },
    {
        "id": "C16",
        "ticker": "AMZN",
        "query": "What was Amazon's operating income in 2022?",
        "terms": ["12,248"],
    },

    {
        "id": "C17",
        "ticker": "GOOGL",
        "query": "What was Google's revenue in 2022?",
        "terms": ["282,836"],
    },
    {
        "id": "C18",
        "ticker": "GOOGL",
        "query": "What was Google's net income in 2022?",
        "terms": ["59,972"],
    },

    {
        "id": "C19",
        "ticker": "INTC",
        "query": "What was Intel's net revenue in 2022?",
        "terms": ["63,054"],
    },
    {
        "id": "C20",
        "ticker": "INTC",
        "query": "What was Intel's net income in 2022?",
        "terms": ["8,017"],
    },
]


def main():
    store = create_vector_store()

    print("=" * 80)
    print("GOLD SET CANDIDATE INSPECTION")
    print("=" * 80)
    print(f"Collection count: {store.count()}")

    for claim in CLAIMS:
        print()
        print("=" * 80)
        print(
            f"{claim['id']} | {claim['ticker']} | "
            f"{claim['query']}"
        )
        print("=" * 80)

        results = store.retrieve(
            query=claim["query"],
            top_k=50,
        )

        candidates = []

        for rank, result in enumerate(results, 1):
            metadata = result.get("metadata", {})
            ticker = metadata.get("ticker")
            text = result.get("text", "")

            if ticker != claim["ticker"]:
                continue

            if all(term.lower() in text.lower() for term in claim["terms"]):
                candidates.append((rank, result))

        if not candidates:
            print("NO EXACT-VALUE CANDIDATE FOUND")
            continue

        print(f"Exact-value candidates: {len(candidates)}")

        for rank, result in candidates:
            metadata = result.get("metadata", {})

            print()
            print("-" * 80)
            print(f"RANK       : {rank}")
            print(f"CHUNK ID   : {result['chunk_id']}")
            print(f"SIMILARITY : {result['similarity']:.4f}")
            print(f"SECTION    : {metadata.get('section')}")
            print(f"SOURCE     : {metadata.get('source_location')}")
            print()
            print(result["text"])


if __name__ == "__main__":
    main()