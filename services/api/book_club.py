"""
book_club.py

Gerencia os ciclos do clube do livro: criação, listagem, ciclo atual,
atualização de datas/status/conclusões e finalização.

Os ciclos vivem em `book_club_cycles` (schema em db.py) e sempre apontam
para um livro existente em `books(id)`.
"""

import sqlite3
from datetime import date

from db import DB_PATH, get_connection

STATUSES = ("planned", "current", "finished")


def _validate_status(status: str):
    if status not in STATUSES:
        raise ValueError(f"status inválido: '{status}'. Use um de {STATUSES}")


def _validate_date(value: str | None) -> str | None:
    """Aceita None/string vazia ou uma string 'YYYY-MM-DD' válida."""
    if value is None or value == "":
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"data inválida: '{value}'. Use o formato AAAA-MM-DD.")
    return value


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _validate_date_range(start_date: str | None, end_date: str | None):
    if start_date and end_date and end_date < start_date:
        raise ValueError("a data de término não pode ser anterior à data de início.")


def _row_to_dict(row) -> dict | None:
    return dict(row) if row else None


def _get_cycle(conn, cycle_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT
            bcc.id,
            bcc.book_id,
            bcc.title,
            bcc.start_date,
            bcc.end_date,
            bcc.status,
            bcc.conclusions,
            bcc.created_at,
            bcc.updated_at,
            b.title AS book_title,
            b.cover_url AS book_cover_url,
            GROUP_CONCAT(DISTINCT a.name) AS authors
        FROM book_club_cycles bcc
        JOIN books b ON b.id = bcc.book_id
        LEFT JOIN book_authors ba ON ba.book_id = b.id
        LEFT JOIN authors a ON a.id = ba.author_id
        WHERE bcc.id = ?
        GROUP BY bcc.id
        """,
        (cycle_id,),
    ).fetchone()
    return _row_to_dict(row)


# ---------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------

def create_cycle(
    conn,
    book_id: int,
    title: str = None,
    start_date: str = None,
    end_date: str = None,
    status: str = "planned",
    conclusions: str = None,
) -> int:
    """Cria um ciclo do clube do livro e retorna o id criado."""
    _validate_status(status)
    start_date = _validate_date(start_date)
    end_date = _validate_date(end_date)
    _validate_date_range(start_date, end_date)

    try:
        cur = conn.execute(
            """
            INSERT INTO book_club_cycles (
                book_id, title, start_date, end_date, status, conclusions
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                book_id,
                _normalize_text(title),
                start_date,
                end_date,
                status,
                _normalize_text(conclusions),
            ),
        )
    except sqlite3.IntegrityError:
        raise ValueError(f"livro (id={book_id}) não encontrado.")

    return cur.lastrowid


def update_cycle(
    conn,
    cycle_id: int,
    title: str = None,
    start_date: str = None,
    end_date: str = None,
    status: str = None,
    conclusions: str = None,
) -> dict:
    """
    Atualiza datas/status/conclusões (e título opcional) de um ciclo.
    Passe None para manter um campo como está; passe string vazia para
    limpar title/start_date/end_date/conclusions.
    """
    row = conn.execute(
        """
        SELECT title, start_date, end_date, status, conclusions
        FROM book_club_cycles
        WHERE id = ?
        """,
        (cycle_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"ciclo (id={cycle_id}) não encontrado.")

    new_title = row["title"] if title is None else _normalize_text(title)
    new_start_date = row["start_date"] if start_date is None else _validate_date(start_date)
    new_end_date = row["end_date"] if end_date is None else _validate_date(end_date)
    new_status = row["status"] if status is None else status
    new_conclusions = row["conclusions"] if conclusions is None else _normalize_text(conclusions)

    _validate_status(new_status)
    _validate_date_range(new_start_date, new_end_date)

    conn.execute(
        """
        UPDATE book_club_cycles
        SET title = ?,
            start_date = ?,
            end_date = ?,
            status = ?,
            conclusions = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (new_title, new_start_date, new_end_date, new_status, new_conclusions, cycle_id),
    )
    return _get_cycle(conn, cycle_id)


def finish_cycle(conn, cycle_id: int, conclusions: str = None, end_date: str = None) -> dict:
    """Finaliza um ciclo, opcionalmente salvando conclusões e data de término."""
    today = date.today().isoformat()
    return update_cycle(
        conn,
        cycle_id,
        end_date=end_date if end_date is not None else today,
        status="finished",
        conclusions=conclusions,
    )


# ---------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------

def list_cycles(conn, status: str = None) -> list[dict]:
    """Lista ciclos do clube, opcionalmente filtrados por status."""
    params = []
    query = """
        SELECT
            bcc.id,
            bcc.book_id,
            bcc.title,
            bcc.start_date,
            bcc.end_date,
            bcc.status,
            bcc.conclusions,
            bcc.created_at,
            bcc.updated_at,
            b.title AS book_title,
            b.cover_url AS book_cover_url,
            GROUP_CONCAT(DISTINCT a.name) AS authors
        FROM book_club_cycles bcc
        JOIN books b ON b.id = bcc.book_id
        LEFT JOIN book_authors ba ON ba.book_id = b.id
        LEFT JOIN authors a ON a.id = ba.author_id
    """
    if status is not None:
        _validate_status(status)
        query += " WHERE bcc.status = ?"
        params.append(status)

    query += " GROUP BY bcc.id ORDER BY COALESCE(bcc.start_date, bcc.created_at) DESC, bcc.id DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_current_cycle(conn) -> dict | None:
    """Retorna o ciclo atual mais recente, ou None se não houver ciclo atual."""
    row = conn.execute(
        """
        SELECT id
        FROM book_club_cycles
        WHERE status = 'current'
        ORDER BY COALESCE(start_date, created_at) DESC, id DESC
        LIMIT 1
        """
    ).fetchone()
    return _get_cycle(conn, row["id"]) if row else None


# ---------------------------------------------------------------------
# Ideias para próximos ciclos
# ---------------------------------------------------------------------

IDEA_ORDERINGS = {
    "votes": "bci.votes DESC, bci.created_at DESC, bci.id DESC",
    "date": "bci.created_at DESC, bci.id DESC",
}


def _validate_votes(votes: int | None) -> int | None:
    if votes is None:
        return None
    if not isinstance(votes, int) or votes < 0:
        raise ValueError("votes deve ser um inteiro maior ou igual a 0.")
    return votes


def _get_idea(conn, idea_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT
            bci.id,
            bci.book_id,
            bci.note,
            bci.suggested_by,
            bci.votes,
            bci.created_at,
            bci.updated_at,
            b.title AS book_title,
            b.cover_url AS book_cover_url,
            GROUP_CONCAT(DISTINCT a.name) AS authors
        FROM book_club_ideas bci
        JOIN books b ON b.id = bci.book_id
        LEFT JOIN book_authors ba ON ba.book_id = b.id
        LEFT JOIN authors a ON a.id = ba.author_id
        WHERE bci.id = ?
        GROUP BY bci.id
        """,
        (idea_id,),
    ).fetchone()
    return _row_to_dict(row)


def add_idea(conn, book_id: int, note: str = None, suggested_by: str = None, votes: int = 0) -> int:
    """Adiciona uma ideia de livro para o clube e retorna o id criado."""
    votes = _validate_votes(votes)

    try:
        cur = conn.execute(
            """
            INSERT INTO book_club_ideas (book_id, note, suggested_by, votes)
            VALUES (?, ?, ?, ?)
            """,
            (book_id, _normalize_text(note), _normalize_text(suggested_by), votes),
        )
    except sqlite3.IntegrityError:
        raise ValueError(f"livro (id={book_id}) não encontrado.")

    return cur.lastrowid


def remove_idea(conn, idea_id: int) -> bool:
    """Remove uma ideia. Retorna True quando alguma linha foi removida."""
    cur = conn.execute("DELETE FROM book_club_ideas WHERE id = ?", (idea_id,))
    return cur.rowcount > 0


def list_ideas(conn, order_by: str = "votes") -> list[dict]:
    """Lista ideias ordenadas por votos (padrão) ou data de criação."""
    if order_by not in IDEA_ORDERINGS:
        raise ValueError("ordenação inválida. Use 'votes' ou 'date'.")

    rows = conn.execute(
        f"""
        SELECT
            bci.id,
            bci.book_id,
            bci.note,
            bci.suggested_by,
            bci.votes,
            bci.created_at,
            bci.updated_at,
            b.title AS book_title,
            b.cover_url AS book_cover_url,
            GROUP_CONCAT(DISTINCT a.name) AS authors
        FROM book_club_ideas bci
        JOIN books b ON b.id = bci.book_id
        LEFT JOIN book_authors ba ON ba.book_id = b.id
        LEFT JOIN authors a ON a.id = ba.author_id
        GROUP BY bci.id
        ORDER BY {IDEA_ORDERINGS[order_by]}
        """
    ).fetchall()
    return [dict(row) for row in rows]


def update_idea(conn, idea_id: int, note: str = None, votes: int = None) -> dict:
    """
    Atualiza observação e/ou votos de uma ideia.
    Passe None para manter o campo atual; passe string vazia para limpar note.
    """
    row = conn.execute(
        "SELECT note, votes FROM book_club_ideas WHERE id = ?",
        (idea_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"ideia (id={idea_id}) não encontrada.")

    new_note = row["note"] if note is None else _normalize_text(note)
    new_votes = row["votes"] if votes is None else _validate_votes(votes)

    conn.execute(
        """
        UPDATE book_club_ideas
        SET note = ?, votes = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (new_note, new_votes, idea_id),
    )
    return _get_idea(conn, idea_id)


def add_book_club_idea(
    book_id: int,
    note: str = None,
    suggested_by: str = None,
    votes: int = 0,
    db_path: str = DB_PATH,
) -> int:
    with get_connection(db_path) as conn:
        return add_idea(conn, book_id, note, suggested_by, votes)


def remove_book_club_idea(idea_id: int, db_path: str = DB_PATH) -> bool:
    with get_connection(db_path) as conn:
        return remove_idea(conn, idea_id)


def list_book_club_ideas(order_by: str = "votes", db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        return list_ideas(conn, order_by)


def update_book_club_idea(
    idea_id: int,
    note: str = None,
    votes: int = None,
    db_path: str = DB_PATH,
) -> dict:
    with get_connection(db_path) as conn:
        return update_idea(conn, idea_id, note, votes)

# ---------------------------------------------------------------------
# Funções de conveniência (abrem a própria conexão)
# ---------------------------------------------------------------------

def create_book_club_cycle(
    book_id: int,
    title: str = None,
    start_date: str = None,
    end_date: str = None,
    status: str = "planned",
    conclusions: str = None,
    db_path: str = DB_PATH,
) -> int:
    with get_connection(db_path) as conn:
        return create_cycle(conn, book_id, title, start_date, end_date, status, conclusions)


def list_book_club_cycles(status: str = None, db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        return list_cycles(conn, status)


def get_current_book_club_cycle(db_path: str = DB_PATH) -> dict | None:
    with get_connection(db_path) as conn:
        return get_current_cycle(conn)


def update_book_club_cycle(
    cycle_id: int,
    title: str = None,
    start_date: str = None,
    end_date: str = None,
    status: str = None,
    conclusions: str = None,
    db_path: str = DB_PATH,
) -> dict:
    with get_connection(db_path) as conn:
        return update_cycle(conn, cycle_id, title, start_date, end_date, status, conclusions)


def finish_book_club_cycle(
    cycle_id: int,
    conclusions: str = None,
    end_date: str = None,
    db_path: str = DB_PATH,
) -> dict:
    with get_connection(db_path) as conn:
        return finish_cycle(conn, cycle_id, conclusions, end_date)
