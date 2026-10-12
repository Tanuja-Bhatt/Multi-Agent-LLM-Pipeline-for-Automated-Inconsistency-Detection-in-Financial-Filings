from pathlib import Path
import sys
import re

# ---------------------------------------------------------
# Make project root importable when running:
# python tests/retrieval_eval.py
# ---------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.vector_store import FinancialFilingsVectorStore


# =========================================================
# Configuration
# =========================================================

TOP_K_VALUES = [1, 3, 5]


CLAIMS = [
    {
        "id": "C01",
        "ticker": "AAPL",
        "query": "What were Apple's total net sales in 2022?",
        "gold_chunk_ids": [
            "AAPL_10K_7ee7322144cd_0166"
        ],
        "evidence_patterns": [
            r"total\s+net\s+sales",
            r"394,328"
        ],
    },
    {
        "id": "C02",
        "ticker": "AAPL",
        "query": "What was Apple's net income in 2022?",
        "gold_chunk_ids": [
            "AAPL_10K_e3eaa053c697_0201"
        ],
        "evidence_patterns": [
            r"net\s+income",
            r"99,803",
        ],
    },
    {
        "id": "C03",
        "ticker": "AAPL",
        "query": "What were Apple's iPhone net sales in 2022?",
        "gold_chunk_ids": [
            "AAPL_10K_7ee7322144cd_0166"
        ],
        "evidence_patterns": [
            r"iphone",
            r"205,489",
        ],
    },
    {
        "id": "C04",
        "ticker": "AAPL",
        "query": "What was Apple's gross margin in 2022?",
        "gold_chunk_ids": [
            "AAPL_10K_896df8a69ca5_0172"
        ],
        "evidence_patterns": [
            r"gross\s+margin",
            r"170,782",
        ],
    },

    {
        "id": "C05",
        "ticker": "JPM",
        "query": "What was JPMorgan's total net revenue in 2022?",
        "gold_chunk_ids": [
            "JPM_10K_fc956b2fc902_0308"
        ],
        "evidence_patterns": [
            r"total\s+net\s+revenue",
            r"(128,695|128\.7\s+billion)",
        ],
    },
    {
        "id": "C06",
        "ticker": "JPM",
        "query": "What was JPMorgan's net income in 2022?",
        "gold_chunk_ids": [
            "JPM_10K_fc956b2fc902_0308"
        ],
        "evidence_patterns": [
            r"net\s+income",
            r"(37,676|37\.7\s+billion)",
        ],
    },
    {
        "id": "C07",
        "ticker": "JPM",
        "query": "What were JPMorgan's total assets at the end of 2022?",
        "gold_chunk_ids": [
            "JPM_10K_eac1f2aa5e67_1626"
        ],
        "evidence_patterns": [
            r"total\s+assets",
            r"3,384,757",
        ],
    },
    {
        "id": "C08",
        "ticker": "JPM",
        "query": "What was JPMorgan's provision for credit losses in 2022?",
        "gold_chunk_ids": [
            "JPM_10K_4e821754008e_0352"
        ],
        "evidence_patterns": [
            r"provision\s+for\s+credit\s+losses",
            r"6,389",
        ],
    },

    {
        "id": "C09",
        "ticker": "WMT",
        "query": "What were Walmart's total revenues in fiscal 2022?",
        "gold_chunk_ids": [
            "WMT_10K_d0c7d0b60069_0379"
        ],
        "evidence_patterns": [
            r"total\s+revenues",
            r"572,754",
        ],
    },
    {
        "id": "C10",
        "ticker": "WMT",
        "query": "What was Walmart's net income attributable to Walmart in fiscal 2022?",
        "gold_chunk_ids": [
            "WMT_10K_8c4d0d0cb35d_0439"
        ],
        "evidence_patterns": [
            r"net\s+income\s+attributable\s+to\s+walmart",
            r"13,673",
        ],
    },
    {
        "id": "C11",
        "ticker": "WMT",
        "query": "What was Walmart's operating income in fiscal 2022?",
        "gold_chunk_ids": [
            "WMT_10K_30bb6f3a4e83_0380"
        ],
        "evidence_patterns": [
            r"operating\s+income",
            r"25,942",
        ],
    },
    {
    "id": "C12",
    "ticker": "WMT",
    "query": "What were Walmart's total assets in fiscal 2022?",
    "gold_chunk_ids": [
        "WMT_10K_17261b986731_0383"
    ],
    "evidence_patterns": [
        r"total\s+assets",
        r"244,860",
    ],
},

    {
        "id": "C13",
        "ticker": "MSFT",
        "query": "What was Microsoft's revenue in fiscal 2022?",
        "gold_chunk_ids": [
            "MSFT_2022_931c925d17c7_0254"
        ],
        "evidence_patterns": [
            r"revenue",
            r"198,270",
        ],
    },
    {
        "id": "C14",
        "ticker": "MSFT",
        "query": "What was Microsoft's net income in fiscal year 2022?",
        "gold_chunk_ids": [
            "MSFT_2022_931c925d17c7_0254"
        ],
        "evidence_patterns": [
            r"net\s+income",
            r"72,738",
        ],
    },

    {
        "id": "C15",
        "ticker": "AMZN",
        "query": "What were Amazon's net sales in 2022?",
        "gold_chunk_ids": [
            "AMZN_2022_85558b6d8228_0224"
        ],
        "evidence_patterns": [
            r"net\s+sales",
            r"513,983",
        ],
    },
    {
        "id": "C16",
        "ticker": "AMZN",
        "query": "What was Amazon's operating income in 2022?",
        "gold_chunk_ids": [
            "AMZN_2022_85558b6d8228_0224"
        ],
        "evidence_patterns": [
            r"operating\s+income",
            r"12,248",
        ],
    },

    {
        "id": "C17",
        "ticker": "GOOGL",
        "query": "What was Google's revenue in 2022?",
        "gold_chunk_ids": [
            "GOOGL_2022_a50a51510f18_0348"
        ],
        "evidence_patterns": [
            r"(total\s+revenues|revenue)",
            r"282,836",
        ],
    },
    {
        "id": "C18",
        "ticker": "GOOGL",
        "query": "What was Google's net income in 2022?",
        "gold_chunk_ids": [
            "GOOGL_2022_48b4ac57d1d5_0296"
        ],
        "evidence_patterns": [
            r"net\s+income",
            r"59,972",
        ],
    },

    {
        "id": "C19",
        "ticker": "INTC",
        "query": "What was Intel's net revenue in 2022?",
        "gold_chunk_ids": [
            "INTC_2022_95d7c23ed204_0570"
        ],
        "evidence_patterns": [
            r"net\s+revenue",
            r"63,054",
        ],
    },
    {
        "id": "C20",
        "ticker": "INTC",
        "query": "What was Intel's net income in 2022?",
        "gold_chunk_ids": [
            "INTC_2022_e8de034f487f_0575"
        ],
        "evidence_patterns": [
            r"net\s+income",
            r"8,017",
        ],
    },
]


# =========================================================
# Helper functions
# =========================================================

def normalize(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def contains_all_patterns(text, patterns):
    """
    Evidence is considered present only when ALL required
    patterns occur in the same retrieved chunk.
    """
    text = normalize(text)

    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE) is None:
            return False

    return True


def ticker_matches(metadata, ticker):
    value = metadata.get("ticker")

    if isinstance(value, list):
        return ticker in value

    return value == ticker


def canonical_hit(results, gold_ids):
    for rank, result in enumerate(results, start=1):
        if result["chunk_id"] in gold_ids:
            return rank

    return None


def evidence_hit(results, claim):
    """
    Returns the first rank containing answer-bearing evidence
    from the correct ticker.
    """
    for rank, result in enumerate(results, start=1):

        metadata = result.get("metadata", {})

        if not ticker_matches(metadata, claim["ticker"]):
            continue

        if contains_all_patterns(
            result.get("text", ""),
            claim["evidence_patterns"]
        ):
            return rank

    return None


# =========================================================
# Evaluation
# =========================================================

def main():

    store = FinancialFilingsVectorStore()

    canonical_hits = {k: 0 for k in TOP_K_VALUES}
    evidence_hits = {k: 0 for k in TOP_K_VALUES}

    canonical_ranks = {}
    evidence_ranks = {}

    print("=" * 80)
    print("PHASE 1C RETRIEVAL EVALUATION")
    print("=" * 80)
    print(f"Collection size: {store.count()}")
    print(f"Claims: {len(CLAIMS)}")
    print()

    for claim in CLAIMS:

        # Retrieve top 20 so we can inspect beyond top 5
        results = store.retrieve(
    claim["query"],
    top_k=20,
    ticker=claim["ticker"]
)

        c_rank = canonical_hit(
            results,
            claim["gold_chunk_ids"]
        )

        e_rank = evidence_hit(
            results,
            claim
        )

        canonical_ranks[claim["id"]] = c_rank
        evidence_ranks[claim["id"]] = e_rank

        for k in TOP_K_VALUES:

            if c_rank is not None and c_rank <= k:
                canonical_hits[k] += 1

            if e_rank is not None and e_rank <= k:
                evidence_hits[k] += 1

        print(
            f"{claim['id']} | "
            f"canonical_rank={c_rank} | "
            f"evidence_rank={e_rank}"
        )

    print()
    print("=" * 80)
    print("CANONICAL CHUNK RECALL")
    print("=" * 80)

    for k in TOP_K_VALUES:
        hits = canonical_hits[k]
        total = len(CLAIMS)
        recall = hits / total

        print(
            f"Canonical Recall@{k}: "
            f"{hits}/{total} ({recall:.2%})"
        )

    print()
    print("=" * 80)
    print("EVIDENCE-BASED RECALL")
    print("=" * 80)

    for k in TOP_K_VALUES:
        hits = evidence_hits[k]
        total = len(CLAIMS)
        recall = hits / total

        print(
            f"Evidence Recall@{k}: "
            f"{hits}/{total} ({recall:.2%})"
        )

    print()
    print("=" * 80)
    print("CLAIMS WITH NO EVIDENCE IN TOP 20")
    print("=" * 80)

    unresolved = []

    for claim in CLAIMS:
        if evidence_ranks[claim["id"]] is None:
            unresolved.append(claim["id"])

    if unresolved:
        print(", ".join(unresolved))
    else:
        print("None")

    print()
    print("=" * 80)
    print("PHASE 1C EVALUATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()