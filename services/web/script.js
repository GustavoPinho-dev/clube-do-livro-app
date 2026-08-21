// ---------------------------------------------------------------
// Catálogo de Leituras — lógica da interface (página inicial)
// Fala com o backend Flask (app.py), que por sua vez usa
// fetch_books.py / db.py / reading_list.py.
// Utilitários compartilhados (apiFetch, escapeHtml, etc.) vêm de common.js.
// ---------------------------------------------------------------

const searchInput = document.getElementById("search-input");
const searchBtn = document.getElementById("search-btn");
const searchFeedback = document.getElementById("search-feedback");
const resultsEl = document.getElementById("results");
const listPanel = document.getElementById("list-panel");
const drawerTabs = document.getElementById("drawer-tabs");
const connectionBanner = document.getElementById("connection-banner");

let currentStatusFilter = "";

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
      saveBtn.textContent = "Adicionado ✓";
      saveBtn.classList.add("btn-ghost");
      await loadList();
    } catch (err) {
      saveBtn.disabled = false;
      saveBtn.textContent = "Salvar na lista";
      showFeedback(searchFeedback, err.message);
    }
  });

  return card;
}

// ---------------- lista de leitura ----------------

async function loadList() {
  showFeedback(listPanel, "Carregando…", "loading");

  try {
    const url = currentStatusFilter
      ? `/api/list?status=${encodeURIComponent(currentStatusFilter)}`
      : "/api/list";
    const livros = await apiFetch(url);
    renderList(livros);
  } catch (err) {
    showFeedback(listPanel, err.message);
  }
}

function renderList(livros) {
  if (livros.length === 0) {
    listPanel.innerHTML = `<p class="empty-state">Nenhum livro nesta gaveta ainda.</p>`;
    return;
  }

  listPanel.innerHTML = "";
  livros.forEach((livro) => listPanel.appendChild(renderListItem(livro)));
}

function renderListItem(livro) {
  const item = document.createElement("div");
  item.className = "list-item";

  const autores = livro.authors || "";
  const ano = livro.first_publish_year ? ` · ${livro.first_publish_year}` : "";
  const rating = livro.rating || 0;

  const statusOptions = Object.entries(STATUS_LABELS)
    .map(
      ([value, label]) =>
        `<option value="${value}" ${value === livro.status ? "selected" : ""}>${label}</option>`
    )
    .join("");

  const starsHtml = [1, 2, 3, 4, 5]
    .map(
      (n) =>
        `<button type="button" data-value="${n}" class="${n <= rating ? "filled" : ""}" aria-label="Avaliar com ${n} estrela(s)">★</button>`
    )
    .join("");

  item.innerHTML = `
    <span class="stamp stamp-${livro.status}">${STATUS_LABELS[livro.status]}</span>
    <div class="list-item-body">
      <button type="button" class="list-item-title link-title">${escapeHtml(livro.title)}</button>
      <p class="list-item-meta">${escapeHtml(autores)}${ano}</p>
    </div>
    <div class="rating" role="group" aria-label="Avaliação">${starsHtml}</div>
    <select class="status-select" aria-label="Mudar status">${statusOptions}</select>
    <button class="remove-btn" type="button" aria-label="Remover da lista">×</button>
  `;

  // Título leva aos detalhes -- aqui o livro já tem book_id garantido
  // (está na lista), então não precisa salvar de novo antes de navegar.
  item.querySelector(".link-title").addEventListener("click", () => {
    window.location.href = `book.html?id=${livro.book_id}`;
  });

  // Avaliação por estrelas
  item.querySelectorAll(".rating button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const value = Number(btn.dataset.value);
      try {
        await apiFetch(`/api/list/${livro.book_id}/rating`, {
          method: "POST",
          body: JSON.stringify({ rating: value }),
        });
        await loadList();
      } catch (err) {
        showFeedback(listPanel, err.message);
      }
    });
  });

  // Mudança de status
  item.querySelector(".status-select").addEventListener("change", async (e) => {
    try {
      await apiFetch(`/api/list/${livro.book_id}`, {
        method: "POST",
        body: JSON.stringify({ status: e.target.value }),
      });
      await loadList();
    } catch (err) {
      showFeedback(listPanel, err.message);
    }
  });

  // Remover
  item.querySelector(".remove-btn").addEventListener("click", async () => {
    try {
      await apiFetch(`/api/list/${livro.book_id}`, { method: "DELETE" });
      await loadList();
    } catch (err) {
      showFeedback(listPanel, err.message);
    }
  });

  return item;
}

// ---------------- gavetas (filtro por status) ----------------

drawerTabs.addEventListener("click", (e) => {
  const tab = e.target.closest(".drawer-tab");
  if (!tab) return;

  drawerTabs.querySelectorAll(".drawer-tab").forEach((t) => t.classList.remove("active"));
  tab.classList.add("active");
  currentStatusFilter = tab.dataset.status;
  loadList();
});

// ---------------- inicialização ----------------

searchBtn.addEventListener("click", runSearch);
searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") runSearch();
});

checkApiConnection(connectionBanner);
loadList();