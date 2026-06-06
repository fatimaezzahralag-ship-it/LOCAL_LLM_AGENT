from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


def _get_env_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "LOCAL_LLM_AGENT")
    app_env: str = os.getenv("APP_ENV", "local")
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    data_dir: Path = _get_env_path("DATA_DIR", "data")
    raw_documents_dir: Path = _get_env_path("RAW_DOCUMENTS_DIR", "data/raw_documents")
    vector_db_dir: Path = _get_env_path("VECTOR_DB_DIR", "data/vector_db")
    models_dir: Path = _get_env_path("MODELS_DIR", "models")
    llm_backend: str = os.getenv("LLM_BACKEND", "transformers")
    llm_model_path: Path = _get_env_path("LLM_MODEL_PATH", "models/Qwen-1.5B-Instruct")
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    secret_key: str = os.getenv("SECRET_KEY", "change-me")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()