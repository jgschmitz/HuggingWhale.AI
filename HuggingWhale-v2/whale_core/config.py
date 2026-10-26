"""Local JSON configuration; AWS credentials use the standard boto3 chain."""
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Identity:
    tenant: str
    principal: str
    admin: bool = False

    @property
    def access(self):
        return ["tenant", self.principal]


@dataclass
class Settings:
    mongo_uri: str = field(repr=False)
    s3_bucket: str
    voyage_api_key: str = field(repr=False)
    database: str = "huggingwhale_v2"
    s3_region: str = "us-east-1"
    embedding_model: str = "voyage-context-4"
    dimensions: int = 1024
    chunk_size: int = 512
    rerank_model: str = "rerank-2.5"
    llm_api_key: str = field(default="", repr=False)
    llm_model: str = ""
    api_tokens: list = field(default_factory=list, repr=False)
    max_upload_bytes: int = 10 * 1024 * 1024
    max_document_chars: int = 100_000
    lease_seconds: int = 600
    max_attempts: int = 3

    def __post_init__(self):
        if self.dimensions not in (256, 512, 1024, 2048):
            raise ValueError("Unsupported embedding dimensions")
        if not 1 <= self.chunk_size <= 32000:
            raise ValueError("chunk_size must be between 1 and 32000")

    @classmethod
    def load(cls, path="config.local.json"):
        value = cls(**json.loads(Path(path).read_text()))
        for secret in (value.mongo_uri, value.voyage_api_key, value.s3_bucket):
            if not secret or "REPLACE" in secret:
                raise ValueError("Fill in config.local.json before starting")
        if not value.api_tokens:
            raise ValueError("Configure at least one API token")
        tokens = set()
        for item in value.api_tokens:
            if (len(item["token"]) < 24 or "REPLACE" in item["token"]
                    or not item["tenant"] or not item["principal"]):
                raise ValueError("Configure long unique API tokens and identities")
            if item["token"] in tokens:
                raise ValueError("API tokens must be unique")
            tokens.add(item["token"])
        return value
