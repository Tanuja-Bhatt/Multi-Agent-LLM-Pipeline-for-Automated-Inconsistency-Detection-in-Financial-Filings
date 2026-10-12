# Multi-Agent LLM Pipeline for Automated Inconsistency Detection

**B.Tech Major Project - Final Year CSE**\
**Graphic Era Hill University**

## Project Overview

A verification framework designed to evaluate whether structured
multi-agent decomposition can detect restated-number inconsistencies in
financial filings more reliably than a single LLM call.

The project focuses on **SEC Form 10-K financial filings** and uses a
four-agent architecture:

``` text
Retrieval Agent
      ↓
Extraction Agent
      ↓
Verification Agent
      ↓
Synthesis Agent
```

The retrieval and verification layers are designed to preserve source
traceability so that detected claims can be linked back to their
originating filing and section.

**Domain:** Financial Filings (SEC 10-K reports)\
**Corpus:** 25 companies across 5 sectors, FY2022 filings\
**Architecture:** Retrieval → Extraction → Verification → Synthesis\
**Future generalization test:** Contracts, planned for Phase 9, schedule
pending

------------------------------------------------------------------------

# Current Status

## Phase 0 - Foundations

**Status: COMPLETE**

Phase 0 established the real financial-filings corpus and verified the
underlying SEC/XBRL data.

### Completed

-   Finalized a corpus of **25 companies across 5 sectors**:
    -   Technology
    -   Healthcare
    -   Retail/Consumer
    -   Energy/Industrial
    -   Finance
-   Built the EDGAR data-fetching pipeline in
    `scripts/fetch_edgar_data.py`
-   Implemented:
    -   CIK-based company lookup
    -   SEC submissions pagination
    -   fiscal-year window selection
    -   support for non-calendar fiscal year-ends
-   Downloaded the complete corpus:
    -   **25/25 companies**
    -   HTML 10-K filings
    -   XBRL facts
-   Manually verified fiscal-year correctness for each company
-   Verified XBRL concept-tag coverage using `scripts/verify_tags_v2.py`
-   Confirmed resolution of:
    -   `NetIncomeLoss`
    -   `Revenues`
    -   `Assets`
-   Added documented fallback tag candidates for variations such as
    post-ASC 606 revenue tags and bank-specific income reporting

------------------------------------------------------------------------

# Phase 1 - Retrieval Layer

**Status: COMPLETE AND FROZEN**

Phase 1 built the retrieval foundation over the complete 25-filing
corpus.

### 1. Section-Aware Parsing

Before generalizing the parser, structurally different filings were
inspected across sectors, including:

-   AAPL - Technology
-   JPM - Finance
-   WMT - Retail

The parser was designed around the actual filing structures rather than
assuming a uniform SEC HTML layout.

The final parser produces four section categories:

``` text
MD&A
FINANCIAL_STATEMENTS
FOOTNOTES
OTHER
```

Structural edge cases were identified and handled during validation,
including differences in table-of-contents content, financial-statement
placement, HTML nesting, and filings that reference information
incorporated by reference.

**Final parser validation: 25/25 filings passed.**

### 2. Chunking

The final chunking strategy is section-preserving and paragraph-first.

``` text
Target size : ~800
Maximum     : 1200
Minimum     : 150
Overlap     : 100
```

A chunk never crosses a section boundary.

Final corpus processing:

``` text
Parsed blocks : 184,713
Chunks        : 16,878
Oversized     : 0
Duplicate IDs : 0
```

### 3. Local Embeddings

The project uses a local embedding implementation:

``` text
Embedding interface : ChromaDB DefaultEmbeddingFunction
Model               : all-MiniLM-L6-v2
Runtime             : local ONNX Runtime
Dimension           : 384
```

No paid embedding API is used.

### 4. ChromaDB

All 25 filings are indexed in one corpus-wide collection:

``` text
financial_filings_2022
```

Every indexed chunk contains traceability metadata:

``` text
document_id
ticker
section
source_location
```

Final collection size:

``` text
16,878 chunks
```

### 5. Retrieval

The retrieval function is:

``` python
retrieve(query, top_k)
```

An optional ticker filter is also supported.

The retrieval layer combines:

-   semantic similarity
-   lexical overlap
-   financial phrase matching
-   financial/table-context signals
-   structural adjacency

The production retrieval logic is query-driven and does not use gold
answers or expected numeric values.

------------------------------------------------------------------------

# Phase 1 Evaluation

A hand-checked evaluation set of **20 real financial claims** was used.

Two metrics were reported.

### Canonical Chunk Recall

This measures whether the exact manually designated gold chunk appears
in the top-k results.

  Metric        Result
  ---------- ---------
  Recall@1     **30%**
  Recall@3     **60%**
  Recall@5     **80%**

### Evidence-Based Recall

This measures whether any retrieved chunk contains valid evidence for
answering the claim.

  Metric        Result
  ---------- ---------
  Recall@1     **65%**
  Recall@3     **80%**
  Recall@5     **90%**

Additional result:

``` text
Claims with no evidence in top 20: 0/20
```

The evidence-based metric is especially important because the same
financial fact can legitimately appear in multiple sections of a 10-K.
Therefore, retrieval should not be considered unsuccessful merely
because a different valid evidence-bearing chunk was returned instead of
the designated canonical chunk.

### Phase 1 Baseline

``` text
Corpus                  : 25 filings
Parsed blocks           : 184,713
Indexed chunks          : 16,878
Embedding               : all-MiniLM-L6-v2
Embedding dimension     : 384
Vector store            : ChromaDB
Collection              : financial_filings_2022

Evidence Recall@1       : 65%
Evidence Recall@3       : 80%
Evidence Recall@5       : 90%
Evidence missing @20    : 0/20
```

This baseline will be retained for comparison with later phases.

------------------------------------------------------------------------

# Team Structure

-   **Member 1:** Orchestration & Agent Framework
-   **Member 2:** Retrieval / RAG Layer
-   **Member 3:** Evaluation Harness
-   **Member 4:** Domain Logic & Interface

The Phase 1 implementation follows the redistributed team-workstream
approach so that parsing, retrieval, indexing, and evaluation integrate
into one pipeline.

------------------------------------------------------------------------

# Repository Structure

``` text
financial-filings-verification/
│
├── data/
│   ├── raw/
│   │   ├── filings/              # Raw SEC 10-K HTML documents
│   │   └── xbrl/                 # XBRL JSON facts
│   ├── metadata/
│   │   ├── corpus_index.json     # Company, CIK, filing/report metadata
│   │   └── fetch_failures.json   # Logged fetch failures, if any
│   ├── chroma/                   # Local ChromaDB vector store
│   └── companies.csv             # Company list, ticker, name, CIK
│
├── docs/
│   └── Phase1.md                 # Phase 1 documentation and results
│
├── scripts/
│   ├── build_vector_store.py     # Build/update ChromaDB index
│   ├── chunk_text.py             # Section-preserving chunking
│   ├── fetch_edgar_data.py       # SEC EDGAR data collection
│   ├── parse_filings.py          # Section-aware HTML parser
│   ├── vector_store.py           # ChromaDB + retrieval implementation
│   └── verify_tags_v2.py         # XBRL concept-tag verification
│
├── test_data/                    # Filing samples/corpus used for validation
│
├── tests/
│   ├── build_gold_set.py         # Build/update evaluation gold set
│   ├── gold_set.json             # 20-claim evaluation set
│   ├── inspect_sections.py       # Filing structure inspection
│   ├── retrieval_eval.py         # Phase 1 retrieval evaluation
│   ├── test_chunking.py          # Chunking unit tests
│   ├── test_parser.py            # Parser tests
│   ├── test_retrieval.py         # Retrieval smoke test
│   ├── validate_chunking.py      # Full chunking validation
│   └── validate_corpus.py        # Full parser/corpus validation
│
├── .gitignore
├── README.md
├── requirements.txt
└── ...
```

------------------------------------------------------------------------

# Key Phase 1 Commands

Activate the Phase 1 environment:

``` powershell
.venv_phase1c\Scripts\Activate.ps1
```

### Validate parser

``` powershell
python -m tests.test_parser
```

### Validate the full corpus

``` powershell
python -m tests.validate_corpus
```

### Run chunking tests

``` powershell
python -m tests.test_chunking
```

### Validate full chunking

``` powershell
python -m tests.validate_chunking
```

### Run retrieval smoke test

``` powershell
python -m tests.test_retrieval
```

### Run the 20-claim retrieval evaluation

``` powershell
python -m tests.retrieval_eval
```

------------------------------------------------------------------------

# Phase 1 Design Principles

### 1. Inspect before generalizing

SEC filings are not assumed to share a uniform HTML structure.

### 2. Preserve financial context

Chunks remain inside section boundaries and are created around natural
paragraph-level units.

### 3. Keep embeddings local

The retrieval layer does not depend on a paid embedding API.

### 4. Preserve source traceability

Every retrieved passage carries document, company, section, and
source-location metadata.

### 5. Measure retrieval quality

The retrieval layer is evaluated against real financial claims rather
than judged only by whether the code executes.

### 6. Avoid evaluation leakage

Production retrieval does not use gold answers or expected numeric
values.

------------------------------------------------------------------------

# Current Project Roadmap

``` text
Phase 0  Foundations                         COMPLETE
   ↓
Phase 1  Retrieval Layer                    COMPLETE
   ↓
Phase 2  Extraction Layer                   NEXT
   ↓
Phase 3  Ground-Truth Injection Pipeline
   ↓
Phase 4  Verification Agent
   ↓
Phase 5  Synthesis Agent
   ↓
Phase 6  End-to-End Pipeline
   ↓
Phase 7  Evaluation & Comparison
   ↓
Phase 8  Interface + Demo Polish
   ↓
Phase 9  Secondary Generalization Test
```

The exact implementation and schedule for later phases may evolve as the
project progresses.

------------------------------------------------------------------------

# Phase 1 Conclusion

Phase 1 established a reproducible retrieval foundation over the
complete 25-filing corpus:

``` text
Real SEC filings
      ↓
Section-aware parsing
      ↓
Paragraph-first chunking
      ↓
Local embeddings
      ↓
Corpus-wide ChromaDB
      ↓
Semantic retrieval
      ↓
Financial-aware reranking
      ↓
Traceable evidence
      ↓
Measured Recall@k
```

The final retrieval baseline achieved **90% evidence Recall@5** on the
20-claim evaluation set, with valid evidence available within the top 20
results for **all 20 claims**.

**Phase 1 is complete and frozen.**

The next development stage is **Phase 2: Extraction Layer**.
