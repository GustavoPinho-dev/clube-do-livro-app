"""
custom_lists.py

Gerencia listas de leitura personalizadas, com nomes escolhidos pelo
usuário (ex: "Favoritos de verão", "Para reler", "Indicações de amigos").

Diferente de user_lists (que representa o status quero_ler/lendo/lido --
uma gaveta fixa por livro), aqui um livro pode estar em quantas listas
personalizadas quiser, e as listas em si são criadas livremente pelo
usuário.

Vive no mesmo books.db que o resto da pipeline (schema definido em
db.py), com FOREIGN KEY de verdade para `books(id)` -- se um livro for
apagado, ele some automaticamente de todas as listas personalizadas
(ON DELETE CASCADE), sem precisar de checagem manual.
"""

import sqlite3

from db import get_connection, DB_PATH


# ---------------------------------------------------------------------
# Listas
# ---------------------------------------------------------------------

def create_list(conn, name: str, description: str = None) -> int:
    """Cria uma lista personalizada. O nome precisa ser único."""
    name = (name or "").strip()
    if not name:
        raise ValueError("o nome da lista não pode ficar vazio.")

    try:
        cur = conn.execute(
            "INSERT INTO custom_lists (name, description) VALUES (?, ?)",
            (name, (description or "").strip() or None),
        )
    except sqlite3.IntegrityError:
        raise ValueError(f"já existe uma lista chamada '{name}'.")

    return cur.lastrowid


def rename_list(conn, list_id: int, name: str = None, description: str = None):
    """Atualiza nome e/ou descrição de uma lista. Passe None para não alterar o campo."""
    row = conn.execute("SELECT name, description FROM custom_lists WHERE id = ?", (list_id,)).fetchone()
    if row is None:
        raise ValueError(f"lista (id={list_id}) não encontrada.")

    novo_nome = row["name"]
    if name is not None:
        novo_nome = name.strip()
        if not novo_nome:
            raise ValueError("o nome da lista não pode ficar vazio.")

    nova_desc = row["description"] if description is None else (description.strip() or None)

    try:
        conn.execute(
            "UPDATE custom_lists SET name = ?, description = ? WHERE id = ?",
            (novo_nome, nova_desc, list_id),
        )
    except sqlite3.IntegrityError:
        raise ValueError(f"já existe uma lista chamada '{novo_nome}'.")


def delete_list(conn, list_id: int):
    """Apaga a lista e todos os vínculos com livros (ON DELETE CASCADE)."""
    conn.execute("DELETE FROM custom_lists WHERE id = ?", (list_id,))


def get_lists(conn) -> list[dict]:
    """Retorna todas as listas, com a contagem de livros em cada uma."""
    rows = conn.execute(
        """
        SELECT
            cl.id, cl.name, cl.description, cl.created_at,
            COUNT(clb.book_id) AS book_count
        FROM custom_lists cl
        LEFT JOIN custom_list_books clb ON clb.list_id = cl.id
        GROUP BY cl.id
        ORDER BY cl.created_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_list_meta(conn, list_id: int) -> dict | None:
    """Metadados de uma lista específica (sem os livros)."""
    row = conn.execute(
        "SELECT id, name, description, created_at FROM custom_lists WHERE id = ?",
        (list_id,),
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------
# Livros dentro das listas
# ---------------------------------------------------------------------

def add_book(conn, list_id: int, book_id: int):
    """
    Adiciona um livro a uma lista (idempotente: se já estiver lá, não faz
    nada). A FK em custom_list_books.book_id garante que o livro precisa
    existir em `books` -- se não existir, o INSERT falha com IntegrityError.
    """
    if get_list_meta(conn, list_id) is None:
        raise ValueError(f"lista (id={list_id}) não encontrada.")

    try:
        conn.execute(
            "INSERT OR IGNORE INTO custom_list_books (list_id, book_id) VALUES (?, ?)",
            (list_id, book_id),
        )
    except sqlite3.IntegrityError:
        raise ValueError(f"livro (id={book_id}) não encontrado.")


def remove_book(conn, list_id: int, book_id: int):
    """Remove um livro de uma lista (não afeta outras listas nem o livro em si)."""
    conn.execute(
        "DELETE FROM custom_list_books WHERE list_id = ? AND book_id = ?",
        (list_id, book_id),
    )


def get_book_ids(conn, list_id: int) -> list[int]:
    """ids dos livros dentro de uma lista, do mais recente pro mais antigo."""
    rows = conn.execute(
        "SELECT book_id FROM custom_list_books WHERE list_id = ? ORDER BY added_at DESC",
        (list_id,),
    ).fetchall()
    return [row["book_id"] for row in rows]


def get_lists_for_book(conn, book_id: int) -> list[dict]:
    """Em quais listas personalizadas um determinado livro aparece."""
    rows = conn.execute(
        """
        SELECT cl.id, cl.name
        FROM custom_lists cl
        JOIN custom_list_books clb ON clb.list_id = cl.id
        WHERE clb.book_id = ?
        ORDER BY cl.name
        """,
        (book_id,),
    ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------
# Funções de conveniência (abrem a própria conexão)
# ---------------------------------------------------------------------

def create_custom_list(name: str, description: str = None, db_path: str = DB_PATH) -> int:
    with get_connection(db_path) as conn:
        return create_list(conn, name, description)


def rename_custom_list(list_id: int, name: str = None, description: str = None, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        rename_list(conn, list_id, name, description)


def delete_custom_list(list_id: int, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        delete_list(conn, list_id)


def list_custom_lists(db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        return get_lists(conn)


def get_custom_list_meta(list_id: int, db_path: str = DB_PATH) -> dict | None:
    with get_connection(db_path) as conn:
        return get_list_meta(conn, list_id)


def add_book_to_custom_list(list_id: int, book_id: int, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        add_book(conn, list_id, book_id)


def remove_book_from_custom_list(list_id: int, book_id: int, db_path: str = DB_PATH):
    with get_connection(db_path) as conn:
        remove_book(conn, list_id, book_id)


def get_custom_list_book_ids(list_id: int, db_path: str = DB_PATH) -> list[int]:
    with get_connection(db_path) as conn:
        return get_book_ids(conn, list_id)


def get_custom_lists_for_book(book_id: int, db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        return get_lists_for_book(conn, book_id)


if __name__ == "__main__":
    # Demonstração rápida (cria livros de exemplo primeiro, já que agora
    # a FK exige que eles existam antes de entrar numa lista personalizada)
    from db import init_db, save_books

    init_db()
    save_books([
        {"source_id": "demo1", "title": "Livro de exemplo 1", "authors": ["Autor A"]},
        {"source_id": "demo2", "title": "Livro de exemplo 2", "authors": ["Autor B"]},
    ])

    with get_connection() as conn:
        ids = [
            row["id"]
            for row in conn.execute("SELECT id FROM books WHERE source_id IN ('demo1', 'demo2')")
        ]

    list_id = create_custom_list("Favoritos de verão", "Leituras leves para as férias")
    print(f"Lista criada com id={list_id}")

    for book_id in ids:
        add_book_to_custom_list(list_id, book_id)
    print("Livros na lista:", get_custom_list_book_ids(list_id))

    print("Todas as listas:", list_custom_lists())