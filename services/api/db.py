"""
db.py

Responsável pela etapa de LOAD da pipeline.
Cria o schema SQLite e insere/atualiza (upsert) os livros normalizados
vindos de fetch_books.py.

Schema (protótipo, mas já relacional):
    books              -> dados do livro
    authors            -> autores (nome único)
    book_authors       -> tabela de junção N:N entre books e authors
    user_lists         -> status/nota/datas/resenha (a "leitura" pessoal)
    book_quotes        -> citações marcadas pelo usuário
    custom_lists       -> listas personalizadas (ex: "Favoritos")
    custom_list_books  -> tabela de junção N:N entre custom_lists e books
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
    started_at TEXT,                -- data de início da leitura (YYYY-MM-DD)
    finished_at TEXT,                -- data de término da leitura (YYYY-MM-DD)
    review TEXT,                     -- resenha pessoal do usuário
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS book_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    quote TEXT NOT NULL,
    page INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS custom_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS custom_list_books (
    list_id INTEGER NOT NULL REFERENCES custom_lists(id) ON DELETE CASCADE,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (list_id, book_id)
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


def _ensure_columns(conn, table: str, columns: dict[str, str]):
    """
    Migração leve: adiciona colunas que ainda não existem em `table`.
    Necessário porque 'CREATE TABLE IF NOT EXISTS' não altera uma tabela
    que já existe -- então um banco criado antes de um campo novo ser
    adicionado ao schema (ex: started_at/finished_at/review) nunca
    ganharia essas colunas sozinho, e a API quebraria com
    "no such column" na primeira tentativa de usá-las.
    """
    existentes = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    for nome, tipo in columns.items():
        if nome not in existentes:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {nome} {tipo}")


def init_db(db_path: str = DB_PATH):
    """Cria as tabelas caso não existam e migra colunas novas em bancos antigos."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        _ensure_columns(conn, "user_lists", {
            "started_at": "TEXT",
            "finished_at": "TEXT",
            "review": "TEXT",
        })


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


def get_books_by_ids(book_ids: list[int], db_path: str = DB_PATH) -> list[dict]:
    """
    Busca dados básicos (título, autores, capa, ano) de vários livros de
    uma vez, na ordem em que os ids foram passados. Usado para montar o
    conteúdo de uma lista personalizada sem fazer uma query por livro.
    ids que não existirem mais em `books` são simplesmente ignorados.
    """
    if not book_ids:
        return []

    with get_connection(db_path) as conn:
        placeholders = ",".join("?" * len(book_ids))
        rows = conn.execute(
            f"""
            SELECT
                b.id AS book_id,
                b.title,
                b.first_publish_year,
                b.cover_url,
                GROUP_CONCAT(DISTINCT a.name) AS authors
            FROM books b
            LEFT JOIN book_authors ba ON ba.book_id = b.id
            LEFT JOIN authors a ON a.id = ba.author_id
            WHERE b.id IN ({placeholders})
            GROUP BY b.id
            """,
            book_ids,
        ).fetchall()

    por_id = {row["book_id"]: dict(row) for row in rows}
    # preserva a ordem recebida (ex: mais recentemente adicionado primeiro)
    return [por_id[bid] for bid in book_ids if bid in por_id]


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
                ul.rating,
                ul.started_at,
                ul.finished_at,
                ul.review
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
                ul.rating,
                ul.started_at,
                ul.finished_at,
                ul.review
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