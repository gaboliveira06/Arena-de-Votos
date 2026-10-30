import time
from flask import session
from database import list_candidates
from services.common import agora_br, user_agent
from services.fraud_service import gerar_token_csrf, hash_token


def chave_duelo(a: str, b: str) -> str:
    return " x ".join(sorted([a, b], key=str.lower))


def candidates_payload(conn):
    rows = list_candidates(conn, only_active=True)
    return [{"id": r["codigo"], "nome": r["nome"], "partido": r["partido"], "img": r["img"]} for r in rows]


def nomes_validos(conn):
    return {r["nome"] for r in list_candidates(conn, only_active=True)}


def total_pares(conn):
    total = len(list_candidates(conn, only_active=True))
    return total * (total - 1) // 2


def pesquisa_atual(conn):
    pid = session.get("pesquisa_id")
    if not pid:
        return None
    return conn.execute("SELECT * FROM pesquisas WHERE id = ?", (pid,)).fetchone()


def iniciar_pesquisa(conn, ip: str, fingerprint: str = "NAO_INFORMADO"):
    candidatos = candidates_payload(conn)
    if len(candidatos) < 2:
        raise RuntimeError("Cadastre pelo menos 2 vereadores ativos.")
    data, hora = agora_br()
    token = gerar_token_csrf()
    cur = conn.execute(
        """
        INSERT INTO pesquisas
        (ip, data_inicio, hora_inicio, user_agent, fingerprint, csrf_hash, current_left, current_right, next_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ip, data, hora, user_agent(), fingerprint, hash_token(token), candidatos[0]["nome"], candidatos[1]["nome"], 2),
    )
    pid = cur.lastrowid
    session["pesquisa_id"] = pid
    session["last_vote_ts"] = 0.0
    return pid, token, candidatos[0]["nome"], candidatos[1]["nome"]


def proximo_estado_confronto(conn, pesquisa, vencedor: str):
    nomes = [c["nome"] for c in candidates_payload(conn)]
    total = len(nomes)
    if total < 2:
        return vencedor, None, 0
    linhas = conn.execute(
        """
        SELECT candidato_votado, candidato_adversario
        FROM duelos
        WHERE pesquisa_id = ? AND (candidato_votado = ? OR candidato_adversario = ?)
        """,
        (pesquisa["id"], vencedor, vencedor),
    ).fetchall()
    ja_enfrentou = set()
    for row in linhas:
        a, b = row["candidato_votado"], row["candidato_adversario"]
        ja_enfrentou.add(b if a == vencedor else a)
    start = int(pesquisa["next_index"] or 0) % total
    for offset in range(total):
        idx = (start + offset) % total
        candidato = nomes[idx]
        if candidato == vencedor or candidato in ja_enfrentou:
            continue
        return vencedor, candidato, (idx + 1) % total
    return vencedor, None, start


def registrar_voto(conn, pesquisa, ip: str, candidato: str, adversario: str, fingerprint: str):
    data, horario = agora_br()
    voto_ts = time.time()
    chave = chave_duelo(candidato, adversario)
    existe = conn.execute("SELECT id FROM duelos WHERE pesquisa_id = ? AND chave_duelo = ?", (pesquisa["id"], chave)).fetchone()
    if existe:
        raise ValueError("Este confronto já aconteceu nesta pesquisa.")
    conn.execute(
        """
        INSERT INTO duelos
        (pesquisa_id, data, horario, ip, candidato_votado, candidato_adversario, chave_duelo, user_agent, fingerprint, voto_ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (pesquisa["id"], data, horario, ip, candidato, adversario, chave, user_agent(), fingerprint, voto_ts),
    )
    total = int(pesquisa["total_duelos"] or 0) + 1
    conn.execute("UPDATE pesquisas SET total_duelos = ?, ultimo_voto_ts = ? WHERE id = ?", (total, voto_ts, pesquisa["id"]))
    pesquisa_atualizada = conn.execute("SELECT * FROM pesquisas WHERE id = ?", (pesquisa["id"],)).fetchone()
    current_left, current_right, next_index = proximo_estado_confronto(conn, pesquisa_atualizada, candidato)
    conn.execute("UPDATE pesquisas SET current_left = ?, current_right = ?, next_index = ? WHERE id = ?", (current_left, current_right, next_index, pesquisa["id"]))
    return current_left, current_right, next_index, total
