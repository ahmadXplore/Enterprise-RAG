"""Pydantic schemas for Health check endpoints."""

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str
    connected: bool
    latency_ms: float | None = None
    timestamp: datetime


class QdrantHealthResponse(BaseModel):
    status: str
    service: str = "qdrant"
    connected: bool
    latency_ms: float | None = None
    timestamp: datetime


class RedisHealthResponse(BaseModel):
    status: str
    service: str = "redis"
    connected: bool
    latency_ms: float | None = None
    timestamp: datetime


class LLMHealthResponse(BaseModel):
    status: str
    service: str = "llm"
    provider: str
    configured: bool
    timestamp: datetime


class CorpusStatsResponse(BaseModel):
    """Aggregated corpus statistics for the dashboard."""

    total_documents: int
    ready_documents: int
    total_chunks: int
    total_queries: int
    timestamp: datetime
