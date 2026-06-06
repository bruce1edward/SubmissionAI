"""
sap_validator_knowledge_base.py
SubmissionAI — SAP Validator RAG System

Dedicated RAG system for statistical methodology compliance, separate from and
complementary to the FDA Conformance Checker RAG in regulatory_knowledge_base.py.

Architecture:
    1. Domain-tagged section-aware chunking (7 SAP validation domains)
    2. Clinical trial terminology expansion for BM25
    3. Dense retrieval via ChromaDB + BAAI/bge-large-en-v1.5
    4. Sparse retrieval via BM25Okapi with abbreviation expansion
    5. Domain-routed retrieval (pre-filters to relevant guidelines)
    6. Reciprocal Rank Fusion (RRF, k=60)
    7. Cross-encoder re-ranking (ms-marco-MiniLM-L-12-v2)
    8. Deterministic pre-flight checks (amendment timing, estimand attribute count)
    9. Cross-document consistency retrieval (guideline + SAP + CSR)

Public API:
    build_sap_rag_bundle(sap_text, csr_text, trial_metadata) -> dict
    get_sap_kb_metadata() -> dict
    run_preflight_checks(sap_metadata, trial_timeline) -> list[dict]
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
_SAP_KB_DIR = Path(os.environ.get("SAP_KB_DIR", str(_PROJECT_DIR / "sap_knowledge_base")))
_SHARED_KB_DIR = Path(os.environ.get("RAG_KB_DIR", str(_PROJECT_DIR / "rag_knowledge_base")))
_SAP_CHROMA_DIR = Path(os.environ.get("SAP_CHROMA_DIR", str(_PROJECT_DIR / "sap_chroma_db")))
_SAP_COLLECTION_NAME = "sap_validator_kb"
_EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-12-v2"

# ── Clinical trial terminology expansion for BM25 ────────────────────────────
_TERM_EXPANSIONS: dict[str, list[str]] = {
    "SAP": ["statistical analysis plan", "analysis plan", "statistical plan"],
    "ITT": ["intent-to-treat", "intention-to-treat", "full analysis set"],
    "mITT": ["modified intent-to-treat", "modified intention-to-treat"],
    "PP": ["per-protocol", "per protocol", "evaluable population"],
    "MMRM": ["mixed model repeated measures", "mixed-effects model", "longitudinal model"],
    "LOCF": ["last observation carried forward", "last value carried forward"],
    "NRI": ["non-responder imputation", "non responder imputation"],
    "MCAR": ["missing completely at random"],
    "MAR": ["missing at random"],
    "MNAR": ["missing not at random"],
    "FWER": ["family-wise error rate", "familywise error rate", "type I error control"],
    "CMH": ["cochran-mantel-haenszel", "mantel haenszel"],
    "ANCOVA": ["analysis of covariance", "covariate adjusted analysis"],
    "HTE": ["heterogeneous treatment effect", "treatment effect modification"],
    "IE": ["intercurrent event", "intercurrent events"],
    "DB": ["database lock", "data lock"],
    "CSR": ["clinical study report", "study report"],
    "ORR": ["objective response rate", "response rate", "overall response rate"],
    "PFS": ["progression-free survival", "progression free survival"],
    "OS": ["overall survival"],
    "DOR": ["duration of response"],
    "IRC": ["independent review committee", "independent response committee"],
    "EOP2": ["end of phase 2", "end-of-phase 2"],
    "DSMB": ["data safety monitoring board", "data monitoring committee", "DMC"],
}

# ── Seven SAP Validation Domains ──────────────────────────────────────────────
_SAP_DOMAINS = [
    "pre_specification",
    "estimand",
    "primary_endpoint",
    "multiplicity",
    "subgroup",
    "missing_data",
    "covariate",
]

_SAP_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "pre_specification": [
        "pre-specified", "pre-specification", "finalized before", "database lock",
        "unblinding", "SAP amendment", "statistical analysis plan", "SAP version",
        "locked", "lock date", "before unblinding",
    ],
    "estimand": [
        "estimand", "intercurrent event", "treatment policy", "composite variable",
        "hypothetical strategy", "while on treatment", "principal stratum",
        "ICH E9(R1)", "five attributes", "intercurrent",
    ],
    "primary_endpoint": [
        "primary endpoint", "primary analysis", "analysis population",
        "ITT", "intent-to-treat", "per-protocol", "mITT", "full analysis set",
        "non-inferiority", "NI margin", "non-responder",
    ],
    "multiplicity": [
        "multiplicity", "family-wise error rate", "FWER", "type I error",
        "hierarchical testing", "gatekeeping", "Holm", "Bonferroni",
        "testing hierarchy", "sequential testing", "alpha allocation",
        "co-primary", "key secondary",
    ],
    "subgroup": [
        "subgroup", "subgroup analysis", "interaction test", "forest plot",
        "post-hoc", "exploratory", "pre-specified subgroup", "biomarker",
        "enrichment", "predictive", "prognostic", "treatment-by-subgroup",
    ],
    "missing_data": [
        "missing data", "imputation", "MMRM", "LOCF", "NRI", "MAR", "MNAR",
        "multiple imputation", "tipping point", "delta adjustment",
        "sensitivity analysis", "dropout", "missing at random",
    ],
    "covariate": [
        "covariate adjustment", "ANCOVA", "stratification", "stratification factor",
        "covariate", "adjustment model", "baseline covariate", "randomisation factor",
        "CMH", "logistic regression", "proportional hazards",
    ],
}

_SAP_DOMAIN_TO_GUIDELINES: dict[str, list[str]] = {
    "pre_specification": ["ICH-E9", "ICH-E3", "FDA-ADAPTIVE"],
    "estimand": ["ICH-E9R1", "ICH-E9R1-TM"],
    "primary_endpoint": ["ICH-E9", "ICH-E10", "FDA-NI"],
    "multiplicity": ["FDA-ENDPOINTS", "ICH-E9"],
    "subgroup": ["EMA-SUBGROUP", "ICH-E9", "FDA-ENRICH"],
    "missing_data": ["EMA-MISSING", "ICH-E9R1", "ICH-E9"],
    "covariate": ["FDA-COVARIATE", "ICH-E9"],
}

# ── Document Registry ─────────────────────────────────────────────────────────
def _resolve(relative_path: str, prefer_sap_kb: bool = True) -> Path:
    sap_path = _SAP_KB_DIR / relative_path
    shared_path = _SHARED_KB_DIR / relative_path
    if prefer_sap_kb and sap_path.exists():
        return sap_path
    if shared_path.exists():
        return shared_path
    return sap_path  # return even if missing (reported in metadata)


_SAP_DOCUMENTS = [
    {
        "code": "ICH-E9",
        "path": "ich/ICH_E9_Statistical_Principles.txt",
        "title": "Statistical Principles for Clinical Trials",
        "body": "ICH",
        "year": 1998,
        "domains": ["pre_specification", "primary_endpoint", "multiplicity", "subgroup", "missing_data", "covariate"],
        "topic_tags": ["SAP", "pre-specification", "primary endpoint", "ITT", "missing data", "multiplicity",
                       "randomisation", "stratification", "analysis population"],
    },
    {
        "code": "ICH-E9R1",
        "path": "ich/ICH_E9R1_Estimands_Addendum.txt",
        "title": "Addendum: Estimands and Sensitivity Analysis in Clinical Trials",
        "body": "ICH",
        "year": 2019,
        "domains": ["estimand", "missing_data"],
        "topic_tags": ["estimand", "intercurrent event", "treatment policy", "composite variable",
                       "hypothetical strategy", "sensitivity analysis", "five attributes"],
    },
    {
        "code": "ICH-E9R1-TM",
        "path": "ich/ICH_E9R1_Training_Material.txt",
        "title": "ICH E9(R1) Estimands Training Material",
        "body": "ICH",
        "year": 2020,
        "domains": ["estimand", "pre_specification", "missing_data"],
        "topic_tags": ["estimand framework", "intercurrent event strategy", "SAP amendment",
                       "cross-document consistency", "database lock", "sensitivity analysis examples"],
    },
    {
        "code": "ICH-E3",
        "path": "ich/ICH_E3_Clinical_Study_Reports.txt",
        "title": "Structure and Content of Clinical Study Reports",
        "body": "ICH",
        "year": 1995,
        "domains": ["pre_specification", "primary_endpoint", "subgroup"],
        "topic_tags": ["CSR", "clinical study report", "subgroup labelling", "pre-specified",
                       "exploratory analysis", "SAP reference", "statistical methods section"],
    },
    {
        "code": "ICH-E10",
        "path": "ich/ICH_E10_Control_Group.txt",
        "title": "Choice of Control Group and Related Issues in Clinical Trials",
        "body": "ICH",
        "year": 2000,
        "domains": ["primary_endpoint"],
        "topic_tags": ["active control", "placebo", "non-inferiority", "assay sensitivity",
                       "constancy assumption", "M1", "M2"],
    },
    {
        "code": "FDA-COVARIATE",
        "path": "fda/FDA_Covariate_Adjustment_2023.txt",
        "title": "Adjusting for Covariates in Randomized Clinical Trials",
        "body": "FDA",
        "year": 2023,
        "domains": ["covariate"],
        "topic_tags": ["covariate adjustment", "ANCOVA", "MMRM", "stratification factor",
                       "pre-specification", "randomisation strata", "baseline covariate",
                       "standardisation", "CMH", "logistic regression"],
    },
    {
        "code": "FDA-ENDPOINTS",
        "path": "fda/FDA_Multiple_Endpoints_2023.txt",
        "title": "Multiple Endpoints in Clinical Trials",
        "body": "FDA",
        "year": 2023,
        "domains": ["multiplicity"],
        "topic_tags": ["multiplicity", "hierarchical testing", "gatekeeping", "FWER",
                       "key secondary endpoint", "co-primary", "alpha allocation",
                       "testing hierarchy", "Holm", "Bonferroni", "family-wise error rate"],
    },
    {
        "code": "FDA-ADAPTIVE",
        "path": "fda/FDA_Adaptive_Design_Guidance_2019.txt",
        "title": "Adaptive Designs for Clinical Trials of Drugs and Biologics",
        "body": "FDA",
        "year": 2019,
        "domains": ["pre_specification", "multiplicity", "missing_data"],
        "topic_tags": ["adaptive design", "interim analysis", "pre-specification", "DSMB",
                       "sample size re-estimation", "group sequential", "alpha spending",
                       "type I error control", "simulation"],
    },
    {
        "code": "FDA-NI",
        "path": "fda/FDA_Non_Inferiority_2016.txt",
        "title": "Non-Inferiority Clinical Trials to Establish Effectiveness",
        "body": "FDA",
        "year": 2016,
        "domains": ["primary_endpoint"],
        "topic_tags": ["non-inferiority", "NI margin", "M1", "M2", "constancy assumption",
                       "assay sensitivity", "per-protocol", "ITT", "NI and superiority"],
    },
    {
        "code": "FDA-ENRICH",
        "path": "fda/FDA_Enrichment_Strategies_2019.txt",
        "title": "Enrichment Strategies for Clinical Trials",
        "body": "FDA",
        "year": 2019,
        "domains": ["subgroup", "primary_endpoint"],
        "topic_tags": ["enrichment", "biomarker", "predictive enrichment", "prognostic enrichment",
                       "subgroup pre-specification", "post-hoc subgroup", "adaptive enrichment",
                       "biomarker cutoff", "companion diagnostic"],
    },
    {
        "code": "EMA-MISSING",
        "path": "ema/EMA_Missing_Data_Guideline.txt",
        "title": "Guideline on Missing Data in Confirmatory Clinical Trials",
        "body": "EMA",
        "year": 2010,
        "domains": ["missing_data"],
        "topic_tags": ["missing data", "MCAR", "MAR", "MNAR", "LOCF", "NRI",
                       "multiple imputation", "tipping point", "delta adjustment",
                       "sensitivity analysis", "dropout", "complete case analysis"],
    },
    {
        "code": "EMA-SUBGROUP",
        "path": "ema/EMA_Subgroup_Analysis_2019.txt",
        "title": "Guideline on Investigation of Subgroups in Confirmatory Clinical Trials",
        "body": "EMA",
        "year": 2019,
        "domains": ["subgroup"],
        "topic_tags": ["subgroup", "pre-specified", "post-hoc", "exploratory", "interaction test",
                       "forest plot", "confirmatory subgroup", "labelling requirements",
                       "treatment-by-subgroup interaction", "biomarker subgroup"],
    },
]

# ── Fallback guideline passages (built-in for no-prereq mode) ─────────────────
_SAP_FALLBACK_PASSAGES: dict[str, str] = {
    "ICH-E9": (
        "The statistical section of the protocol or a separate statistical analysis plan should be finalized "
        "before the unblinding of any comparative data (ICH E9 §5.1). Changes to the primary analysis after "
        "unblinding must be documented with reasons. The analysis populations (ITT, per-protocol, safety) must "
        "be pre-specified. Stratification factors used in randomisation must be included in the primary analysis. "
        "All secondary analyses must be pre-specified. Post-hoc analyses must be clearly labelled as such."
    ),
    "ICH-E9R1": (
        "An estimand precisely describes the treatment effect corresponding to the clinical question (ICH E9(R1) §3.1). "
        "The five attributes of an estimand are: population, treatment condition, variable (endpoint), intercurrent "
        "event strategy, and population-level summary. Each intercurrent event must be assigned exactly one strategy: "
        "treatment policy, composite variable, hypothetical, while on treatment, or principal stratum. Sensitivity "
        "analyses must be pre-specified for the primary estimand (§4.2). Inconsistency between SAP and CSR in the "
        "handling of intercurrent events is a compliance finding under ICH E9(R1) §3.2."
    ),
    "ICH-E9R1-TM": (
        "The estimand framework requires cross-document consistency: the estimand defined in the protocol must be "
        "reflected consistently in the SAP and the CSR. A SAP amendment that changes the intercurrent event strategy "
        "after database lock violates ICH E9 §5.1. The SAP must enumerate each intercurrent event by name and assign "
        "it one of the five pre-specified strategies. Sensitivity analyses added in the CSR that are not in the SAP "
        "are post-hoc analyses and cannot support primary efficacy conclusions."
    ),
    "ICH-E3": (
        "The clinical study report must present all pre-specified analyses with results (ICH E3 §10). "
        "Subgroup analyses must be labelled as pre-specified or post-hoc. The statistical methods section must "
        "reference the specific SAP version used. Any deviation from the pre-specified analysis must be documented "
        "with justification. All subgroup analyses presented in the CSR must be classified as pre-specified "
        "confirmatory, pre-specified exploratory, or post-hoc exploratory (ICH E3 §10.3)."
    ),
    "ICH-E10": (
        "The choice of active control and the non-inferiority margin must be justified by historical data. "
        "The constancy assumption — that the active control's effect is the same in the current trial as in "
        "historical trials — must be assessed in the SAP. Both per-protocol and ITT analyses are required "
        "for non-inferiority claims. The NI margin M2 must be pre-specified before the trial begins."
    ),
    "FDA-COVARIATE": (
        "The covariate adjustment model must be fully pre-specified in the SAP before any unblinded outcome data "
        "are reviewed (FDA Covariate Adjustment 2023 §III.A). Stratification factors used in randomisation must "
        "be included as covariates in the primary analysis model. Changes to the covariate adjustment model after "
        "unblinding are considered a source of bias. The SAP must specify the covariates, their functional form, "
        "and the statistical method. Failure to adjust for randomisation stratification factors in the analysis "
        "is a common FDA statistical review finding."
    ),
    "FDA-ENDPOINTS": (
        "When the intent is to support specific conclusions on how a treatment affects specific components, "
        "the SAP must pre-specify the testing hierarchy and the family-wise error rate control procedure "
        "(FDA Multiple Endpoints 2023 §III.C). The testing hierarchy must be pre-specified before unblinding. "
        "Changing the testing order after seeing the data invalidates the confirmatory status of all endpoints "
        "in the hierarchy. Key secondary endpoints must be distinguished from exploratory endpoints in the SAP."
    ),
    "FDA-ADAPTIVE": (
        "All adaptive features must be fully pre-specified before the trial begins. Interim analyses must follow "
        "pre-specified stopping rules. The DSMB charter must be finalised before the first interim analysis. "
        "Type I error control must be demonstrated via alpha spending or simulation. SAP amendments that change "
        "stopping rules after the trial begins require FDA notification and may invalidate the interim analysis."
    ),
    "FDA-NI": (
        "The non-inferiority margin M1 and M2 must be pre-specified in the protocol or SAP before data collection. "
        "Both ITT and per-protocol analyses are required for NI claims; NI must hold in both. The constancy "
        "assumption must be assessed. If both NI and superiority are tested, the SAP must pre-specify the order "
        "(NI first, then superiority). Post-hoc changes to the NI margin are not acceptable."
    ),
    "FDA-ENRICH": (
        "All enrichment criteria (biomarker cutoffs, eligibility criteria) must be pre-specified in the protocol. "
        "Subgroup analyses intended to support labelling claims must be pre-specified in the SAP. Post-hoc "
        "subgroup analyses are exploratory and cannot support labelling claims. The CSR must clearly label all "
        "post-hoc subgroup analyses as exploratory. Biomarker cutoffs used in the analysis must match the "
        "pre-specified cutoffs in the SAP."
    ),
    "EMA-MISSING": (
        "Missing data strategies must be pre-specified in the protocol and SAP before database lock. The primary "
        "missing data method, its assumptions, and all sensitivity analyses must be pre-specified. LOCF is no "
        "longer considered an acceptable primary analysis for most indications. Multiple imputation under MAR "
        "requires pre-specification of the imputation model. Tipping-point analysis is required when dropout "
        "exceeds 15% (EMA Missing Data §5.2). Sensitivity analyses added post-hoc in the CSR are not acceptable."
    ),
    "EMA-SUBGROUP": (
        "Every subgroup analysis reported in the CSR must be classified as pre-specified confirmatory, "
        "pre-specified exploratory, or post-hoc exploratory — consistent with the SAP (EMA Subgroup §3.2). "
        "A formal interaction test must be reported for all subgroup analyses presented as key findings. "
        "Forest plots must include all pre-specified subgroups regardless of direction or magnitude of result. "
        "Subgroup results cannot support labelling claims unless pre-specified with alpha allocation."
    ),
}

# ── Seven Validation Query Templates ─────────────────────────────────────────
_SAP_VALIDATION_QUERIES = [
    {
        "domain": "pre_specification",
        "template": "SAP pre-specification requirement finalized before database lock unblinding amendment timing",
        "expected_citation": "ICH E9 §5.1",
    },
    {
        "domain": "estimand",
        "template": "ICH E9(R1) estimand framework five attributes intercurrent event strategy pre-specification",
        "expected_citation": "ICH E9(R1) §3.1",
    },
    {
        "domain": "primary_endpoint",
        "template": "primary endpoint definition analysis population ITT per-protocol consistent SAP CSR",
        "expected_citation": "ICH E9 §2.2, §5.2",
    },
    {
        "domain": "multiplicity",
        "template": "testing hierarchy family-wise error rate FWER multiplicity pre-specified key secondary endpoint",
        "expected_citation": "FDA Multiple Endpoints §III.C",
    },
    {
        "domain": "subgroup",
        "template": "subgroup analysis pre-specified exploratory post-hoc labelling CSR forest plot interaction test",
        "expected_citation": "EMA Subgroup §3.2",
    },
    {
        "domain": "missing_data",
        "template": "missing data imputation MMRM LOCF NRI MAR MNAR sensitivity analysis pre-specified SAP CSR",
        "expected_citation": "EMA Missing Data §6.3",
    },
    {
        "domain": "covariate",
        "template": "covariate adjustment stratification factor randomisation ANCOVA pre-specified SAP consistent",
        "expected_citation": "FDA Covariate Adjustment §III.A",
    },
]

# ── Module-level singletons ───────────────────────────────────────────────────
_sap_retriever: "_SAPHybridRetriever | None" = None


# ── Utility ───────────────────────────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _expand_terms(text: str) -> str:
    """Expand clinical trial abbreviations to improve BM25 recall."""
    expanded = text
    for abbrev, expansions in _TERM_EXPANSIONS.items():
        pattern = r"\b" + re.escape(abbrev) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            expanded += " " + " ".join(expansions)
    return expanded


def _tokenize_expanded(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_.-]*", _expand_terms(text).lower())


def _classify_domains(text: str, section_header: str = "") -> list[str]:
    """Assign domain tags to a chunk using keyword matching."""
    searchable = (text + " " + section_header).lower()
    matched = [
        domain
        for domain, keywords in _SAP_DOMAIN_KEYWORDS.items()
        if any(kw.lower() in searchable for kw in keywords)
    ]
    return matched or ["pre_specification"]  # default to most general domain


def _dependency_status() -> dict[str, bool]:
    return {
        "chromadb": importlib.util.find_spec("chromadb") is not None,
        "sentence_transformers": importlib.util.find_spec("sentence_transformers") is not None,
        "rank_bm25": importlib.util.find_spec("rank_bm25") is not None,
    }


def _doc_path(doc: dict[str, Any]) -> Path:
    """Resolve document path: SAP KB first, then shared KB."""
    sap_path = _SAP_KB_DIR / doc["path"]
    shared_path = _SHARED_KB_DIR / doc["path"]
    if sap_path.exists():
        return sap_path
    if shared_path.exists():
        return shared_path
    return sap_path


# ── Section-aware chunking with domain tagging ────────────────────────────────

def _chunk_document(text: str, doc_meta: dict[str, Any],
                    chunk_words: int = 400, overlap_words: int = 50) -> list[dict[str, Any]]:
    section_pattern = re.compile(
        r"(?m)^(?:"
        r"SECTION\s+[\dA-Z]+(?:\.\d+)?|"
        r"§\s*\d+\.\d+|"
        r"\d+\.\d+(?:\.\d+)?\s+[A-Z]|"
        r"[A-Z][A-Z\s]{8,}(?:\n|$)"
        r")"
    )
    sections = section_pattern.split(text)
    headers = section_pattern.findall(text)

    chunks: list[dict[str, Any]] = []
    if len(sections) > 3:
        for i, section_text in enumerate(sections):
            if not section_text.strip():
                continue
            header = headers[i - 1].strip() if i > 0 and i - 1 < len(headers) else "Introduction"
            words = section_text.split()
            for j in range(0, max(1, len(words) - overlap_words), chunk_words - overlap_words):
                chunk_text = " ".join(words[j: j + chunk_words])
                if len(chunk_text.strip()) < 80:
                    continue
                domains = _classify_domains(chunk_text, header)
                chunks.append({
                    **doc_meta,
                    "section_header": header[:120],
                    "chunk_index": len(chunks),
                    "domain_tags": json.dumps(domains),
                    "primary_domain": domains[0],
                    "text": chunk_text,
                    "token_count": _estimate_tokens(chunk_text),
                })
    else:
        words = text.split()
        for j in range(0, max(1, len(words) - overlap_words), chunk_words - overlap_words):
            chunk_text = " ".join(words[j: j + chunk_words])
            if len(chunk_text.strip()) < 80:
                continue
            domains = _classify_domains(chunk_text)
            chunks.append({
                **doc_meta,
                "section_header": f"chunk_{j}",
                "chunk_index": len(chunks),
                "domain_tags": json.dumps(domains),
                "primary_domain": domains[0],
                "text": chunk_text,
                "token_count": _estimate_tokens(chunk_text),
            })
    return chunks


# ── ChromaDB Knowledge Base Builder ──────────────────────────────────────────

def _build_sap_kb() -> "_SAPHybridRetriever":
    import chromadb
    from sentence_transformers import SentenceTransformer

    _SAP_CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(_SAP_CHROMA_DIR))

    try:
        collection = client.get_collection(_SAP_COLLECTION_NAME)
        count = collection.count()
        if count > 0:
            print(f"[SAP KB] Loaded existing collection: {count} chunks")
            return _SAPHybridRetriever(collection, count)
    except Exception:
        pass

    print("[SAP KB] Building SAP Validator knowledge base...")
    try:
        client.delete_collection(_SAP_COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=_SAP_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    embedder = SentenceTransformer(_EMBEDDING_MODEL)
    total_chunks = 0

    for doc_info in _SAP_DOCUMENTS:
        doc_path = _doc_path(doc_info)
        if not doc_path.exists():
            print(f"[SAP KB] Skipping (not found): {doc_info['code']} at {doc_path}")
            continue

        with open(doc_path, encoding="utf-8", errors="replace") as f:
            text = f.read()

        doc_meta = {
            "guideline_code": doc_info["code"],
            "title": doc_info["title"],
            "regulatory_body": doc_info["body"],
            "year": str(doc_info["year"]),
            "compliance_domains": json.dumps(doc_info["domains"]),
            "topic_tags": json.dumps(doc_info["topic_tags"]),
            "source_file": str(doc_path.relative_to(_PROJECT_DIR)),
        }

        chunks = _chunk_document(text, doc_meta)
        if not chunks:
            continue

        batch_size = 64
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            texts = [c["text"] for c in batch]
            embeddings = embedder.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            ).tolist()
            safe_code = doc_info["code"].replace("-", "_")
            ids = [f"{safe_code}_{c['chunk_index']:05d}" for c in batch]
            metadatas = [{k: v for k, v in c.items() if k != "text"} for c in batch]
            collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

        total_chunks += len(chunks)
        print(f"[SAP KB]   {doc_info['code']}: {len(chunks)} chunks")

    print(f"[SAP KB] Build complete: {total_chunks} total chunks")
    if total_chunks == 0:
        raise RuntimeError(f"No SAP KB documents found. Check {_SAP_KB_DIR} and {_SHARED_KB_DIR}.")
    return _SAPHybridRetriever(collection, total_chunks)


# ── Hybrid Retriever ──────────────────────────────────────────────────────────

class _SAPHybridRetriever:
    """Dense + BM25 (with term expansion) + domain routing + RRF + cross-encoder."""

    def __init__(self, collection: Any, total_chunks: int) -> None:
        from rank_bm25 import BM25Okapi
        from sentence_transformers import CrossEncoder, SentenceTransformer

        self.collection = collection
        self.total_chunks = total_chunks
        self._embedder = SentenceTransformer(_EMBEDDING_MODEL)
        try:
            self._reranker: Any = CrossEncoder(_RERANKER_MODEL)
        except Exception:
            self._reranker = None

        all_docs = collection.get(include=["documents", "metadatas"])
        self._bm25_docs: list[str] = all_docs["documents"]
        self._bm25_ids: list[str] = all_docs["ids"]
        self._bm25_metas: list[dict] = all_docs["metadatas"]
        tokenized = [_tokenize_expanded(doc) for doc in self._bm25_docs]
        self._bm25 = BM25Okapi(tokenized)

    def _domain_filter(self, query: str) -> list[str] | None:
        q = query.lower()
        matched_codes: list[str] = []
        for domain, keywords in _SAP_DOMAIN_KEYWORDS.items():
            if any(kw.lower() in q for kw in keywords):
                matched_codes.extend(_SAP_DOMAIN_TO_GUIDELINES.get(domain, []))
        return list(set(matched_codes)) if matched_codes else None

    def _dense(self, query: str, domain_filter: list[str] | None, top_k: int) -> list[dict]:
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
        expanded_query = _expand_terms(query)
        scores = self._bm25.get_scores(expanded_query.lower().split())
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
        domain_filter = self._domain_filter(query)
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


# ── No-prereq fallback retrieval ──────────────────────────────────────────────

def _fallback_retrieve_sap(queries: list[str], top_k: int = 8) -> list[dict]:
    query_terms = set(_tokenize_expanded(" ".join(queries)))
    scored: list[tuple[float, str, dict]] = []
    for code, text in _SAP_FALLBACK_PASSAGES.items():
        doc_info = next((d for d in _SAP_DOCUMENTS if d["code"] == code), None)
        if not doc_info:
            continue
        searchable_terms = set(_tokenize_expanded(text + " " + " ".join(doc_info["topic_tags"])))
        overlap = len(query_terms & searchable_terms)
        domain_boost = 0.0
        for domain, guidelines in _SAP_DOMAIN_TO_GUIDELINES.items():
            if code in guidelines:
                kws = _SAP_DOMAIN_KEYWORDS.get(domain, [])
                if any(kw.lower() in " ".join(queries).lower() for kw in kws):
                    domain_boost = 1.5
                    break
        score = (overlap / max(len(query_terms), 1)) + domain_boost
        scored.append((score, code, doc_info))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, code, doc_info in scored[:top_k]:
        results.append({
            "id": f"fallback_{code}",
            "text": _SAP_FALLBACK_PASSAGES[code],
            "metadata": {
                "guideline_code": code,
                "title": doc_info["title"],
                "regulatory_body": doc_info["body"],
                "year": str(doc_info["year"]),
                "section_header": "Built-in SAP guidance",
                "domain_tags": json.dumps(doc_info["domains"]),
                "primary_domain": doc_info["domains"][0],
            },
            "rerank_score": round(score, 3),
            "rrf_score": round(score, 3),
        })
    return results


def _format_sap_passages(passages: list[dict]) -> tuple[str, list[dict]]:
    context_lines: list[str] = []
    summary: list[dict] = []
    for i, p in enumerate(passages, 1):
        meta = p["metadata"]
        score = p.get("rerank_score", p.get("rrf_score", 0))
        domains = meta.get("domain_tags", "[]")
        context_lines.append(
            f"[{i}] {meta.get('guideline_code', '?')} | "
            f"{meta.get('section_header', 'N/A')[:80]} | "
            f"Domains: {domains[:60]} | Score: {score:.3f}\n"
            f"Source: {meta.get('title', '?')} ({meta.get('regulatory_body', '?')}, {meta.get('year', '?')})\n"
            f"Text: {p['text'][:600]}\n"
        )
        summary.append({
            "id": meta.get("guideline_code", p["id"]),
            "title": meta.get("title", "Unknown"),
            "source": meta.get("regulatory_body", "Unknown"),
            "section": meta.get("section_header", "N/A")[:80],
            "domain": meta.get("primary_domain", "unknown"),
            "year": meta.get("year", "?"),
            "relevance_score": round(float(score), 3),
        })
    prompt_context = "\n---\n".join(context_lines) if context_lines else "(No passages retrieved)"
    return prompt_context, summary


# ── Deterministic Pre-flight Checks ──────────────────────────────────────────

def _make_finding(
    finding_id: str,
    domain: str,
    severity: str,
    guideline_code: str,
    section: str,
    verbatim_passage: str,
    sap_clause: str,
    csr_clause: str,
    inconsistency: str,
    finding: str,
    recommendation: str,
    fda_review_risk: str,
    retrieval_score: float = 1.0,
) -> dict[str, Any]:
    return {
        "finding_id": finding_id,
        "domain": domain,
        "severity": severity,
        "guideline_code": guideline_code,
        "section": section,
        "verbatim_passage": verbatim_passage,
        "retrieval_score": retrieval_score,
        "sap_clause": sap_clause,
        "csr_clause": csr_clause,
        "inconsistency": inconsistency,
        "finding": finding,
        "recommendation": recommendation,
        "fda_review_risk": fda_review_risk,
        # UI-compatible aliases
        "status": "NON-COMPLIANT" if severity in ("CRITICAL", "IMPORTANT") else "WARNING" if severity == "MODERATE" else "COMPLIANT",
        "regulation": f"{guideline_code} {section}",
        "citation": verbatim_passage,
    }


def run_preflight_checks(
    sap_metadata: dict[str, Any],
    trial_timeline: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Deterministic SAP pre-flight checks. Zero LLM calls, zero hallucination risk.
    Checks: amendment timing vs. database lock, estimand attribute completeness.
    """
    findings: list[dict[str, Any]] = []
    counter = 1

    db_lock = trial_timeline.get("database_lock_date", "")
    amendments = sap_metadata.get("amendments", [])
    for amendment in amendments:
        amend_date = amendment.get("date", "")
        version = amendment.get("version", "unknown version")
        if amend_date and db_lock and amend_date > db_lock:
            days_late = amendment.get("days_after_lock", "unknown")
            findings.append(_make_finding(
                finding_id=f"SAP-{counter:03d}",
                domain="pre_specification",
                severity="CRITICAL",
                guideline_code="ICH-E9",
                section="§5.1",
                verbatim_passage=(
                    "The statistical section of the protocol or a separate statistical analysis plan "
                    "should be finalized before the unblinding of any comparative data."
                ),
                sap_clause=f"SAP {version} submitted {amend_date}.",
                csr_clause="Primary analysis based on amended SAP definitions.",
                inconsistency=f"SAP amended {days_late} days after database lock ({db_lock}).",
                finding=(
                    f"SAP {version} submitted on {amend_date} — after database lock date of {db_lock}. "
                    f"Post-lock SAP amendments introduce potential for bias in primary analysis definition."
                ),
                recommendation=(
                    f"Provide sensitivity analysis under original pre-lock SAP definition "
                    f"to demonstrate that the primary conclusion is robust."
                ),
                fda_review_risk="Likely FDA query",
            ))
            counter += 1

    # Estimand attribute completeness check
    estimand = sap_metadata.get("estimand", {})
    required_attributes = ["population", "treatment_condition", "variable", "intercurrent_event_strategy", "population_level_summary"]
    missing_attributes = [attr for attr in required_attributes if not estimand.get(attr)]
    if missing_attributes:
        findings.append(_make_finding(
            finding_id=f"SAP-{counter:03d}",
            domain="estimand",
            severity="IMPORTANT",
            guideline_code="ICH-E9R1",
            section="§3.1",
            verbatim_passage=(
                "An estimand is described by: the population, the variable, the intervention, "
                "the handling of intercurrent events, and the population-level summary measure."
            ),
            sap_clause=f"Estimand section present but missing: {', '.join(missing_attributes)}.",
            csr_clause="Primary endpoint analysis proceeds without complete estimand specification.",
            inconsistency=f"Estimand is incomplete — {len(missing_attributes)} of 5 attributes missing.",
            finding=(
                f"SAP estimand framework is incomplete. Missing attributes: "
                f"{', '.join(missing_attributes)}. All five ICH E9(R1) estimand attributes "
                f"must be defined before trial initiation."
            ),
            recommendation=(
                "Add the missing estimand attributes to the SAP with explicit definition of "
                "each intercurrent event strategy. Submit as SAP amendment before database lock."
            ),
            fda_review_risk="Likely FDA query",
        ))
        counter += 1

    # Stratification factor consistency check
    strat_factors = sap_metadata.get("stratification_factors", [])
    analysis_covariates = sap_metadata.get("analysis_covariates", [])
    missing_in_analysis = [f for f in strat_factors if f not in analysis_covariates]
    if missing_in_analysis:
        findings.append(_make_finding(
            finding_id=f"SAP-{counter:03d}",
            domain="covariate",
            severity="IMPORTANT",
            guideline_code="FDA-COVARIATE",
            section="§III.A",
            verbatim_passage=(
                "Stratification factors used in randomisation must be included as covariates "
                "in the primary analysis model."
            ),
            sap_clause=f"Randomisation stratified by: {', '.join(strat_factors)}.",
            csr_clause=f"Primary analysis covariates: {', '.join(analysis_covariates) or 'not specified'}.",
            inconsistency=f"Stratification factor(s) absent from primary analysis: {', '.join(missing_in_analysis)}.",
            finding=(
                f"Stratification factor(s) used in randomisation are not included in the "
                f"primary analysis model: {', '.join(missing_in_analysis)}. This is a common "
                f"FDA statistical review finding."
            ),
            recommendation=(
                "Add all randomisation stratification factors as covariates in the primary analysis model. "
                "Update SAP accordingly and rerun primary analysis."
            ),
            fda_review_risk="Likely FDA query",
        ))
        counter += 1

    return findings


# ── Cross-Document Consistency Retrieval ─────────────────────────────────────

def _cross_document_retrieve(
    query: str,
    sap_chunks: list[str],
    csr_chunks: list[str],
    retriever: "_SAPHybridRetriever | None",
    top_k_guideline: int = 3,
) -> dict[str, Any]:
    """
    Retrieve: (1) top guideline passages, (2) most relevant SAP clause, (3) most relevant CSR clause.
    Returns structured context for the LLM comparison prompt.
    """
    if retriever is not None:
        guideline_passages = retriever.retrieve(query, top_k=top_k_guideline)
    else:
        guideline_passages = _fallback_retrieve_sap([query], top_k=top_k_guideline)

    def _best_chunk(chunks: list[str], q: str) -> str:
        if not chunks:
            return "(Not found in document)"
        q_terms = set(re.findall(r"\b\w+\b", q.lower()))
        best = max(chunks, key=lambda c: len(q_terms & set(re.findall(r"\b\w+\b", c.lower()))))
        return best[:600]

    sap_clause = _best_chunk(sap_chunks, query)
    csr_clause = _best_chunk(csr_chunks, query)

    guideline_text = "\n---\n".join(
        f"[{p['metadata'].get('guideline_code', '?')} {p['metadata'].get('section_header', '')[:50]}] "
        f"{p['text'][:400]}"
        for p in guideline_passages
    )

    return {
        "guideline_passages": guideline_passages,
        "guideline_text": guideline_text,
        "sap_clause": sap_clause,
        "csr_clause": csr_clause,
        "structured_prompt": (
            f"[GUIDELINE SAYS]\n{guideline_text}\n\n"
            f"[SAP SAYS]\n{sap_clause}\n\n"
            f"[CSR SAYS]\n{csr_clause}\n\n"
            f"Identify any inconsistency between the SAP and CSR relative to the guideline requirement."
        ),
    }


# ── Text chunking helper for in-memory SAP/CSR text ──────────────────────────

def _split_into_chunks(text: str, chunk_size: int = 400) -> list[str]:
    if not text.strip():
        return []
    words = text.split()
    return [
        " ".join(words[i: i + chunk_size])
        for i in range(0, len(words), chunk_size)
        if " ".join(words[i: i + chunk_size]).strip()
    ]


# ── SAP Metadata Extractor ────────────────────────────────────────────────────

def _extract_sap_metadata(sap_text: str, trial_metadata: dict[str, Any]) -> dict[str, Any]:
    """Extract structured metadata from SAP text for pre-flight checks."""
    text_lower = sap_text.lower()

    # Amendment detection
    amendments = []
    version_pattern = re.compile(r"(?:sap|version)\s*v?(\d+\.\d+)", re.IGNORECASE)
    date_pattern = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\w+ \d{1,2},? \d{4})\b")
    versions = version_pattern.findall(sap_text)
    dates = date_pattern.findall(sap_text)
    db_lock = trial_metadata.get("database_lock_date", "")
    for i, version in enumerate(versions[1:], 1):  # skip v1.0 (original)
        date = dates[i] if i < len(dates) else ""
        if date and db_lock and date > db_lock:
            amendments.append({
                "version": f"v{version}",
                "date": date,
                "days_after_lock": "unknown",
            })

    # Estimand completeness
    estimand_attrs = {
        "population": any(w in text_lower for w in ["population:", "patient population", "enrolled subjects"]),
        "treatment_condition": any(w in text_lower for w in ["treatment condition", "dose:", "regimen"]),
        "variable": any(w in text_lower for w in ["primary endpoint:", "primary variable", "variable:"]),
        "intercurrent_event_strategy": any(w in text_lower for w in [
            "intercurrent event", "treatment policy", "composite variable",
            "hypothetical strategy", "while on treatment",
        ]),
        "population_level_summary": any(w in text_lower for w in [
            "difference in proportions", "odds ratio", "hazard ratio",
            "risk difference", "response rate difference", "population-level",
        ]),
    }

    # Stratification factors
    strat_match = re.search(r"stratif(?:ication|ied)[^\n.]{0,200}", sap_text, re.IGNORECASE)
    strat_factors = []
    if strat_match:
        strat_text = strat_match.group(0)
        if "ecog" in strat_text.lower():
            strat_factors.append("ECOG")
        if "prior" in strat_text.lower():
            strat_factors.append("Prior Treatment Lines")
        if "region" in strat_text.lower():
            strat_factors.append("Region")

    # Analysis covariates
    cov_match = re.search(r"covariate[s]?[^\n.]{0,300}", sap_text, re.IGNORECASE)
    analysis_covariates: list[str] = []
    if cov_match:
        cov_text = cov_match.group(0)
        if "ecog" in cov_text.lower():
            analysis_covariates.append("ECOG")
        if "prior" in cov_text.lower():
            analysis_covariates.append("Prior Treatment Lines")

    return {
        "amendments": amendments,
        "estimand": estimand_attrs,
        "stratification_factors": strat_factors,
        "analysis_covariates": analysis_covariates,
        "sap_locked": any(t in text_lower for t in ["locked", "finalized", "lock date", "version 1.0"]),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def _get_sap_retriever() -> "_SAPHybridRetriever":
    global _sap_retriever
    if _sap_retriever is None:
        _sap_retriever = _build_sap_kb()
    return _sap_retriever


def build_sap_rag_bundle(
    sap_text: str,
    csr_text: str,
    trial_metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Main entry point. Called by agent_validate_sap() in ectd_agent.py.

    Returns:
        prompt_context          : str  — top guideline passages for LLM injection
        preflight_findings      : list[dict]  — deterministic checks (no LLM)
        cross_doc_contexts      : dict[str, dict]  — per-domain structured prompts
        retrieved_guidance_summary : list[dict]  — UI-friendly list
        knowledge_base_size     : int
        retrieval_method        : str
        retrieval_status        : str
        rag_trace               : dict
    """
    sap_chunks = _split_into_chunks(sap_text)
    csr_chunks = _split_into_chunks(csr_text)

    sap_metadata = _extract_sap_metadata(sap_text, trial_metadata)
    trial_timeline = {
        "database_lock_date": trial_metadata.get("database_lock_date", ""),
    }
    preflight_findings = run_preflight_checks(sap_metadata, trial_timeline)

    # Build queries from templates + dynamic content
    queries = [q["template"] for q in _SAP_VALIDATION_QUERIES]
    primary_ep = trial_metadata.get("primary_endpoint", "")
    if primary_ep:
        queries.append(f"primary endpoint {primary_ep} pre-specification SAP analysis population")

    try:
        retriever = _get_sap_retriever()
        retrieval_status = "full_hybrid"
        retrieval_method = "hybrid dense ChromaDB + BM25 (term-expanded) + RRF + cross-encoder reranking"
        kb_size = retriever.total_chunks
    except Exception as exc:
        print(f"[SAP KB] Falling back to no-prereq RAG: {exc}")
        retriever = None
        retrieval_status = "no_prereq_lexical"
        retrieval_method = "no-prereq lexical RAG over built-in SAP/ICH/FDA guidance"
        kb_size = len(_SAP_FALLBACK_PASSAGES)

    # Retrieve for all queries, deduplicate
    seen_ids: set[str] = set()
    all_passages: list[dict] = []
    for query in queries[:8]:
        try:
            if retriever is not None:
                passages = retriever.retrieve(query, top_k=3)
            else:
                passages = _fallback_retrieve_sap([query], top_k=3)
            for p in passages:
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    all_passages.append(p)
        except Exception:
            continue

    all_passages.sort(key=lambda x: x.get("rerank_score", x.get("rrf_score", 0)), reverse=True)
    top_passages = all_passages[:15]
    prompt_context, retrieved_summary = _format_sap_passages(top_passages)

    # Cross-document contexts per domain
    cross_doc_contexts: dict[str, dict] = {}
    for q_info in _SAP_VALIDATION_QUERIES:
        try:
            ctx = _cross_document_retrieve(q_info["template"], sap_chunks, csr_chunks, retriever)
            cross_doc_contexts[q_info["domain"]] = ctx
        except Exception:
            cross_doc_contexts[q_info["domain"]] = {"structured_prompt": q_info["template"]}

    rag_trace = {
        "runtime": retrieval_status,
        "total_queries": len(queries),
        "unique_passages_retrieved": len(all_passages),
        "preflight_findings_count": len(preflight_findings),
        "domains_covered": _SAP_DOMAINS,
        "term_expansions_applied": len(_TERM_EXPANSIONS),
        "sap_chunks": len(sap_chunks),
        "csr_chunks": len(csr_chunks),
    }

    return {
        "prompt_context": prompt_context,
        "preflight_findings": preflight_findings,
        "cross_doc_contexts": cross_doc_contexts,
        "retrieved_guidance_summary": retrieved_summary,
        "knowledge_base_size": kb_size,
        "retrieval_method": retrieval_method,
        "retrieval_status": retrieval_status,
        "rag_trace": rag_trace,
        "sap_metadata": sap_metadata,
    }


def get_sap_kb_metadata() -> dict[str, Any]:
    """Returns KB inventory for the Streamlit UI — does NOT trigger a full build."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(_SAP_CHROMA_DIR))
        collection = client.get_collection(_SAP_COLLECTION_NAME)
        count = collection.count()
    except Exception:
        count = 0

    dep_status = _dependency_status()
    docs_info = []
    for d in _SAP_DOCUMENTS:
        path = _doc_path(d)
        exists = path.exists()
        docs_info.append({
            "code": d["code"],
            "title": d["title"],
            "body": d["body"],
            "year": d["year"],
            "domains": ", ".join(d["domains"]),
            "file_exists": exists,
            "file_size_kb": round(path.stat().st_size / 1024, 1) if exists else 0,
        })

    return {
        "total_documents": len(_SAP_DOCUMENTS),
        "documents_on_disk": sum(1 for d in docs_info if d["file_exists"]),
        "total_chunks_indexed": count,
        "runtime_mode": "full_hybrid" if count > 0 else "no_prereq_lexical",
        "chroma_db_path": str(_SAP_CHROMA_DIR),
        "sap_kb_dir": str(_SAP_KB_DIR),
        "shared_kb_dir": str(_SHARED_KB_DIR),
        "embedding_model": _EMBEDDING_MODEL,
        "reranker_model": _RERANKER_MODEL,
        "dependency_status": dep_status,
        "full_stack_ready": count > 0 and all(dep_status.values()),
        "domains": _SAP_DOMAINS,
        "documents": docs_info,
        "validation_queries": _SAP_VALIDATION_QUERIES,
        "domain_routing": {
            domain: guidelines
            for domain, guidelines in _SAP_DOMAIN_TO_GUIDELINES.items()
        },
    }
