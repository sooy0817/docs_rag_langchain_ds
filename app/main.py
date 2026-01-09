from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from news_controller import router as news_router
from app.pdf.controller import router as pdf_router
from app.pdf.page_render import router as pdf_page_image_router


app = FastAPI(title="News Vector RAG Demo")

app.mount("/files/pdfs", StaticFiles(directory="data/pdfs"), name="pdfs")
app.include_router(pdf_page_image_router)
app.include_router(news_router)
app.include_router(pdf_router)

@app.get("/health")
def health():
    return {"ok": True}
