import os

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    embedding_model: str
    reranker_model: str


app = FastAPI(title="Doctor Chat Embedding Service")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="doctor-chat-embedding-service",
        embedding_model=os.environ.get("EMBEDDING_MODEL", "not-configured"),
        reranker_model=os.environ.get("RERANKER_MODEL", "not-configured"),
    )
