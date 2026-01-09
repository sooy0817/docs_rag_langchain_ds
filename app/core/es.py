from elasticsearch import Elasticsearch
from app.core.config import settings

def get_es() -> Elasticsearch:
    return Elasticsearch(
        settings.ES_URL,
        basic_auth=(
            settings.ES_USER,
            settings.ES_PASS,
        ) if settings.ES_USER and settings.ES_PASS else None,
        verify_certs=settings.ES_VERIFY_CERTS,
        ssl_show_warn=False,
        request_timeout=30,
    )
