"""Smoke test for the eCTD demo submission.

This verifies the path that should work in a clean demo/backtesting environment
without a Nebius key and without optional full-RAG dependencies.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from ectd_agent import run_demo_analysis, validate_input_package
from regulatory_knowledge_base import get_kb_metadata


def _write_package(root: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        file_path = root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")


def test_compliant_demo_package() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_package(
            root,
            {
                "submissionunit.xml": '<?xml version="1.0"?><submissionUnit/>',
                "m1/us/form-1571.txt": "Form FDA 1571 cover sheet.",
                "m2/clinical-overview.txt": "Clinical overview summary.",
                "m3/quality/drug-substance.txt": "Drug substance quality information.",
                "m4/nonclinical/toxicology-summary.txt": "Toxicology study report.",
                "m5/clinical/statistical-analysis-plan.txt": (
                    "SAP finalized before database lock. Primary endpoint ORR."
                ),
            },
        )

        validation = validate_input_package(root)
        result = run_demo_analysis(root)
        conformance = result["conformance"]
        knowledge_base = conformance.get("knowledge_base", {})

        assert validation["status"] == "PASS"
        assert result["analysis_mode"] == "deterministic_demo"
        assert result["documents_analyzed"] >= 6
        assert result["overall_score"] > 0.8
        assert knowledge_base.get("chunks_retrieved", 0) > 0
        assert knowledge_base.get("retrieval_status") in {"no_prereq_live_rag", "full_hybrid"}
        assert conformance.get("retrieved_guidance")
        assert conformance.get("rag_trace", {}).get("steps")


def test_broken_package_findings() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_package(
            root,
            {
                "m1/us/form-1571.txt": "Form FDA 1571 cover sheet.",
                "m2/clinical-overview.txt": "Clinical overview summary.",
                "m3/quality/drug-substance.txt": "Drug substance quality information.",
                "m5/clinical/phase3-protocol.txt": "Phase 3 protocol.",
            },
        )

        findings = run_demo_analysis(root)["conformance"].get("rule_based_findings", [])
        rule_ids = {finding["rule_id"] for finding in findings}

        assert "ICH-M4-MODULES" in rule_ids
        assert "FDA-ECTD-XML-BACKBONE" in rule_ids


def main() -> None:
    metadata = get_kb_metadata()
    assert metadata["fallback_chunks_available"] > 0

    test_compliant_demo_package()
    test_broken_package_findings()

    print("SMOKE_TEST_PASS")
    print(f"Runtime mode: {metadata['runtime_mode']}")
    print(f"No-prereq chunks: {metadata['fallback_chunks_available']}")


if __name__ == "__main__":
    main()
