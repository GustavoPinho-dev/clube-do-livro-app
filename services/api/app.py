"""
services/api/app.py

Serviço de API — responsabilidade única: expor a pipeline (busca, banco,
listas de leitura) como endpoints REST/JSON.

Este serviço NÃO sabe nada sobre HTML, CSS ou como a informação será
exibida. Qualquer cliente HTTP pode consumi-lo: o frontend web deste
projeto, um app mobile, outro script, o Postman, etc. Essa é a ideia
central de separar em microsserviços: o contrato é a API HTTP, não o
código compartilhado.

Rodar (independente do frontend):
    pip install -r requirements.txt
    cp .env.example .env   # e preencha GOOGLE_BOOKS_API_KEY
    python app.py
    # API disponível em http://localhost:5001 -- sozinha, sem frontend nenhum
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import requests as requests_lib

from fetch_books import search_and_normalize, get_and_normalize_volume
from db import (
    init_db,
    save_book,
    get_book_detail,
    get_book_detail_by_source_id,
    get_books_by_ids,
)
from reading_list import (
    add_book_to_list,
    rate_book,
    list_books,
    remove_book_from_list,
    update_reading_dates,
    update_review,
    add_quote_to_book,
    remove_quote_from_book,
    list_quotes,
    STATUSES,
)
from custom_lists import (
    create_custom_list,
    rename_custom_list,
    delete_custom_list,
    list_custom_lists,
    get_custom_list_meta,
    add_book_to_custom_list,
    remove_book_from_custom_list,
    get_custom_list_book_ids,
    get_custom_lists_for_book,
)
import sqlite3

load_dotenv()

app = Flask(__name__)

# CORS liberado para as origens configuradas (o frontend roda em outra porta/
# domínio, então sem isso o navegador bloquearia as chamadas). Em produção,
# restrinja CORS_ORIGINS ao domínio real do frontend em vez de usar "*".
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
CORS(app, origins=CORS_ORIGINS.split(",") if CORS_ORIGINS != "*" else "*")


@app.route("/health")
def health():
    """Endpoint de saúde — útil para orquestradores/monitoramento saberem
    que este serviço está de pé, independente do frontend."""
    return jsonify({"status": "ok", "service": "api"})


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    limit = request.args.get("limit", default=10, type=int)

    if not query:
        return jsonify({"error": "Parâmetro 'q' é obrigatório."}), 400

    try:
        livros = search_and_normalize(query, max_results=limit)
    except requests_lib.exceptions.HTTPError as e:
        return jsonify({"error": f"Erro ao consultar a Google Books API: {e}"}), 502
    except requests_lib.exceptions.RequestException as e:
        return jsonify({"error": f"Falha de conexão: {e}"}), 502

    return jsonify(livros)


@app.route("/api/books", methods=["POST"])
def api_save_book():
    book = request.get_json(silent=True)

    if not book or not book.get("source_id"):
        return jsonify({"error": "Corpo inválido: 'source_id' é obrigatório."}), 400

    init_db()
    book_id = save_book(book)
    return jsonify({"book_id": book_id}), 201


@app.route("/api/books/<int:book_id>")
def api_get_book(book_id):
    init_db()
    livro = get_book_detail(book_id)

    if livro is None:
        return jsonify({"error": f"Livro id={book_id} não encontrado."}), 404

    livro = _normalize_book_response(livro)
    livro["quotes"] = list_quotes(book_id)
    livro["custom_lists"] = get_custom_lists_for_book(book_id)
    return jsonify(livro)


@app.route("/api/volumes/<path:source_id>")
def api_get_volume(source_id):
    """
    Detalhes de um livro identificados pelo id da Google Books (source_id).
    Diferente de /api/books/<id>, esse endpoint funciona mesmo para livros
    que o usuário ainda não salvou: nesse caso, busca ao vivo na Google
    Books e retorna com book_id=None (indicando "ainda não está na lista").
    """
    init_db()

    livro = get_book_detail_by_source_id(source_id)
    if livro is not None:
        livro = _normalize_book_response(livro)
        livro["quotes"] = list_quotes(livro["book_id"])
        livro["custom_lists"] = get_custom_lists_for_book(livro["book_id"])
        return jsonify(livro)

    # Não está salvo ainda -> busca direto na Google Books
    try:
        livro = get_and_normalize_volume(source_id)
    except requests_lib.exceptions.HTTPError as e:
        return jsonify({"error": f"Erro ao consultar a Google Books API: {e}"}), 502
    except requests_lib.exceptions.RequestException as e:
        return jsonify({"error": f"Falha de conexão: {e}"}), 502

    if livro is None:
        return jsonify({"error": f"Volume '{source_id}' não encontrado."}), 404

    livro.update({
        "book_id": None,
        "status": None,
        "rating": None,
        "started_at": None,
        "finished_at": None,
        "review": None,
    })
    livro = _normalize_book_response(livro)
    livro["quotes"] = []  # ainda não salvo -> não pode ter citações registradas
    livro["custom_lists"] = []  # idem para listas personalizadas
    return jsonify(livro)


def _normalize_book_response(livro: dict) -> dict:
    """
    Deixa a resposta de detalhes consistente com o resto da API:
    - 'id' (coluna interna do banco) vira 'book_id', igual aos outros
      endpoints (/api/list, /api/books POST).
    - 'categories' sempre chega como lista, venha do banco (string
      'a, b') ou direto da Google Books (já é lista).
    """
    livro = dict(livro)

    if "id" in livro:
        livro["book_id"] = livro.pop("id")

    categories = livro.get("categories")
    if isinstance(categories, str):
        livro["categories"] = [c.strip() for c in categories.split(",") if c.strip()]
    elif categories is None:
        livro["categories"] = []

    return livro


@app.route("/api/list")
def api_list():
    status = request.args.get("status")

    if status and status not in STATUSES:
        return jsonify({"error": f"status inválido. Use um de {STATUSES}"}), 400

    init_db()
    return jsonify(list_books(status=status))


@app.route("/api/list/<int:book_id>", methods=["POST"])
def api_update_status(book_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")

    if status not in STATUSES:
        return jsonify({"error": f"status inválido. Use um de {STATUSES}"}), 400

    try:
        add_book_to_list(book_id, status=status)
    except Exception:
        return jsonify({"error": f"Livro id={book_id} não encontrado."}), 404

    return jsonify({"ok": True})


@app.route("/api/list/<int:book_id>/rating", methods=["POST"])
def api_rate(book_id):
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")

    if not isinstance(rating, int) or not (1 <= rating <= 5):
        return jsonify({"error": "rating deve ser um inteiro entre 1 e 5."}), 400

    try:
        rate_book(book_id, rating)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"ok": True})


@app.route("/api/list/<int:book_id>", methods=["DELETE"])
def api_remove(book_id):
    remove_book_from_list(book_id)
    return jsonify({"ok": True})


@app.route("/api/list/<int:book_id>/dates", methods=["POST"])
def api_set_dates(book_id):
    """
    Define as datas de início/término de leitura.
    Corpo: {"started_at": "YYYY-MM-DD" | "", "finished_at": "YYYY-MM-DD" | ""}
    Envie string vazia para limpar uma data já definida.
    """
    data = request.get_json(silent=True) or {}

    try:
        update_reading_dates(
            book_id,
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"ok": True})


@app.route("/api/list/<int:book_id>/review", methods=["POST"])
def api_set_review(book_id):
    """Define (ou limpa, com string vazia) a resenha pessoal. Corpo: {"review": "..."}"""
    data = request.get_json(silent=True) or {}

    try:
        update_review(book_id, data.get("review", ""))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"ok": True})


@app.route("/api/books/<int:book_id>/quotes", methods=["POST"])
def api_add_quote(book_id):
    """Adiciona uma citação. Corpo: {"quote": "...", "page": 123 (opcional)}"""
    data = request.get_json(silent=True) or {}
    quote = data.get("quote", "")
    page = data.get("page")

    if page is not None and not isinstance(page, int):
        return jsonify({"error": "page deve ser um número inteiro."}), 400

    try:
        quote_id = add_quote_to_book(book_id, quote, page)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Livro id={book_id} não encontrado."}), 404

    return jsonify({"quote_id": quote_id}), 201


@app.route("/api/quotes/<int:quote_id>", methods=["DELETE"])
def api_remove_quote(quote_id):
    remove_quote_from_book(quote_id)
    return jsonify({"ok": True})


@app.route("/api/custom-lists")
def api_custom_lists():
    """Lista todas as listas personalizadas, com a contagem de livros em cada uma."""
    init_db()
    return jsonify(list_custom_lists())


@app.route("/api/custom-lists", methods=["POST"])
def api_create_custom_list():
    """Cria uma lista personalizada. Corpo: {"name": "...", "description": "..." (opcional)}"""
    data = request.get_json(silent=True) or {}
    init_db()

    try:
        list_id = create_custom_list(data.get("name", ""), data.get("description"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"list_id": list_id}), 201


@app.route("/api/custom-lists/<int:list_id>")
def api_get_custom_list(list_id):
    """Detalhe de uma lista personalizada, com os livros já montados."""
    init_db()
    meta = get_custom_list_meta(list_id)

    if meta is None:
        return jsonify({"error": f"Lista (id={list_id}) não encontrada."}), 404

    book_ids = get_custom_list_book_ids(list_id)
    meta["books"] = get_books_by_ids(book_ids)
    return jsonify(meta)


@app.route("/api/custom-lists/<int:list_id>", methods=["PATCH"])
def api_update_custom_list(list_id):
    """Renomeia/atualiza a descrição. Corpo: {"name": "..." e/ou "description": "..."}"""
    data = request.get_json(silent=True) or {}

    try:
        rename_custom_list(list_id, name=data.get("name"), description=data.get("description"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"ok": True})


@app.route("/api/custom-lists/<int:list_id>", methods=["DELETE"])
def api_delete_custom_list(list_id):
    delete_custom_list(list_id)
    return jsonify({"ok": True})


@app.route("/api/custom-lists/<int:list_id>/books", methods=["POST"])
def api_add_book_to_custom_list(list_id):
    """Adiciona um livro à lista. Corpo: {"book_id": 123}"""
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")

    if not isinstance(book_id, int):
        return jsonify({"error": "book_id é obrigatório e deve ser um inteiro."}), 400

    # Confirma que o livro existe antes de vincular -- dá um erro mais claro
    # (404 com mensagem) do que deixar a FK de custom_list_books estourar
    # um IntegrityError genérico lá na frente.
    if get_book_detail(book_id) is None:
        return jsonify({"error": f"Livro id={book_id} não encontrado."}), 404

    try:
        add_book_to_custom_list(list_id, book_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify({"ok": True})


@app.route("/api/custom-lists/<int:list_id>/books/<int:book_id>", methods=["DELETE"])
def api_remove_book_from_custom_list(list_id, book_id):
    remove_book_from_custom_list(list_id, book_id)
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("API_PORT", 5001))
    app.run(host="0.0.0.0", debug=True, port=port)