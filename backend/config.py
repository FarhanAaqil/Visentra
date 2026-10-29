from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./visentra.db"
    storage_root: str = str(PROJECT_ROOT / "storage")
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Hex encoded 32 byte Ed25519 seed. When empty a key is generated once and
    # kept under storage/keys so signatures survive restarts.
    signing_key: str = ""

    # Demo endpoints (tamper / restore) and startup seeding are handy locally
    # and in the hosted demo, but should be switched off for real deployments.
    enable_demo: bool = True
    auto_seed: bool = True

    # Optional ONNX feature extractor (e.g. MobileNetV2) used for OOD embeddings.
    embedder_onnx: str = ""

    sandbox_timeout_s: float = 60.0
    sandbox_memory_mb: int = 3072
    cascade_delay_s: float = 0.15

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
