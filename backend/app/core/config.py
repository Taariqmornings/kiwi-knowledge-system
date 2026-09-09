import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Base directories
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
ZIM_DIR  = DATA_DIR / "zim_archives"
TEMP_DIR = DATA_DIR / "temp"

DATA_DIR.mkdir(parents=True, exist_ok=True)
ZIM_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Database
# Override with DATABASE_PATH env var to point at a custom location.
# ---------------------------------------------------------------------------
DATABASE_PATH: str = os.environ.get(
    "DATABASE_PATH",
    str(DATA_DIR / "knowledge.db"),
)

# ---------------------------------------------------------------------------
# Ollama / local LLM  (used by /api/chat — completely optional)
# Set OLLAMA_HOST if your Ollama daemon runs on a non-default address/port.
# Set OLLAMA_MODEL to use a different model (e.g. "llama3.2:3b").
# If Ollama is not installed, all search features still work; only the
# AI chat sidebar will be unavailable.
# ---------------------------------------------------------------------------
OLLAMA_HOST:  str = os.environ.get("OLLAMA_HOST",  "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "gemma3:1b")

# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------
INDEX_BATCH_SIZE   = int(os.environ.get("INDEX_BATCH_SIZE",   "1000"))
MAX_SUMMARY_LENGTH = int(os.environ.get("MAX_SUMMARY_LENGTH", "500"))

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------
APP_NAME = "Kiwi"
VERSION  = "1.2.0"

# ---------------------------------------------------------------------------
# CORS — restrict to known local origins.
# Vite defaults to 5173 but auto-falls back through 5174-5183 if busy.
# "null" covers Electron's file:// origin.
# ---------------------------------------------------------------------------
_ALLOWED_PORTS = list(range(5173, 5184)) + [4173]
_ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
ALLOWED_ORIGINS = (
    [f"http://{host}:{port}" for host in _ALLOWED_HOSTS for port in _ALLOWED_PORTS]
    + ["null"]
)

# ---------------------------------------------------------------------------
# Request limits
# ---------------------------------------------------------------------------
MAX_REQUEST_SIZE_MB    = int(os.environ.get("MAX_REQUEST_SIZE_MB",    "50"))
RATE_LIMIT_PER_MINUTE  = int(os.environ.get("RATE_LIMIT_PER_MINUTE",  "60"))
