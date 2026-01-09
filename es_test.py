from elasticsearch import Elasticsearch
import os

ES_URL  = os.getenv("ES_URL", "http://localhost:9200")
ES_USER = os.getenv("ES_USER")
ES_PASS = os.getenv("ES_PASS")

def get_es() -> Elasticsearch:
    if ES_USER and ES_PASS:
        return Elasticsearch(
            ES_URL,
            basic_auth=(ES_USER, ES_PASS),
            verify_certs=False,
            request_timeout=30,
        )
    return Elasticsearch(ES_URL, request_timeout=30)

es = get_es()
print(es.info())

INDEX = "naver_news_ai_v1_openai"

print(es.indices.exists(index=INDEX))
print(es.indices.get_mapping(index=INDEX))

doc = es.get(index=INDEX, id="ES_DOCUMENT_ID")
print(doc["_source"])