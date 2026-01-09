import os
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

ES_URL = os.getenv("ES_URL", "https://localhost:9200")
ES_INDEX = os.getenv("ES_INDEX", "naver_news_ai_v1_openai")
ES_USER = os.getenv("ES_USER")
ES_PASS = os.getenv("ES_PASS")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

VECTOR_FIELD = "embedding"


def get_es_client() -> Elasticsearch:
    return Elasticsearch(
        ES_URL,
        basic_auth=(ES_USER, ES_PASS) if (ES_USER or ES_PASS) else None,
        verify_certs=False,
        ssl_show_warn=False,
        request_timeout=30,
    )


def get_embeddings() -> OpenAIEmbeddings:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing.")
    return OpenAIEmbeddings(model=OPENAI_EMBED_MODEL, api_key=OPENAI_API_KEY)


def embed_query(text: str) -> List[float]:
    return get_embeddings().embed_query(text)


def get_llm() -> ChatOpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing.")
    return ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=0, api_key=OPENAI_API_KEY)


def es_knn_search(es: Elasticsearch, question: str, k: int, topic: Optional[str] = None) -> List[Dict[str, Any]]:
    qvec = embed_query(question)

    body: Dict[str, Any] = {
        "size": k,
        "knn": {
            "field": VECTOR_FIELD,
            "query_vector": qvec,
            "k": k,
            "num_candidates": max(200, k * 50),
        },
        "_source": ["doc_id", "topic", "title", "text", "pub_date", "link", "originallink"],
    }

    if topic:
        body["query"] = {"bool": {"filter": [{"term": {"topic": topic}}]}}

    res = es.search(index=ES_INDEX, body=body)
    return res.get("hits", {}).get("hits", [])


def answer_news_question(question: str, k: int = 6, topic: Optional[str] = None) -> Dict[str, Any]:
    es = get_es_client()
    hits = es_knn_search(es, question=question, k=k, topic=topic)

    context_lines = []
    sources = []

    for i, h in enumerate(hits, start=1):
        src = h.get("_source", {}) or {}
        context_lines.append(
            f"[{i}] title={src.get('title')}\n"
            f"    pub_date={src.get('pub_date')} topic={src.get('topic')}\n"
            f"    link={src.get('link') or src.get('originallink')}\n"
            f"    text={src.get('text')}\n"
        )
        sources.append(
            {
                "title": src.get("title"),
                "link": src.get("link") or src.get("originallink"),
                "pub_date": src.get("pub_date"),
                "topic": src.get("topic"),
                "doc_id": src.get("doc_id"),
                "snippet": (src.get("text") or "")[:240],
                "score": h.get("_score"),
            }
        )

    context = "\n".join(context_lines) if context_lines else "(검색 결과 없음)"

    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "당신은 뉴스 검색 결과(근거)만 바탕으로 답변합니다. "
                "근거에 없는 내용은 추측하지 말고 '근거 부족'이라고 말하세요. "
                "가능하면 핵심을 불릿으로 정리하고, 마지막에 출처 링크를 요약하세요.",
            ),
            ("human", "질문: {question}\n\n아래는 검색된 근거 문서입니다:\n{context}\n\n답변:"),
        ]
    )

    msg = prompt.format_messages(question=question, context=context)
    resp = llm.invoke(msg)

    return {"answer": resp.content, "sources": sources, "k": k, "topic": topic, "index": ES_INDEX}
