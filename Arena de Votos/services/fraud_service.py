import hashlib
import re
import secrets
import time
from flask import session, request
from config import MIN_SEGUNDOS_ENTRE_VOTOS

RATE_LIMIT_IP: dict[str, float] = {}


def gerar_token_csrf() -> str:
    token = secrets.token_urlsafe(32)
    session["csrf_token"] = token
    return token


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validar_csrf(pesquisa) -> bool:
    token_header = request.headers.get("X-CSRF-Token", "")
    token_session = session.get("csrf_token", "")
    if not token_header or not token_session or token_header != token_session:
        return False
    return bool(pesquisa and pesquisa["csrf_hash"] == hash_token(token_header))


def fingerprint_from_payload(dados: dict | None = None) -> str:
    valor = ""
    if dados:
        valor = str(dados.get("fingerprint", ""))[:200]
    return valor or "NAO_INFORMADO"


def normalizar_whatsapp(numero: str) -> str | None:
    digitos = re.sub(r"\D", "", numero or "")
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11):
        return None
    ddd = int(digitos[:2])
    numero_local = digitos[2:]
    if ddd < 11 or ddd > 99:
        return None
    if len(set(digitos)) <= 2:
        return None
    if numero_local in ("00000000", "000000000", "12345678", "123456789", "99999999", "999999999"):
        return None
    return digitos


def limitar_velocidade(ip: str, pesquisa) -> tuple[bool, str | None]:
    agora_ts = time.time()
    ultimo_sessao = float(session.get("last_vote_ts") or 0)
    ultimo_ip = RATE_LIMIT_IP.get(ip, 0)
    ultimo_db = float(pesquisa["ultimo_voto_ts"] or 0) if pesquisa else 0
    ultimo = max(ultimo_sessao, ultimo_ip, ultimo_db)
    if agora_ts - ultimo < MIN_SEGUNDOS_ENTRE_VOTOS:
        return False, "Voto rápido demais. Aguarde um instante antes de votar novamente."
    session["last_vote_ts"] = agora_ts
    RATE_LIMIT_IP[ip] = agora_ts
    return True, None


def calcular_status_antifraude(conn, ip: str, ganhador: str, whatsapp: str | None, fingerprint: str) -> tuple[str, str]:
    ultimas = conn.execute(
        """
        SELECT ganhador FROM pesquisas
        WHERE ip = ? AND status IN ('VALIDO', 'IGNORADO_REPETICAO')
        ORDER BY id DESC LIMIT 2
        """,
        (ip,),
    ).fetchall()
    repetidas = 0
    for row in ultimas:
        if row["ganhador"] == ganhador:
            repetidas += 1
        else:
            break
    if repetidas >= 2:
        return "IGNORADO_REPETICAO", "3ª ou mais pesquisas seguidas do mesmo IP com o mesmo ganhador. Mantida para auditoria, ignorada na análise."

    if whatsapp:
        usos_whats = conn.execute(
            "SELECT COUNT(*) AS t FROM pesquisas WHERE whatsapp = ? AND status IN ('VALIDO','IGNORADO_REPETICAO','SUSPEITO')",
            (whatsapp,),
        ).fetchone()["t"]
        if usos_whats >= 3:
            return "SUSPEITO", "WhatsApp reutilizado em várias pesquisas. Conferir antes de usar na análise principal."

    usos_fp = conn.execute(
        "SELECT COUNT(*) AS t FROM pesquisas WHERE fingerprint = ? AND status IN ('VALIDO','IGNORADO_REPETICAO','SUSPEITO')",
        (fingerprint,),
    ).fetchone()["t"]
    if fingerprint != "NAO_INFORMADO" and usos_fp >= 5:
        return "SUSPEITO", "Mesmo navegador/dispositivo apareceu muitas vezes. Conferir antes de usar na análise principal."

    return "VALIDO", "Pesquisa válida para análise."
