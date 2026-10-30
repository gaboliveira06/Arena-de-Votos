from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DB_FILE = INSTANCE_DIR / "arena_votos.db"
EXPORT_FILE = BASE_DIR / "votos_arena.xlsx"
UPLOAD_FOLDER = BASE_DIR / "static" / "images"

SECRET_KEY = os.getenv("SECRET_KEY", "troque-essa-chave-em-producao")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "arena@2025")
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH", "")
MIN_SEGUNDOS_ENTRE_VOTOS = float(os.getenv("MIN_SEGUNDOS_ENTRE_VOTOS", "1.2"))
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOGIN_LOCK_SECONDS = int(os.getenv("LOGIN_LOCK_SECONDS", "300"))
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
