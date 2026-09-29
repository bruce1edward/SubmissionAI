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
    llm_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    access_token: str = ""

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
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/"),
            llm_api_key=os.getenv("LLM_API_KEY", "") or os.getenv("NEBIUS_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", ""),
            access_token=os.getenv("APP_ACCESS_TOKEN", ""),
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
        if self.vector_enabled and (self.storage_backend != "mongodb" or not self.voyage_api_key):
            raise ValueError("Vector search requires MongoDB mode and VOYAGE_API_KEY")
        if self.voyage_dimensions < 1:
            raise ValueError("VOYAGE_DIMENSIONS must be positive")
