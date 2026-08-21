"""
fetch_books.py

Responsável pela etapa de EXTRACT (+ parte do TRANSFORM) da pipeline.
Busca dados de livros na Google Books API e normaliza para um formato
simples e consistente, pronto para ser salvo no banco de dados.

Docs da API usada:
- https://developers.google.com/books/docs/v1/using

IMPORTANTE sobre a chave de API:
Nunca deixe a chave fixa (hardcoded) no código, principalmente se ele for
compartilhado ou versionado (ex: git). Configure-a como variável de
ambiente antes de rodar o script:

    export GOOGLE_BOOKS_API_KEY="sua_chave_aqui"      # Linux/Mac
    setx GOOGLE_BOOKS_API_KEY "sua_chave_aqui"          # Windows

Se você já expôs uma chave em algum lugar público (ex: chat, repositório),
regenere-a no Google Cloud Console.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()  # carrega as variáveis definidas no arquivo .env, se existir

BASE_URL = "https://www.googleapis.com/books/v1/volumes"

# A chave é opcional para poucas requisições, mas recomendada para evitar
# limites de taxa mais baixos. Lida da variável de ambiente.
API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY")

# Configuração do retry para erros de limite de requisições (429)
MAX_RETRIES = 3
BACKOFF_SECONDS = 2  # dobra a cada tentativa: 2s, 4s, 8s...


def _request_with_retry(url: str, params: dict) -> requests.Response | None:
    """
    Faz um GET com retry/backoff em caso de 429 (Too Many Requests).
    Retorna a Response em caso de sucesso, ou None se o recurso não existir (404).
    """
    for tentativa in range(1, MAX_RETRIES + 1):
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 404:
            return None

        if response.status_code == 429:
            if tentativa == MAX_RETRIES:
                response.raise_for_status()  # desiste e propaga o erro

            espera = BACKOFF_SECONDS * (2 ** (tentativa - 1))
            print(
                f"[aviso] 429 recebido (tentativa {tentativa}/{MAX_RETRIES}). "
                f"Aguardando {espera}s antes de tentar de novo..."
            )
            time.sleep(espera)
            continue

        response.raise_for_status()  # lança erro para outros status ruins (4xx/5xx)
        return response

    return None  # não deveria chegar aqui, mas evita warning de "missing return"


def search_books(query: str, max_results: int = 10) -> list[dict]:
    """
    Busca livros por título, autor ou termo livre.
    Retorna a lista bruta de resultados (formato original da API).

    Se a API retornar 429 (Too Many Requests), tenta novamente algumas
    vezes com espera crescente entre as tentativas.
    """
    params = {"q": query, "maxResults": max_results}
    if API_KEY:
        params["key"] = API_KEY

    response = _request_with_retry(BASE_URL, params)
    if response is None:
        return []

    return response.json().get("items", [])


def get_volume_by_id(volume_id: str) -> dict | None:
    """
    Busca um único volume pelo id da Google Books (o mesmo valor guardado
    em `source_id`). Traz mais detalhes que a busca por texto (descrição,
    editora, número de páginas, categorias). Retorna None se não existir.
    """
    params = {}
    if API_KEY:
        params["key"] = API_KEY

    response = _request_with_retry(f"{BASE_URL}/{volume_id}", params)
    if response is None:
        return None

    return response.json()


def normalize_book(raw: dict) -> dict:
    """
    Transforma um item bruto da Google Books API em um dicionário
    normalizado e consistente, pronto para o banco de dados.
    """
    info = raw.get("volumeInfo", {})

    # ISBN-13 é preferido; cai para ISBN-10 se não houver
    isbn = None
    for ident in info.get("industryIdentifiers", []):
        if ident.get("type") == "ISBN_13":
            isbn = ident.get("identifier")
            break
    if isbn is None:
        for ident in info.get("industryIdentifiers", []):
            if ident.get("type") == "ISBN_10":
                isbn = ident.get("identifier")
                break

    # publishedDate pode vir como "2015", "2015-03" ou "2015-03-10"
    published_year = None
    published_date = info.get("publishedDate")
    if published_date:
        try:
            published_year = int(published_date[:4])
        except ValueError:
            published_year = None

    cover_url = info.get("imageLinks", {}).get("thumbnail")

    return {
        # id do volume na Google Books, usado como identificador único da fonte
        "source_id": raw.get("id"),
        "title": info.get("title", "Sem título").strip(),
        "authors": info.get("authors") or ["Autor desconhecido"],
        "first_publish_year": published_year,
        "isbn": isbn,
        "cover_url": cover_url,
        "source_api": "google_books",
        # Campos extras, usados na página de detalhes do livro
        "description": info.get("description"),
        "publisher": info.get("publisher"),
        "page_count": info.get("pageCount"),
        "categories": info.get("categories") or [],
        # Média de avaliações públicas da própria Google Books (não é a nota
        # pessoal do usuário, que fica em user_lists.rating)
        "average_rating": info.get("averageRating"),
    }


def search_and_normalize(query: str, max_results: int = 10) -> list[dict]:
    """
    Função de conveniência: busca e já retorna os dados normalizados.
    Descarta itens sem id (não teríamos como fazer upsert no banco).
    """
    raw_results = search_books(query, max_results=max_results)
    normalizados = [normalize_book(item) for item in raw_results]
    return [b for b in normalizados if b["source_id"]]


def get_and_normalize_volume(volume_id: str) -> dict | None:
    """
    Função de conveniência: busca um volume específico e já normaliza.
    Retorna None se o volume não existir na Google Books.
    """
    raw = get_volume_by_id(volume_id)
    return normalize_book(raw) if raw else None


if __name__ == "__main__":
    # Exemplo de uso rápido via linha de comando
    import sys
    import json

    termo = sys.argv[1] if len(sys.argv) > 1 else "Sociedade do Cansaço"

    print(f"Buscando por: {termo}\n")
    livros = search_and_normalize(termo, max_results=5)

    for livro in livros:
        print(json.dumps(livro, ensure_ascii=False, indent=2))