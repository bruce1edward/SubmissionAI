from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

CheckId = Literal["endpoint_alignment", "referenced_documents"]
CHECKS = ("endpoint_alignment", "referenced_documents")
CHECK_TITLES = {
    "endpoint_alignment": "Endpoint timing alignment",
    "referenced_documents": "Referenced document coverage",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentInput(StrictModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=150)
    kind: Literal["protocol", "sap", "checklist", "supporting"]
    text: str = Field(min_length=1, max_length=30000)


class PackageInput(StrictModel):
    study_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    version: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_.-]+$")
    documents: list[DocumentInput] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_documents(self):
        ids = [d.id for d in self.documents]
        if len(set(ids)) != len(ids):
            raise ValueError("Document IDs must be unique within a package")
        for kind in ("protocol", "sap", "checklist"):
            if sum(d.kind == kind for d in self.documents) > 1:
                raise ValueError(f"Only one {kind} document is supported in this MVP")
        return self


class DemoInput(StrictModel):
    study_id: str = Field(default="SYN-014", min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class RunInput(StrictModel):
    package_id: str
    force_full: bool = False


class ExecuteInput(StrictModel):
    mode: Literal["step", "continue"] = "continue"


class MemoryInput(StrictModel):
    package_id: str
    document_id: str
    quote: str = Field(min_length=4, max_length=1000)
    summary: str = Field(min_length=5, max_length=800)
    check_ids: list[CheckId] = Field(min_length=1, max_length=2)
    kind: Literal["review_note", "document_alias"] = "review_note"
    alias: str = Field(default="", max_length=80, pattern=r"^[a-zA-Z0-9_.-]*$")

    @model_validator(mode="after")
    def alias_required(self):
        if self.kind == "document_alias" and not self.alias:
            raise ValueError("A document alias needs an alias filename")
        if self.kind == "document_alias" and self.check_ids != ["referenced_documents"]:
            raise ValueError("Document aliases apply only to referenced_documents")
        return self


class Citation(StrictModel):
    document_id: str
    quote: str = Field(min_length=1, max_length=3000)


class AgentDecision(StrictModel):
    action: Literal["conclude", "retrieve"]
    query: str = Field(default="", max_length=300)
    status: Literal["open", "clear", "unresolved"] = "unresolved"
    explanation: str = Field(default="", max_length=2000)
    citations: list[Citation] = Field(default_factory=list, max_length=12)
    missing_documents: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_action(self):
        if self.action == "retrieve" and not self.query.strip():
            raise ValueError("A retrieval action requires a query")
        if self.action == "conclude" and not self.explanation.strip():
            raise ValueError("A conclusion requires an explanation")
        return self
