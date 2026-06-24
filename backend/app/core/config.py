import os
from pathlib import Path

# Base Directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
ZIM_DIR = DATA_DIR / "zim_archives"
TEMP_DIR = DATA_DIR / "temp"

# Create directories if they don't exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
ZIM_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_PATH = str(DATA_DIR / "knowledge.db")

# Offline LLM (Gemma 3 1B GGUF) — used by /api/chat
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "gemma-3-1B-it-QAT-Q4_0.gguf"

# Indexing Configurations
INDEX_BATCH_SIZE = 1000
MAX_SUMMARY_LENGTH = 500

# App Metadata
APP_NAME = "Kiwi"
VERSION = "1.0.0"

# Security
# Restrict CORS to known frontend origins
# Vite defaults to 5173 but auto-falls back through 5174-5183 if busy
_ALLOWED_PORTS = list(range(5173, 5184)) + [4173]
_ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
ALLOWED_ORIGINS = (
    [f"http://{host}:{port}" for host in _ALLOWED_HOSTS for port in _ALLOWED_PORTS]
    + ["null"]  # Electron file:// protocol origin
)

# Maximum request body size (MB)
MAX_REQUEST_SIZE_MB = 50

# Rate limiting (requests per minute per IP)
RATE_LIMIT_PER_MINUTE = 60
