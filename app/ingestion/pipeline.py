from __future__ import annotations

import json
from typing import Protocol

from redis import Redis

from app.config import get_settings
from app.ingestion.schemas import IngestionJob

INGESTION_STREAM = "agentops:ingestion"


class IngestionQueue(Protocol):
    def enqueue(self, job: IngestionJob) -> str:
        ...


class RedisIngestionQueue:
    def __init__(self, redis_client: Redis, stream_name: str = INGESTION_STREAM) -> None:
        self.redis_client = redis_client
        self.stream_name = stream_name

    def enqueue(self, job: IngestionJob) -> str:
        stream_id = self.redis_client.xadd(
            self.stream_name,
            {"job": job.model_dump_json()},
        )
        if isinstance(stream_id, bytes):
            return stream_id.decode("utf-8")
        return str(stream_id)


class InMemoryIngestionQueue:
    def __init__(self) -> None:
        self.jobs: list[IngestionJob] = []

    def enqueue(self, job: IngestionJob) -> str:
        self.jobs.append(job)
        return job.job_id

    def pop_all(self) -> list[IngestionJob]:
        jobs = list(self.jobs)
        self.jobs.clear()
        return jobs


def serialize_job(job: IngestionJob) -> str:
    return job.model_dump_json()


def deserialize_job(raw: str | bytes) -> IngestionJob:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return IngestionJob.model_validate(json.loads(raw))


def get_ingestion_queue() -> IngestionQueue:
    settings = get_settings()
    return RedisIngestionQueue(Redis.from_url(settings.redis_url, decode_responses=True))
