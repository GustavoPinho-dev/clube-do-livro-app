"""
reading_list.py

Gerencia as listas de leitura do usuário: adicionar livros, mudar status
(quero_ler / lendo / lido) e avaliar (rating de 1 a 5).

Regra do protótipo: cada livro tem, no máximo, UMA entrada na lista
(constraint UNIQUE em user_lists.book_id). Ou seja, "adicionar à lista"
é sempre um upsert -- se o livro já estiver lá, apenas atualiza o status.
"""

from datetime import date

from db import get_connection, DB_PATH

STATUSES = ("quero_ler", "lendo", "lido")


def _validate_status(status: str):
    if status not in STATUSES:
        raise ValueError(f"status inválido: '{status}'. Use um de {STATUSES}")


def _validate_rating(rating):
    if rating is not None and not (1 <= rating <= 5):
        raise ValueError("rating deve ser um inteiro entre 1 e 5")


def _validate_date(value: str | None) -> str | None:
    """Aceita None (limpa a data) ou uma string 'YYYY-MM-DD' válida."""
    if value is None or value == "":
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"data inválida: '{value}'. Use o formato AAAA-MM-DD.")
    return value


# ---------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------

def add_to_list(conn, book_id: int, status: str = "quero_ler") -> int:
    """
    Adiciona um livro à lista com o status informado (padrão: 'quero_ler').
    Se o livro já estiver na lista, apenas atualiza o status
    (o rating existente é preservado).
    Retorna o id da entrada em user_lists.
    """
    _validate_status(status)

    cur = conn.execute(
        """
        INSERT INTO user_lists (book_id, status)
        VALUES (?, ?)
        ON CONFLICT(book_id) DO UPDATE SET
            status = excluded.status,
            updated_at = CURRENT_TIMESTAMP
        """,
        (book_id, status),
    )

    row = conn.execute(
        "SELECT id FROM user_lists WHERE book_id = ?", (book_id,)
    ).fetchone()
    return row["id"]


def update_status(conn, book_id: int, new_status: str):
    """Atualiza apenas o status de um livro que já está na lista."""
    _validate_status(new_status)

    cur = conn.execute(
        """
        UPDATE user_lists
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE book_id = ?
        """,
        (new_status, book_id),
    )

    if cur.rowcount == 0:
        raise ValueError(
            f"Livro (id={book_id}) não está na lista. Use add_to_list primeiro."
        )


def set_rating(conn, book_id: int, rating: int):
    """
    Define a avaliação (1-5) de um livro. Normalmente faz sentido
    quando o status é 'lido', mas isso não é forçado aqui.
    """
    _validate_rating(rating)

    cur = conn.execute(
        """
        UPDATE user_lists
        SET rating = ?, updated_at = CURRENT_TIMESTAMP
        WHERE book_id = ?
        """,
        (rating, book_id),
    )

    if cur.rowcount == 0:
        raise ValueError(
            f"Livro (id={book_id}) não está na lista. Use add_to_list primeiro."
        )


def mark_as_read(conn, book_id: int, rating: int = None):
    """Atalho: marca como 'lido' e, opcionalmente, já define o rating."""
    update_status(conn, book_id, "lido")
    if rating is not None:
        set_rating(conn, book_id, rating)


def set_reading_dates(conn, book_id: int, started_at: str = None, finished_at: str = None):
    """
    Define a data de início e/ou término da leitura (formato 'YYYY-MM-DD').
    Passar None para um campo o mantém como está -- use string vazia (\"\")
    explicitamente para limpar uma data já definida.

    Faz uma validação leve: se as duas datas ficarem definidas (a que está
    sendo passada agora + a que já existia no banco), a data de término não
    pode ser anterior à de início.
    """
    row = conn.execute(
        "SELECT started_at, finished_at FROM user_lists WHERE book_id = ?", (book_id,)
    ).fetchone()
    if row is None:
        raise ValueError(
            f"Livro (id={book_id}) não está na lista. Use add_to_list primeiro."
        )

    novo_started = _validate_date(started_at) if started_at is not None else row["started_at"]
    novo_finished = _validate_date(finished_at) if finished_at is not None else row["finished_at"]

    if novo_started and novo_finished and novo_finished < novo_started:
        raise ValueError("a data de término não pode ser anterior à data de início.")

    conn.execute(
        """
        UPDATE user_lists
        SET started_at = ?, finished_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE book_id = ?
        """,
        (novo_started, novo_finished, book_id),
    )


def set_review(conn, book_id: int, review: str):
    """Define (ou limpa, com string vazia/None) a resenha pessoal do livro."""
    cur = conn.execute(
        """
        UPDATE user_lists
        SET review = ?, updated_at = CURRENT_TIMESTAMP
        WHERE book_id = ?
        """,
        (review or None, book_id),
    )

    if cur.rowcount == 0:
        raise ValueError(
            f"Livro (id={book_id}) não está na lista. Use add_to_list primeiro."
        )


def add_quote(conn, book_id: int, quote: str, page: int = None) -> int:
    """Adiciona uma citação a um livro. Retorna o id da citação criada."""
    quote = (quote or "").strip()
    if not quote:
        raise ValueError("a citação não pode ficar vazia.")

    cur = conn.execute(
        "INSERT INTO book_quotes (book_id, quote, page) VALUES (?, ?, ?)",
        (book_id, quote, page),
    )
    return cur.lastrowid


def remove_quote(conn, quote_id: int):
    """Remove uma citação pelo id dela."""
    conn.execute("DELETE FROM book_quotes WHERE id = ?", (quote_id,))


def get_quotes(conn, book_id: int) -> list[dict]:
    """Lista as citações salvas para um livro, da mais recente pra mais antiga."""
    rows = conn.execute(
        "SELECT id, quote, page, created_at FROM book_quotes WHERE book_id = ? ORDER BY created_at DESC",
        (book_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def remove_from_list(conn, book_id: int):
    """Remove um livro da lista (não apaga o livro da tabela books)."""
    conn.execute("DELETE FROM user_lists WHERE book_id = ?", (book_id,))


# ---------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------

def get_list(conn, status: str = None) -> list[dict]:
    """
    Retorna os livros da lista, com título, autores, status e rating.
    Se `status` for informado, filtra só por ele.
    """
    if status is not None:
        _validate_status(status)

    query = """
        SELECT
            b.id AS book_id,
            b.source_id,
            b.title,
            b.first_publish_year,
            GROUP_CONCAT(a.name, ', ') AS authors,
            ul.status,
            ul.rating,
            ul.added_at,
            ul.updated_at
        FROM user_lists ul
        JOIN books b ON b.id = ul.book_id
        LEFT JOIN book_authors ba ON ba.book_id = b.id
        LEFT JOIN authors a ON a.id = ba.author_id
    """

    params = ()
    if status is not None:
        query += " WHERE ul.status = ?"
        params = (status,)

    query += " GROUP BY b.id ORDER BY ul.updated_at DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------
# Funções de conveniência (abrem a própria conexão)
# ---------------------------------------------------------------------

def add_book_to_list(book_id: int, status: str = "quero_ler", db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        return add_to_list(conn, book_id, status)


def change_status(book_id: int, new_status: str, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        update_status(conn, book_id, new_status)


def rate_book(book_id: int, rating: int, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        set_rating(conn, book_id, rating)


def list_books(status: str = None, db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        return get_list(conn, status)


def remove_book_from_list(book_id: int, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        remove_from_list(conn, book_id)


def update_reading_dates(book_id: int, started_at: str = None, finished_at: str = None, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        set_reading_dates(conn, book_id, started_at=started_at, finished_at=finished_at)


def update_review(book_id: int, review: str, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        set_review(conn, book_id, review)


def add_quote_to_book(book_id: int, quote: str, page: int = None, db_path: str = DB_PATH) -> int:
    with get_connection(db_path) as conn:
        return add_quote(conn, book_id, quote, page)


def remove_quote_from_book(quote_id: int, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        remove_quote(conn, quote_id)


def list_quotes(book_id: int, db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        return get_quotes(conn, book_id)


if __name__ == "__main__":
    # Demonstração rápida usando o livro de exemplo criado por db.py
    from db import init_db, save_books

    init_db()
    save_books([
        {
            "source_id": "abc123XYZ",
            "title": "Dom Casmurro",
            "authors": ["Machado de Assis"],
            "isbn": "9788535910663",
            "first_publish_year": 1899,
            "cover_url": None,
            "source_api": "google_books",
        }
    ])

    with get_connection() as conn:
        row = conn.execute("SELECT id FROM books WHERE source_id = 'abc123XYZ'").fetchone()
        book_id = row["id"]

        add_to_list(conn, book_id, "quero_ler")
        print("Adicionado como 'quero_ler'")

        update_status(conn, book_id, "lendo")
        print("Status atualizado para 'lendo'")

        mark_as_read(conn, book_id, rating=5)
        print("Marcado como 'lido' com nota 5")

    print("\nLista completa:")
    for livro in list_books():
        print(livro)