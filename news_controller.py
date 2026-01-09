import os
import re
import hashlib
import logging
from email.utils import parsedate_to_datetime
from datetime import timezone
from typing import Any, Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()
# -----------------------------
# Router / Logger
# -----------------------------
router = APIRouter(prefix="/news", tags=["news"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("news")


# -----------------------------
# Env
# -----------------------------
NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

ES_URL = os.getenv("ES_URL", "https://localhost:9200")
ES_INDEX = os.getenv("ES_INDEX", "naver_news_ai_v1_openai")
ES_VERIFY_CERTS_RAW = os.getenv("ES_VERIFY_CERTS", "false")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

# text-embedding-3-small은 보통 1536 dims
EMBED_DIMS = int(os.getenv("OPENAI_EMBED_DIMS", "1536"))


def str_to_bool(v: str) -> bool:
    return (v or "").strip().lower() == "true"


ES_VERIFY_CERTS = str_to_bool(ES_VERIFY_CERTS_RAW)


# -----------------------------
# Helpers
# -----------------------------
def clean_html(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"<[^>]+>", "", s).strip()


def make_doc_id(originallink: str, link: str, pub: str) -> str:
    base = (originallink or link or "") + "|" + (pub or "")
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def fetch_naver_news(query: str, sort: str = "date", display: int = 10, start: int = 1) -> list[dict]:
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise RuntimeError("Missing NAVER_CLIENT_ID / NAVER_CLIENT_SECRET env vars")

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": display, "start": start, "sort": sort}

    r = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=20)
    r.raise_for_status()
    return r.json().get("items", [])


def normalize_items(items: list[dict], topic: str) -> list[dict]:
    out: list[dict] = []
    for it in items:
        title = clean_html(it.get("title", ""))
        desc = clean_html(it.get("description", ""))
        pub = it.get("pubDate", "")

        pub_dt = None
        if pub:
            try:
                pub_dt = parsedate_to_datetime(pub).astimezone(timezone.utc).isoformat()
            except Exception:
                pub_dt = None

        origin = it.get("originallink", "")
        link = it.get("link", "")
        doc_id = make_doc_id(origin, link, pub)

        out.append(
            {
                "doc_id": doc_id,
                "topic": topic,
                "title": title,
                "description": desc,
                "pub_date": pub_dt,
                "link": link,
                "originallink": origin,
            }
        )
    return out


def dedupe_by_link(docs: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for d in docs:
        key = d.get("originallink") or d.get("link") or d["doc_id"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(d)
    return unique


def build_text(d: dict[str, Any]) -> str:
    title = (d.get("title") or "").strip()
    desc = (d.get("description") or "").strip()
    if title and desc:
        return f"{title}\n{desc}"
    return title or desc


# -----------------------------
# Clients
# -----------------------------
def get_es() -> Elasticsearch:
    return Elasticsearch(
        ES_URL,
        basic_auth=(os.getenv("ES_USER"), os.getenv("ES_PASS")),
        verify_certs=False,
        ssl_show_warn=False,
        request_timeout=30,
    )


def get_openai() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing (needed for embeddings).")
    return OpenAI(api_key=OPENAI_API_KEY)


def embed_texts(texts: list[str]) -> list[list[float]]:
    client = get_openai()
    resp = client.embeddings.create(model=OPENAI_EMBED_MODEL, input=texts)
    return [item.embedding for item in resp.data]


# -----------------------------
# Elasticsearch index bootstrap
# -----------------------------
def ensure_index(es: Elasticsearch, dims: int) -> None:
    if es.indices.exists(index=ES_INDEX):
        return

    body = {
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "topic": {"type": "keyword"},
                "title": {"type": "text"},
                "text": {"type": "text"},
                "pub_date": {"type": "date"},
                "link": {"type": "keyword"},
                "originallink": {"type": "keyword"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": dims,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        }
    }

    es.indices.create(index=ES_INDEX, body=body)
    logger.info("Created index=%s (dense_vector dims=%d)", ES_INDEX, dims)


def es_bulk_upsert(es: Elasticsearch, docs: list[dict[str, Any]]) -> int:
    actions = []
    for d in docs:
        doc_id = d["doc_id"]
        actions.append(
            {
                "_op_type": "index",   # 같은 _id면 덮어씀 (upsert 효과)
                "_index": ES_INDEX,
                "_id": doc_id,
                "_source": d,
            }
        )

    if not actions:
        return 0

    success, _ = bulk(es, actions, raise_on_error=False)
    return int(success)


# -----------------------------
# API Schemas
# -----------------------------
DEFAULT_TOPICS = {
    "quantum": "양자 양자컴퓨팅 큐비트 quantum qubit",
    "space": "우주항공 우주산업 위성 발사체 로켓 SpaceX 스페이스X",
    "robotics": "로봇 휴머노이드 로보틱스 자율로봇",
    "autonomous": "자율주행 ADAS 로보택시 무인차",
    "energy_ai": "AI 에너지 전력 원자력 핵융합 SMR",
    "defense_ai": "AI 국방 방산 드론 무인기",
    "bio_ai": "AI 바이오 신약 유전체 헬스케어",
}


class CollectAndIndexReq(BaseModel):
    topics: dict[str, str] = Field(default_factory=lambda: DEFAULT_TOPICS)
    sort: str = Field(default="date")  # date | sim
    per_page: int = Field(default=10, ge=1, le=100)
    max_items_per_topic: int = Field(default=100, ge=1, le=1000)


# -----------------------------
# Routes
# -----------------------------
@router.post("/collect_and_index")
def collect_and_index(req: CollectAndIndexReq):
    """
    토픽별로 네이버 뉴스 수집 -> 임베딩 생성 -> ES bulk upsert
    """
    es = get_es()

    # ES 연결 체크
    try:
        if not es.ping():
            raise RuntimeError("Elasticsearch ping failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elasticsearch connection error: {e}")

    # 인덱스 없으면 생성
    try:
        ensure_index(es, dims=EMBED_DIMS)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elasticsearch index create error: {e}")

    logger.info(
        "NEWS collect_and_index start | topics=%d | per_page=%d | max_items/topic=%d",
        len(req.topics), req.per_page, req.max_items_per_topic
    )

    summary = {"by_topic": {}, "total_indexed": 0}

    try:
        for topic, query in req.topics.items():
            logger.info("[topic=%s] start", topic)

            indexed_topic = 0
            start = 1
            batch_no = 0

            while indexed_topic < req.max_items_per_topic:
                batch_no += 1

                items = fetch_naver_news(query=query, sort=req.sort, display=req.per_page, start=start)
                logger.info("[topic=%s][batch=%d] fetched=%d (start=%d)", topic, batch_no, len(items), start)

                if not items:
                    logger.info("[topic=%s] no more items, stop", topic)
                    break

                normalized = normalize_items(items, topic=topic)
                unique = dedupe_by_link(normalized)

                remaining = req.max_items_per_topic - indexed_topic
                unique = unique[:remaining]

                texts = [build_text(d) for d in unique]

                filtered_docs = []
                filtered_texts = []
                for d, t in zip(unique, texts):
                    if t and t.strip():
                        filtered_docs.append(d)
                        filtered_texts.append(t)

                if not filtered_docs:
                    logger.info("[topic=%s][batch=%d] nothing to embed/index (empty texts), continue", topic, batch_no)
                    start += req.per_page
                    continue

                embeddings = embed_texts(filtered_texts)

                es_docs = []
                for d, t, emb in zip(filtered_docs, filtered_texts, embeddings):
                    es_docs.append(
                        {
                            "doc_id": d["doc_id"],
                            "topic": d["topic"],
                            "title": d.get("title"),
                            "text": t,
                            "pub_date": d.get("pub_date"),
                            "link": d.get("link"),
                            "originallink": d.get("originallink"),
                            "embedding": emb,
                        }
                    )

                indexed = es_bulk_upsert(es, es_docs)
                indexed_topic += indexed
                summary["total_indexed"] += indexed

                logger.info(
                    "[topic=%s][batch=%d] indexed=%d | topic_total=%d | overall_total=%d",
                    topic, batch_no, indexed, indexed_topic, summary["total_indexed"]
                )

                start += req.per_page

                # 네이버 start 제한 안전장치
                if start > 1000:
                    logger.warning("[topic=%s] start exceeded 1000, stop", topic)
                    break

            summary["by_topic"][topic] = indexed_topic
            logger.info("[topic=%s] done | indexed=%d", topic, indexed_topic)

        logger.info("NEWS collect_and_index done | %s", summary)
        return {"ok": True, **summary, "index": ES_INDEX}

    except requests.HTTPError as e:
        logger.exception("Naver HTTPError")
        raise HTTPException(status_code=502, detail=f"Naver HTTP error: {str(e)}")
    except Exception as e:
        logger.exception("collect_and_index error")
        raise HTTPException(status_code=500, detail=str(e))


class RagReq(BaseModel):
    question: str = Field(..., min_length=1)
    k: int = Field(default=6, ge=1, le=20)
    topic: Optional[str] = Field(default=None)


@router.post("/rag")
def rag(req: RagReq):
    try:
        from app.news.rag_service import answer_news_question
        return {"ok": True, **answer_news_question(req.question, k=req.k, topic=req.topic)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
