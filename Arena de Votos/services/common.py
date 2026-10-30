from datetime import datetime
from flask import request


def agora_br():
    a = datetime.now()
    return a.strftime("%d/%m/%Y"), a.strftime("%H:%M:%S")


def get_ip():
    raw = request.headers.get("X-Forwarded-For", request.remote_addr or "Desconhecido")
    return raw.split(",")[0].strip()


def user_agent():
    return (request.headers.get("User-Agent") or "")[:300]
