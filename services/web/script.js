// ---------------------------------------------------------------
// Catálogo de Leituras — lógica da interface
// Fala com o backend Flask (app.py), que por sua vez usa
// fetch_books.py / db.py / reading_list.py.
// ---------------------------------------------------------------

const searchInput = document.getElementById("search-input");
const searchBtn = document.getElementById("search-btn");
const searchFeedback = document.getElementById("search-feedback");
const resultsEl = document.getElementById("results");
const listPanel = document.getElementById("list-panel");
const drawerTabs = document.getElementById("drawer-tabs");
const connectionBanner = document.getElementById("connection-banner");
const bookModal = document.getElementById("book-modal");
const bookModalCard = bookModal.querySelector(".book-modal-card");
const bookModalContent = document.getElementById("book-modal-content");

const STATUS_LABELS = {
  quero_ler: "Quero ler",
  lendo: "Lendo",
  lido: "Lido",
};

let currentStatusFilter = "";
let lastFocusedElement = null;

// ---------------- utilidades ----------------

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function showFeedback(container, message, type = "error") {
  container.innerHTML = `<div class="${type === "error" ? "error-banner" : "loading"}">${escapeHtml(message)}</div>`;
}

function clearFeedback(container) {
  container.innerHTML = "";
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Erro ${response.status}`);
  }
  return data;
}

async function checkApiConnection() {
  try {
    await apiFetch("/health");
    connectionBanner.innerHTML = "";
  } catch (err) {
    connectionBanner.innerHTML = `<div class="error-banner">Não foi possível conectar à API em ${API_BASE_URL}. Verifique se o serviço está rodando.</div>`;
  }
}


function formatValue(value, fallback = "Não informado") {
  return value ? escapeHtml(value) : fallback;
}

function formatDate(dateValue) {
  if (!dateValue) return "Não informado";
  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) return escapeHtml(dateValue);
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function renderStars(rating) {
  const value = rating || 0;
  return [1, 2, 3, 4, 5].map((n) => (n <= value ? "★" : "☆")).join("");
}

function openBookModal(livro) {
  lastFocusedElement = document.activeElement;

  const coverHtml = livro.cover_url
    ? `<img class="book-detail-cover" src="${escapeHtml(livro.cover_url)}" alt="Capa de ${escapeHtml(livro.title)}">`
    : `<div class="book-detail-cover-placeholder" aria-hidden="true">?</div>`;

  bookModalContent.innerHTML = `
    <div class="book-detail">
      <div>${coverHtml}</div>
      <div>
        <p class="book-detail-kicker">Ficha catalográfica</p>
        <h2 class="book-detail-title" id="book-modal-title">${escapeHtml(livro.title)}</h2>
        <span class="stamp stamp-${livro.status}">${STATUS_LABELS[livro.status]}</span>
        <div class="book-detail-meta">
          <div class="book-detail-field">
            <span class="book-detail-label">Autor(es)</span>
            <p class="book-detail-value">${formatValue(livro.authors)}</p>
          </div>
          <div class="book-detail-field">
            <span class="book-detail-label">Ano de publicação</span>
            <p class="book-detail-value">${formatValue(livro.first_publish_year)}</p>
          </div>
          <div class="book-detail-field">
            <span class="book-detail-label">ISBN</span>
            <p class="book-detail-value">${formatValue(livro.isbn)}</p>
          </div>
          <div class="book-detail-field">
            <span class="book-detail-label">Avaliação</span>
            <p class="book-detail-value" aria-label="${livro.rating || 0} de 5 estrelas">${renderStars(livro.rating)}</p>
          </div>
          <div class="book-detail-field">
            <span class="book-detail-label">Adicionado em</span>
            <p class="book-detail-value">${formatDate(livro.added_at)}</p>
          </div>
          <div class="book-detail-field">
            <span class="book-detail-label">Última atualização</span>
            <p class="book-detail-value">${formatDate(livro.updated_at)}</p>
          </div>
        </div>
      </div>
    </div>
  `;

  bookModal.hidden = false;
  document.body.style.overflow = "hidden";
  bookModalCard.focus();
}

function closeBookModal() {
  bookModal.hidden = true;
  bookModalContent.innerHTML = "";
  document.body.style.overflow = "";
  lastFocusedElement?.focus();
}

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
      <p class="card-title">${escapeHtml(livro.title)}</p>
      <p class="card-meta">${escapeHtml(autores)}${ano}</p>
    </div>
    <div class="card-actions">
      <button class="btn btn-small save-btn" type="button">Salvar na lista</button>
    </div>
  `;

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
  item.className = "list-item list-item-clickable";

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
      <button class="list-item-detail-btn" type="button" aria-label="Ver detalhes de ${escapeHtml(livro.title)}">
        <p class="list-item-title">${escapeHtml(livro.title)}</p>
        <p class="list-item-meta">${escapeHtml(autores)}${ano}</p>
      </button>
    </div>
    <button class="btn btn-small btn-ghost details-btn" type="button" aria-label="Ver detalhes de ${escapeHtml(livro.title)}">Ver detalhes</button>
    <div class="rating" role="group" aria-label="Avaliação">${starsHtml}</div>
    <select class="status-select" aria-label="Mudar status">${statusOptions}</select>
    <button class="remove-btn" type="button" aria-label="Remover da lista">×</button>
  `;

  item.addEventListener("click", (e) => {
    if (e.target.closest("button, select")) return;
    openBookModal(livro);
  });
  item.querySelector(".details-btn").addEventListener("click", () => openBookModal(livro));

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

bookModal.addEventListener("click", (e) => {
  if (e.target.matches("[data-close-modal]")) closeBookModal();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !bookModal.hidden) closeBookModal();
});

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

checkApiConnection();
loadList();