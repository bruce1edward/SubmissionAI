# SubmissionAI

**Regulatory provenance, SAP validation, and FDA conformance analysis for Phase 2 to Phase 3 eCTD submissions.**

SubmissionAI is a multi-agent AI system that takes an eCTD-style package as input, validates its structure and statistical planning against FDA, ICH, and EMA guidelines, and produces a reviewer-ready readiness report — all grounded in a hybrid RAG knowledge base rather than LLM parametric memory alone.

---

## Demo

```bash
pip install -r requirements.txt
export NEBIUS_API_KEY="your-nebius-api-key"
streamlit run app.py
```

The app runs immediately with no-prereq live RAG. Click **Run Generated Demo** on the Overview page to see the full flow without uploading a package.

---

## Architecture

### Five agents

| Agent | What it does |
|---|---|
| **Content Extractor** | Reads eCTD documents and extracts Phase 2/3 trial facts |
| **Provenance Tracer** | Maps Phase 2 efficacy, dose, and safety to Phase 3 design decisions |
| **SAP Validator** | Checks SAP pre-specification, estimand framework, multiplicity, missing data handling |
| **Conformance Checker** | Verifies FDA eCTD/CTD structure, 21 CFR Part 312, ICH M4 module completeness |
| **Report Generator** | Produces an executive compliance report with priority remediation items |

### Two RAG knowledge bases

**FDA Conformance Checker KB** (`rag_knowledge_base/`) — 13 documents, 227 chunks
- ICH E3, E8(R1), E9, E9(R1), E10
- FDA eCTD v4.0 TCG, Study Data TCG, Adaptive Design 2019, Formal Meetings, IND CMC Phase 2-3
- 21 CFR Part 312 (IND), 21 CFR Part 11 (electronic records)
- EMA Missing Data 2010

**SAP Validator KB** (`sap_knowledge_base/`) — 12 documents, 182 chunks
- ICH E9(R1) Training Material
- FDA Covariate Adjustment 2023, Multiple Endpoints 2023, Non-Inferiority 2016, Enrichment Strategies 2019
- EMA Subgroup Analysis 2019
- Shared with the FDA Conformance KB: ICH E9, E9(R1), E3, E10, FDA Adaptive Design, EMA Missing Data

### Hybrid retrieval pipeline

```
Query → clinical term expansion (BM25)
      → domain routing (7 SAP domains / 9 conformance domains)
      → Dense retrieval (ChromaDB + BAAI/bge-large-en-v1.5)
      → Sparse retrieval (BM25Okapi)
      → RRF fusion (k=60)
      → Cross-encoder re-ranking (ms-marco-MiniLM-L-12-v2)
      → Top passages injected into LLM prompt
```

Deterministic pre-flight checks run before any LLM call: SAP amendment timing vs. database lock (ICH E9 §5.1), estimand attribute completeness (ICH E9(R1) §3.1), stratification factor/covariate consistency (FDA Covariate Adjustment §III.A).

---

## Project structure

```
app.py                          — Streamlit UI (6 pages)
ectd_agent.py                   — Five LLM agents + fallback demo data
regulatory_knowledge_base.py    — FDA Conformance Checker RAG
sap_validator_knowledge_base.py — SAP Validator RAG

rag_knowledge_base/             — FDA Conformance KB source documents
  ich/    fda/    cfr/    ema/

sap_knowledge_base/             — SAP Validator KB additional documents
  ich/    fda/    ema/

requirements.txt                — All dependencies
smoke_test.py                   — Quick validation script
```

---

## LLM backend

Uses the [Nebius Token Factory](https://nebius.com/) OpenAI-compatible API. Supported models:
- `deepseek-ai/DeepSeek-R1-0528`
- `meta-llama/Llama-3.3-70B-Instruct`

Set your key in the sidebar or via environment variable:
```bash
export NEBIUS_API_KEY="your-key"
```

---

## Pages

| Page | Description |
|---|---|
| **Overview** | System overview, one-click demo run |
| **Upload & Analyze** | Upload your own eCTD ZIP package |
| **Detailed Report** | Input Validation, Provenance, SAP, Conformance, FDA Questions tabs |
| **RAG Knowledge Base** | KB inventory, retrieval architecture, live stats (Tab A: FDA; Tab B: SAP) |
| **Technical Blog** | Evidence brief, multi-agent design, regulatory statistics |
| **Demo Setup** | Run instructions and API key info |
