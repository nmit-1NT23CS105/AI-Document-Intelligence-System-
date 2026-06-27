from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Document Intelligence System"
    app_version: str = "0.1.0"
    database_url: str = "sqlite:///./dev.db"
    upload_dir: str = "uploads"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    embedding_provider: str = "local"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    vector_store_provider: str = "database"
    chroma_persist_dir: str = "chromadb"
    chunk_size_words: int = 180
    chunk_overlap_words: int = 30
    chat_retrieval_limit: int = 4
    classifier_provider: str = "local"
    summary_sentence_count: int = 2
    jwt_secret_key: str = "change-this-secret-key-for-local-development-only"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


def _load_env_file() -> dict[str, str]:
    env_path = Path(os.getenv("ENV_FILE", ".env"))
    if not env_path.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value

    return values


def _env_value(name: str, default: str, env_file_values: dict[str, str]) -> str:
    process_value = os.getenv(name)
    if process_value:
        return process_value
    return env_file_values.get(name, default)


@lru_cache
def get_settings() -> Settings:
    env_file_values = _load_env_file()
    return Settings(
        app_name=_env_value("APP_NAME", Settings.app_name, env_file_values),
        app_version=_env_value("APP_VERSION", Settings.app_version, env_file_values),
        database_url=_env_value("DATABASE_URL", Settings.database_url, env_file_values),
        upload_dir=_env_value("UPLOAD_DIR", Settings.upload_dir, env_file_values),
        max_upload_size_bytes=int(
            _env_value(
                "MAX_UPLOAD_SIZE_BYTES",
                str(Settings.max_upload_size_bytes),
                env_file_values,
            )
        ),
        embedding_provider=_env_value(
            "EMBEDDING_PROVIDER",
            Settings.embedding_provider,
            env_file_values,
        ),
        embedding_model_name=_env_value(
            "EMBEDDING_MODEL_NAME",
            Settings.embedding_model_name,
            env_file_values,
        ),
        vector_store_provider=_env_value(
            "VECTOR_STORE_PROVIDER",
            Settings.vector_store_provider,
            env_file_values,
        ),
        chroma_persist_dir=_env_value(
            "CHROMA_PERSIST_DIR",
            Settings.chroma_persist_dir,
            env_file_values,
        ),
        chunk_size_words=int(
            _env_value(
                "CHUNK_SIZE_WORDS",
                str(Settings.chunk_size_words),
                env_file_values,
            )
        ),
        chunk_overlap_words=int(
            _env_value(
                "CHUNK_OVERLAP_WORDS",
                str(Settings.chunk_overlap_words),
                env_file_values,
            )
        ),
        chat_retrieval_limit=int(
            _env_value(
                "CHAT_RETRIEVAL_LIMIT",
                str(Settings.chat_retrieval_limit),
                env_file_values,
            )
        ),
        classifier_provider=_env_value(
            "CLASSIFIER_PROVIDER",
            Settings.classifier_provider,
            env_file_values,
        ),
        summary_sentence_count=int(
            _env_value(
                "SUMMARY_SENTENCE_COUNT",
                str(Settings.summary_sentence_count),
                env_file_values,
            )
        ),
        jwt_secret_key=_env_value(
            "JWT_SECRET_KEY",
            Settings.jwt_secret_key,
            env_file_values,
        ),
        jwt_algorithm=_env_value(
            "JWT_ALGORITHM",
            Settings.jwt_algorithm,
            env_file_values,
        ),
        access_token_expire_minutes=int(
            _env_value(
                "ACCESS_TOKEN_EXPIRE_MINUTES",
                str(Settings.access_token_expire_minutes),
                env_file_values,
            )
        ),
    )
