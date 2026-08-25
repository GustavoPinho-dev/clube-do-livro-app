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
