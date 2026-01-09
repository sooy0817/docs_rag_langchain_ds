# app/core/config.py
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _to_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "t", "yes", "y", "on")

@dataclass(frozen=True)
class Settings:
    # Elasticsearch
    ES_URL: str = os.getenv("ES_URL", "https://localhost:9200")
    ES_USER: str | None = os.getenv("ES_USER")
    ES_PASS: str | None = os.getenv("ES_PASS")
    ES_VERIFY_CERTS: bool = _to_bool(os.getenv("ES_VERIFY_CERTS"), default=False)

    # Index names (사내문서 RAG)
    PDF_INDEX: str = os.getenv("PDF_INDEX", "pdf_chunks_v1")

    # OpenAI
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_EMBED_MODEL: str = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    EMBED_DIMS: int = int(os.getenv("OPENAI_EMBED_DIMS", "1536"))
    LLM_MODEL = "gpt-4o-mini"


settings = Settings()
