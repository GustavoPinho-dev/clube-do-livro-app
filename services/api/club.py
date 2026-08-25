"""
club.py

Gerencia o "clube do livro": ciclos de leitura coletiva, um livro por vez.

Cada ciclo (club_sessions) tem seu próprio livro, datas de início/fim e
conclusões -- separado de user_lists (leitura pessoal), já que o ritmo e
as datas do clube não têm por que coincidir com a leitura individual do
usuário. Só pode existir um ciclo com status='atual' de cada vez; ao
concluir um ciclo, ele vira histórico permanente e libera escolher o
próximo livro.

As ideias de discussão (club_ideas) ficam amarradas a um ciclo específico,
então ideias de uma releitura futura do mesmo livro não se misturam com
as de agora.
"""

from datetime import date

from db import get_connection, DB_PATH


def _validate_date(value: str | None) -> str | None:
    """Aceita None/"" (sem data) ou uma string 'YYYY-MM-DD' válida."""
    if value is None or value == "":
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"data inválida: '{value}'. Use o formato AAAA-MM-DD.")
    return value


def _session_with_book(conn, session_id: int) -> dict | None:
    """Detalhe de um ciclo, com dados do livro e ideias já embutidos."""
    row = conn.execute(
        """
        SELECT
            cs.id, cs.book_id, cs.status, cs.start_date, cs.end_date,
            cs.conclusions, cs.created_at, cs.updated_at,
            b.title, b.cover_url, b.first_publish_year,
            GROUP_CONCAT(DISTINCT a.name) AS authors
        FROM club_sessions cs
        JOIN books b ON b.id = cs.book_id
        LEFT JOIN book_authors ba ON ba.book_id = b.id
        LEFT JOIN authors a ON a.id = ba.author_id
        WHERE cs.id = ?
        GROUP BY cs.id
        """,
        (session_id,),
    ).fetchone()

    if row is None:
        return None

    sessao = dict(row)
    sessao["ideas"] = get_ideas(conn, session_id)
    return sessao


# ---------------------------------------------------------------------
# Ciclo atual
# ---------------------------------------------------------------------

def get_current_session(conn) -> dict | None:
    """O ciclo em andamento agora, com livro e ideias embutidos. None se não houver."""
    row = conn.execute("SELECT id FROM club_sessions WHERE status = 'atual'").fetchone()
    return _session_with_book(conn, row["id"]) if row else None


def start_session(conn, book_id: int, start_date: str = None) -> int:
    """
    Inicia um novo ciclo do clube com o livro informado. Falha se já
    existir um ciclo em andamento (precisa concluir o atual primeiro).
    """
    if conn.execute("SELECT id FROM club_sessions WHERE status = 'atual'").fetchone():
        raise ValueError(
            "já existe uma leitura em andamento no clube. Conclua-a antes de começar outra."
        )

    inicio = _validate_date(start_date) or date.today().isoformat()

    cur = conn.execute(
        "INSERT INTO club_sessions (book_id, status, start_date) VALUES (?, 'atual', ?)",
        (book_id, inicio),
    )
    return cur.lastrowid


def conclude_session(conn, session_id: int, end_date: str = None, conclusions: str = None):
    """Encerra o ciclo atual, registrando data de término e conclusões."""
    row = conn.execute(
        "SELECT status, start_date FROM club_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"ciclo (id={session_id}) não encontrado.")
    if row["status"] != "atual":
        raise ValueError("esse ciclo já está concluído.")

    fim = _validate_date(end_date) or date.today().isoformat()
    if row["start_date"] and fim < row["start_date"]:
        raise ValueError("A data de término não pode ser anterior à data de início.")

    conn.execute(
        """
        UPDATE club_sessions
        SET status = 'concluida', end_date = ?, conclusions = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (fim, (conclusions or "").strip() or None, session_id),
    )


# ---------------------------------------------------------------------
# Edição e histórico
# ---------------------------------------------------------------------

def update_session(conn, session_id: int, start_date: str = None, end_date: str = None, conclusions: str = None):
    """
    Edita um ciclo (atual ou já concluído) -- útil para corrigir datas ou
    revisar as conclusões depois. Passe None para não alterar aquele campo.
    """
    row = conn.execute(
        "SELECT start_date, end_date, conclusions FROM club_sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"ciclo (id={session_id}) não encontrado.")

    novo_inicio = _validate_date(start_date) if start_date is not None else row["start_date"]
    novo_fim = _validate_date(end_date) if end_date is not None else row["end_date"]
    novas_conclusoes = conclusions.strip() or None if conclusions is not None else row["conclusions"]

    if novo_inicio and novo_fim and novo_fim < novo_inicio:
        raise ValueError("A data de término não pode ser anterior à data de início.")

    conn.execute(
        """
        UPDATE club_sessions
        SET start_date = ?, end_date = ?, conclusions = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (novo_inicio, novo_fim, novas_conclusoes, session_id),
    )


def delete_session(conn, session_id: int):
    """Apaga um ciclo por completo (e suas ideias, via ON DELETE CASCADE)."""
    conn.execute("DELETE FROM club_sessions WHERE id = ?", (session_id,))


def get_history(conn) -> list[dict]:
    """Ciclos já concluídos, do mais recente para o mais antigo."""
    rows = conn.execute(
        "SELECT id FROM club_sessions WHERE status = 'concluida' ORDER BY end_date DESC, id DESC"
    ).fetchall()
    return [_session_with_book(conn, row["id"]) for row in rows]


def get_session(conn, session_id: int) -> dict | None:
    """Detalhe de um ciclo específico, atual ou histórico."""
    return _session_with_book(conn, session_id)


# ---------------------------------------------------------------------
# Ideias de discussão
# ---------------------------------------------------------------------

def add_idea(conn, session_id: int, idea: str) -> int:
    """Adiciona uma ideia de discussão a um ciclo. Retorna o id da ideia."""
    idea = (idea or "").strip()
    if not idea:
        raise ValueError("a ideia não pode ficar vazia.")

    if conn.execute("SELECT id FROM club_sessions WHERE id = ?", (session_id,)).fetchone() is None:
        raise ValueError(f"ciclo (id={session_id}) não encontrado.")

    cur = conn.execute(
        "INSERT INTO club_ideas (session_id, idea) VALUES (?, ?)",
        (session_id, idea),
    )
    return cur.lastrowid


def remove_idea(conn, idea_id: int):
    """Remove uma ideia pelo id dela."""
    conn.execute("DELETE FROM club_ideas WHERE id = ?", (idea_id,))


def get_ideas(conn, session_id: int) -> list[dict]:
    """Ideias de um ciclo, da mais antiga pra mais nova (ordem de sugestão)."""
    rows = conn.execute(
        "SELECT id, idea, created_at FROM club_ideas WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------
# Funções de conveniência (abrem a própria conexão)
# ---------------------------------------------------------------------

def get_current_club_session(db_path: str = DB_PATH) -> dict | None:
    with get_connection(db_path) as conn:
        return get_current_session(conn)


def start_club_session(book_id: int, start_date: str = None, db_path: str = DB_PATH) -> int:
    with get_connection(db_path) as conn:
        return start_session(conn, book_id, start_date)


def conclude_club_session(session_id: int, end_date: str = None, conclusions: str = None, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        conclude_session(conn, session_id, end_date, conclusions)


def update_club_session(session_id: int, start_date: str = None, end_date: str = None, conclusions: str = None, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        update_session(conn, session_id, start_date, end_date, conclusions)


def delete_club_session(session_id: int, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        delete_session(conn, session_id)


def get_club_history(db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        return get_history(conn)


def get_club_session(session_id: int, db_path: str = DB_PATH) -> dict | None:
    with get_connection(db_path) as conn:
        return get_session(conn, session_id)


def add_club_idea(session_id: int, idea: str, db_path: str = DB_PATH) -> int:
    with get_connection(db_path) as conn:
        return add_idea(conn, session_id, idea)


def remove_club_idea(idea_id: int, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        remove_idea(conn, idea_id)


if __name__ == "__main__":
    # Demonstração rápida
    from db import init_db, save_books

    init_db()
    save_books([{"source_id": "clube-demo", "title": "Livro do clube", "authors": ["Autor Exemplo"]}])

    with get_connection() as conn:
        book_id = conn.execute("SELECT id FROM books WHERE source_id = 'clube-demo'").fetchone()["id"]

    session_id = start_club_session(book_id, start_date="2026-01-10")
    print("Ciclo iniciado:", get_current_club_session())

    add_club_idea(session_id, "O que simboliza o título?")
    conclude_club_session(session_id, end_date="2026-02-01", conclusions="Ótima discussão sobre o final.")

    print("Ciclo atual agora:", get_current_club_session())
    print("Histórico:", get_club_history())