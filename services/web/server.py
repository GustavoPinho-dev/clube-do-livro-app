"""
services/web/server.py

Servidor estático — responsabilidade única: entregar HTML/CSS/JS.
Não importa fetch_books, db ou reading_list. Não sabe o que é SQLite.
Não tem a chave da Google Books API. Só serve arquivos.

Isso é o que torna esse serviço fisicamente incapaz de virar uma
dependência forte da API: ele não compartilha processo, memória nem
código com o serviço de API. A única ponta que os liga é config.js,
que aponta para a URL onde a API está rodando.

Rodar (independente da API):
    python server.py
    # Frontend disponível em http://localhost:8000, mesmo que a API
    # esteja fora do ar (só não vai conseguir buscar/salvar livros).
"""

import http.server
import os

PORT = int(os.environ.get("WEB_PORT", 8000))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, directory=DIRECTORY, **kwargs)


if __name__ == "__main__":
    with http.server.ThreadingHTTPServer(("", PORT), Handler) as httpd:
        print(f"Servindo {DIRECTORY} em http://localhost:{PORT}")
        httpd.serve_forever()