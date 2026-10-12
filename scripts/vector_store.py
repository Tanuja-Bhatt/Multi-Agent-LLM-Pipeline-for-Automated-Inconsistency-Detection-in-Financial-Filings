from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "chroma"
DEFAULT_COLLECTION_NAME = "financial_filings_2022"


class FinancialFilingsVectorStore:
    """
    Chroma-backed vector store for SEC financial filing chunks.

    Retrieval pipeline:

        1. Semantic retrieval
        2. Lexical overlap
        3. Financial phrase matching
        4. Financial/table-context signals
        5. Hybrid reranking
        6. Structural adjacency expansion

    Important:
    - Does NOT use gold answers.
    - Does NOT use expected numeric values.
    - Does NOT modify the existing Chroma vectors.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.collection_name = collection_name

        self.db_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.db_path)
        )

        self.embedding_function = DefaultEmbeddingFunction()

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

        self._document_section_index = (
            self._build_document_section_index()
        )

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build_document_section_index(self) -> Dict[Tuple[str, str], List[Dict]]:
        """
        Build a structural index so chunks can be expanded using
        document + section + DOM order.
        """

        try:
            data = self.collection.get(
                include=["documents", "metadatas"],
                limit=100000,
            )
        except Exception:
            return {}

        ids = data.get("ids", [])
        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])

        index: Dict[Tuple[str, str], List[Dict]] = {}

        for chunk_id, document, metadata in zip(
            ids,
            documents,
            metadatas,
        ):
            metadata = metadata or {}

            document_id = metadata.get("document_id")
            section = metadata.get("section")

            if not document_id or not section:
                continue

            dom_index = self._extract_first_dom_index(
                metadata.get("dom_index")
            )

            key = (document_id, section)

            index.setdefault(key, []).append(
                {
                    "id": chunk_id,
                    "document": document or "",
                    "metadata": metadata,
                    "dom_index": dom_index,
                }
            )

        for key in index:
            index[key].sort(
                key=lambda item: (
                    item["dom_index"]
                    if item["dom_index"] is not None
                    else float("inf")
                )
            )

        return index

    @staticmethod
    def _extract_first_dom_index(value: Any) -> Optional[int]:
        if value is None:
            return None

        text = str(value)

        match = re.search(r"\d+", text)

        if not match:
            return None

        try:
            return int(match.group())
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Chunk insertion
    # ------------------------------------------------------------------

    def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        batch_size: int = 500,
    ) -> int:
        """
        Upsert retrieval-ready chunks into Chroma.

        Required chunk fields:
            id
            text
            section
            document_id
            ticker
            source_location
        """

        if not chunks:
            return 0

        prepared_ids = []
        prepared_documents = []
        prepared_metadatas = []

        for chunk in chunks:
            chunk_id = chunk.get("id") or chunk.get("chunk_id")
            text = chunk.get("text")

            if not chunk_id:
                raise ValueError(
                    "Chunk is missing required 'id'/'chunk_id'."
                )

            if not text or not str(text).strip():
                raise ValueError(
                    f"Chunk {chunk_id} has empty text."
                )

            metadata = {
                "document_id": chunk.get("document_id", ""),
                "ticker": chunk.get("ticker", ""),
                "section": chunk.get("section", ""),
                "source_location": chunk.get(
                    "source_location",
                    "",
                ),
            }

            # Chroma metadata cannot contain None.
            for key, value in list(metadata.items()):
                if value is None:
                    metadata[key] = ""

            if chunk.get("dom_index") is not None:
                metadata["dom_index"] = str(
                    chunk.get("dom_index")
                )

            if chunk.get("page") is not None:
                metadata["page"] = str(
                    chunk.get("page")
                )

            prepared_ids.append(str(chunk_id))
            prepared_documents.append(str(text))
            prepared_metadatas.append(metadata)

        total = 0

        for start in range(
            0,
            len(prepared_ids),
            batch_size,
        ):
            end = start + batch_size

            self.collection.upsert(
                ids=prepared_ids[start:end],
                documents=prepared_documents[start:end],
                metadatas=prepared_metadatas[start:end],
            )

            total += len(prepared_ids[start:end])

        # Refresh structural index after writes.
        self._document_section_index = (
            self._build_document_section_index()
        )

        return total

    # ------------------------------------------------------------------
    # Tokenization
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """
        Tokenize words and financial numeric expressions.
        """

        if not text:
            return []

        return re.findall(
            r"[a-zA-Z]+(?:'[a-zA-Z]+)?|\d[\d,.%$()-]*",
            text.lower(),
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(
            r"\s+",
            " ",
            (text or "").lower(),
        ).strip()

    # ------------------------------------------------------------------
    # Lexical scoring
    # ------------------------------------------------------------------

    def _lexical_score(
        self,
        query: str,
        document: str,
    ) -> float:
        """
        Basic query-token overlap.
        """

        query_tokens = set(
            self._tokenize(query)
        )

        document_tokens = set(
            self._tokenize(document)
        )

        if not query_tokens:
            return 0.0

        overlap = query_tokens.intersection(
            document_tokens
        )

        return len(overlap) / len(query_tokens)

    # ------------------------------------------------------------------
    # Financial phrase extraction
    # ------------------------------------------------------------------

    def _extract_financial_phrases(
        self,
        query: str,
    ) -> List[str]:
        """
        Identify financial concepts directly from the user's query.

        This uses ONLY the query. It does not know the expected answer.
        """

        normalized = self._normalize_text(query)

        phrase_patterns = [
            "total net sales",
            "net sales",
            "total net revenue",
            "net revenue",
            "total revenues",
            "revenue",
            "net income attributable to walmart",
            "net income",
            "operating income",
            "gross margin",
            "total assets",
            "total liabilities",
            "provision for credit losses",
            "credit losses",
            "cash and cash equivalents",
            "accounts receivable",
            "inventory",
            "long term debt",
            "short term borrowings",
            "operating expenses",
            "income from operations",
            "earnings per share",
            "diluted earnings per share",
            "basic earnings per share",
            "research and development",
            "selling general and administrative",
        ]

        matches = []

        for phrase in phrase_patterns:
            if phrase in normalized:
                matches.append(phrase)

        # Longest phrases should dominate shorter overlapping phrases.
        matches.sort(
            key=len,
            reverse=True,
        )

        return matches

    def _financial_phrase_score(
        self,
        query: str,
        document: str,
    ) -> float:
        """
        Score exact financial phrases shared by query and chunk.
        """

        phrases = self._extract_financial_phrases(
            query
        )

        if not phrases:
            return 0.0

        normalized_document = self._normalize_text(
            document
        )

        matched = 0

        for phrase in phrases:
            if phrase in normalized_document:
                matched += 1

        return matched / len(phrases)

    # ------------------------------------------------------------------
    # Table / financial context
    # ------------------------------------------------------------------

    def _financial_context_score(
        self,
        query: str,
        document: str,
    ) -> float:
        """
        Detect whether a chunk looks like a financial statement/table
        relevant to the query.

        This is query-driven and answer-independent.
        """

        text = self._normalize_text(document)
        query_text = self._normalize_text(query)

        score = 0.0

        financial_table_terms = [
            "total assets",
            "total liabilities",
            "total revenue",
            "total revenues",
            "net income",
            "operating income",
            "gross margin",
            "net sales",
            "net revenue",
            "provision for credit losses",
            "cash and cash equivalents",
            "accounts payable",
            "accounts receivable",
            "inventory",
            "long-term debt",
            "short-term borrowings",
        ]

        matched_terms = 0

        for term in financial_table_terms:
            if term in query_text and term in text:
                matched_terms += 1

        if matched_terms:
            score += min(
                matched_terms / 2.0,
                1.0,
            )

        # Financial table chunks commonly contain several numeric values.
        numeric_tokens = re.findall(
            r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b",
            document,
        )

        if len(numeric_tokens) >= 2:
            score += 0.15

        # Common financial-statement language.
        statement_terms = [
            "year ended",
            "years ended",
            "fiscal year",
            "balance sheet",
            "statements of operations",
            "statements of income",
            "consolidated statements",
            "income statement",
            "cash flows",
            "financial statements",
        ]

        statement_matches = sum(
            1
            for term in statement_terms
            if term in text
        )

        if statement_matches:
            score += min(
                statement_matches * 0.10,
                0.30,
            )

        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Query type
    # ------------------------------------------------------------------

    def _query_type(self, query: str) -> str:
        """
        Determine the broad financial query type.
        """

        text = self._normalize_text(query)

        if "total assets" in text:
            return "assets"

        if "net income" in text:
            return "net_income"

        if "operating income" in text:
            return "operating_income"

        if "gross margin" in text:
            return "gross_margin"

        if "provision for credit losses" in text:
            return "credit_losses"

        if "net revenue" in text:
            return "revenue"

        if "net sales" in text:
            return "sales"

        if "revenue" in text:
            return "revenue"

        return "general"

    # ------------------------------------------------------------------
    # Combined score
    # ------------------------------------------------------------------

    def _combined_score(
        self,
        query: str,
        document: str,
        semantic_similarity: float,
    ) -> float:
        """
        Production query-time reranking score.

        No gold answers or expected numeric values are used.
        """

        lexical = self._lexical_score(
            query,
            document,
        )

        phrase = self._financial_phrase_score(
            query,
            document,
        )

        financial_context = self._financial_context_score(
            query,
            document,
        )

        query_type = self._query_type(query)

        # Base weights.
        semantic_weight = 0.50
        lexical_weight = 0.20
        phrase_weight = 0.20
        context_weight = 0.10

        # Financial fact queries benefit more from exact phrase/table
        # matching because embeddings can prefer narrative sections.
        if query_type != "general":
            semantic_weight = 0.40
            lexical_weight = 0.20
            phrase_weight = 0.25
            context_weight = 0.15

        score = (
            semantic_weight * semantic_similarity
            + lexical_weight * lexical
            + phrase_weight * phrase
            + context_weight * financial_context
        )

        return score

    # ------------------------------------------------------------------
    # Semantic candidates
    # ------------------------------------------------------------------

    def _semantic_candidates(
        self,
        query: str,
        top_k: int,
        ticker: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve a larger semantic candidate pool before reranking.
        """

        candidate_k = max(
            top_k * 10,
            100,
        )

        where = None

        if ticker:
            where = {
                "ticker": ticker,
            }

        result = self.collection.query(
            query_texts=[query],
            n_results=candidate_k,
            where=where,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        ids = result.get("ids", [[]])[0]
        documents = result.get(
            "documents",
            [[]],
        )[0]

        metadatas = result.get(
            "metadatas",
            [[]],
        )[0]

        distances = result.get(
            "distances",
            [[]],
        )[0]

        candidates = []

        for chunk_id, document, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
        ):
            metadata = metadata or {}

            similarity = max(
                0.0,
                min(
                    1.0,
                    1.0 - float(distance),
                ),
            )

            score = self._combined_score(
                query,
                document or "",
                similarity,
            )

            candidates.append(
                {
                    "id": chunk_id,
                    "document": document or "",
                    "metadata": metadata,
                    "distance": float(distance),
                    "similarity": similarity,
                    "score": score,
                }
            )

        candidates.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return candidates

    # ------------------------------------------------------------------
    # Structural adjacency
    # ------------------------------------------------------------------

    def _expand_with_neighbors(
        self,
        candidates: List[Dict[str, Any]],
        max_seed_candidates: int = 10,
        window: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Add structurally adjacent chunks from the same document + section.
        """

        expanded: Dict[str, Dict[str, Any]] = {
            candidate["id"]: candidate
            for candidate in candidates
        }

        for candidate in candidates[:max_seed_candidates]:
            metadata = candidate.get(
                "metadata",
                {},
            )

            document_id = metadata.get(
                "document_id"
            )

            section = metadata.get(
                "section"
            )

            if not document_id or not section:
                continue

            key = (
                document_id,
                section,
            )

            ordered_chunks = (
                self._document_section_index.get(
                    key,
                    [],
                )
            )

            if not ordered_chunks:
                continue

            current_position = None

            for index, item in enumerate(
                ordered_chunks
            ):
                if item["id"] == candidate["id"]:
                    current_position = index
                    break

            if current_position is None:
                continue

            for offset in range(
                -window,
                window + 1,
            ):
                if offset == 0:
                    continue

                neighbor_position = (
                    current_position + offset
                )

                if (
                    neighbor_position < 0
                    or neighbor_position >= len(
                        ordered_chunks
                    )
                ):
                    continue

                neighbor = ordered_chunks[
                    neighbor_position
                ]

                if neighbor["id"] in expanded:
                    continue

                similarity = candidate[
                    "similarity"
                ]

                lexical = self._lexical_score(
                    "",
                    neighbor["document"],
                )

                expanded[
                    neighbor["id"]
                ] = {
                    "id": neighbor["id"],
                    "document": neighbor[
                        "document"
                    ],
                    "metadata": neighbor[
                        "metadata"
                    ],
                    "distance": None,
                    "similarity": similarity * 0.85,
                    "score": candidate[
                        "score"
                    ] * 0.70,
                }

        return list(expanded.values())

    # ------------------------------------------------------------------
    # Public retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        ticker: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k relevant chunks.

        Returns:
            [
                {
                    "id": ...,
                    "text": ...,
                    "metadata": ...,
                    "score": ...,
                    "similarity": ...
                }
            ]
        """

        if not query or not query.strip():
            return []

        candidates = self._semantic_candidates(
            query=query,
            top_k=top_k,
            ticker=ticker,
        )

        # Structural context expansion.
        expanded = self._expand_with_neighbors(
            candidates,
            max_seed_candidates=10,
            window=1,
        )

        # Re-score expanded candidates using the same
        # query-driven scoring logic.
        final_candidates = []

        for candidate in expanded:
            document = candidate.get(
                "document",
                "",
            )

            similarity = candidate.get(
                "similarity",
                0.0,
            )

            score = self._combined_score(
                query,
                document,
                similarity,
            )

            candidate["score"] = score

            final_candidates.append(
                candidate
            )

        final_candidates.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        results = []

        for candidate in final_candidates[:top_k]:
            results.append(
    {
        "id": candidate["id"],
        "chunk_id": candidate["id"],
        "text": candidate["document"],
        "metadata": candidate["metadata"],
        "score": candidate["score"],
        "similarity": candidate["similarity"],
    }
)

        return results

    # ------------------------------------------------------------------
    # Collection utilities
    # ------------------------------------------------------------------

    def count(self) -> int:
        return self.collection.count()

    def reset_collection(self) -> None:
        """
        Delete and recreate the collection.

        This is intentionally explicit because retrieval development
        should not accidentally destroy the existing corpus.
        """

        try:
            self.client.delete_collection(
                self.collection_name
            )
        except Exception:
            pass

        self.collection = (
            self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
        )

        self._document_section_index = {}

    def reset_collection(self):
        """
        Delete and recreate the Chroma collection.
        """
        try:
            self.client.delete_collection(name=self.collection_name)
        except Exception:
            pass

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )


def create_vector_store(
    db_path=None,
    collection_name="financial_filings_2022",
):
    """
    Backward-compatible factory used by Phase 1 tests and scripts.
    """
    return FinancialFilingsVectorStore(
        db_path=db_path,
        collection_name=collection_name,
    )
# ----------------------------------------------------------------------
# Simple manual test
# ----------------------------------------------------------------------

if __name__ == "__main__":
    store = FinancialFilingsVectorStore()

    print(
        f"Collection: {store.collection_name}"
    )
    print(
        f"Vectors: {store.count()}"
    )

    results = store.retrieve(
        query="What were Apple's total net sales in 2022?",
        top_k=5,
        ticker="AAPL",
    )

    print("\nTop results:")

    for rank, result in enumerate(
        results,
        start=1,
    ):
        print(
            f"\nRank {rank}"
        )
        print(
            f"ID: {result['id']}"
        )
        print(
            f"Score: {result['score']:.4f}"
        )
        print(
            f"Similarity: {result['similarity']:.4f}"
        )
        print(
            f"Section: "
            f"{result['metadata'].get('section')}"
        )
        print(
            f"Source: "
            f"{result['metadata'].get('source_location')}"
        )
        print(
            f"Text: {result['text'][:500]}"
        )