"""
Central configuration for the bot + API.
All values are pulled from environment variables (see .env.example).
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent

# --- Telegram ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Comma-separated list of Telegram user IDs who are admins by default
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()}

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR}/bot_database.db")

# --- Dashboard / API ---
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-please")
SECRET_KEY = os.getenv("SECRET_KEY", "insecure-dev-secret-change-in-prod")

# --- Bot behaviour defaults (overridable at runtime via dashboard Settings) ---
DEFAULT_WELCOME_MESSAGE = (
    "👋 <b>Welcome, {name}!</b>\n\n"
    "I'm your all-in-one assistant bot. Use the menu below to get started."
)
