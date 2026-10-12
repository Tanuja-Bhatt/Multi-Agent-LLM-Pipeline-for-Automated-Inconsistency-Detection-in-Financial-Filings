# Phase 1 Final Documentation

## Retrieval Layer - Financial Filings Verification Project

**Status: COMPLETE AND FROZEN**

### 1. Objective

Phase 1 builds the retrieval foundation for the multi-agent
financial-filings verification pipeline. The objective is to transform
real SEC Form 10-K HTML into section-aware, traceable retrieval
passages, index them locally, expose `retrieve(query, top_k)`, and
measure retrieval quality on a real 20-claim evaluation set.

The Phase 1 requirements are: inspect structurally different filings
before generalizing the parser; preserve section boundaries; chunk by
paragraph; use local embeddings; use one ChromaDB collection for the
corpus; preserve `document_id`, `ticker`, `section`, and
`source_location`; and report measured recall@k.

------------------------------------------------------------------------

# 2. Final Architecture

``` text
SEC 10-K HTML
      |
      v
Section-aware parser
      |
      v
Parsed section blocks
      |
      v
Paragraph-first chunker
      |
      v
Traceable chunks
      |
      v
Local embedding model
      |
      v
ChromaDB
      |
      v
Semantic candidate retrieval
      |
      v
Lexical + financial reranking
      |
      v
Structural adjacency
      |
      v
retrieve(query, top_k)
      |
      v
Ranked evidence + source metadata
```

------------------------------------------------------------------------

# 3. Corpus

The final Phase 1 corpus contains:

-   **25 FY2022 SEC Form 10-K filings**
-   **184,713 parsed blocks**
-   **16,878 indexed chunks**
-   One ChromaDB collection: `financial_filings_2022`

The initial structural inspection deliberately covered different
sectors:

-   AAPL: technology
-   JPM: banking
-   WMT: retail

This was done before writing a generalized parser so that the
implementation was based on actual filing structures rather than an
assumed uniform `<PART>/<ITEM>` layout.

------------------------------------------------------------------------

# 4. Workstream A: Section-Aware Parsing

## 4.1 Parser objective

The parser converts raw HTML into retrieval-ready blocks while
preserving section identity and structural source location.

The fixed section vocabulary is:

``` text
MD&A
FINANCIAL_STATEMENTS
FOOTNOTES
OTHER
```

Each block contains fields equivalent to:

``` python
{
    "text": "...",
    "section": "MD&A",
    "page": None,
    "source_location": "dom_index N",
    "dom_index": N,
    "element_id": ...
}
```

Numeric page extraction was not used as the primary source locator
because HTML page-number extraction was not sufficiently reliable.
DOM-based locations were retained instead.

## 4.2 Structural variance discovered

The parser was deliberately tested against real structural differences.

### HON

Honeywell contained table-of-contents/navigation content that could
resemble actual financial-statement headings. The parser therefore had
to distinguish navigation references from the real Financial Statements
and Supplementary Data section.

### WFC

Wells Fargo was a stronger structural exception. Its 10-K referred to
financial statements and notes contained in an annual report
incorporated by reference rather than presenting the complete expected
financial-statement content directly in the 10-K. The parser therefore
could not assume that every filing physically contains the same
statement structure.

### General variance

Across the corpus, filings also differed in:

-   heading placement;
-   HTML nesting;
-   table representation;
-   paragraph boundaries;
-   navigation content;
-   placement of financial statements;
-   placement and formatting of footnotes.

The parser was revised based on observed structures rather than by
adding a generic assumption.

## 4.3 Parser validation

The final parser was validated across all 25 filings.

**Final parser result: 25/25 successfully parsed.**

The parser is frozen for Phase 1.

------------------------------------------------------------------------

# 5. Workstream B: Paragraph-First Chunking

## 5.1 Final chunking rules

``` text
Target size : ~800
Maximum     : 1200
Minimum     : 150
Overlap     : 100
```

A chunk never crosses a section boundary.

Consecutive parser blocks from the same section are accumulated into
retrieval-sized chunks.

Long content is split further rather than producing oversized chunks.

## 5.2 Why paragraph-first

Financial claims often depend on their surrounding table or explanatory
paragraph. Arbitrary character windows can separate a financial label
from its value or split a table at an unhelpful boundary.

Paragraph-first chunking therefore preserves semantic units whenever
possible while section boundaries provide an additional structural
constraint.

## 5.3 Final chunking validation

``` text
Parsed blocks processed : 184,713
Chunks generated       : 16,878
Oversized chunks       : 0
Duplicate IDs          : 0
Missing traceability   : 0
```

Unit tests passed for:

``` text
basic chunk metadata
section isolation
long paragraph splitting
deterministic chunk IDs
chunk ID uniqueness
```

The chunker is frozen for Phase 1.

------------------------------------------------------------------------

# 6. Workstream B/C: Local Embeddings

## Final implementation

``` text
Embedding interface : ChromaDB DefaultEmbeddingFunction
Underlying model   : all-MiniLM-L6-v2
Runtime             : local ONNX Runtime
Dimension           : 384
```

No paid embedding API is used.

The original design considered sentence-transformers/all-mpnet-base-v2
or a smaller alternative. The final implementation selected the smaller
local all-MiniLM-L6-v2 path because it integrates directly with ChromaDB
and provides a stable local deployment without the PyTorch dependency
stack.

This is an engineering tradeoff between model size, local execution,
dependency stability, and the current corpus size.

------------------------------------------------------------------------

# 7. Workstream C: ChromaDB

## 7.1 Collection

One collection is used for the entire corpus:

``` text
financial_filings_2022
```

Separate collections are not created per company. Company and section
are metadata dimensions.

## 7.2 Required metadata

Every indexed record carries:

``` text
document_id
ticker
section
source_location
```

DOM information is retained where available.

Example:

``` text
document_id     : AAPL_10K
ticker          : AAPL
section         : FOOTNOTES
source_location : dom_index ...
```

## 7.3 Final index

``` text
Collection : financial_filings_2022
Vectors    : 16,878
Status     : PASS
```

All generated chunks were confirmed to be indexed.

------------------------------------------------------------------------

# 8. Retrieval Interface

The final interface is:

``` python
retrieve(query, top_k)
```

An optional ticker filter is supported:

``` python
retrieve(query, top_k, ticker="AAPL")
```

Returned records contain:

``` python
{
    "id": ...,
    "chunk_id": ...,
    "text": ...,
    "metadata": ...,
    "score": ...,
    "similarity": ...
}
```

The metadata remains attached to every result.

------------------------------------------------------------------------

# 9. Retrieval Strategy

The final retrieval pipeline is query-driven and answer-independent.

## Stage 1: Semantic retrieval

ChromaDB retrieves a larger semantic candidate pool.

## Stage 2: Lexical overlap

Query terms are compared with candidate text.

## Stage 3: Financial phrase matching

The query is checked for financial concepts such as:

``` text
total net sales
net sales
total net revenue
net revenue
total revenues
net income
operating income
gross margin
total assets
provision for credit losses
```

## Stage 4: Financial/table context

Candidates receive additional relevance when they contain
financial-statement language and table-like numeric content.

## Stage 5: Structural adjacency

Nearby chunks from the same document and section can be considered
because a financial fact can span adjacent retrieval chunks.

## Important constraint

Production retrieval does not use:

-   canonical gold IDs;
-   expected numeric values;
-   gold answers;
-   evaluation labels.

Gold-aware experiments were used only diagnostically to understand
retrieval failures and were not included in the production scoring
logic.

------------------------------------------------------------------------

# 10. Retrieval Smoke Test

The final smoke test used:

``` text
Collection : financial_filings_2022
Count      : 16,878
Query      : What were Apple's total net sales?
Top-k      : 5
```

Multiple retrieved Apple passages contained:

``` text
Total net sales = 394,328 million
```

The canonical chunk:

``` text
AAPL_10K_7ee7322144cd_0166
```

was retrieved and retained full source metadata.

Final result:

``` text
PASS: Retrieval and source traceability verified.
```

------------------------------------------------------------------------

# 11. Evaluation Dataset

A hand-checked set of 20 claims was created from the real corpus.

The claims cover AAPL, JPM, WMT, MSFT, AMZN, GOOGL, and INTC.

Examples:

``` text
What were Apple's total net sales in 2022?
What was Apple's net income in 2022?
What were Apple's iPhone net sales in 2022?
What was Apple's gross margin in 2022?
What was JPMorgan's total net revenue in 2022?
What was JPMorgan's net income in 2022?
What were JPMorgan's total assets at the end of 2022?
What was JPMorgan's provision for credit losses in 2022?
What were Walmart's total revenues in fiscal 2022?
What was Walmart's net income attributable to Walmart in fiscal 2022?
What was Walmart's operating income in fiscal 2022?
What were Walmart's total assets in fiscal 2022?
What was Microsoft's revenue in fiscal 2022?
What was Microsoft's net income in fiscal year 2022?
What were Amazon's net sales in 2022?
What was Amazon's operating income in 2022?
What was Google's revenue in 2022?
What was Google's net income in 2022?
What was Intel's net revenue in 2022?
What was Intel's net income in 2022?
```

------------------------------------------------------------------------

# 12. Evaluation Metrics

Two measures are maintained.

## Canonical chunk recall

The exact manually designated gold chunk must appear in the top-k
results.

This is a strict metric.

## Evidence-based recall

Any returned chunk containing valid evidence for answering the claim
counts as a successful retrieval.

This is more representative of downstream verification because the same
financial fact can legitimately appear in multiple sections of a 10-K.

------------------------------------------------------------------------

# 13. Final Evaluation Results

## Canonical chunk recall

  Metric                Result
  ---------- -----------------
  Recall@1      6/20 = **30%**
  Recall@3     12/20 = **60%**
  Recall@5     16/20 = **80%**

## Evidence-based recall

  Metric                Result
  ---------- -----------------
  Recall@1     13/20 = **65%**
  Recall@3     16/20 = **80%**
  Recall@5     18/20 = **90%**

Additional result:

``` text
Claims with no evidence in top 20: 0/20
```

Therefore every evaluated claim had valid evidence somewhere in its
top-20 retrieval results.

------------------------------------------------------------------------

# 14. Claim-Level Results

  Claim     Canonical Rank   Evidence Rank
  ------- ---------------- ---------------
  C01                    2               1
  C02                    4               1
  C03                    2               1
  C04                    1               1
  C05                    4               4
  C06                    4               2
  C07                    2               1
  C08                    7               6
  C09                    1               1
  C10                    2               1
  C11                   11               7
  C12                 None               2
  C13                    7               1
  C14                    3               1
  C15                    1               1
  C16                    1               1
  C17                    5               5
  C18                    1               1
  C19                    3               3
  C20                    1               1

The key example is C12:

``` text
canonical_rank = None
evidence_rank  = 2
```

The exact designated chunk was not returned, but valid evidence was
ranked second. This demonstrates why both metrics are reported.

------------------------------------------------------------------------

# 15. Retrieval Failure Analysis

No claim had an evidence failure within the top 20.

The relatively weaker cases were:

### C08

Evidence ranked 6. The provision-for-credit-losses wording is a
difficult financial-table retrieval case because the natural-language
query and table wording are not identical.

### C11

Evidence ranked 7. Walmart operating-income evidence was retrieved but
ranked below several other relevant passages.

### C12

The canonical chunk was absent from the evaluated canonical ranking, but
valid total-assets evidence was ranked 2.

These are retrieval-ranking limitations, not missing-corpus failures.

------------------------------------------------------------------------

# 16. Why Phase 1 Was Frozen

The final system achieved:

``` text
Evidence Recall@1 : 65%
Evidence Recall@3 : 80%
Evidence Recall@5 : 90%
Top-20 evidence   : 20/20
```

Further tuning specifically against these 20 claims could overfit the
retrieval layer.

Therefore Phase 1 is frozen with this retrieval configuration as the
baseline.

Future retrieval improvements should be tested as separate experiments
and compared against this baseline.

------------------------------------------------------------------------

# 17. Definition of Done

  Requirement                              Status
  ---------------------------------------- --------
  Inspect real structural variance first   PASS
  Section-aware parser                     PASS
  25-filing parser validation              PASS
  Structural variance documented           PASS
  Paragraph-first chunking                 PASS
  Section boundaries preserved             PASS
  Long-content splitting                   PASS
  Deterministic chunk IDs                  PASS
  Unique chunk IDs                         PASS
  Local embeddings                         PASS
  Single ChromaDB collection               PASS
  Required metadata                        PASS
  16,878 chunks indexed                    PASS
  `retrieve(query, top_k)`                 PASS
  Source traceability                      PASS
  20-claim evaluation                      PASS
  Recall@k measured                        PASS
  Evidence Recall@5 = 90%                  PASS
  Evidence for all claims within top 20    PASS

**Phase 1: COMPLETE.**

------------------------------------------------------------------------

# 18. Final Technical Decisions

### Decision 1: Section-aware parser

**Chosen:** section-aware HTML parsing.

**Reason:** real SEC filings have structural variation.

### Decision 2: DOM-based source location

**Chosen:** DOM index rather than unreliable numeric HTML page
extraction.

### Decision 3: Paragraph-first chunking

**Chosen:** paragraph-first chunks constrained to sections.

**Reason:** better preservation of financial claims and table context
than arbitrary windows.

### Decision 4: Local embedding model

**Chosen:** Chroma DefaultEmbeddingFunction / all-MiniLM-L6-v2 / ONNX.

**Reason:** local, free of paid API dependency, stable in the final
environment.

### Decision 5: One vector collection

**Chosen:** one corpus-wide Chroma collection.

**Reason:** metadata filtering is sufficient for company and section
scoping.

### Decision 6: Query-driven reranking

**Chosen:** semantic + lexical + financial phrase + financial-context
signals.

**Reason:** pure semantic similarity can rank narrative passages above
exact financial evidence.

### Decision 7: Evidence-based evaluation

**Chosen:** report both canonical and evidence recall.

**Reason:** repeated financial facts make exact-chunk matching
unnecessarily strict as the only metric.

------------------------------------------------------------------------

# 19. Known Limitations

1.  **20-claim evaluation set:** sufficient for Phase 1 but not a
    comprehensive benchmark.
2.  **Canonical/evidence distinction:** canonical recall can understate
    practical retrieval quality.
3.  **Embedding model size:** all-MiniLM-L6-v2 is smaller than larger
    alternatives such as all-mpnet-base-v2.
4.  **DOM source locations:** useful for structural traceability but
    less human-friendly than page numbers.
5.  **Upstream dependency:** Phase 2 extraction quality depends on
    retrieval surfacing the correct evidence.

------------------------------------------------------------------------

# 20. Official Phase 1 Baseline

These values should be preserved for comparison with later phases:

``` text
Corpus                         : 25 filings
Parsed blocks                  : 184,713
Indexed chunks                 : 16,878

Embedding                      : all-MiniLM-L6-v2
Runtime                        : local ONNX
Embedding dimension            : 384
Vector store                   : ChromaDB
Collection                     : financial_filings_2022

Evaluation claims              : 20

Canonical Recall@1             : 30%
Canonical Recall@3             : 60%
Canonical Recall@5             : 80%

Evidence Recall@1              : 65%
Evidence Recall@3              : 80%
Evidence Recall@5              : 90%

Evidence missing in top-20     : 0/20
```

------------------------------------------------------------------------


# 22. Conclusion

Phase 1 established the complete retrieval foundation:

``` text
Real SEC filing
    ->
Section-aware parsing
    ->
Traceable chunks
    ->
Local embeddings
    ->
Corpus-wide ChromaDB
    ->
Semantic retrieval
    ->
Financial-aware reranking
    ->
Traceable evidence
    ->
Measured retrieval quality
```

The retrieval layer is now ready to serve Phase 2.

**PHASE 1 COMPLETE AND FROZEN.**
