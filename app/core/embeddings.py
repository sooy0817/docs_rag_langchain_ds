from typing import List
from openai import OpenAI
from app.core.config import settings

_client: OpenAI | None = None

def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client

def embed_texts(texts: List[str]) -> List[list[float]]:
    """
    texts -> embedding vectors
    """
    client = get_openai_client()
    res = client.embeddings.create(
        model=settings.OPENAI_EMBED_MODEL,
        input=texts,
    )
    vectors = [d.embedding for d in res.data]

    if vectors and len(vectors[0]) != settings.EMBED_DIMS:
        raise RuntimeError(
            f"임베딩 dims 불일치: expected={settings.EMBED_DIMS}, got={len(vectors[0])}"
        )

    return vectors

def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
