# Catálogo de Leituras — arquitetura

Este projeto é dividido em **dois serviços independentes**, cada um em sua
própria pasta, com seu próprio `requirements.txt`/dependências, seu próprio
processo, e sua própria porta:

```
services/
├── api/     -> serviço de API (Flask). Só fala JSON. Não sabe o que é HTML.
└── web/     -> serviço web (estático). Só serve HTML/CSS/JS. Não sabe o
                que é SQLite, nem tem a chave da Google Books API.
```

## O que caracteriza isso como microsserviços (e não só "pastas separadas")

1. **Processos separados.** `api/app.py` e `web/server.py` rodam com `python`
   independentemente, cada um escutando sua própria porta. Não existe um
   processo pai que os une.

2. **Nenhum código compartilhado em tempo de execução.** O serviço `web`
   nunca importa `db.py`, `fetch_books.py` ou `reading_list.py`. Ele não tem
   acesso ao banco, nem à chave de API — só sabe fazer requisições HTTP.

3. **O único acoplamento é um contrato HTTP.** A API expõe endpoints
   documentados (`/api/search`, `/api/books`, `/api/list`, etc). O frontend
   consome esses endpoints via a URL configurada em `web/config.js`
   (`API_BASE_URL`). Trocar essa URL é o suficiente para o frontend falar
   com outra instância da API — local, staging, produção, ou uma
   reimplementação inteira em outra linguagem, desde que respeite o mesmo
   contrato.

4. **Um pode subir sem o outro.** Se você desligar a API, o serviço web
   continua respondendo normalmente (a página carrega, só a busca/salvar
   avisam que não há conexão). Se desligar o web, a API continua
   respondendo a chamadas diretas (`curl`, Postman, outro cliente).

5. **CORS explícito.** Como os dois rodam em origens diferentes
   (`localhost:5001` vs `localhost:8000`), a API precisa liberar
   explicitamente quem pode chamá-la (`CORS_ORIGINS` no `.env`). Isso força
   a fronteira entre os serviços a ficar visível no código, em vez de
   escondida atrás de "mesma origem".

## Rodando localmente (sem Docker)

Em dois terminais separados:

```bash
# terminal 1 — API
cd services/api
pip install -r requirements.txt
cp .env.example .env   # preencha GOOGLE_BOOKS_API_KEY
python app.py
# -> http://localhost:5001

# terminal 2 — Web
cd services/web
python server.py
# -> http://localhost:8000
```

Abra `http://localhost:8000` no navegador. Ele vai chamar a API em
`http://localhost:5001` (definido em `web/config.js`).

## Rodando com Docker (opcional)

```bash
export GOOGLE_BOOKS_API_KEY="sua_chave"
docker compose up
```

Isso builda e sobe os dois serviços como containers separados
(`docker-compose.yml` na raiz). Você pode parar um sem afetar o outro:

```bash
docker compose stop api   # o site continua no ar, só sem busca/salvar
```

## Próximo passo natural: um terceiro serviço

Hoje, a busca na Google Books acontece dentro do próprio request HTTP da
API (`GET /api/search` chama a Google Books na hora). Se um dia isso
crescer — por exemplo, você quiser popular o banco periodicamente em
background, sem depender de alguém abrir a página — dá pra extrair isso
para um **terceiro serviço** (um worker/job agendado), que só escreve no
banco. A API deixaria de chamar a Google Books diretamente e passaria a
apenas ler do banco. Os serviços continuariam desacoplados: o worker nem
precisa saber que existe uma API ou um frontend, só escreve no SQLite (ou,
numa versão maior, publica em uma fila).