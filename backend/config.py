import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = BASE_DIR / "raw"
OUTPUT_DIR = BASE_DIR / "output"
DB_PATH = RAW_DATA_DIR / "seed.sqlite"

# SQLite & Postgres Compatibility
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")

# Industrial EnergyIQ Plant Defaults
DEFAULT_SEED = 20261022
DEFAULT_PLANT_ID = "PLANT-001"
DEFAULT_PLANT_TZ = "America/Chicago"
DEFAULT_INTERVAL_MIN = 15

# LLM API Config (Optional - deterministic rule-based fallback active by default)
LLM_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY") or ""
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")

# Roles supported
USER_ROLES = [
    "Plant Operator",
    "Maintenance/Quality Engineer",
    "Production Planner",
    "OT/IT Administrator"
]

