import sqlite3
from config import DB_FILE, INSTANCE_DIR
from data.candidates import DEFAULT_CANDIDATES


def get_db():
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _add_col_if_missing(conn, table: str, col: str, definition: str) -> None:
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")


def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS vereadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            nome TEXT NOT NULL UNIQUE,
            partido TEXT NOT NULL,
            img TEXT NOT NULL,
            ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT
        );
        CREATE TABLE IF NOT EXISTS pesquisas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            whatsapp TEXT,
            data_inicio TEXT NOT NULL,
            hora_inicio TEXT NOT NULL,
            data_fim TEXT,
            hora_fim TEXT,
            ganhador TEXT,
            total_duelos INTEGER DEFAULT 0,
            status TEXT DEFAULT 'EM_ANDAMENTO',
            motivo_status TEXT,
            user_agent TEXT,
            fingerprint TEXT,
            csrf_hash TEXT,
            current_left TEXT,
            current_right TEXT,
            next_index INTEGER DEFAULT 2,
            ultimo_voto_ts REAL
        );
        CREATE TABLE IF NOT EXISTS duelos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pesquisa_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            horario TEXT NOT NULL,
            ip TEXT NOT NULL,
            candidato_votado TEXT NOT NULL,
            candidato_adversario TEXT NOT NULL,
            chave_duelo TEXT NOT NULL,
            user_agent TEXT,
            fingerprint TEXT,
            voto_ts REAL,
            FOREIGN KEY(pesquisa_id) REFERENCES pesquisas(id)
        );
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            horario TEXT NOT NULL,
            ip TEXT,
            acao TEXT NOT NULL,
            detalhe TEXT,
            user_agent TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pesquisas_ip ON pesquisas(ip);
        CREATE INDEX IF NOT EXISTS idx_pesquisas_status ON pesquisas(status);
        CREATE INDEX IF NOT EXISTS idx_duelos_pesquisa ON duelos(pesquisa_id);
        CREATE INDEX IF NOT EXISTS idx_vereadores_nome ON vereadores(nome);
        """)
        for col, definition in [
            ("user_agent", "TEXT"), ("fingerprint", "TEXT"), ("csrf_hash", "TEXT"),
            ("current_left", "TEXT"), ("current_right", "TEXT"), ("next_index", "INTEGER DEFAULT 2"),
            ("ultimo_voto_ts", "REAL")
        ]:
            _add_col_if_missing(conn, "pesquisas", col, definition)
        for col, definition in [("user_agent", "TEXT"), ("fingerprint", "TEXT"), ("voto_ts", "REAL")]:
            _add_col_if_missing(conn, "duelos", col, definition)
        seed_candidates(conn)


def seed_candidates(conn) -> None:
    total = conn.execute("SELECT COUNT(*) AS total FROM vereadores").fetchone()["total"]
    if total:
        return
    for c in DEFAULT_CANDIDATES:
        conn.execute(
            "INSERT INTO vereadores (codigo, nome, partido, img, ativo) VALUES (?, ?, ?, ?, 1)",
            (str(c["id"]), c["nome"], c["partido"], c["img"]),
        )


def list_candidates(conn, only_active: bool = True):
    sql = "SELECT * FROM vereadores"
    if only_active:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY CAST(codigo AS INTEGER), nome"
    return conn.execute(sql).fetchall()
