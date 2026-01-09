from langchain_openai import ChatOpenAI
from app.core.config import settings

def get_llm():
    """
    사내문서 RAG 공용 LLM 클라이언트
    """
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=0.0,
    )
