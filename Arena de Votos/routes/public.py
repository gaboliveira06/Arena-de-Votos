from flask import Blueprint, jsonify, render_template, request, session
from database import get_db
from services.common import get_ip, agora_br
from services.fraud_service import fingerprint_from_payload, validar_csrf, limitar_velocidade, normalizar_whatsapp, calcular_status_antifraude
from services.voting_service import candidates_payload, total_pares, pesquisa_atual, iniciar_pesquisa, nomes_validos, registrar_voto

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    return render_template("index.html")


@public_bp.route("/api/candidatos")
def api_candidatos():
    with get_db() as conn:
        return jsonify({"candidatos": candidates_payload(conn), "total_duelos": total_pares(conn)})


@public_bp.route("/api/pesquisa/iniciar", methods=["POST"])
def api_iniciar():
    dados = request.get_json(silent=True) or {}
    ip = get_ip()
    fingerprint = fingerprint_from_payload(dados)
    with get_db() as conn:
        existente = pesquisa_atual(conn)
        if existente and existente["status"] == "EM_ANDAMENTO":
            pid, token, left, right = None, None, None, None
            from services.fraud_service import gerar_token_csrf, hash_token
            token = gerar_token_csrf()
            conn.execute("UPDATE pesquisas SET csrf_hash = ?, fingerprint = COALESCE(NULLIF(?, ''), fingerprint) WHERE id = ?", (hash_token(token), fingerprint, existente["id"]))
            return jsonify({
                "sucesso": True,
                "pesquisa_id": existente["id"],
                "csrf_token": token,
                "current_left": existente["current_left"],
                "current_right": existente["current_right"],
                "next_index": existente["next_index"],
                "duelos_feitos": existente["total_duelos"],
                "total_duelos": total_pares(conn),
            })
        try:
            pid, token, left, right = iniciar_pesquisa(conn, ip, fingerprint)
        except RuntimeError as e:
            return jsonify({"sucesso": False, "erro": str(e)}), 400
        return jsonify({"sucesso": True, "pesquisa_id": pid, "csrf_token": token, "total_duelos": total_pares(conn), "duelos_feitos": 0, "current_left": left, "current_right": right, "next_index": 2})


@public_bp.route("/votar", methods=["POST"])
def votar():
    dados = request.get_json(silent=True) or {}
    candidato = str(dados.get("candidato_votado", "")).strip()
    adversario = str(dados.get("candidato_adversario", "")).strip()
    fingerprint = fingerprint_from_payload(dados)
    if not candidato or not adversario:
        return jsonify({"sucesso": False, "erro": "Campos obrigatórios ausentes."}), 400
    if candidato == adversario:
        return jsonify({"sucesso": False, "erro": "Um candidato não pode concorrer contra ele mesmo."}), 400
    ip = get_ip()
    with get_db() as conn:
        validos = nomes_validos(conn)
        if candidato not in validos or adversario not in validos:
            return jsonify({"sucesso": False, "erro": "Candidato inválido."}), 400
        pesquisa = pesquisa_atual(conn)
        if not pesquisa or pesquisa["status"] != "EM_ANDAMENTO":
            return jsonify({"sucesso": False, "erro": "Pesquisa não iniciada."}), 400
        if not validar_csrf(pesquisa):
            return jsonify({"sucesso": False, "erro": "Token de segurança inválido."}), 403
        ok, erro = limitar_velocidade(ip, pesquisa)
        if not ok:
            return jsonify({"sucesso": False, "erro": erro}), 429
        if pesquisa["current_left"] != candidato and pesquisa["current_right"] != candidato:
            return jsonify({"sucesso": False, "erro": "Vencedor não pertence ao confronto atual."}), 400
        if pesquisa["current_left"] != adversario and pesquisa["current_right"] != adversario:
            return jsonify({"sucesso": False, "erro": "Adversário não pertence ao confronto atual."}), 400
        try:
            current_left, current_right, next_index, total = registrar_voto(conn, pesquisa, ip, candidato, adversario, fingerprint)
        except ValueError as e:
            return jsonify({"sucesso": False, "erro": str(e)}), 400
        return jsonify({"sucesso": True, "mensagem": "Voto registrado.", "current_left": current_left, "current_right": current_right, "next_index": next_index, "duelos_feitos": total})


@public_bp.route("/api/pesquisa/finalizar", methods=["POST"])
def finalizar_pesquisa():
    dados = request.get_json(silent=True) or {}
    sem_whatsapp = bool(dados.get("sem_whatsapp"))
    whatsapp_bruto = str(dados.get("whatsapp", "")).strip()
    whatsapp = None if sem_whatsapp or not whatsapp_bruto else normalizar_whatsapp(whatsapp_bruto)
    ganhador = str(dados.get("ganhador", "")).strip()
    fingerprint = fingerprint_from_payload(dados)

    if whatsapp_bruto and not sem_whatsapp and not whatsapp:
        return jsonify({"sucesso": False, "erro": "WhatsApp inválido. Informe com DDD ou finalize sem WhatsApp."}), 400

    ip = get_ip()
    data, hora = agora_br()
    with get_db() as conn:
        pesquisa = pesquisa_atual(conn)
        if not pesquisa or pesquisa["status"] != "EM_ANDAMENTO":
            return jsonify({"sucesso": False, "erro": "Pesquisa não iniciada ou já finalizada."}), 400
        if not validar_csrf(pesquisa):
            return jsonify({"sucesso": False, "erro": "Token de segurança inválido."}), 403
        if ganhador not in nomes_validos(conn):
            return jsonify({"sucesso": False, "erro": "Ganhador inválido."}), 400
        if int(pesquisa["total_duelos"] or 0) <= 0:
            return jsonify({"sucesso": False, "erro": "Vote pelo menos uma vez antes de finalizar."}), 400

        status, motivo = calcular_status_antifraude(conn, ip, ganhador, whatsapp, fingerprint)
        if not whatsapp:
            motivo = motivo + " WhatsApp não informado por preferência do participante."

        conn.execute(
            """
            UPDATE pesquisas
            SET whatsapp = ?, data_fim = ?, hora_fim = ?, ganhador = ?, status = ?, motivo_status = ?, fingerprint = COALESCE(NULLIF(?, ''), fingerprint)
            WHERE id = ?
            """,
            (whatsapp, data, hora, ganhador, status, motivo, fingerprint, pesquisa["id"]),
        )
        session.pop("pesquisa_id", None)
        session.pop("csrf_token", None)
        return jsonify({"sucesso": True, "ganhador": ganhador, "status": status, "motivo": motivo, "whatsapp_informado": bool(whatsapp)})
