from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    storage_backend: str = "sqlite"
    review_mode: str = "deterministic"
    data_dir: Path = Path(".data")
    mongodb_uri: str = ""
    mongodb_database: str = "submissionai_continuity"
    vector_index: str = "evidence_vector"
    vector_enabled: bool = False
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3.5-lite"
    voyage_dimensions: int = 1024
    embedding_provider: str = "voyage"
    embedding_model: str = ""
    embedding_dimensions: int = 0
    nebius_api_key: str = ""
    llm_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_api_style: str = "chat_completions"
    llm_reasoning_effort: str = ""
    llm_max_output_tokens: int = 2400
    access_token: str = ""
    demo_study_id: str = ""
    demo_drug_name: str = ""

    @classmethod
    def from_env(cls):
        load_dotenv()
        obj = cls(
            storage_backend=os.getenv("STORAGE_BACKEND", "sqlite"),
            review_mode=os.getenv("REVIEW_MODE", "deterministic"),
            data_dir=Path(os.getenv("DATA_DIR", ".data")),
            mongodb_uri=os.getenv("MONGODB_URI", ""),
            mongodb_database=os.getenv("MONGODB_DATABASE", "submissionai_continuity"),
            vector_index=os.getenv("MONGODB_VECTOR_INDEX", "evidence_vector"),
            vector_enabled=os.getenv("VECTOR_SEARCH_ENABLED", "false").lower() == "true",
            voyage_api_key=os.getenv("VOYAGE_API_KEY", ""),
            voyage_model=os.getenv("VOYAGE_MODEL", "voyage-3.5-lite"),
            voyage_dimensions=int(os.getenv("VOYAGE_DIMENSIONS", "1024")),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "voyage"),
            embedding_model=os.getenv("EMBEDDING_MODEL", ""),
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "0")),
            nebius_api_key=os.getenv("NEBIUS_API_KEY", ""),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/"),
            llm_api_key=os.getenv("LLM_API_KEY", "") or os.getenv("NEBIUS_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", ""),
            llm_api_style=os.getenv("LLM_API_STYLE", "chat_completions"),
            llm_reasoning_effort=os.getenv("LLM_REASONING_EFFORT", ""),
            llm_max_output_tokens=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "2400")),
            access_token=os.getenv("APP_ACCESS_TOKEN", ""),
            demo_study_id=os.getenv("DEMO_STUDY_ID", ""),
            demo_drug_name=os.getenv("DEMO_DRUG_NAME", ""),
        )
        obj.validate()
        return obj

    def validate(self):
        if self.storage_backend not in {"sqlite", "mongodb"}:
            raise ValueError("STORAGE_BACKEND must be sqlite or mongodb")
        if self.review_mode not in {"deterministic", "llm"}:
            raise ValueError("REVIEW_MODE must be deterministic or llm")
        if self.storage_backend == "mongodb" and not self.mongodb_uri:
            raise ValueError("MONGODB_URI is required for MongoDB mode")
        if self.review_mode == "llm" and not (self.llm_api_key and self.llm_model):
            raise ValueError("LLM_API_KEY and LLM_MODEL are required for live model review")
        if self.llm_api_style not in {"responses", "chat_completions"}:
            raise ValueError("LLM_API_STYLE must be responses or chat_completions")
        if self.llm_reasoning_effort not in {"", "none", "minimal", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("LLM_REASONING_EFFORT is not supported by this configuration")
        if not 256 <= self.llm_max_output_tokens <= 16000:
            raise ValueError("LLM_MAX_OUTPUT_TOKENS must be between 256 and 16000")
        if self.embedding_provider not in {"voyage", "nebius"}:
            raise ValueError("EMBEDDING_PROVIDER must be voyage or nebius")
        key = self.nebius_api_key if self.embedding_provider == "nebius" else self.voyage_api_key
        if self.vector_enabled and (self.storage_backend != "mongodb" or not key):
            raise ValueError("Vector search requires MongoDB mode and the selected embedding provider's API key")
        if self.embedding_dimensions < 0 or not 1 <= self.effective_embedding_dimensions <= 8192:
            raise ValueError("Embedding dimensions must be between 1 and 8192")
        if self.voyage_dimensions < 1:
            raise ValueError("VOYAGE_DIMENSIONS must be positive")

    @property
    def effective_embedding_model(self):
        return self.embedding_model or ("Qwen/Qwen3-Embedding-8B" if self.embedding_provider == "nebius" else self.voyage_model)

    @property
    def effective_embedding_dimensions(self):
        return self.embedding_dimensions or (4096 if self.embedding_provider == "nebius" else self.voyage_dimensions)

    @property
    def embedding_profile(self):
        from .storage import digest
        # Include query formatting so a future change invalidates cached reviews.
        return digest([self.embedding_provider, self.effective_embedding_model,
                       self.effective_embedding_dimensions, "retrieval-query-v1"])
