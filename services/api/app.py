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

from fetch_books import search_and_normalize
from db import init_db, save_book
from reading_list import (
    add_book_to_list,
    rate_book,
    list_books,
    remove_book_from_list,
    STATUSES,
)

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


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("API_PORT", 5001))
    app.run(host="0.0.0.0", debug=True, port=port)