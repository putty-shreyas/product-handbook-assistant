from pathlib import Path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    data_dir: Path = ROOT / "data"
    groq_api_key: SecretStr = SecretStr("")
    llm_model: str = "qwen/qwen3.8-27b"
    top_k: int = Field(default=5, ge=1, le=8)


# An index is compatible only with the embedding configuration that created it.
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 160
SCHEMA_VERSION = 1
