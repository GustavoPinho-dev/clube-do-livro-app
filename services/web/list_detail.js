// ---------------------------------------------------------------
// list_detail.js
// Lógica da página de detalhe de uma lista personalizada.
// Utilitários compartilhados (apiFetch, escapeHtml, etc.) vêm de common.js.
// ---------------------------------------------------------------

const connectionBanner = document.getElementById("connection-banner");
const detailFeedback = document.getElementById("detail-feedback");
const detailContainer = document.getElementById("detail-container");

function getListIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");
  return id ? Number(id) : null;
}

async function loadList() {
  const listId = getListIdFromUrl();

  if (!listId) {
    showFeedback(detailFeedback, "Nenhuma lista informada na URL.");
    return;
  }

  showFeedback(detailFeedback, "Carregando…", "loading");

  try {
    const lista = await apiFetch(`/api/custom-lists/${listId}`);
    clearFeedback(detailFeedback);
    renderList(lista);
  } catch (err) {
    clearFeedback(detailFeedback);
    showFeedback(detailFeedback, err.message);
  }
}

function renderList(lista) {
  const descHtml = lista.description
    ? `<p class="list-detail-desc">${escapeHtml(lista.description)}</p>`
    : `<p class="list-detail-desc">Sem descrição.</p>`;

  const booksHtml = lista.books.length
    ? lista.books.map((livro) => renderBookMiniCard(livro, lista.id)).join("")
    : `<p class="empty-state">Nenhum livro nesta lista ainda. Adicione pela página de detalhes de um livro.</p>`;

  detailContainer.innerHTML = `
    <div class="list-detail-header">
      <h1 class="list-detail-name">${escapeHtml(lista.name)}</h1>
      ${descHtml}
      <div class="list-detail-actions">
        <button class="btn btn-small btn-ghost" type="button" id="edit-list-btn">Editar</button>
        <button class="btn btn-small btn-ghost" type="button" id="delete-list-btn">Apagar lista</button>
      </div>
      <div id="edit-list-area"></div>
    </div>
    <div class="detail-card" id="books-container">${booksHtml}</div>
  `;

  wireBookRemoveButtons(lista.id);

  document.getElementById("edit-list-btn").addEventListener("click", () => {
    renderEditForm(lista);
  });

  document.getElementById("delete-list-btn").addEventListener("click", async () => {
    const confirmado = window.confirm(`Apagar a lista "${lista.name}"? Os livros continuam salvos, só a lista some.`);
    if (!confirmado) return;

    try {
      await apiFetch(`/api/custom-lists/${lista.id}`, { method: "DELETE" });
      window.location.href = "lists.html";
    } catch (err) {
      showFeedback(detailFeedback, err.message);
    }
  });
}

function renderBookMiniCard(livro, listId) {
  const autores = livro.authors || "Autor desconhecido";
  const ano = livro.first_publish_year ? ` · ${livro.first_publish_year}` : "";

  const coverHtml = livro.cover_url
    ? `<img class="book-mini-cover" src="${escapeHtml(livro.cover_url)}" alt="">`
    : `<div class="book-mini-cover-placeholder">?</div>`;

  return `
    <div class="book-mini-card" data-book-id="${livro.book_id}">
      ${coverHtml}
      <div class="book-mini-body">
        <button type="button" class="list-item-title link-title">${escapeHtml(livro.title)}</button>
        <p class="card-meta">${escapeHtml(autores)}${ano}</p>
      </div>
      <button class="remove-btn" type="button" data-remove-book="${livro.book_id}" aria-label="Remover desta lista">×</button>
    </div>
  `;
}

function wireBookRemoveButtons(listId) {
  document.querySelectorAll(".book-mini-card").forEach((cardEl) => {
    const bookId = cardEl.dataset.bookId;

    cardEl.querySelector(".link-title").addEventListener("click", () => {
      window.location.href = `book.html?id=${bookId}`;
    });

    cardEl.querySelector("[data-remove-book]").addEventListener("click", async () => {
      try {
        await apiFetch(`/api/custom-lists/${listId}/books/${bookId}`, { method: "DELETE" });
        await loadList();
      } catch (err) {
        showFeedback(detailFeedback, err.message);
      }
    });
  });
}

function renderEditForm(lista) {
  const areaEl = document.getElementById("edit-list-area");

  areaEl.innerHTML = `
    <form class="edit-list-form" id="edit-list-form">
      <input type="text" id="edit-name" value="${escapeHtml(lista.name)}" required>
      <input type="text" id="edit-desc" value="${escapeHtml(lista.description || "")}" placeholder="Descrição (opcional)">
      <div>
        <button class="btn btn-small" type="submit">Salvar</button>
        <button class="btn btn-small btn-ghost" type="button" id="cancel-edit-btn">Cancelar</button>
      </div>
    </form>
  `;

  document.getElementById("cancel-edit-btn").addEventListener("click", () => {
    areaEl.innerHTML = "";
  });

  document.getElementById("edit-list-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("edit-name").value.trim();
    const description = document.getElementById("edit-desc").value.trim();

    try {
      await apiFetch(`/api/custom-lists/${lista.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name, description }),
      });
      await loadList();
    } catch (err) {
      showFeedback(detailFeedback, err.message);
    }
  });
}

checkApiConnection(connectionBanner);
loadList();