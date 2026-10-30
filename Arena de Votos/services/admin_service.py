import time
from functools import wraps
from flask import redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from config import ADMIN_PASS, ADMIN_PASS_HASH, MAX_LOGIN_ATTEMPTS, LOGIN_LOCK_SECONDS
from database import get_db
from services.common import agora_br, get_ip, user_agent

LOGIN_ATTEMPTS: dict[str, dict] = {}


def password_hash():
    return ADMIN_PASS_HASH or generate_password_hash(ADMIN_PASS)


def check_admin_password(password: str) -> bool:
    return check_password_hash(password_hash(), password)


def login_blocked(ip: str):
    rec = LOGIN_ATTEMPTS.get(ip)
    if not rec:
        return False, None
    until = rec.get("locked_until", 0)
    if until and time.time() < until:
        return True, int(until - time.time())
    return False, None


def register_login_fail(ip: str):
    rec = LOGIN_ATTEMPTS.setdefault(ip, {"count": 0, "locked_until": 0})
    rec["count"] += 1
    if rec["count"] >= MAX_LOGIN_ATTEMPTS:
        rec["locked_until"] = time.time() + LOGIN_LOCK_SECONDS


def register_login_success(ip: str):
    LOGIN_ATTEMPTS.pop(ip, None)


def log_admin(acao: str, detalhe: str = ""):
    data, hora = agora_br()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO admin_logs (data, horario, ip, acao, detalhe, user_agent) VALUES (?, ?, ?, ?, ?, ?)",
            (data, hora, get_ip(), acao, detalhe[:500], user_agent()),
        )


def requer_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logado"):
            return redirect(url_for("admin.admin_login"))
        return f(*args, **kwargs)
    return wrapper
