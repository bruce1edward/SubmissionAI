"""
regulatory_knowledge_base.py
SubmissionAI — RAG Knowledge Base for the FDA Conformance Checker Agent

This module satisfies the import in ectd_agent.py:
    from regulatory_knowledge_base import build_conformance_rag_bundle

Architecture:
    1. Section-aware chunking of 13 FDA/ICH/EMA/CFR guideline documents
    2. Dense retrieval via ChromaDB + BAAI/bge-large-en-v1.5 embeddings
    3. Sparse retrieval via BM25Okapi (rank-bm25)
    4. Reciprocal Rank Fusion (RRF) to merge ranked lists
    5. Cross-encoder re-ranking (cross-encoder/ms-marco-MiniLM-L-12-v2)

Public API:
    build_conformance_rag_bundle(extracted_data, provenance, sap, documents,
                                  validation_report=None) -> dict

The returned bundle has the keys that ectd_agent.agent_check_conformance() expects:
    - "prompt_context"          : formatted string of top-k retrieved passages
    - "rule_based_checks"       : dict of deterministic preflight findings
    - "retrieved_guidance_summary" : list of dicts for the Streamlit UI
    - "knowledge_base_size"     : total number of indexed chunks
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
_PROJECT_DIR = Path(__file__).resolve().parent
_KB_DIR = Path(os.environ.get("RAG_KB_DIR", str(_PROJECT_DIR / "rag_knowledge_base")))
_CHROMA_DIR = Path(os.environ.get("RAG_CHROMA_DIR", str(_PROJECT_DIR / "rag_chroma_db")))
_COLLECTION_NAME = "fda_conformance_kb"
_EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-12-v2"

# ── Document Registry ──────────────────────────────────────────────────────────
_DOCUMENTS = [
    {
        "path": "ich/ICH_E3_Clinical_Study_Reports.txt",
        "guideline_code": "ICH E3",
        "title": "Structure and Content of Clinical Study Reports",
        "regulatory_body": "ICH",
        "document_type": "efficacy_guideline",
        "effective_date": "1996-11-01",
        "compliance_domains": ["csr_structure", "clinical_reporting"],
        "topic_tags": ["CSR", "clinical study report", "synopsis", "appendix",
                       "study report structure", "efficacy", "safety reporting"],
    },
    {
        "path": "ich/ICH_E9_Statistical_Principles.txt",
        "guideline_code": "ICH E9",
        "title": "Statistical Principles for Clinical Trials",
        "regulatory_body": "ICH",
        "document_type": "efficacy_guideline",
        "effective_date": "1998-09-01",
        "compliance_domains": ["statistical_analysis", "sap_prespecification",
                               "missing_data", "multiplicity"],
        "topic_tags": ["SAP", "statistical analysis plan", "pre-specification",
                       "primary endpoint", "missing data", "NRI", "LOCF",
                       "multiplicity", "gatekeeping", "randomization", "blinding"],
    },
    {
        "path": "ich/ICH_E9R1_Estimands_Addendum.txt",
        "guideline_code": "ICH E9(R1)",
        "title": "Addendum: Estimands and Sensitivity Analysis in Clinical Trials",
        "regulatory_body": "ICH",
        "document_type": "efficacy_guideline",
        "effective_date": "2019-11-20",
        "compliance_domains": ["statistical_analysis", "estimands", "sensitivity_analysis"],
        "topic_tags": ["estimand", "intercurrent event", "sensitivity analysis",
                       "treatment policy", "hypothetical strategy", "principal stratum",
                       "while on treatment", "composite strategy"],
    },
    {
        "path": "ich/ICH_E10_Control_Group.txt",
        "guideline_code": "ICH E10",
        "title": "Choice of Control Group and Related Issues in Clinical Trials",
        "regulatory_body": "ICH",
        "document_type": "efficacy_guideline",
        "effective_date": "2001-07-27",
        "compliance_domains": ["study_design", "control_group"],
        "topic_tags": ["placebo", "active control", "assay sensitivity",
                       "non-inferiority", "superiority", "control group"],
    },
    {
        "path": "ich/ICH_E8R1_General_Considerations.txt",
        "guideline_code": "ICH E8(R1)",
        "title": "General Considerations for Clinical Studies",
        "regulatory_body": "ICH",
        "document_type": "efficacy_guideline",
        "effective_date": "2021-10-06",
        "compliance_domains": ["study_design", "quality_factors"],
        "topic_tags": ["study design", "quality", "clinical study", "protocol",
                       "risk proportionate", "critical to quality"],
    },
    {
        "path": "fda/FDA_eCTD_v40_Technical_Conformance.txt",
        "guideline_code": "FDA eCTD v4.0 TCG",
        "title": "eCTD v4.0 Technical Conformance Guide",
        "regulatory_body": "FDA",
        "document_type": "technical_specification",
        "effective_date": "2024-09-16",
        "compliance_domains": ["ectd_format", "file_naming", "submission_format"],
        "topic_tags": ["eCTD", "module", "file naming", "XML", "backbone",
                       "sequence", "folder structure", "submission unit",
                       "document type", "regional M1"],
    },
    {
        "path": "fda/FDA_Study_Data_Technical_Conformance_Guide.txt",
        "guideline_code": "FDA Study Data TCG",
        "title": "Study Data Technical Conformance Guide",
        "regulatory_body": "FDA",
        "document_type": "technical_specification",
        "effective_date": "2023-05-01",
        "compliance_domains": ["cdisc_standards", "data_submission"],
        "topic_tags": ["SDTM", "ADaM", "CDISC", "define.xml", "dataset",
                       "reviewer's guide", "SEND", "data standards",
                       "analysis dataset", "tabulation dataset"],
    },
    {
        "path": "fda/FDA_Adaptive_Design_Guidance_2019.txt",
        "guideline_code": "FDA Adaptive Design 2019",
        "title": "Adaptive Designs for Clinical Trials of Drugs and Biologics",
        "regulatory_body": "FDA",
        "document_type": "guidance",
        "effective_date": "2019-11-01",
        "compliance_domains": ["adaptive_design", "sap_prespecification"],
        "topic_tags": ["adaptive design", "interim analysis", "sample size re-estimation",
                       "pre-specification", "simulation", "type I error",
                       "adaptation rule", "DSMB", "blinded review"],
    },
    {
        "path": "fda/FDA_Formal_Meetings_Guidance.txt",
        "guideline_code": "FDA Formal Meetings 2017",
        "title": "Formal Meetings Between the FDA and Sponsors or Applicants",
        "regulatory_body": "FDA",
        "document_type": "guidance",
        "effective_date": "2017-12-01",
        "compliance_domains": ["ind_meetings", "regulatory_process"],
        "topic_tags": ["EOP2", "end of phase 2", "Type B meeting", "pre-NDA",
                       "briefing document", "meeting request", "FDA meeting"],
    },
    {
        "path": "fda/FDA_IND_Phase2_Phase3_CMC.txt",
        "guideline_code": "FDA IND CMC Phase 2-3",
        "title": "INDs for Phase 2 and Phase 3 Studies: CMC Information",
        "regulatory_body": "FDA",
        "document_type": "guidance",
        "effective_date": "2003-05-01",
        "compliance_domains": ["ind_content", "cmc"],
        "topic_tags": ["IND", "CMC", "chemistry manufacturing controls",
                       "drug substance", "drug product", "stability",
                       "Phase 2", "Phase 3", "manufacturing"],
    },
    {
        "path": "cfr/21_CFR_Part_312_IND_Regulations.txt",
        "guideline_code": "21 CFR Part 312",
        "title": "Investigational New Drug Application",
        "regulatory_body": "FDA",
        "document_type": "regulation",
        "effective_date": "1987-06-20",
        "compliance_domains": ["ind_requirements", "regulatory_compliance"],
        "topic_tags": ["IND", "investigational new drug", "protocol",
                       "informed consent", "sponsor", "investigator",
                       "annual report", "safety report", "Phase 1", "Phase 2", "Phase 3"],
    },
    {
        "path": "cfr/21_CFR_Part_11_Electronic_Records.txt",
        "guideline_code": "21 CFR Part 11",
        "title": "Electronic Records; Electronic Signatures",
        "regulatory_body": "FDA",
        "document_type": "regulation",
        "effective_date": "1997-08-20",
        "compliance_domains": ["electronic_records", "data_integrity"],
        "topic_tags": ["electronic records", "electronic signatures", "audit trail",
                       "21 CFR 11", "data integrity", "access controls"],
    },
    {
        "path": "ema/EMA_Missing_Data_Guideline.txt",
        "guideline_code": "EMA Missing Data 2010",
        "title": "Guideline on Missing Data in Confirmatory Clinical Trials",
        "regulatory_body": "EMA",
        "document_type": "guideline",
        "effective_date": "2010-07-02",
        "compliance_domains": ["missing_data", "statistical_analysis"],
        "topic_tags": ["missing data", "multiple imputation", "MCAR", "MAR", "MNAR",
                       "sensitivity analysis", "tipping point", "LOCF",
                       "complete case analysis", "NRI"],
    },
]

# ── Domain routing keywords ────────────────────────────────────────────────────
_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "sap_prespecification": ["SAP", "pre-specified", "locked", "analysis plan",
                              "primary endpoint", "pre-specification", "statistical plan"],
    "missing_data": ["missing data", "imputation", "NRI", "LOCF", "MCAR", "MAR",
                     "rescue medication", "non-responder", "withdrawal", "dropout"],
    "csr_structure": ["CSR", "clinical study report", "synopsis", "appendix",
                      "study report", "ICH E3", "module 5"],
    "ectd_format": ["eCTD", "module", "file naming", "XML", "backbone",
                    "sequence number", "submission unit", "folder structure"],
    "cdisc_standards": ["SDTM", "ADaM", "CDISC", "define.xml", "dataset",
                        "tabulation", "analysis dataset"],
    "ind_requirements": ["IND", "investigational new drug", "protocol",
                         "21 CFR 312", "sponsor", "investigator", "amendment"],
    "multiplicity": ["multiplicity", "gatekeeping", "hierarchical testing",
                     "alpha", "Type I error", "family-wise error", "FWER"],
    "electronic_records": ["audit trail", "21 CFR 11", "electronic records",
                           "electronic signature", "data integrity"],
    "adaptive_design": ["adaptive", "interim analysis", "sample size re-estimation",
                        "DSMB", "blinded review", "adaptation"],
}

_DOMAIN_TO_GUIDELINES: dict[str, list[str]] = {
    "sap_prespecification": ["ICH E9", "ICH E9(R1)", "FDA Adaptive Design 2019"],
    "missing_data": ["ICH E9", "EMA Missing Data 2010", "ICH E9(R1)"],
    "csr_structure": ["ICH E3"],
    "ectd_format": ["FDA eCTD v4.0 TCG"],
    "cdisc_standards": ["FDA Study Data TCG"],
    "ind_requirements": ["21 CFR Part 312", "FDA IND CMC Phase 2-3"],
    "multiplicity": ["ICH E9"],
    "electronic_records": ["21 CFR Part 11"],
    "adaptive_design": ["FDA Adaptive Design 2019", "ICH E9"],
}

_FALLBACK_GUIDANCE_TEXT: dict[str, str] = {
    "ICH E3": (
        "Clinical study reports should present trial design, conduct, efficacy, and safety in a structured "
        "reviewable format. A Module 5 clinical package should preserve protocol, statistical methods, results, "
        "safety summaries, and appendices so reviewers can trace claims back to study evidence."
    ),
    "ICH E9": (
        "Statistical principles for clinical trials emphasize pre-specification of primary endpoints, analysis "
        "sets, statistical methods, multiplicity control, interim analyses, and missing-data handling. The SAP "
        "should be finalized before unblinded outcome knowledge can bias analysis choices."
    ),
    "ICH E9(R1)": (
        "The estimand framework connects trial objectives to population, treatment condition, endpoint variable, "
        "intercurrent-event strategy, and population-level summary. Sensitivity analyses should assess robustness "
        "of conclusions to assumptions about intercurrent events and missing data."
    ),
    "ICH E10": (
        "Choice of control group should support assay sensitivity and interpretability. Placebo, active-control, "
        "dose-response, and non-inferiority designs need rationale tied to trial objective, ethics, and available "
        "standard therapy."
    ),
    "ICH E8(R1)": (
        "Quality by design for clinical studies focuses on factors critical to participant protection, reliability "
        "of results, and decision usefulness. Protocols should align objectives, endpoints, design, operational "
        "feasibility, and risk controls."
    ),
    "FDA eCTD v4.0 TCG": (
        "FDA eCTD v4.0 uses a submission unit message and submission content to form a complete sequence. "
        "submissionunit.xml is the key message file. Context of Use and keywords place documents under CTD "
        "headings, and file paths/document titles should remain short, descriptive, and technically valid."
    ),
    "FDA Study Data TCG": (
        "Study data submissions should include reviewer-usable standardized data packages such as SDTM, ADaM, "
        "define.xml, analysis datasets, tabulation datasets, and reviewer guides where applicable. Dataset and "
        "metadata consistency affects reviewability."
    ),
    "FDA Adaptive Design 2019": (
        "Adaptive design features such as interim analyses, sample-size re-estimation, stopping rules, or adaptation "
        "algorithms should be prospectively planned and justified. Simulations and Type I error control are central "
        "to regulatory interpretability."
    ),
    "FDA Formal Meetings 2017": (
        "End-of-Phase 2 and other formal FDA meetings should be supported by clear meeting requests, briefing "
        "packages, proposed questions, and enough evidence for FDA to comment on Phase 3 design and readiness."
    ),
    "FDA IND CMC Phase 2-3": (
        "Phase 2 and Phase 3 IND CMC submissions should provide appropriate drug substance, drug product, "
        "manufacturing, controls, specifications, and stability information to support the proposed clinical scope."
    ),
    "21 CFR Part 312": (
        "IND submissions under 21 CFR Part 312 include Form FDA 1571, table of contents, introductory statement "
        "and investigational plan, investigator brochure when required, detailed Phase 2/3 protocols, CMC, "
        "pharmacology/toxicology, prior human experience, amendments, and safety reporting obligations."
    ),
    "21 CFR Part 11": (
        "Electronic records and signatures require attention to data integrity controls such as audit trails, "
        "access controls, record retention, system validation, and trustworthy electronic records."
    ),
    "EMA Missing Data 2010": (
        "Missing-data strategies in confirmatory trials should be prospectively planned, clinically justified, and "
        "stress-tested with sensitivity analyses. Simple imputation rules can be problematic when assumptions are "
        "not aligned with trial estimands."
    ),
}

# ── Module-level singletons (lazy-loaded) ─────────────────────────────────────
_retriever: "_HybridRetriever | None" = None
_kb_metadata: dict[str, Any] = {}


# ── Chunking ──────────────────────────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_.-]*", text.lower())


def _dependency_status() -> dict[str, bool]:
    return {
        "chromadb": importlib.util.find_spec("chromadb") is not None,
        "sentence_transformers": importlib.util.find_spec("sentence_transformers") is not None,
        "rank_bm25": importlib.util.find_spec("rank_bm25") is not None,
    }


def _fallback_passages() -> list[dict[str, Any]]:
    passages: list[dict[str, Any]] = []
    for idx, doc in enumerate(_DOCUMENTS):
        text = _FALLBACK_GUIDANCE_TEXT.get(
            doc["guideline_code"],
            f"{doc['title']} covers {', '.join(doc['compliance_domains'])}.",
        )
        passages.append(
            {
                "id": f"fallback_{idx:03d}_{doc['guideline_code'].replace(' ', '_')}",
                "text": text,
                "metadata": {
                    "guideline_code": doc["guideline_code"],
                    "title": doc["title"],
                    "regulatory_body": doc["regulatory_body"],
                    "document_type": doc["document_type"],
                    "effective_date": doc["effective_date"],
                    "section_header": "Built-in demo guidance",
                    "source_file": doc["path"],
                    "compliance_domains": json.dumps(doc["compliance_domains"]),
                    "topic_tags": json.dumps(doc["topic_tags"]),
                },
            }
        )
    return passages


def _chunk_fallback_passages(chunk_words: int = 80) -> list[dict[str, Any]]:
    """Create small demo chunks from the built-in regulatory corpus."""
    chunks: list[dict[str, Any]] = []
    for passage in _fallback_passages():
        words = passage["text"].split()
        chunk_count = max(1, (len(words) + chunk_words - 1) // chunk_words)
        for index in range(chunk_count):
            chunk_text = " ".join(words[index * chunk_words : (index + 1) * chunk_words])
            if not chunk_text:
                continue
            meta = dict(passage["metadata"])
            meta["section_header"] = f"Built-in demo guidance chunk {index + 1}"
            chunks.append(
                {
                    "id": f"{passage['id']}_chunk_{index + 1:02d}",
                    "text": chunk_text,
                    "metadata": meta,
                    "token_count": _estimate_tokens(chunk_text),
                }
            )
    return chunks


def _route_domains_for_queries(queries: list[str]) -> list[str]:
    q = " ".join(queries).lower()
    matched = [
        domain
        for domain, keywords in _DOMAIN_KEYWORDS.items()
        if any(keyword.lower() in q for keyword in keywords)
    ]
    return matched or ["ectd_format", "ind_requirements", "sap_prespecification"]


def _build_no_prereq_index(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    tokenized = [_tokenize(chunk["text"]) for chunk in chunks]
    document_frequency: dict[str, int] = {}
    for tokens in tokenized:
        for token in set(tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1
    return {
        "tokenized": tokenized,
        "document_frequency": document_frequency,
        "total_chunks": len(chunks),
        "unique_terms": len(document_frequency),
        "average_chunk_terms": round(sum(len(tokens) for tokens in tokenized) / max(len(tokenized), 1), 1),
    }


def _score_no_prereq_chunks(
    *,
    queries: list[str],
    chunks: list[dict[str, Any]],
    index: dict[str, Any],
    top_k: int = 15,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """BM25-ish lexical scoring plus metadata/domain boosts, with no external packages."""
    query_text = " ".join(queries)
    query_terms = _tokenize(query_text)
    query_unique = set(query_terms)
    routed_domains = _route_domains_for_queries(queries)
    routed_guidelines = {
        guideline
        for domain in routed_domains
        for guideline in _DOMAIN_TO_GUIDELINES.get(domain, [])
    }
    df = index["document_frequency"]
    total_chunks = max(index["total_chunks"], 1)
    tokenized = index["tokenized"]

    scored: list[dict[str, Any]] = []
    for chunk, tokens in zip(chunks, tokenized):
        token_counts: dict[str, int] = {}
        for token in tokens:
            token_counts[token] = token_counts.get(token, 0) + 1

        matched_terms = sorted(query_unique & set(tokens))
        lexical_score = 0.0
        for term in query_unique:
            if term not in token_counts:
                continue
            idf = 1.0 + ((total_chunks + 1) / (df.get(term, 0) + 1))
            lexical_score += token_counts[term] * idf

        overlap_score = len(matched_terms) / max(len(query_unique), 1)
        meta = chunk["metadata"]
        guideline = meta.get("guideline_code", "")
        domain_boost = 1.25 if guideline in routed_guidelines else 0.0
        source_boost = 0.35 if meta.get("regulatory_body") in {"FDA", "ICH"} else 0.1
        rerank_score = lexical_score + (2.5 * overlap_score) + domain_boost + source_boost

        candidate = dict(chunk)
        candidate.update(
            {
                "lexical_score": round(lexical_score, 3),
                "overlap_score": round(overlap_score, 3),
                "domain_boost": round(domain_boost, 3),
                "rerank_score": round(rerank_score, 3),
                "rrf_score": round(rerank_score, 3),
                "matched_terms": matched_terms[:12],
            }
        )
        scored.append(candidate)

    scored.sort(key=lambda item: item["rerank_score"], reverse=True)
    retrieval_meta = {
        "query": query_text,
        "query_terms": sorted(query_unique)[:40],
        "routed_domains": routed_domains,
        "routed_guidelines": sorted(routed_guidelines),
        "candidate_count": len(scored),
    }
    return scored[:top_k], retrieval_meta


def build_no_prereq_rag_trace(queries: list[str], top_k: int = 8) -> dict[str, Any]:
    """Run the whole built-in RAG pipeline and return a UI-friendly trace."""
    source_docs = _fallback_passages()
    chunks = _chunk_fallback_passages()
    index = _build_no_prereq_index(chunks)
    candidates, retrieval_meta = _score_no_prereq_chunks(
        queries=queries,
        chunks=chunks,
        index=index,
        top_k=max(top_k, 15),
    )
    selected = candidates[:top_k]

    return {
        "runtime": "no_prereq_live_rag",
        "steps": [
            {
                "Step": "1. Load regulatory corpus",
                "Result": f"Loaded {len(source_docs)} built-in FDA/ICH/EMA/CFR source documents.",
            },
            {
                "Step": "2. Chunk source documents",
                "Result": f"Created {len(chunks)} chunks with metadata, source IDs, and effective dates.",
            },
            {
                "Step": "3. Build lexical index",
                "Result": (
                    f"Indexed {index['unique_terms']} unique terms across {index['total_chunks']} chunks "
                    f"(avg {index['average_chunk_terms']} terms/chunk)."
                ),
            },
            {
                "Step": "4. Build retrieval query",
                "Result": f"Combined {len(queries)} regulatory and package-aware queries.",
            },
            {
                "Step": "5. Route domains",
                "Result": "Matched domains: " + ", ".join(retrieval_meta["routed_domains"]),
            },
            {
                "Step": "6. Retrieve candidates",
                "Result": f"Scored {retrieval_meta['candidate_count']} candidate chunks with BM25-style lexical retrieval.",
            },
            {
                "Step": "7. Rerank candidates",
                "Result": "Applied term-overlap, guideline-domain, and FDA/ICH source boosts.",
            },
            {
                "Step": "8. Assemble prompt context",
                "Result": f"Selected top {len(selected)} cited chunks for the conformance checker prompt.",
            },
        ],
        "query": retrieval_meta["query"],
        "routed_domains": retrieval_meta["routed_domains"],
        "routed_guidelines": retrieval_meta["routed_guidelines"],
        "index_summary": {
            "source_documents": len(source_docs),
            "chunks": len(chunks),
            "unique_terms": index["unique_terms"],
            "average_chunk_terms": index["average_chunk_terms"],
        },
        "top_chunks": [
            {
                "id": candidate["metadata"].get("guideline_code", candidate["id"]),
                "title": candidate["metadata"].get("title", "Unknown"),
                "source": candidate["metadata"].get("regulatory_body", "Unknown"),
                "section": candidate["metadata"].get("section_header", "N/A"),
                "lexical_score": candidate["lexical_score"],
                "overlap_score": candidate["overlap_score"],
                "domain_boost": candidate["domain_boost"],
                "rerank_score": candidate["rerank_score"],
                "matched_terms": ", ".join(candidate["matched_terms"]),
            }
            for candidate in selected
        ],
        "selected_passages": selected,
    }


def _fallback_retrieve(queries: list[str], top_k: int = 15) -> list[dict[str, Any]]:
    query_terms = set(_tokenize(" ".join(queries)))
    scored: list[tuple[float, dict[str, Any]]] = []
    for passage in _fallback_passages():
        meta = passage["metadata"]
        searchable = " ".join(
            [
                passage["text"],
                meta.get("guideline_code", ""),
                meta.get("title", ""),
                meta.get("document_type", ""),
                meta.get("compliance_domains", ""),
                meta.get("topic_tags", ""),
            ]
        )
        terms = set(_tokenize(searchable))
        overlap = len(query_terms & terms)
        title_boost = 2.0 if meta.get("guideline_code", "").lower() in " ".join(queries).lower() else 0.0
        score = (overlap / max(len(query_terms), 1)) + title_boost
        scored.append((score, passage))

    scored.sort(key=lambda item: item[0], reverse=True)
    results: list[dict[str, Any]] = []
    for score, passage in scored[:top_k]:
        enriched = dict(passage)
        enriched["rerank_score"] = round(score, 3)
        enriched["rrf_score"] = round(score, 3)
        results.append(enriched)
    return results


def _format_passages(passages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    context_lines: list[str] = []
    retrieved_guidance_summary: list[dict[str, Any]] = []

    for i, p in enumerate(passages, 1):
        meta = p["metadata"]
        score = p.get("rerank_score", p.get("rrf_score", 0))
        context_lines.append(
            f"[{i}] {meta.get('guideline_code', 'Unknown')} | "
            f"{meta.get('section_header', 'N/A')[:80]} | "
            f"Score: {score:.3f}\n"
            f"Source: {meta.get('title', 'Unknown')} ({meta.get('regulatory_body', '?')}, "
            f"effective {meta.get('effective_date', 'unknown')})\n"
            f"Text: {p['text'][:600]}\n"
        )
        retrieved_guidance_summary.append(
            {
                "id": meta.get("guideline_code", p["id"]),
                "title": meta.get("title", "Unknown"),
                "source": meta.get("regulatory_body", "Unknown"),
                "section": meta.get("section_header", "N/A")[:80],
                "effective_date": meta.get("effective_date", "Unknown"),
                "relevance_score": round(float(score), 3),
            }
        )

    prompt_context = "\n---\n".join(context_lines) if context_lines else "(No passages retrieved)"
    return prompt_context, retrieved_guidance_summary


def _build_fallback_bundle(
    *,
    queries: list[str],
    documents: dict[str, str],
    validation_report: dict[str, Any] | None,
    reason: str,
) -> dict[str, Any]:
    rag_trace = build_no_prereq_rag_trace(queries, top_k=8)
    passages = rag_trace["selected_passages"]
    prompt_context, retrieved_guidance_summary = _format_passages(passages)
    return {
        "prompt_context": prompt_context,
        "rule_based_checks": _run_preflight(documents, validation_report),
        "retrieved_guidance_summary": retrieved_guidance_summary,
        "knowledge_base_size": rag_trace["index_summary"]["chunks"],
        "retrieval_method": "real-time no-prereq lexical RAG over built-in FDA/ICH/CFR guidance",
        "retrieval_status": "no_prereq_live_rag",
        "retrieval_note": reason,
        "rag_trace": {
            key: value
            for key, value in rag_trace.items()
            if key != "selected_passages"
        },
    }


def _chunk_document(text: str, doc_meta: dict[str, Any],
                    chunk_words: int = 450, overlap_words: int = 50) -> list[dict[str, Any]]:
    """Section-aware chunking with sliding-window fallback."""
    chunks: list[dict[str, Any]] = []

    section_pattern = re.compile(
        r"(?m)^(?:"
        r"SECTION\s+\d+|"
        r"§\s*\d+\.\d+|"
        r"\d+\.\d+(?:\.\d+)?\s+[A-Z]|"
        r"[A-Z][A-Z\s]{10,}(?:\n|$)"
        r")"
    )
    sections = section_pattern.split(text)
    headers = section_pattern.findall(text)

    if len(sections) > 3:
        for i, section_text in enumerate(sections):
            if not section_text.strip():
                continue
            header = headers[i - 1].strip() if i > 0 and i - 1 < len(headers) else "Introduction"
            words = section_text.split()
            for j in range(0, max(1, len(words) - overlap_words), chunk_words - overlap_words):
                chunk_text = " ".join(words[j : j + chunk_words])
                if len(chunk_text.strip()) < 80:
                    continue
                chunks.append({
                    **doc_meta,
                    "section_header": header[:120],
                    "chunk_index": len(chunks),
                    "text": chunk_text,
                    "token_count": _estimate_tokens(chunk_text),
                })
    else:
        words = text.split()
        for j in range(0, max(1, len(words) - overlap_words), chunk_words - overlap_words):
            chunk_text = " ".join(words[j : j + chunk_words])
            if len(chunk_text.strip()) < 80:
                continue
            chunks.append({
                **doc_meta,
                "section_header": f"chunk_{j}",
                "chunk_index": len(chunks),
                "text": chunk_text,
                "token_count": _estimate_tokens(chunk_text),
            })

    return chunks


# ── Knowledge Base Builder ────────────────────────────────────────────────────

def _build_kb() -> "_HybridRetriever":
    """Build (or load) the ChromaDB collection and BM25 index, return a retriever."""
    import chromadb
    from sentence_transformers import SentenceTransformer

    _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(_CHROMA_DIR))

    # Check if collection already exists and is populated
    try:
        collection = client.get_collection(_COLLECTION_NAME)
        count = collection.count()
        if count > 0:
            print(f"[RAG KB] Loaded existing ChromaDB collection: {count} chunks")
            return _HybridRetriever(collection, count)
    except Exception:
        pass

    # Build from scratch
    print("[RAG KB] Building knowledge base from guideline documents...")
    try:
        client.delete_collection(_COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    embedder = SentenceTransformer(_EMBEDDING_MODEL)
    total_chunks = 0

    for doc_info in _DOCUMENTS:
        doc_path = _KB_DIR / doc_info["path"]
        if not doc_path.exists():
            print(f"[RAG KB] Skipping (not found): {doc_info['guideline_code']}")
            continue

        with open(doc_path, encoding="utf-8", errors="replace") as f:
            text = f.read()

        doc_meta = {
            "guideline_code": doc_info["guideline_code"],
            "title": doc_info["title"],
            "regulatory_body": doc_info["regulatory_body"],
            "document_type": doc_info["document_type"],
            "effective_date": doc_info["effective_date"],
            "compliance_domains": json.dumps(doc_info["compliance_domains"]),
            "topic_tags": json.dumps(doc_info["topic_tags"]),
            "source_file": doc_info["path"],
        }

        chunks = _chunk_document(text, doc_meta)
        if not chunks:
            continue

        batch_size = 64
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c["text"] for c in batch]
            embeddings = embedder.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            ).tolist()
            safe_code = doc_info["guideline_code"].replace(" ", "_").replace("(", "").replace(")", "")
            ids = [f"{safe_code}_{c['chunk_index']:05d}" for c in batch]
            metadatas = [{k: v for k, v in c.items() if k != "text"} for c in batch]
            collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

        total_chunks += len(chunks)
        print(f"[RAG KB]   {doc_info['guideline_code']}: {len(chunks)} chunks")

    print(f"[RAG KB] Build complete: {total_chunks} total chunks")
    if total_chunks == 0:
        raise RuntimeError(f"No knowledge-base source documents found in {_KB_DIR}")
    return _HybridRetriever(collection, total_chunks)


# ── Hybrid Retriever ──────────────────────────────────────────────────────────

class _HybridRetriever:
    """Dense + BM25 + RRF + cross-encoder re-ranking."""

    def __init__(self, collection: Any, total_chunks: int) -> None:
        from rank_bm25 import BM25Okapi

        self.collection = collection
        self.total_chunks = total_chunks

        # Load embedding model (reuse if already loaded)
        from sentence_transformers import SentenceTransformer
        self._embedder = SentenceTransformer(_EMBEDDING_MODEL)

        # Load cross-encoder re-ranker
        try:
            from sentence_transformers import CrossEncoder
            self._reranker: Any = CrossEncoder(_RERANKER_MODEL)
        except Exception:
            self._reranker = None

        # Build BM25 index
        all_docs = collection.get(include=["documents", "metadatas"])
        self._bm25_docs: list[str] = all_docs["documents"]
        self._bm25_ids: list[str] = all_docs["ids"]
        self._bm25_metas: list[dict] = all_docs["metadatas"]
        tokenized = [doc.lower().split() for doc in self._bm25_docs]
        self._bm25 = BM25Okapi(tokenized)

    def _route_domain(self, query: str) -> list[str] | None:
        q = query.lower()
        matched: list[str] = []
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            if any(kw.lower() in q for kw in keywords):
                matched.extend(_DOMAIN_TO_GUIDELINES.get(domain, []))
        return list(set(matched)) if matched else None

    def _dense(self, query: str, domain_filter: list[str] | None, top_k: int) -> list[dict]:
        from sentence_transformers import SentenceTransformer
        qe = self._embedder.encode(query, normalize_embeddings=True).tolist()
        where = {"guideline_code": {"$in": domain_filter}} if domain_filter else None
        n = min(top_k, max(1, self.collection.count()))
        kwargs: dict[str, Any] = dict(
            query_embeddings=[qe],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )
        if where:
            kwargs["where"] = where
        r = self.collection.query(**kwargs)
        return [
            {
                "id": r["ids"][0][i],
                "text": r["documents"][0][i],
                "metadata": r["metadatas"][0][i],
                "dense_score": 1 - r["distances"][0][i],
            }
            for i in range(len(r["ids"][0]))
        ]

    def _sparse(self, query: str, top_k: int) -> list[dict]:
        scores = self._bm25.get_scores(query.lower().split())
        top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            {
                "id": self._bm25_ids[idx],
                "text": self._bm25_docs[idx],
                "metadata": self._bm25_metas[idx],
                "sparse_score": float(scores[idx]),
            }
            for idx in top_idx
            if scores[idx] > 0
        ]

    def _rrf(self, dense: list[dict], sparse: list[dict], k: int = 60) -> list[dict]:
        scores: dict[str, float] = {}
        data: dict[str, dict] = {}
        for rank, doc in enumerate(dense):
            scores[doc["id"]] = scores.get(doc["id"], 0) + 1 / (k + rank + 1)
            data[doc["id"]] = doc
        for rank, doc in enumerate(sparse):
            scores[doc["id"]] = scores.get(doc["id"], 0) + 1 / (k + rank + 1)
            if doc["id"] not in data:
                data[doc["id"]] = doc
        return [{"rrf_score": scores[i], **data[i]} for i in sorted(scores, key=scores.get, reverse=True)]

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        domain_filter = self._route_domain(query)
        dense = self._dense(query, domain_filter, top_k=20)
        sparse = self._sparse(query, top_k=20)
        fused = self._rrf(dense, sparse)[:20]

        if self._reranker is not None and fused:
            pairs = [(query, p["text"]) for p in fused]
            rerank_scores = self._reranker.predict(pairs)
            for i, p in enumerate(fused):
                p["rerank_score"] = float(rerank_scores[i])
            fused.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

        return fused[:top_k]


# ── Deterministic Preflight Checks ───────────────────────────────────────────

def _run_preflight(documents: dict[str, str], validation_report: dict | None) -> dict[str, Any]:
    """
    Fast, deterministic checks that do not require an LLM.
    These mirror the original rule_based_checks expected by ectd_agent.py.
    """
    validation_files = [
        file_info.get("path", "")
        for file_info in (validation_report or {}).get("files", [])
        if file_info.get("path")
    ]
    file_list = sorted(set(documents.keys()) | set(validation_files))

    # Module presence
    modules_present = sorted({
        f.split("/")[0].upper()
        for f in file_list
        if "/" in f and f.split("/")[0].lower().startswith("m")
    })
    expected_modules = {"M1", "M2", "M3", "M4", "M5"}
    missing_modules = sorted(expected_modules - set(modules_present))

    # XML backbone
    has_submissionunit_xml = any("submissionunit.xml" in f.lower() for f in file_list)
    has_legacy_backbone_xml = any(
        f.lower().endswith(".xml") and "backbone" in f.lower() for f in file_list
    )

    # FDA eCTD TCG path-length criterion used by the demo preflight.
    max_path_chars = 180
    long_paths = [f for f in file_list if len(f) > max_path_chars]

    # SAP lock signal
    sap_files = [k for k in documents if "sap" in k.lower() or "statistical" in k.lower()]
    sap_text = " ".join(documents.get(k, "") for k in sap_files).lower()
    sap_locked = any(term in sap_text for term in ["locked", "finalized", "lock date", "version"])

    # Validation issues passthrough
    validation_issues = (validation_report or {}).get("issues", [])
    error_count = sum(1 for i in validation_issues if i.get("severity") == "ERROR")
    warning_count = sum(1 for i in validation_issues if i.get("severity") == "WARNING")

    # Build findings list
    findings: list[dict[str, Any]] = []

    if missing_modules:
        findings.append({
            "severity": "ERROR",
            "rule_id": "ICH-M4-MODULES",
            "finding": f"Missing eCTD modules: {', '.join(missing_modules)}.",
            "recommendation": "Ensure all five CTD modules (M1–M5) are present in the submission package.",
            "source": "ICH M4E(R2) — CTD Efficacy Module",
        })

    if not has_submissionunit_xml and not has_legacy_backbone_xml:
        findings.append({
            "severity": "ERROR",
            "rule_id": "FDA-ECTD-XML-BACKBONE",
            "finding": "No eCTD XML backbone file (submissionunit.xml or backbone.xml) detected.",
            "recommendation": "Add a valid eCTD v4.0 submissionunit.xml or v3.2.2 backbone.xml per FDA eCTD TCG.",
            "source": "FDA eCTD v4.0 Technical Conformance Guide",
        })

    if long_paths:
        findings.append({
            "severity": "WARNING",
            "rule_id": "FDA-ECTD-PATH-LENGTH",
            "finding": f"{len(long_paths)} file path(s) exceed {max_path_chars} characters.",
            "recommendation": "Shorten folder and file names while preserving meaningful document titles.",
            "source": "FDA eCTD v4.0 Technical Conformance Guide",
        })

    if not sap_locked and sap_files:
        findings.append({
            "severity": "WARNING",
            "rule_id": "ICH-E9-SAP-LOCK",
            "finding": "SAP lock date or finalization confirmation not detected in SAP document.",
            "recommendation": "Confirm SAP was locked before database lock per ICH E9 Section 5.1.",
            "source": "ICH E9 — Statistical Principles for Clinical Trials, Section 5.1",
        })

    if error_count > 0:
        findings.append({
            "severity": "ERROR",
            "rule_id": "INPUT-VALIDATION",
            "finding": f"Input validation layer raised {error_count} error(s) and {warning_count} warning(s).",
            "recommendation": "Resolve all ERROR-level validation issues before submission.",
            "source": "SubmissionAI input validation",
        })

    score = max(0.5, 1.0 - 0.15 * sum(1 for f in findings if f["severity"] == "ERROR")
                       - 0.05 * sum(1 for f in findings if f["severity"] == "WARNING"))

    return {
        "modules_present": modules_present,
        "missing_modules": missing_modules,
        "has_submissionunit_xml": has_submissionunit_xml,
        "has_legacy_backbone_xml": has_legacy_backbone_xml,
        "long_paths": long_paths,
        "max_path_chars": max_path_chars,
        "sap_locked": sap_locked,
        "findings": findings,
        "score": round(score, 3),
    }


# ── Retrieval Queries for Conformance Check ───────────────────────────────────

_CONFORMANCE_QUERIES = [
    "SAP pre-specification requirements before database lock",
    "eCTD module structure and folder naming requirements",
    "missing data handling NRI LOCF imputation methods",
    "IND investigational new drug application content requirements 21 CFR 312",
    "clinical study report structure and content ICH E3",
    "CDISC SDTM ADaM dataset submission requirements",
    "multiplicity adjustment gatekeeping hierarchical testing",
    "electronic records audit trail 21 CFR Part 11",
    "adaptive design interim analysis pre-specification",
    "subgroup analysis pre-specified post-hoc labeling requirements",
]


# ── Public API ────────────────────────────────────────────────────────────────

def _get_retriever() -> "_HybridRetriever":
    """Lazy-load the retriever singleton."""
    global _retriever
    if _retriever is None:
        _retriever = _build_kb()
    return _retriever


def build_conformance_rag_bundle(
    extracted_data: dict[str, Any],
    provenance: dict[str, Any],
    sap: dict[str, Any],
    documents: dict[str, str],
    validation_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build the RAG bundle consumed by ectd_agent.agent_check_conformance().

    Returns a dict with:
        prompt_context              : str  — formatted passages for the LLM prompt
        rule_based_checks           : dict — deterministic preflight findings
        retrieved_guidance_summary  : list — UI-friendly list of retrieved chunks
        knowledge_base_size         : int  — total indexed chunks
    """
    # Build context-aware queries from the submission content
    queries = list(_CONFORMANCE_QUERIES)

    # Add dynamic queries from extracted data
    primary_ep = (extracted_data.get("phase3") or {}).get("primary_endpoint", "")
    if primary_ep:
        queries.append(f"primary endpoint {primary_ep} statistical analysis requirements")

    sap_issues = (sap.get("issues") or [])
    for issue in sap_issues[:3]:
        if issue.get("issue"):
            queries.append(issue["issue"])

    try:
        retriever = _get_retriever()
    except Exception as exc:
        # Graceful degradation keeps the demo useful without large local ML deps.
        print(f"[RAG KB] Warning: could not load full hybrid retriever ({exc}). Using no-prereq live RAG.")
        return _build_fallback_bundle(
            queries=queries,
            documents=documents,
            validation_report=validation_report,
            reason=str(exc),
        )

    # Retrieve passages for all queries, deduplicate by chunk ID
    seen_ids: set[str] = set()
    all_passages: list[dict] = []
    for query in queries[:8]:  # cap at 8 queries to keep latency reasonable
        try:
            passages = retriever.retrieve(query, top_k=3)
            for p in passages:
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    all_passages.append(p)
        except Exception:
            continue

    # Sort by rerank score (descending), keep top 15 for the prompt
    all_passages.sort(key=lambda x: x.get("rerank_score", x.get("rrf_score", 0)), reverse=True)
    top_passages = all_passages[:15]

    prompt_context, retrieved_guidance_summary = _format_passages(top_passages)

    # Run deterministic preflight
    rule_based_checks = _run_preflight(documents, validation_report)

    return {
        "prompt_context": prompt_context,
        "rule_based_checks": rule_based_checks,
        "retrieved_guidance_summary": retrieved_guidance_summary,
        "knowledge_base_size": retriever.total_chunks,
        "retrieval_method": "hybrid dense ChromaDB + BM25 + RRF + cross-encoder reranking",
        "retrieval_status": "full_hybrid",
    }


# ── KB Metadata for UI ────────────────────────────────────────────────────────

def get_kb_metadata() -> dict[str, Any]:
    """
    Return metadata about the knowledge base for the Streamlit UI.
    Does NOT trigger a full KB build — reads from ChromaDB if available.
    """
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
        collection = client.get_collection(_COLLECTION_NAME)
        count = collection.count()
    except Exception:
        count = 0

    dependency_status = _dependency_status()

    docs_on_disk = [
        {
            "guideline_code": d["guideline_code"],
            "title": d["title"],
            "regulatory_body": d["regulatory_body"],
            "document_type": d["document_type"],
            "effective_date": d["effective_date"],
            "file_exists": (_KB_DIR / d["path"]).exists(),
            "file_size_kb": round((_KB_DIR / d["path"]).stat().st_size / 1024, 1)
            if (_KB_DIR / d["path"]).exists() else 0,
        }
        for d in _DOCUMENTS
    ]

    return {
        "total_documents": len(_DOCUMENTS),
        "documents_on_disk": sum(1 for d in docs_on_disk if d["file_exists"]),
        "total_chunks_indexed": count,
        "fallback_chunks_available": len(_chunk_fallback_passages()),
        "runtime_mode": "full_hybrid" if count > 0 else "no_prereq_live_rag",
        "chroma_db_path": str(_CHROMA_DIR),
        "kb_dir": str(_KB_DIR),
        "embedding_model": _EMBEDDING_MODEL,
        "reranker_model": _RERANKER_MODEL,
        "dependency_status": dependency_status,
        "full_stack_ready": count > 0 and all(dependency_status.values()),
        "documents": docs_on_disk,
    }
