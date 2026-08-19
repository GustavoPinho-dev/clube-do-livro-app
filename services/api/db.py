"""
db.py

Responsável pela etapa de LOAD da pipeline.
Cria o schema SQLite e insere/atualiza (upsert) os livros normalizados
vindos de fetch_books.py.

Schema (protótipo, mas já relacional):
    books           -> dados do livro
    authors         -> autores (nome único)
    book_authors    -> tabela de junção N:N entre books e authors
"""

import sqlite3
from contextlib import contextmanager

DB_PATH = "books.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT UNIQUE,         -- id do livro na API de origem, evita duplicatas
    title TEXT NOT NULL,
    isbn TEXT,
    first_publish_year INTEGER,
    cover_url TEXT,
    source_api TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS book_authors (
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, author_id)
);

CREATE TABLE IF NOT EXISTS user_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL UNIQUE REFERENCES books(id) ON DELETE CASCADE,
    status TEXT CHECK(status IN ('quero_ler', 'lendo', 'lido')) DEFAULT 'quero_ler',
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def get_connection(db_path: str = DB_PATH):
    """Context manager simples para abrir/fechar a conexão com o SQLite."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str = DB_PATH):
    """Cria as tabelas caso não existam."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)


def _get_or_create_author(conn, name: str) -> int:
    """Busca o id do autor pelo nome, ou cria caso não exista."""
    cur = conn.execute("SELECT id FROM authors WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        return row["id"]

    cur = conn.execute("INSERT INTO authors (name) VALUES (?)", (name,))
    return cur.lastrowid


def upsert_book(conn, book: dict) -> int:
    """
    Insere o livro se ele ainda não existe (baseado no olid),
    ou atualiza os dados caso já exista. Retorna o id do livro no banco.
    Também garante os vínculos com os autores.
    """
    cur = conn.execute(
        """
        INSERT INTO books (source_id, title, isbn, first_publish_year, cover_url, source_api)
        VALUES (:source_id, :title, :isbn, :first_publish_year, :cover_url, :source_api)
        ON CONFLICT(source_id) DO UPDATE SET
            title = excluded.title,
            isbn = excluded.isbn,
            first_publish_year = excluded.first_publish_year,
            cover_url = excluded.cover_url
        """,
        book,
    )

    if cur.lastrowid and cur.rowcount == 1 and cur.lastrowid != 0:
        book_id = cur.lastrowid
    else:
        # Em caso de UPDATE, lastrowid não é confiável -> buscamos pelo source_id
        row = conn.execute(
            "SELECT id FROM books WHERE source_id = ?", (book["source_id"],)
        ).fetchone()
        book_id = row["id"]

    # Vincula autores (evita duplicar vínculo com INSERT OR IGNORE)
    for author_name in book.get("authors", []):
        author_id = _get_or_create_author(conn, author_name)
        conn.execute(
            "INSERT OR IGNORE INTO book_authors (book_id, author_id) VALUES (?, ?)",
            (book_id, author_id),
        )

    return book_id


def save_books(books: list[dict], db_path: str = DB_PATH):
    """Função de conveniência: salva uma lista de livros normalizados."""
    with get_connection(db_path) as conn:
        for book in books:
            upsert_book(conn, book)


def save_book(book: dict, db_path: str = DB_PATH) -> int:
    """Salva um único livro e retorna o id dele no banco (útil para APIs)."""
    with get_connection(db_path) as conn:
        return upsert_book(conn, book)


if __name__ == "__main__":
    # Exemplo/teste rápido com dados fake, sem depender da API
    init_db()

    exemplo = [
        {
            "source_id": "abc123XYZ",
            "title": "Dom Casmurro",
            "authors": ["Machado de Assis"],
            "isbn": "9788535910663",
            "first_publish_year": 1899,
            "cover_url": None,
            "source_api": "google_books",
        }
    ]

    save_books(exemplo)
    print("Banco inicializado e livro de exemplo salvo em", DB_PATH)