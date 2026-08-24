// ---------------------------------------------------------------
// Catálogo de Leituras — lógica da interface (página de Busca)
// Fala com o backend Flask (app.py), que por sua vez usa
// fetch_books.py / db.py / reading_list.py.
// Utilitários compartilhados (apiFetch, escapeHtml, etc.) vêm de common.js.
// ---------------------------------------------------------------

const searchInput = document.getElementById("search-input");
const searchBtn = document.getElementById("search-btn");
const searchFeedback = document.getElementById("search-feedback");
const resultsEl = document.getElementById("results");
const connectionBanner = document.getElementById("connection-banner");

// ---------------- busca ----------------

async function runSearch() {
  const termo = searchInput.value.trim();
  if (!termo) {
    showFeedback(searchFeedback, "Digite um termo para buscar.");
    return;
  }

  clearFeedback(searchFeedback);
  showFeedback(searchFeedback, "Buscando…", "loading");
  resultsEl.innerHTML = "";

  try {
    const livros = await apiFetch(`/api/search?q=${encodeURIComponent(termo)}&limit=10`);
    clearFeedback(searchFeedback);

    if (livros.length === 0) {
      resultsEl.innerHTML = `<p class="empty-state">Nenhum resultado para "${escapeHtml(termo)}".</p>`;
      return;
    }

    resultsEl.innerHTML = "";
    livros.forEach((livro) => resultsEl.appendChild(renderSearchCard(livro)));
  } catch (err) {
    clearFeedback(searchFeedback);
    showFeedback(searchFeedback, err.message);
  }
}

function renderSearchCard(livro) {
  const card = document.createElement("article");
  card.className = "card";

  const autores = (livro.authors || []).join(", ");
  const ano = livro.first_publish_year ? ` · ${livro.first_publish_year}` : "";

  const coverHtml = livro.cover_url
    ? `<img class="card-cover" src="${escapeHtml(livro.cover_url)}" alt="">`
    : `<div class="card-cover-placeholder">?</div>`;

  card.innerHTML = `
    ${coverHtml}
    <div class="card-body">
      <button type="button" class="card-title link-title">${escapeHtml(livro.title)}</button>
      <p class="card-meta">${escapeHtml(autores)}${ano}</p>
    </div>
    <div class="card-actions">
      <button class="btn btn-small save-btn" type="button">Salvar na lista</button>
    </div>
  `;

  // Clicar no título salva o livro (se ainda não estiver salvo) e abre a
  // página de detalhes. Isso não adiciona o livro a nenhuma gaveta --
  // só garante que ele exista no banco para termos um id a consultar.
  card.querySelector(".link-title").addEventListener("click", async () => {
    try {
      const { book_id } = await apiFetch("/api/books", {
        method: "POST",
        body: JSON.stringify(livro),
      });
      window.location.href = `book.html?id=${book_id}`;
    } catch (err) {
      showFeedback(searchFeedback, err.message);
    }
  });

  const saveBtn = card.querySelector(".save-btn");
  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    saveBtn.textContent = "Salvando…";
    try {
      const { book_id } = await apiFetch("/api/books", {
        method: "POST",
        body: JSON.stringify(livro),
      });
      await apiFetch(`/api/list/${book_id}`, {
        method: "POST",
        body: JSON.stringify({ status: "quero_ler" }),
      });
      saveBtn.textContent = "Adicionado à leitura ✓";
      saveBtn.classList.add("btn-ghost");
    } catch (err) {
      saveBtn.disabled = false;
      saveBtn.textContent = "Salvar na lista";
      showFeedback(searchFeedback, err.message);
    }
  });

  return card;
}

// ---------------- inicialização ----------------

searchBtn.addEventListener("click", runSearch);
searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") runSearch();
});

checkApiConnection(connectionBanner);