# Multi-Agent LLM Pipeline for Automated Inconsistency Detection

**B.Tech Major Project - Final Year CSE**  
**Graphic Era Hill University**

## Project Overview

A verification framework measuring whether structured multi-agent decomposition catches restated-number inconsistencies more reliably than a single LLM call.

**Domain:** Financial Filings (SEC 10-K reports) — Contracts planned as a secondary generalization test (Phase 9), pending schedule

**Corpus:** 25 companies across 5 sectors, FY2022 filings

**Approach:** 4-agent pipeline (Retrieval → Extraction → Verification → Synthesis)

## Current Status: Phase 0 Complete — Moving to Phase 1 (Retrieval Layer)

### What's Done

- Company list finalized (25 companies across Technology, Healthcare, Retail/Consumer, Energy/Industrial, Finance)
- Data fetch script built (`scripts/fetch_edgar_data.py`) — handles CIK-based lookup, SEC submissions pagination (needed for high-filing-volume companies), and fiscal-year window selection for non-calendar fiscal year-ends
- EDGAR corpus downloaded — 25/25 companies, HTML 10-K + XBRL facts
- Fiscal year correctness manually verified per company (report dates checked against each company's actual fiscal year end)
- XBRL concept-tag coverage verified (`scripts/verify_tags_v2.py`) — all 25 companies resolve `NetIncomeLoss`, `Revenues`, and `Assets` via a documented fallback tag list, accounting for post-ASC 606 revenue tags and bank-specific income reporting
- HTML section parsing (Phase 1, in progress — manual inspection of filing structure across sectors before writing a general parser)
- Chunking, local embeddings, ChromaDB indexing (Phase 1)

## Team Structure

- **Member 1:** Orchestration & Agent Framework
- **Member 2:** Retrieval / RAG Layer
- **Member 3:** Evaluation Harness
- **Member 4:** Domain Logic & Interface

## Repository Structure

```text
.
├── data/
│   ├── raw/
│   │   ├── filings/          # 10-K HTML documents (25 companies)
│   │   └── xbrl/             # XBRL JSON facts (25 companies)
│   ├── metadata/
│   │   ├── corpus_index.json     # Master index: company, CIK, filing date, report date, paths
│   │   └── fetch_failures.json   # Logged per-company fetch errors, if any
│   └── companies.csv          # Company list (ticker, name, CIK)
├── scripts/
│   ├── fetch_edgar_data.py    # EDGAR data collection (submissions + XBRL)
│   └── verify_tags_v2.py      # XBRL concept-tag verification with fallback candidates
├── docs/
│   └── phase0_status_brief.md # Full Phase 0 debugging record
└── README.md