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
    description TEXT,
    publisher TEXT,
    page_count INTEGER,
    categories TEXT,                -- categorias separadas por vírgula
    average_rating REAL,            -- avaliação pública da Google Books (não é a do usuário)
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


DEFAULT_BOOK_FIELDS = {
    "source_id": None,
    "title": None,
    "isbn": None,
    "first_publish_year": None,
    "cover_url": None,
    "source_api": None,
    "description": None,
    "publisher": None,
    "page_count": None,
    "categories": None,
    "average_rating": None,
    "authors": [],
}


def upsert_book(conn, book: dict) -> int:
    """
    Insere o livro se ele ainda não existe (baseado no source_id),
    ou atualiza os dados caso já exista. Retorna o id do livro no banco.
    Também garante os vínculos com os autores.

    Campos ausentes em `book` recebem um default seguro (None / lista
    vazia), então chamadores antigos que não conheçam os campos mais
    recentes (ex: description, publisher) continuam funcionando.
    """
    data = {**DEFAULT_BOOK_FIELDS, **book}

    # categories pode vir como lista (da API) -> guardamos como string simples
    if isinstance(data.get("categories"), list):
        data["categories"] = ", ".join(data["categories"]) or None

    cur = conn.execute(
        """
        INSERT INTO books (
            source_id, title, isbn, first_publish_year, cover_url, source_api,
            description, publisher, page_count, categories, average_rating
        )
        VALUES (
            :source_id, :title, :isbn, :first_publish_year, :cover_url, :source_api,
            :description, :publisher, :page_count, :categories, :average_rating
        )
        ON CONFLICT(source_id) DO UPDATE SET
            title = excluded.title,
            isbn = excluded.isbn,
            first_publish_year = excluded.first_publish_year,
            cover_url = excluded.cover_url,
            description = excluded.description,
            publisher = excluded.publisher,
            page_count = excluded.page_count,
            categories = excluded.categories,
            average_rating = excluded.average_rating
        """,
        data,
    )

    if cur.lastrowid and cur.rowcount == 1 and cur.lastrowid != 0:
        book_id = cur.lastrowid
    else:
        # Em caso de UPDATE, lastrowid não é confiável -> buscamos pelo source_id
        row = conn.execute(
            "SELECT id FROM books WHERE source_id = ?", (data["source_id"],)
        ).fetchone()
        book_id = row["id"]

    # Vincula autores (evita duplicar vínculo com INSERT OR IGNORE)
    for author_name in data.get("authors") or []:
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


def get_book_detail(book_id: int, db_path: str = DB_PATH) -> dict | None:
    """
    Retorna todos os dados de um livro (para a página de detalhes),
    juntando autores e, se o livro estiver na lista de leitura, o
    status/nota do usuário. Retorna None se o id não existir.
    """
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                b.*,
                GROUP_CONCAT(DISTINCT a.name) AS authors,
                ul.status,
                ul.rating
            FROM books b
            LEFT JOIN book_authors ba ON ba.book_id = b.id
            LEFT JOIN authors a ON a.id = ba.author_id
            LEFT JOIN user_lists ul ON ul.book_id = b.id
            WHERE b.id = ?
            GROUP BY b.id
            """,
            (book_id,),
        ).fetchone()

        return dict(row) if row else None


def get_book_detail_by_source_id(source_id: str, db_path: str = DB_PATH) -> dict | None:
    """
    Mesma ideia de get_book_detail, mas busca pelo source_id (id da API
    de origem) em vez do id interno. É o que permite a página de detalhes
    funcionar com um único identificador estável na URL, usado tanto para
    livros já salvos quanto para resultados de busca ainda não salvos
    (nesse caso, retorna None e quem chamou busca na API externa).
    """
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                b.*,
                GROUP_CONCAT(DISTINCT a.name) AS authors,
                ul.status,
                ul.rating
            FROM books b
            LEFT JOIN book_authors ba ON ba.book_id = b.id
            LEFT JOIN authors a ON a.id = ba.author_id
            LEFT JOIN user_lists ul ON ul.book_id = b.id
            WHERE b.source_id = ?
            GROUP BY b.id
            """,
            (source_id,),
        ).fetchone()

        return dict(row) if row else None


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