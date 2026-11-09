"""Application-controlled paths and limits."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# All managed data lives under DATA_DIR. Override with SDSTRACKER_DATA_DIR
# (used by tests to work in a temporary directory).
DATA_DIR = Path(os.environ.get("SDSTRACKER_DATA_DIR", PROJECT_ROOT / "data"))

# Documented upload limit. Matches server.maxUploadSize in .streamlit/config.toml.
MAX_UPLOAD_MB = 20
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def db_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or DATA_DIR) / "tracker.db"


def documents_dir(data_dir: Path | None = None) -> Path:
    return Path(data_dir or DATA_DIR) / "documents"


def synthetic_demo_dir(data_dir: Path | None = None) -> Path:
    return Path(data_dir or DATA_DIR) / "synthetic_demo"
