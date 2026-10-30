
from pathlib import Path
from flask import Blueprint, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename
from config import ADMIN_USER, UPLOAD_FOLDER, ALLOWED_IMAGE_EXTENSIONS
from database import get_db, list_candidates
from services.admin_service import requer_admin, check_admin_password, login_blocked, register_login_fail, register_login_success, log_admin
from services.common import get_ip
from services.report_service import dashboard_context, pesquisa_detalhes, gerar_excel

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@admin_bp.route("", methods=["GET"])
def admin_login():
    if session.get("admin_logado"):
        return redirect(url_for("admin.admin_painel"))
    return render_template("admin_login.html", erro=None)


@admin_bp.route("/login", methods=["POST"])
def admin_autenticar():
    ip = get_ip()
    blocked, seconds = login_blocked(ip)
    if blocked:
        return render_template("admin_login.html", erro=f"Muitas tentativas. Aguarde {seconds}s."), 429
    usuario = request.form.get("usuario", "").strip()
    senha = request.form.get("senha", "").strip()
    if usuario == ADMIN_USER and check_admin_password(senha):
        session["admin_logado"] = True
        session.permanent = False
        register_login_success(ip)
        log_admin("LOGIN", "Login bem-sucedido")
        return redirect(url_for("admin.admin_painel"))
    register_login_fail(ip)
    log_admin("LOGIN_FALHOU", f"Usuário informado: {usuario}")
    return render_template("admin_login.html", erro="Usuário ou senha incorretos."), 401


@admin_bp.route("/painel")
@requer_admin
def admin_painel():
    with get_db() as conn:
        ctx = dashboard_context(conn)
    return render_template("admin_painel.html", **ctx)


@admin_bp.route("/api/pesquisa/<int:pesquisa_id>")
@requer_admin
def api_pesquisa_detalhes(pesquisa_id):
    with get_db() as conn:
        detalhes = pesquisa_detalhes(conn, pesquisa_id)
    if not detalhes:
        return jsonify({"erro": "Pesquisa não encontrada."}), 404
    return jsonify(detalhes)


@admin_bp.route("/vereadores", methods=["GET"])
@requer_admin
def vereadores():
    with get_db() as conn:
        rows = [dict(r) for r in list_candidates(conn, only_active=False)]
    return render_template("admin_vereadores.html", vereadores=rows)


@admin_bp.route("/vereadores/<int:vereador_id>", methods=["POST"])
@requer_admin
def atualizar_vereador(vereador_id):
    nome = request.form.get("nome", "").strip()
    partido = request.form.get("partido", "").strip()
    ativo = 1 if request.form.get("ativo") == "on" else 0
    imagem_path = None
    arquivo = request.files.get("imagem")
    with get_db() as conn:
        vereador = conn.execute("SELECT * FROM vereadores WHERE id = ?", (vereador_id,)).fetchone()
        if not vereador:
            return "Vereador não encontrado", 404
        if arquivo and arquivo.filename and allowed_file(arquivo.filename):
            ext = secure_filename(arquivo.filename).rsplit(".", 1)[1].lower()
            filename = f"candidato_{vereador_id}.{ext}"
            UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
            destino = UPLOAD_FOLDER / filename
            arquivo.save(destino)
            imagem_path = f"/static/images/{filename}"
        if imagem_path:
            conn.execute("UPDATE vereadores SET nome=?, partido=?, ativo=?, img=?, atualizado_em=CURRENT_TIMESTAMP WHERE id=?", (nome, partido, ativo, imagem_path, vereador_id))
        else:
            conn.execute("UPDATE vereadores SET nome=?, partido=?, ativo=?, atualizado_em=CURRENT_TIMESTAMP WHERE id=?", (nome, partido, ativo, vereador_id))
    log_admin("EDITOU_VEREADOR", f"ID {vereador_id} - {nome}")
    return redirect(url_for("admin.vereadores"))


@admin_bp.route("/download")
@requer_admin
def admin_download():
    with get_db() as conn:
        arquivo = gerar_excel(conn)
    log_admin("DOWNLOAD_EXCEL", "Relatório exportado")
    return send_file(arquivo, as_attachment=True, download_name="votos_arena.xlsx")


@admin_bp.route("/logs")
@requer_admin
def logs():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM admin_logs ORDER BY id DESC LIMIT 200").fetchall()
    return render_template("admin_logs.html", logs=[dict(r) for r in rows])


@admin_bp.route("/logout")
@requer_admin
def admin_logout():
    log_admin("LOGOUT", "Sessão encerrada")
    session.clear()
    return redirect(url_for("admin.admin_login"))
