# Multi-Agent LLM Pipeline for Automated Inconsistency Detection

B.Tech Major Project - Final Year CSE  
Graphic Era Hill University

## Project Overview

A verification framework measuring whether structured multi-agent decomposition catches restated-number inconsistencies more reliably than a single LLM call.

**Domain:** Financial Filings (SEC 10-K reports)  
**Corpus:** 17 companies across 5 sectors, FY2022 filings  
**Approach:** 4-agent pipeline (Retrieval → Extraction → Verification → Synthesis)

## Current Status: Phase 0 - Data Collection

### What's Done
- [x] Company list finalized (17 S&P 500 companies)
- [x] Data fetch script created
- [ ] EDGAR corpus downloaded
- [ ] XBRL facts extracted

### Team Structure
- **Member 1:** Orchestration & Agent Framework
- **Member 2:** Retrieval / RAG Layer
- **Member 3:** Evaluation Harness
- **Member 4:** Domain Logic & Interface

## Repository Structure
## Repository Structure

```text
.
├── data/
│   ├── raw/
│   │   ├── filings/          # 10-K HTML documents
│   │   └── xbrl/             # XBRL JSON facts
│   ├── metadata/             # Corpus index
│   └── companies.csv         # Company list (CIK mapping)
├── scripts/
│   └── fetch_edgar_data.py
└── README.md
```