"""
main.py

CLI que une toda a pipeline:
1. fetch_books.py    -> busca e normaliza dados da Google Books API (EXTRACT + TRANSFORM)
2. db.py              -> salva no SQLite (LOAD)
3. reading_list.py    -> gerencia status (quero_ler/lendo/lido) e avaliação

Uso:
    python main.py buscar "nome do livro ou autor" [--limit N]
    python main.py listar [--status quero_ler|lendo|lido]
    python main.py status <book_id> <novo_status>
    python main.py avaliar <book_id> <nota_1_a_5>
"""

import argparse

from services.api.fetch_books import search_and_normalize
from services.api.db import init_db, save_books
from services.api.reading_list import change_status, rate_book, list_books, STATUSES


def cmd_buscar(args):
    """Busca livros na API, salva no banco e já mostra o id de cada um."""
    init_db()

    print(f"Buscando '{args.termo}' na Google Books...")
    livros = search_and_normalize(args.termo, max_results=args.limit)
    print(f"{len(livros)} livro(s) encontrado(s).\n")

    if not livros:
        return

    save_books(livros)

    print("Livros salvos (use o id para adicionar à lista com outro comando):")
    for livro in livros:
        autores = ", ".join(livro["authors"])
        print(f"  - {livro['title']} ({autores})")

    print(
        "\nDica: rode 'python main.py listar' para ver os ids "
        "e depois 'python main.py status <id> quero_ler'."
    )


def cmd_listar(args):
    """Lista os livros da lista de leitura, opcionalmente filtrando por status."""
    init_db()
    livros = list_books(status=args.status)

    if not livros:
        print("Nenhum livro encontrado.")
        return

    for livro in livros:
        nota = f" — nota {livro['rating']}" if livro["rating"] else ""
        print(
            f"[{livro['book_id']}] {livro['title']} ({livro['authors']}) "
            f"- {livro['status']}{nota}"
        )


def cmd_status(args):
    """Muda o status de um livro na lista (adiciona se ainda não estiver lá)."""
    init_db()
    from services.api.reading_list import add_book_to_list
    import sqlite3

    try:
        add_book_to_list(args.book_id, status=args.novo_status)
    except sqlite3.IntegrityError:
        print(f"Erro: não existe livro com id={args.book_id} no banco.")
        return
    print(f"Livro {args.book_id} agora está com status '{args.novo_status}'.")


def cmd_avaliar(args):
    """Define a nota (1-5) de um livro já presente na lista."""
    init_db()
    try:
        rate_book(args.book_id, args.nota)
    except ValueError as e:
        print(f"Erro: {e}")
        return
    print(f"Livro {args.book_id} avaliado com nota {args.nota}.")


def build_parser():
    parser = argparse.ArgumentParser(description="Gerenciador de leituras")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    p_buscar = subparsers.add_parser("buscar", help="Busca livros e salva no banco")
    p_buscar.add_argument("termo", help="Título, autor ou termo de busca")
    p_buscar.add_argument("--limit", type=int, default=5, help="Máx. de resultados")
    p_buscar.set_defaults(func=cmd_buscar)

    p_listar = subparsers.add_parser("listar", help="Lista livros da lista de leitura")
    p_listar.add_argument(
        "--status", choices=STATUSES, default=None, help="Filtrar por status"
    )
    p_listar.set_defaults(func=cmd_listar)

    p_status = subparsers.add_parser("status", help="Muda o status de um livro")
    p_status.add_argument("book_id", type=int)
    p_status.add_argument("novo_status", choices=STATUSES)
    p_status.set_defaults(func=cmd_status)

    p_avaliar = subparsers.add_parser("avaliar", help="Avalia um livro (1-5)")
    p_avaliar.add_argument("book_id", type=int)
    p_avaliar.add_argument("nota", type=int, choices=range(1, 6))
    p_avaliar.set_defaults(func=cmd_avaliar)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)